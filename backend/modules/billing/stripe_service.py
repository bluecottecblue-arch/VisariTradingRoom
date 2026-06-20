"""
Integrazione Stripe — abbonamenti €50/mese + referral.

Variabili d'ambiente richieste:
  STRIPE_SECRET_KEY            sk_live_... o sk_test_...
  STRIPE_WEBHOOK_SECRET        whsec_... (firma webhook)
  STRIPE_PRICE_ID             price_... (prezzo ricorrente €50/mese)
  STRIPE_REFERRAL_COUPON_ID   coupon ... (60% off, duration=once) [opzionale]
  APP_BASE_URL                URL frontend per redirect (es. https://...vercel.app)
  SUBSCRIPTION_PRICE_CENTS    default 5000 (€50) — usato per il credito referral
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Prezzo mensile in centesimi (per il credito "1 mese gratis" al referrer)
SUBSCRIPTION_PRICE_CENTS = int(os.environ.get("SUBSCRIPTION_PRICE_CENTS", "5000"))
CURRENCY = os.environ.get("SUBSCRIPTION_CURRENCY", "eur")


class StripeNotConfigured(RuntimeError):
    """Sollevata quando Stripe non è configurato (chiave mancante o libreria assente)."""


def _get_stripe():
    """Importa e configura stripe in modo lazy. Solleva StripeNotConfigured se manca."""
    secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        raise StripeNotConfigured(
            "STRIPE_SECRET_KEY non configurata. Imposta la chiave Stripe negli env var."
        )
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover
        raise StripeNotConfigured("Libreria 'stripe' non installata.") from exc
    stripe.api_key = secret
    return stripe


def is_configured() -> bool:
    """True se Stripe è pronto all'uso."""
    if not os.environ.get("STRIPE_SECRET_KEY", "").strip():
        return False
    try:
        import stripe  # noqa: F401
        return True
    except ImportError:
        return False


def _app_base_url() -> str:
    return os.environ.get("APP_BASE_URL", "").strip().rstrip("/") or "http://localhost:3000"


def _price_id() -> str:
    price = os.environ.get("STRIPE_PRICE_ID", "").strip()
    if not price:
        raise StripeNotConfigured(
            "STRIPE_PRICE_ID non configurato. Crea un prezzo ricorrente €50/mese su Stripe."
        )
    return price


def create_checkout_session(
    *,
    username: str,
    email: str,
    referred_by_code: Optional[str] = None,
    has_valid_referral: bool = False,
) -> dict:
    """
    Crea una sessione di checkout Stripe per l'abbonamento.
    Se has_valid_referral=True applica il coupon 60% off (primo mese).
    Ritorna {"url": ..., "session_id": ...}.
    """
    stripe = _get_stripe()
    base = _app_base_url()

    discounts = []
    coupon_id = os.environ.get("STRIPE_REFERRAL_COUPON_ID", "").strip()
    if has_valid_referral and coupon_id:
        discounts = [{"coupon": coupon_id}]

    session_kwargs = dict(
        mode="subscription",
        line_items=[{"price": _price_id(), "quantity": 1}],
        customer_email=email,
        client_reference_id=username,
        success_url=f"{base}/login?registrazione=ok",
        cancel_url=f"{base}/register?annullato=1",
        metadata={
            "username": username,
            "referred_by": (referred_by_code or "").strip().upper(),
        },
        subscription_data={
            "metadata": {
                "username": username,
                "referred_by": (referred_by_code or "").strip().upper(),
            },
        },
        allow_promotion_codes=False if discounts else True,
    )
    if discounts:
        session_kwargs["discounts"] = discounts

    session = stripe.checkout.Session.create(**session_kwargs)
    return {"url": session.url, "session_id": session.id}


def create_billing_portal_session(customer_id: str) -> dict:
    """Crea un link al portale Stripe per gestire/cancellare l'abbonamento."""
    stripe = _get_stripe()
    base = _app_base_url()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{base}/dashboard",
    )
    return {"url": session.url}


def apply_referrer_free_month(customer_id: str) -> bool:
    """
    Accredita un mese gratis al referrer aggiungendo un credito al saldo
    del cliente Stripe (verrà scalato dalla prossima fattura).
    Ritorna True se applicato.
    """
    if not customer_id:
        return False
    try:
        stripe = _get_stripe()
        stripe.Customer.create_balance_transaction(
            customer_id,
            amount=-SUBSCRIPTION_PRICE_CENTS,  # credito (negativo = a favore del cliente)
            currency=CURRENCY,
            description="Referral reward: 1 mese gratis",
        )
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("Impossibile applicare credito referral su Stripe: %s", exc)
        return False


def verify_and_parse_webhook(payload: bytes, sig_header: str):
    """Verifica la firma del webhook e ritorna l'evento Stripe."""
    stripe = _get_stripe()
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise StripeNotConfigured("STRIPE_WEBHOOK_SECRET non configurato.")
    return stripe.Webhook.construct_event(payload, sig_header, secret)
