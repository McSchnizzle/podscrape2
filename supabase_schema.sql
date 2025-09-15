BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 1ad9f7f93530

CREATE TABLE feeds (
    id SERIAL NOT NULL, 
    feed_url VARCHAR(2048) NOT NULL, 
    title VARCHAR(512) NOT NULL, 
    description TEXT, 
    active BOOLEAN NOT NULL, 
    consecutive_failures INTEGER NOT NULL, 
    last_checked TIMESTAMP WITHOUT TIME ZONE, 
    last_episode_date TIMESTAMP WITHOUT TIME ZONE, 
    total_episodes_processed INTEGER NOT NULL, 
    total_episodes_failed INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (feed_url)
);

CREATE INDEX ix_feeds_active ON feeds (active);

CREATE TABLE episodes (
    id SERIAL NOT NULL, 
    episode_guid VARCHAR(1024) NOT NULL, 
    feed_id INTEGER NOT NULL, 
    title VARCHAR(1024) NOT NULL, 
    published_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    audio_url VARCHAR(4096) NOT NULL, 
    duration_seconds INTEGER, 
    description TEXT, 
    audio_path VARCHAR(4096), 
    audio_downloaded_at TIMESTAMP WITHOUT TIME ZONE, 
    transcript_path VARCHAR(4096), 
    transcript_generated_at TIMESTAMP WITHOUT TIME ZONE, 
    transcript_word_count INTEGER, 
    chunk_count INTEGER NOT NULL, 
    scores JSONB, 
    scored_at TIMESTAMP WITHOUT TIME ZONE, 
    status VARCHAR(64) NOT NULL, 
    failure_count INTEGER NOT NULL, 
    failure_reason TEXT, 
    last_failure_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (episode_guid)
);

CREATE INDEX ix_episodes_status_published ON episodes (status, published_date);

CREATE INDEX ix_episodes_scored ON episodes (scored_at);

CREATE TABLE digests (
    id SERIAL NOT NULL, 
    topic VARCHAR(256) NOT NULL, 
    digest_date DATE NOT NULL, 
    script_path VARCHAR(4096), 
    script_word_count INTEGER, 
    mp3_path VARCHAR(4096), 
    mp3_duration_seconds INTEGER, 
    mp3_title VARCHAR(1024), 
    mp3_summary TEXT, 
    episode_ids JSONB, 
    episode_count INTEGER NOT NULL, 
    average_score INTEGER, 
    github_url VARCHAR(4096), 
    published_at TIMESTAMP WITHOUT TIME ZONE, 
    generated_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_digests_date ON digests (digest_date);

CREATE UNIQUE INDEX ix_digests_topic ON digests (topic, digest_date);

INSERT INTO alembic_version (version_num) VALUES ('1ad9f7f93530') RETURNING alembic_version.version_num;

COMMIT;

