-- Create feeds table
CREATE TABLE feeds (
    id SERIAL PRIMARY KEY,
    feed_url VARCHAR(2048) UNIQUE NOT NULL,
    title VARCHAR(512) NOT NULL,
    description TEXT,
    active BOOLEAN NOT NULL DEFAULT true,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_checked TIMESTAMP,
    last_episode_date TIMESTAMP,
    total_episodes_processed INTEGER NOT NULL DEFAULT 0,
    total_episodes_failed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_feeds_active ON feeds(active);

-- Create episodes table
CREATE TABLE episodes (
    id SERIAL PRIMARY KEY,
    episode_guid VARCHAR(1024) UNIQUE NOT NULL,
    feed_id INTEGER NOT NULL,
    title VARCHAR(1024) NOT NULL,
    published_date TIMESTAMP NOT NULL,
    audio_url VARCHAR(4096) NOT NULL,
    duration_seconds INTEGER,
    description TEXT,
    audio_path VARCHAR(4096),
    audio_downloaded_at TIMESTAMP,
    transcript_path VARCHAR(4096),
    transcript_generated_at TIMESTAMP,
    transcript_word_count INTEGER,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    scores JSONB,
    scored_at TIMESTAMP,
    status VARCHAR(64) NOT NULL DEFAULT 'pending',
    failure_count INTEGER NOT NULL DEFAULT 0,
    failure_reason TEXT,
    last_failure_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_episodes_status_published ON episodes(status, published_date);
CREATE INDEX ix_episodes_scored ON episodes(scored_at);

-- Create digests table
CREATE TABLE digests (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(256) NOT NULL,
    digest_date DATE NOT NULL,
    script_path VARCHAR(4096),
    script_word_count INTEGER,
    mp3_path VARCHAR(4096),
    mp3_duration_seconds INTEGER,
    mp3_title VARCHAR(1024),
    mp3_summary TEXT,
    episode_ids JSONB,
    episode_count INTEGER NOT NULL DEFAULT 0,
    average_score INTEGER,
    github_url VARCHAR(4096),
    published_at TIMESTAMP,
    generated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(topic, digest_date)
);

CREATE INDEX ix_digests_date ON digests(digest_date);