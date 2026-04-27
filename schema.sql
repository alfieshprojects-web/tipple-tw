-- TIPPLE D1 Schema v1.0
-- 執行方式：
--   npx wrangler d1 execute tipple-db --file=schema.sql            (remote)
--   npx wrangler d1 execute tipple-db --file=schema.sql --local    (local dev)

CREATE TABLE IF NOT EXISTS users (
  id         TEXT    PRIMARY KEY,   -- Google "sub" claim
  name       TEXT    NOT NULL,
  email      TEXT,
  avatar     TEXT,
  points     INTEGER DEFAULT 0,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token      TEXT    PRIMARY KEY,
  user_id    TEXT    NOT NULL,
  expires_at INTEGER NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reviews (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    TEXT    NOT NULL,
  bar_id     INTEGER NOT NULL,
  rating     INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
  text       TEXT    NOT NULL CHECK(length(text) >= 10),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  UNIQUE(user_id, bar_id),
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS helpful_votes (
  user_id   TEXT    NOT NULL,
  review_id INTEGER NOT NULL,
  PRIMARY KEY(user_id, review_id),
  FOREIGN KEY(user_id)   REFERENCES users(id)   ON DELETE CASCADE,
  FOREIGN KEY(review_id) REFERENCES reviews(id) ON DELETE CASCADE
);

-- 快速查詢索引
CREATE INDEX IF NOT EXISTS idx_reviews_bar   ON reviews(bar_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user  ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_helpful_review ON helpful_votes(review_id);
