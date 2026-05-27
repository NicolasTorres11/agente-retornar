PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS sessions (
    wa_id TEXT PRIMARY KEY,
    user_name_encrypted BLOB,
    consent_given INTEGER NOT NULL DEFAULT 0,
    flow_state TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL,
    last_activity TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    wa_id TEXT NOT NULL,
    message_id_meta TEXT UNIQUE,
    direction TEXT NOT NULL,
    content_encrypted BLOB NOT NULL,
    timestamp TEXT NOT NULL,
    category TEXT,
    confidence REAL,
    action TEXT,
    risk_level TEXT,
    status TEXT,
    error TEXT,
    FOREIGN KEY (wa_id) REFERENCES sessions(wa_id)
);

CREATE TABLE IF NOT EXISTS escalations (
    id TEXT PRIMARY KEY,
    wa_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority TEXT NOT NULL,
    category TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS consents (
    id TEXT PRIMARY KEY,
    wa_id TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appointment_requests (
    wa_id TEXT PRIMARY KEY,
    tipo_cita_encrypted BLOB,
    especialidad_encrypted BLOB,
    eps_encrypted BLOB,
    urgencia_encrypted BLOB,
    status TEXT NOT NULL DEFAULT 'collecting',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (wa_id) REFERENCES sessions(wa_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    event TEXT NOT NULL,
    wa_id_hash TEXT,
    timestamp TEXT NOT NULL,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_wa_id ON messages(wa_id);
CREATE INDEX IF NOT EXISTS idx_escalations_wa_id ON escalations(wa_id);
