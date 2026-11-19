import hashlib
import json
import uuid
from enum import Enum
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from app.config import settings
from app.memory.database import get_connection


class ActionCategory(str, Enum):
    FREE = "free"
    REQUIRES_AUTH = "requires_auth"
    EXTERNAL = "external"


def _payload_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SecurityManager:
    def __init__(self):
        # In-memory store for pending authorizations requested by the model.
        # Authorizations are single-use, expire quickly and are bound to the
        # exact tool + parameters that were shown to the user.
        self.pending_actions: Dict[str, Dict[str, Any]] = {}

    def log_action(
        self,
        action_type: str,
        category: ActionCategory,
        resource: str,
        authorized: bool,
        details: str = ""
    ):
        """Persists every relevant security decision to the audit log."""
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_logs (action_type, category, resource, authorized, details)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (action_type, category.value, resource, 1 if authorized else 0, details)
                )
        except Exception as e:
            print(f"Failed to log audit event: {e}")

    def _purge_expired(self):
        now = datetime.now(timezone.utc).timestamp()
        expired = [aid for aid, a in self.pending_actions.items() if a["expires_at"] < now]
        for aid in expired:
            action = self.pending_actions.pop(aid, None)
            if action:
                self.log_action(
                    action_type=action["action_type"],
                    category=ActionCategory(action["category"]),
                    resource=action["resource"],
                    authorized=False,
                    details="Authorization expired before user decision",
                )
        # Hard cap: never let the in-memory queue grow indefinitely.
        if len(self.pending_actions) > 50:
            for aid in list(self.pending_actions.keys())[: len(self.pending_actions) - 50]:
                self.pending_actions.pop(aid, None)

    def create_authorization_request(
        self,
        action_type: str,
        category: ActionCategory,
        resource: str,
        description: str,
        payload: Dict[str, Any]
    ) -> str:
        """
        Registers an action that requires user consent.
        Returns a unique action_id, valid only for the configured TTL.
        """
        self._purge_expired()
        action_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).timestamp()
        ttl = max(30, int(settings.authorization_ttl_seconds))
        self.pending_actions[action_id] = {
            "id": action_id,
            "action_type": action_type,
            "category": category.value,
            "resource": resource,
            "description": description,
            "payload": dict(payload or {}),
            "payload_hash": _payload_hash(payload or {}),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "expires_at": now + ttl,
            "expires_at_iso": datetime.fromtimestamp(now + ttl).isoformat(timespec="seconds"),
        }
        self.log_action(
            action_type=action_type,
            category=category,
            resource=resource,
            authorized=False,
            details=f"Authorization requested (valid for {ttl}s; not executed)",
        )
        return action_id

    def get_pending_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        self._purge_expired()
        return self.pending_actions.get(action_id)

    def list_pending_actions(self) -> list:
        self._purge_expired()
        public_fields = (
            "id", "action_type", "category", "resource", "description",
            "payload", "timestamp", "expires_at", "expires_at_iso",
        )
        return [
            {k: a.get(k) for k in public_fields}
            for a in self.pending_actions.values()
        ]

    def resolve_action_detailed(
        self, action_id: str, approved: bool
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Single-use resolution. Returns (status, action) where status is one of:
        approved, rejected, not_found, expired, tampered.
        """
        self._purge_expired()
        action = self.pending_actions.pop(action_id, None)
        if not action:
            return "not_found", None

        now = datetime.now(timezone.utc).timestamp()
        if action["expires_at"] < now:
            self.log_action(
                action_type=action["action_type"],
                category=ActionCategory(action["category"]),
                resource=action["resource"],
                authorized=False,
                details="Authorization expired",
            )
            return "expired", None

        if not approved:
            self.log_action(
                action_type=action["action_type"],
                category=ActionCategory(action["category"]),
                resource=action["resource"],
                authorized=False,
                details="User rejected the action",
            )
            return "rejected", None

        if _payload_hash(action["payload"]) != action["payload_hash"]:
            self.log_action(
                action_type=action["action_type"],
                category=ActionCategory(action["category"]),
                resource=action["resource"],
                authorized=False,
                details="Payload mismatch; action blocked",
            )
            return "tampered", None

        self.log_action(
            action_type=action["action_type"],
            category=ActionCategory(action["category"]),
            resource=action["resource"],
            authorized=True,
            details="User approved the action (single use)",
        )
        return "approved", action

    def resolve_action(self, action_id: str, approved: bool) -> Optional[Dict[str, Any]]:
        status, action = self.resolve_action_detailed(action_id, approved)
        return action if status == "approved" else None


security_manager = SecurityManager()
