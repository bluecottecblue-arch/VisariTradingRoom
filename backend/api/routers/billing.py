"""
Router pagamenti e referral (Stripe).

Endpoints pubblici:
  GET  /api/billing/config            stato configurazione (per il frontend)
  POST /api/billing/register          registrazione + sessione checkout
  POST /api/billing/webhook           webhook Stripe (firma verificata)

Endpoints autenticati:
  GET  /api/billing/me                stato abbonamento dell'utente
  GET  /api/billing/referral          codice referral + statistiche
  POST /api/billing/portal            link al portale Stripe (gestione/cancellazione)
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from modules.auth.security import AuthContext, require_authenticated
from modules.auth import user_store
from modules.billing import stripe_service

logger = logging.getLogger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)
    referral_code: str | None = None


@router.get("/config")
async def billing_config():
    """Info pubbliche per il frontend: prezzo e se il pagamento è attivo."""
    return {
        "ok": True,
        "billing_enabled": stripe_service.is_configured(),
        "price_eur": int(stripe_service.SUBSCRIPTION_PRICE_CENTS) / 100,
        "currency": stripe_service.CURRENCY,
        "referral_discount_pct": 60,
        "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY", ""),
    }


@router.post("/register")
async def register(payload: RegisterRequest):
    """
    Registra un nuovo utente in stato 'pending' e avvia il checkout Stripe.
    L'account si attiva solo dopo il pagamento confermato (webhook).
    """
    if not stripe_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Pagamenti non ancora configurati. Riprova più tardi.",
        )

    email = str(payload.email).strip().lower()

    # Username = email (identità unica per SaaS)
    existing = await user_store.get_user_profile(email)
    if existing:
        status = str(existing.get("status") or "")
        if status == "pending":
            # Account creato ma pagamento mai completato: si può riprovare il checkout
            pass
        else:
            raise HTTPException(status_code=409, detail="Esiste già un account con questa email.")

    # Validazione codice referral (opzionale)
    referral_code = str(payload.referral_code or "").strip().upper() or None
    valid_referral = False
    if referral_code:
        referrer = await user_store.get_user_by_referral_code(referral_code)
        if not referrer:
            raise HTTPException(status_code=400, detail="Codice referral non valido.")
        if referrer.get("username") == email:
            raise HTTPException(status_code=400, detail="Non puoi usare il tuo stesso codice referral.")
        valid_referral = True

    # Crea l'utente pending (se non esiste già)
    if not existing:
        try:
            await user_store.create_pending_user(
                email, payload.password, email=email, referred_by=referral_code,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # Avvia checkout Stripe
    try:
        checkout = stripe_service.create_checkout_session(
            username=email,
            email=email,
            referred_by_code=referral_code,
            has_valid_referral=valid_referral,
        )
    except stripe_service.StripeNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Errore creazione checkout: %s", exc)
        raise HTTPException(status_code=502, detail="Errore comunicazione con Stripe. Riprova.")

    return {
        "ok": True,
        "checkout_url": checkout["url"],
        "referral_applied": valid_referral,
    }


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Riceve gli eventi Stripe. La firma è verificata; nessuna auth utente."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.verify_and_parse_webhook(payload, sig)
    except stripe_service.StripeNotConfigured as exc:
        logger.error("Webhook ricevuto ma Stripe non configurato: %s", exc)
        raise HTTPException(status_code=503, detail="Webhook non configurato")
    except Exception as exc:
        logger.warning("Firma webhook non valida: %s", exc)
        raise HTTPException(status_code=400, detail="Firma non valida")

    event_type = event["type"]
    obj = event["data"]["object"]
    logger.info("Stripe webhook: %s", event_type)

    try:
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(obj)
        elif event_type == "invoice.paid":
            await _handle_invoice_paid(obj)
        elif event_type in ("customer.subscription.deleted", "customer.subscription.canceled"):
            await _handle_subscription_canceled(obj)
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(obj)
    except Exception as exc:
        logger.exception("Errore gestione webhook %s: %s", event_type, exc)
        # Ritorna 200 comunque per evitare retry infiniti su errori non recuperabili
        return {"ok": False, "handled": False}

    return {"ok": True, "handled": True}


async def _handle_checkout_completed(session: dict) -> None:
    metadata = session.get("metadata") or {}
    username = metadata.get("username") or session.get("client_reference_id")
    if not username:
        logger.warning("checkout.session.completed senza username")
        return

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    await user_store.set_subscription(
        username,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        subscription_status="active",
        activate=True,
    )
    logger.info("Account attivato: %s", username)

    # Reward referrer
    referred_by = (metadata.get("referred_by") or "").strip().upper()
    if referred_by:
        referrer = await user_store.get_user_by_referral_code(referred_by)
        if referrer:
            await user_store.credit_referrer(referred_by)
            billing = await user_store.get_billing_record(referrer["username"])
            if billing and billing.get("stripe_customer_id"):
                stripe_service.apply_referrer_free_month(billing["stripe_customer_id"])
            logger.info("Referrer accreditato: %s (+1 mese)", referrer["username"])


async def _handle_invoice_paid(invoice: dict) -> None:
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    user = await user_store.get_user_by_stripe_customer(customer_id)
    if user:
        await user_store.set_subscription(
            user["username"], subscription_status="active", activate=True,
        )


async def _handle_subscription_canceled(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    user = await user_store.get_user_by_stripe_customer(customer_id)
    if user:
        await user_store.set_subscription(
            user["username"], subscription_status="canceled", deactivate=True,
        )
        logger.info("Abbonamento cancellato: %s", user["username"])


async def _handle_payment_failed(invoice: dict) -> None:
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    user = await user_store.get_user_by_stripe_customer(customer_id)
    if user:
        await user_store.set_subscription(user["username"], subscription_status="past_due")


@router.get("/me")
async def my_subscription(context: AuthContext = Depends(require_authenticated)):
    profile = await user_store.get_user_profile(context.username)
    if not profile:
        return {"ok": True, "subscription_status": "none"}
    return {
        "ok": True,
        "subscription_status": profile.get("subscription_status", "none"),
        "plan": profile.get("plan"),
        "status": profile.get("status"),
    }


@router.get("/referral")
async def my_referral(context: AuthContext = Depends(require_authenticated)):
    """Codice referral dell'utente + statistiche. Lo crea se non esiste."""
    # L'admin (env-based) non è un utente del DB: nessun referral disponibile
    profile_check = await user_store.get_user_profile(context.username)
    if not profile_check:
        return {
            "ok": True,
            "referral_code": None,
            "referral_link": None,
            "referral_count": 0,
            "free_months_credit": 0,
            "note": "L'account admin non partecipa al programma referral.",
        }
    try:
        code = await user_store.ensure_referral_code(context.username)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Errore generazione codice: {exc}")

    profile = await user_store.get_user_profile(context.username)
    base = os.environ.get("APP_BASE_URL", "").strip().rstrip("/")
    return {
        "ok": True,
        "referral_code": code,
        "referral_link": f"{base}/register?ref={code}" if base else None,
        "referral_count": int((profile or {}).get("referral_count") or 0),
        "free_months_credit": int((profile or {}).get("free_months_credit") or 0),
    }


@router.post("/portal")
async def billing_portal(context: AuthContext = Depends(require_authenticated)):
    """Link al portale Stripe per gestire o cancellare l'abbonamento."""
    billing = await user_store.get_billing_record(context.username)
    if not billing or not billing.get("stripe_customer_id"):
        raise HTTPException(status_code=404, detail="Nessun abbonamento attivo trovato.")
    try:
        portal = stripe_service.create_billing_portal_session(billing["stripe_customer_id"])
    except Exception as exc:
        logger.exception("Errore portale Stripe: %s", exc)
        raise HTTPException(status_code=502, detail="Errore apertura portale Stripe.")
    return {"ok": True, "url": portal["url"]}
