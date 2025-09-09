-- RSS Podcast Transcript Digest System Database Schema
-- SQLite3 Database Schema for Episodes, Feeds, and Digests

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Feeds table: RSS podcast feeds being monitored
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    active BOOLEAN DEFAULT 1,
    consecutive_failures INTEGER DEFAULT 0,
    last_checked DATETIME,
    last_episode_date DATETIME,
    total_episodes_processed INTEGER DEFAULT 0,
    total_episodes_failed INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Episodes table: Individual podcast episodes and their processing status
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_guid TEXT UNIQUE NOT NULL,
    feed_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    published_date DATETIME NOT NULL,
    duration_seconds INTEGER,
    description TEXT,
    audio_url TEXT NOT NULL,
    audio_path TEXT,
    audio_downloaded_at DATETIME,
    transcript_path TEXT,
    transcript_generated_at DATETIME,
    transcript_word_count INTEGER,
    chunk_count INTEGER DEFAULT 0,
    scores JSON,
    scored_at DATETIME,
    status TEXT CHECK(status IN (
        'pending',
        'downloading',
        'chunking',
        'transcribing',
        'transcribed',
        'scoring',
        'scored',
        'digested',
        'failed'
    )) DEFAULT 'pending',
    failure_count INTEGER DEFAULT 0,
    failure_reason TEXT,
    last_failure_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feed_id) REFERENCES feeds(id) ON DELETE CASCADE
);

-- Digests table: Generated topic-based daily digests
CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    digest_date DATE NOT NULL,
    script_path TEXT,
    script_word_count INTEGER,
    mp3_path TEXT,
    mp3_duration_seconds INTEGER,
    mp3_title TEXT,
    mp3_summary TEXT,
    episode_ids JSON,
    episode_count INTEGER DEFAULT 0,
    average_score REAL,
    github_url TEXT,
    published_at DATETIME,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(topic, digest_date)
);

-- System metadata table: Track database version and system state
CREATE TABLE IF NOT EXISTS system_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);
CREATE INDEX IF NOT EXISTS idx_episodes_published ON episodes(published_date);
CREATE INDEX IF NOT EXISTS idx_episodes_feed ON episodes(feed_id);
CREATE INDEX IF NOT EXISTS idx_episodes_scores ON episodes(scores) WHERE scores IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_feeds_active ON feeds(active) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_digests_date ON digests(digest_date);
CREATE INDEX IF NOT EXISTS idx_digests_topic ON digests(topic);

-- Triggers for automatic timestamp updates
CREATE TRIGGER IF NOT EXISTS update_feeds_timestamp 
    AFTER UPDATE ON feeds
    BEGIN
        UPDATE feeds SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_episodes_timestamp 
    AFTER UPDATE ON episodes
    BEGIN
        UPDATE episodes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- Insert initial system metadata
INSERT OR REPLACE INTO system_metadata (key, value) VALUES 
    ('schema_version', '1.0'),
    ('created_at', datetime('now')),
    ('last_migration', datetime('now'));

-- Views for common queries
CREATE VIEW IF NOT EXISTS active_feeds AS
SELECT * FROM feeds WHERE active = 1;

CREATE VIEW IF NOT EXISTS recent_episodes AS
SELECT 
    e.*,
    f.title as feed_title,
    julianday('now') - julianday(e.published_date) as days_old
FROM episodes e
JOIN feeds f ON e.feed_id = f.id
WHERE e.published_date > date('now', '-30 days')
ORDER BY e.published_date DESC;

CREATE VIEW IF NOT EXISTS scored_episodes AS
SELECT 
    e.*,
    f.title as feed_title,
    json_extract(e.scores, '$') as all_scores
FROM episodes e
JOIN feeds f ON e.feed_id = f.id
WHERE e.status = 'scored' AND e.scores IS NOT NULL;

CREATE VIEW IF NOT EXISTS digest_stats AS
SELECT 
    topic,
    COUNT(*) as total_digests,
    AVG(episode_count) as avg_episodes_per_digest,
    AVG(average_score) as avg_relevancy_score,
    MAX(digest_date) as latest_digest
FROM digests
GROUP BY topic;