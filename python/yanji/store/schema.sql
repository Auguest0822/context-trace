-- ContextTrace schema for seekdb 1.4.x (MySQL protocol).
-- Run against a newly created database. Existing draft tables need an explicit migration.
-- Application timestamps are UTC. API BIGINT identifiers are serialized as strings.

CREATE TABLE IF NOT EXISTS conversations (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  scope VARCHAR(128) NOT NULL,
  platform VARCHAR(16) NOT NULL,
  external_conversation_id VARCHAR(512) NULL,
  title VARCHAR(256) NOT NULL,
  source_url TEXT NULL,
  capture_method VARCHAR(32) NOT NULL,
  capture_completeness VARCHAR(16) NOT NULL,
  message_count INT NOT NULL DEFAULT 0,
  memory_count INT NOT NULL DEFAULT 0,
  captured_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_conversation_external (scope, platform, external_conversation_id),
  KEY idx_conversation_list (scope, updated_at, id)
);

CREATE TABLE IF NOT EXISTS messages (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  conversation_id BIGINT NOT NULL,
  scope VARCHAR(128) NOT NULL,
  external_message_id VARCHAR(512) NULL,
  sequence INT NOT NULL,
  role VARCHAR(16) NOT NULL,
  content MEDIUMTEXT NOT NULL,
  content_sha256 CHAR(64) NOT NULL,
  sent_at DATETIME(6) NULL,
  captured_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_message_sequence (conversation_id, sequence),
  UNIQUE KEY uq_message_external (conversation_id, external_message_id),
  KEY idx_message_list (scope, conversation_id, sequence, id)
);

CREATE TABLE IF NOT EXISTS extraction_previews (
  id CHAR(36) NOT NULL PRIMARY KEY,
  scope VARCHAR(128) NOT NULL,
  conversation_id BIGINT NOT NULL,
  selected_message_ids JSON NOT NULL,
  candidates JSON NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'pending',
  expires_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  committed_at DATETIME(6) NULL,
  KEY idx_preview_conversation (scope, conversation_id, expires_at)
);

CREATE TABLE IF NOT EXISTS memories (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  scope VARCHAR(128) NOT NULL,
  kind VARCHAR(16) NOT NULL,
  content TEXT NOT NULL,
  summary VARCHAR(512) NULL,
  embedding VECTOR(1024) NULL,
  embedding_model VARCHAR(128) NULL,
  embedding_dim INT NULL,
  importance FLOAT NOT NULL DEFAULT 0.5,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  superseded_by BIGINT NULL,
  source_type VARCHAR(16) NOT NULL,
  source_ref VARCHAR(512) NOT NULL,
  source_excerpt VARCHAR(1000) NOT NULL,
  source_platform VARCHAR(16) NULL,
  conversation_id BIGINT NULL,
  client_request_id CHAR(36) NULL,
  valid_from DATETIME(6) NULL,
  valid_to DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_memory_request (scope, client_request_id),
  KEY idx_memory_list (scope, status, created_at, id),
  KEY idx_memory_conversation (scope, conversation_id, id),
  FULLTEXT INDEX idx_memory_fulltext (content) WITH PARSER ik,
  VECTOR INDEX idx_memory_vector (embedding) WITH (DISTANCE=l2, TYPE=hnsw)
) ORGANIZATION = HEAP;

CREATE TABLE IF NOT EXISTS memory_message_links (
  memory_id BIGINT NOT NULL,
  message_id BIGINT NOT NULL,
  scope VARCHAR(128) NOT NULL,
  source_excerpt VARCHAR(1000) NOT NULL,
  PRIMARY KEY (memory_id, message_id),
  KEY idx_memory_link_message (scope, message_id, memory_id)
);

CREATE TABLE IF NOT EXISTS retrieval_traces (
  trace_id CHAR(36) NOT NULL PRIMARY KEY,
  scope VARCHAR(128) NOT NULL,
  query TEXT NOT NULL,
  mode_requested VARCHAR(16) NOT NULL,
  mode_used VARCHAR(16) NOT NULL,
  filters_applied JSON NOT NULL,
  budget JSON NOT NULL,
  candidate_count INT NOT NULL DEFAULT 0,
  selected_count INT NOT NULL DEFAULT 0,
  elapsed_ms INT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_trace_list (scope, created_at, trace_id)
);

CREATE TABLE IF NOT EXISTS retrieval_trace_items (
  trace_id CHAR(36) NOT NULL,
  memory_id BIGINT NOT NULL,
  scope VARCHAR(128) NOT NULL,
  fusion_rank INT NOT NULL,
  keyword_rank INT NULL,
  vector_rank INT NULL,
  fusion_score DOUBLE NULL,
  decision VARCHAR(16) NOT NULL,
  selected_form VARCHAR(16) NULL,
  reason_codes JSON NOT NULL,
  PRIMARY KEY (trace_id, memory_id),
  KEY idx_trace_item_memory (scope, memory_id, trace_id)
);

CREATE TABLE IF NOT EXISTS memory_revisions (
  old_memory_id BIGINT NOT NULL PRIMARY KEY,
  new_memory_id BIGINT NOT NULL,
  scope VARCHAR(128) NOT NULL,
  reason VARCHAR(500) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_revision_new (scope, new_memory_id)
);

CREATE TABLE IF NOT EXISTS idempotency_requests (
  scope VARCHAR(128) NOT NULL,
  client_request_id CHAR(36) NOT NULL,
  operation VARCHAR(64) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  response_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (scope, client_request_id)
);
