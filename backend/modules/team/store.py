from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from db.database import AsyncSessionLocal, InMemorySessionStore, is_db_available
from modules.auth.user_store import get_user_profile

try:
    from sqlalchemy import delete, or_, select
    from db.models import Team, TeamMember
except Exception:  # pragma: no cover
    Team = TeamMember = None  # type: ignore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    raw = raw.strip("-")
    return raw or f"team-{uuid.uuid4().hex[:6]}"


class TeamStore:
    _ROOT = "__team__"

    @classmethod
    def _state(cls) -> dict[str, Any]:
        state = InMemorySessionStore.get(cls._ROOT, "state")
        if not state:
            state = {"teams": {}, "members": {}}
            InMemorySessionStore.save(cls._ROOT, "state", state)
        return state

    @classmethod
    async def user_team_ids(cls, username: str) -> list[str]:
        normalized = str(username or "").strip().lower()
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    owned_rows = (
                        await db.execute(select(Team.id).where(Team.owner_username == normalized))
                    ).scalars().all()
                    member_rows = (
                        await db.execute(select(TeamMember.team_id).where(TeamMember.username == normalized))
                    ).scalars().all()
                    return sorted({*owned_rows, *member_rows})
            except Exception:
                pass

        state = cls._state()
        team_ids = {
            team_id
            for team_id, team in state["teams"].items()
            if str(team.get("owner_username") or "").strip().lower() == normalized
        }
        for team_id, members in state["members"].items():
            if any(str(member.get("username") or "").strip().lower() == normalized for member in members):
                team_ids.add(team_id)
        return sorted(team_ids)

    @classmethod
    async def list_teams_for_user(cls, username: str) -> list[dict[str, Any]]:
        team_ids = await cls.user_team_ids(username)
        teams = []
        for team_id in team_ids:
            team = await cls.get_team_for_user(username, team_id)
            if team:
                teams.append(team)
        return sorted(teams, key=lambda item: item.get("updated_at") or "", reverse=True)

    @classmethod
    async def get_team_for_user(cls, username: str, team_id: str) -> Optional[dict[str, Any]]:
        normalized = str(username or "").strip().lower()
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    team_row = (
                        await db.execute(
                            select(Team).where(
                                Team.id == team_id,
                                or_(
                                    Team.owner_username == normalized,
                                    Team.id.in_(select(TeamMember.team_id).where(TeamMember.username == normalized)),
                                ),
                            )
                        )
                    ).scalar_one_or_none()
                    if not team_row:
                        return None
                    member_rows = (
                        await db.execute(select(TeamMember).where(TeamMember.team_id == team_id))
                    ).scalars().all()
                    return cls._serialize_team_row(team_row, member_rows)
            except Exception:
                pass

        state = cls._state()
        team = state["teams"].get(team_id)
        if not team:
            return None
        member_rows = state["members"].get(team_id, [])
        allowed = str(team.get("owner_username") or "").strip().lower() == normalized or any(
            str(member.get("username") or "").strip().lower() == normalized for member in member_rows
        )
        if not allowed:
            return None
        return {**team, "members": list(member_rows)}

    @classmethod
    async def create_team(cls, *, owner_username: str, name: str) -> dict[str, Any]:
        team_id = str(uuid.uuid4())
        now = _utc_now()
        payload = {
            "team_id": team_id,
            "owner_username": str(owner_username or "").strip().lower(),
            "name": (name or "Nuovo team").strip() or "Nuovo team",
            "slug": _slugify(name),
            "brand_name": (name or "Nuovo team").strip() or "Nuovo team",
            "primary_accent": "cyan",
            "support_email": "",
            "legal_label": "",
            "white_label_enabled": False,
            "settings": {
                "workspace_label": "Desk team",
                "shared_projects_enabled": True,
                "brand_footer": "",
            },
            "created_at": now,
            "updated_at": now,
        }
        owner_member = {
            "team_member_id": str(uuid.uuid4()),
            "team_id": team_id,
            "username": payload["owner_username"],
            "role": "owner",
            "created_at": now,
            "updated_at": now,
        }

        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    db.add(
                        Team(
                            id=team_id,
                            owner_username=payload["owner_username"],
                            name=payload["name"],
                            slug=payload["slug"],
                            brand_name=payload["brand_name"],
                            primary_accent=payload["primary_accent"],
                            support_email=payload["support_email"],
                            legal_label=payload["legal_label"],
                            white_label_enabled=payload["white_label_enabled"],
                            settings_json=payload["settings"],
                        )
                    )
                    db.add(
                        TeamMember(
                            id=owner_member["team_member_id"],
                            team_id=team_id,
                            username=payload["owner_username"],
                            role="owner",
                        )
                    )
                    await db.commit()
                return {**payload, "members": [owner_member]}
            except Exception:
                pass

        state = cls._state()
        state["teams"][team_id] = payload
        state["members"][team_id] = [owner_member]
        InMemorySessionStore.save(cls._ROOT, "state", state)
        return {**payload, "members": [owner_member]}

    @classmethod
    async def upsert_branding(
        cls,
        *,
        owner_username: str,
        team_id: str,
        brand_name: Optional[str] = None,
        primary_accent: Optional[str] = None,
        support_email: Optional[str] = None,
        legal_label: Optional[str] = None,
        white_label_enabled: Optional[bool] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        team = await cls.get_team_for_user(owner_username, team_id)
        if not team or team.get("owner_username") != str(owner_username or "").strip().lower():
            return None
        changes = {
            "brand_name": brand_name,
            "primary_accent": primary_accent,
            "support_email": support_email,
            "legal_label": legal_label,
            "white_label_enabled": white_label_enabled,
            "settings": settings,
        }

        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    row = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
                    if not row:
                        return None
                    if brand_name is not None:
                        row.brand_name = brand_name.strip() or row.brand_name
                    if primary_accent is not None:
                        row.primary_accent = primary_accent.strip() or row.primary_accent
                    if support_email is not None:
                        row.support_email = support_email.strip()
                    if legal_label is not None:
                        row.legal_label = legal_label.strip()
                    if white_label_enabled is not None:
                        row.white_label_enabled = bool(white_label_enabled)
                    if settings is not None:
                        merged = dict(row.settings_json or {})
                        merged.update(settings or {})
                        row.settings_json = merged
                    await db.commit()
                return await cls.get_team_for_user(owner_username, team_id)
            except Exception:
                pass

        state = cls._state()
        item = state["teams"].get(team_id)
        if not item:
            return None
        if brand_name is not None:
            item["brand_name"] = brand_name.strip() or item.get("brand_name")
        if primary_accent is not None:
            item["primary_accent"] = primary_accent.strip() or item.get("primary_accent")
        if support_email is not None:
            item["support_email"] = support_email.strip()
        if legal_label is not None:
            item["legal_label"] = legal_label.strip()
        if white_label_enabled is not None:
            item["white_label_enabled"] = bool(white_label_enabled)
        if settings is not None:
            merged = dict(item.get("settings") or {})
            merged.update(settings or {})
            item["settings"] = merged
        item["updated_at"] = _utc_now()
        InMemorySessionStore.save(cls._ROOT, "state", state)
        return await cls.get_team_for_user(owner_username, team_id)

    @classmethod
    async def replace_members(
        cls,
        *,
        owner_username: str,
        team_id: str,
        members: list[dict[str, str]],
    ) -> Optional[dict[str, Any]]:
        team = await cls.get_team_for_user(owner_username, team_id)
        normalized_owner = str(owner_username or "").strip().lower()
        if not team or team.get("owner_username") != normalized_owner:
            return None

        cleaned_members: list[dict[str, Any]] = []
        seen = {normalized_owner}
        now = _utc_now()
        for raw_member in members:
            username = str((raw_member or {}).get("username") or "").strip().lower()
            role = str((raw_member or {}).get("role") or "viewer").strip().lower()
            if not username or username in seen:
                continue
            if role not in {"admin", "editor", "viewer"}:
                role = "viewer"
            if not await get_user_profile(username):
                continue
            seen.add(username)
            cleaned_members.append(
                {
                    "team_member_id": str(uuid.uuid4()),
                    "team_id": team_id,
                    "username": username,
                    "role": role,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        owner_record = {
            "team_member_id": str(uuid.uuid4()),
            "team_id": team_id,
            "username": normalized_owner,
            "role": "owner",
            "created_at": now,
            "updated_at": now,
        }
        final_members = [owner_record, *cleaned_members]

        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    await db.execute(delete(TeamMember).where(TeamMember.team_id == team_id))
                    for member in final_members:
                        db.add(
                            TeamMember(
                                id=member["team_member_id"],
                                team_id=team_id,
                                username=member["username"],
                                role=member["role"],
                            )
                        )
                    await db.commit()
                return await cls.get_team_for_user(owner_username, team_id)
            except Exception:
                pass

        state = cls._state()
        state["members"][team_id] = final_members
        team_item = state["teams"].get(team_id)
        if team_item:
            team_item["updated_at"] = _utc_now()
        InMemorySessionStore.save(cls._ROOT, "state", state)
        return await cls.get_team_for_user(owner_username, team_id)

    @classmethod
    async def assign_project_to_team(
        cls,
        *,
        owner_username: str,
        project_id: str,
        team_id: Optional[str],
    ) -> bool:
        from modules.projects.store import ProjectStore

        if team_id:
            team = await cls.get_team_for_user(owner_username, team_id)
            if not team or team.get("owner_username") != str(owner_username or "").strip().lower():
                return False
        project = await ProjectStore.get_project(owner_username, project_id)
        if not project:
            return False
        await ProjectStore.update_project(project_id, metadata={"team_id": team_id or None})
        return True

    @classmethod
    def _serialize_team_row(cls, row: Any, member_rows: list[Any]) -> dict[str, Any]:
        return {
            "team_id": row.id,
            "owner_username": row.owner_username,
            "name": row.name,
            "slug": row.slug,
            "brand_name": row.brand_name,
            "primary_accent": row.primary_accent,
            "support_email": row.support_email,
            "legal_label": row.legal_label,
            "white_label_enabled": bool(row.white_label_enabled),
            "settings": row.settings_json or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "members": [
                {
                    "team_member_id": member.id,
                    "team_id": member.team_id,
                    "username": member.username,
                    "role": member.role,
                    "created_at": member.created_at.isoformat() if member.created_at else None,
                    "updated_at": member.updated_at.isoformat() if member.updated_at else None,
                }
                for member in member_rows
            ],
        }
