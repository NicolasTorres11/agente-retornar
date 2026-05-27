"""SQLite implementation of persistence ports for the local agent."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from src.classifier.models import ClassificationResult
from src.domain.models import FlowState, InboundMessage, Priority

from .encryption import FieldCipher, hash_identifier


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteConversationRepository:
    def __init__(self, db_path: Path, encryption_key: str) -> None:
        self.db_path = db_path
        self.cipher = FieldCipher(encryption_key)

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema)
            await db.commit()

    async def record_inbound(self, message: InboundMessage) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR IGNORE INTO sessions
                   (wa_id, user_name_encrypted, created_at, last_activity)
                   VALUES (?, ?, ?, ?)""",
                (
                    message.wa_id,
                    self.cipher.encrypt(message.user_name) if message.user_name else None,
                    message.received_at,
                    message.received_at,
                ),
            )
            cursor = await db.execute(
                """INSERT OR IGNORE INTO messages
                   (id, wa_id, message_id_meta, direction, content_encrypted, timestamp, status)
                   VALUES (?, ?, ?, 'inbound', ?, ?, 'received')""",
                (
                    str(uuid.uuid4()),
                    message.wa_id,
                    message.message_id,
                    self.cipher.encrypt(message.text),
                    message.received_at,
                ),
            )
            inserted = cursor.rowcount == 1
            if inserted:
                await db.execute(
                    "UPDATE sessions SET last_activity = ? WHERE wa_id = ?",
                    (message.received_at, message.wa_id),
                )
            await db.commit()
        return inserted

    async def has_consent(self, wa_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT consent_given FROM sessions WHERE wa_id = ?", (wa_id,)
            )
            row = await cursor.fetchone()
        return bool(row and row[0])

    async def record_consent(self, wa_id: str, accepted: bool) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET consent_given = ?, flow_state = ? WHERE wa_id = ?",
                (int(accepted), FlowState.IN_PROGRESS if accepted else FlowState.CLOSED, wa_id),
            )
            await db.execute(
                "INSERT INTO consents (id, wa_id, accepted, created_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), wa_id, int(accepted), _now()),
            )
            await self._audit(db, "consent_recorded", wa_id, {"accepted": accepted})
            await db.commit()

    async def set_state(self, wa_id: str, state: FlowState) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE sessions SET flow_state = ? WHERE wa_id = ?", (state, wa_id))
            await self._audit(db, "state_changed", wa_id, {"state": state.value})
            await db.commit()

    async def get_open_appointment(self, wa_id: str) -> dict[str, str] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT tipo_cita_encrypted, especialidad_encrypted, eps_encrypted,
                          urgencia_encrypted
                   FROM appointment_requests
                   WHERE wa_id = ? AND status = 'collecting'""",
                (wa_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        columns = {
            "tipo_cita": "tipo_cita_encrypted",
            "especialidad": "especialidad_encrypted",
            "eps": "eps_encrypted",
            "urgencia": "urgencia_encrypted",
        }
        return {
            slot: self.cipher.decrypt(row[column])
            for slot, column in columns.items()
            if row[column] is not None
        }

    async def save_appointment(
        self, wa_id: str, slots: dict[str, str], status: str = "collecting"
    ) -> None:
        timestamp = _now()
        encrypted = {
            name: self.cipher.encrypt(slots[name]) if name in slots else None
            for name in ("tipo_cita", "especialidad", "eps", "urgencia")
        }
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO appointment_requests
                   (wa_id, tipo_cita_encrypted, especialidad_encrypted, eps_encrypted,
                    urgencia_encrypted, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(wa_id) DO UPDATE SET
                     tipo_cita_encrypted = excluded.tipo_cita_encrypted,
                     especialidad_encrypted = excluded.especialidad_encrypted,
                     eps_encrypted = excluded.eps_encrypted,
                     urgencia_encrypted = excluded.urgencia_encrypted,
                     status = excluded.status,
                     updated_at = excluded.updated_at""",
                (
                    wa_id,
                    encrypted["tipo_cita"],
                    encrypted["especialidad"],
                    encrypted["eps"],
                    encrypted["urgencia"],
                    status,
                    timestamp,
                    timestamp,
                ),
            )
            await self._audit(db, "appointment_updated", wa_id, {"status": status})
            await db.commit()

    async def record_classification(self, message_id: str, result: ClassificationResult) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE messages SET category = ?, confidence = ?, action = ?, risk_level = ?
                   WHERE message_id_meta = ?""",
                (
                    result.category.value,
                    result.confidence,
                    result.suggested_action.value,
                    result.metadata.risk_level.value,
                    message_id,
                ),
            )
            await db.commit()

    async def record_escalation(
        self, wa_id: str, reason: str, priority: Priority, result: ClassificationResult
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO escalations
                   (id, wa_id, timestamp, reason, priority, category, risk_level)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    wa_id,
                    _now(),
                    reason,
                    priority.value,
                    result.category.value,
                    result.metadata.risk_level.value,
                ),
            )
            await self._audit(db, "escalation_created", wa_id, {"priority": priority.value})
            await db.commit()

    async def queue_outbound(self, wa_id: str, text: str) -> str:
        local_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO messages
                   (id, wa_id, direction, content_encrypted, timestamp, status)
                   VALUES (?, ?, 'outbound', ?, ?, 'queued')""",
                (local_id, wa_id, self.cipher.encrypt(text), _now()),
            )
            await db.commit()
        return local_id

    async def mark_outbound_sent(self, local_id: str, meta_id: str | None = None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE messages SET status = 'sent', message_id_meta = ? WHERE id = ?",
                (meta_id, local_id),
            )
            await db.commit()

    async def mark_outbound_failed(self, local_id: str, error: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE messages SET status = 'failed', error = ? WHERE id = ?",
                (error[:300], local_id),
            )
            await db.commit()

    async def update_delivery_status(self, meta_id: str, status: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE messages SET status = ? WHERE message_id_meta = ?", (status, meta_id)
            )
            await db.commit()

    async def list_messages(self, wa_id: str) -> list[dict[str, object]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT id, direction, content_encrypted, timestamp, category, confidence,
                          action, risk_level, status FROM messages
                   WHERE wa_id = ? ORDER BY timestamp""",
                (wa_id,),
            )
            rows = await cursor.fetchall()
        return [
            {
                **{key: row[key] for key in row.keys() if key != "content_encrypted"},
                "text": self.cipher.decrypt(row["content_encrypted"]),
            }
            for row in rows
        ]

    async def list_escalations(self) -> list[dict[str, object]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT timestamp, reason, priority, category, risk_level FROM escalations"
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def _audit(
        self, db: aiosqlite.Connection, event: str, wa_id: str, details: dict[str, object]
    ) -> None:
        await db.execute(
            """INSERT INTO audit_log (id, event, wa_id_hash, timestamp, details)
               VALUES (?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), event, hash_identifier(wa_id), _now(), json.dumps(details)),
        )
