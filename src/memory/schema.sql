-- Sidecar only. Never store raw transcripts, file bytes, or guest data here.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS memory_files (
  file_id TEXT PRIMARY KEY,
  sha256 TEXT UNIQUE NOT NULL,
  storage_key TEXT NOT NULL,
  original_name_redacted TEXT,
  detected_mime TEXT NOT NULL,
  byte_count INTEGER NOT NULL,
  intake_source TEXT NOT NULL,
  status TEXT NOT NULL,
  pii_status TEXT NOT NULL,
  received_at TEXT NOT NULL,
  retained_until TEXT,
  deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS memory_extractions (
  extraction_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL REFERENCES memory_files(file_id),
  extractor_version TEXT NOT NULL,
  transcript_hash TEXT,
  extraction_status TEXT NOT NULL,
  injection_flags_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_claims (
  claim_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  file_id TEXT REFERENCES memory_files(file_id),
  parent_claim_id TEXT,
  kind TEXT NOT NULL,
  property_id TEXT,
  scope_type TEXT NOT NULL,
  stay_from TEXT,
  stay_to TEXT,
  value_json TEXT NOT NULL,
  effect_class TEXT NOT NULL,
  confidence REAL NOT NULL,
  status TEXT NOT NULL,
  accepted_by TEXT,
  accepted_at TEXT,
  review_after TEXT,
  supersedes_claim_id TEXT,
  source_excerpt_hash TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (claim_id, revision)
);

CREATE TABLE IF NOT EXISTS memory_events (
  event_id TEXT PRIMARY KEY,
  claim_id TEXT,
  file_id TEXT,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);
