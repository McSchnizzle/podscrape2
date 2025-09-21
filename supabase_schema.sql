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

CREATE TABLE topics (
    id SERIAL NOT NULL,
    slug VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    voice_id VARCHAR(255),
    voice_settings JSONB,
    instructions_md TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    last_generated_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT uq_topics_slug UNIQUE (slug),
    PRIMARY KEY (id)
);

CREATE INDEX ix_topics_active ON topics (is_active);
CREATE INDEX ix_topics_sort ON topics (sort_order);

CREATE TABLE topic_instruction_versions (
    id SERIAL NOT NULL,
    topic_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    instructions_md TEXT NOT NULL,
    change_note TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_by VARCHAR(255),
    CONSTRAINT uq_topic_instruction_version UNIQUE (topic_id, version),
    PRIMARY KEY (id)
);

CREATE INDEX ix_topic_instruction_topic ON topic_instruction_versions (topic_id);

CREATE TABLE pipeline_runs (
    id VARCHAR(64) NOT NULL,
    workflow_run_id BIGINT,
    workflow_name VARCHAR(255),
    trigger VARCHAR(128),
    status VARCHAR(64),
    conclusion VARCHAR(64),
    started_at TIMESTAMP WITHOUT TIME ZONE,
    finished_at TIMESTAMP WITHOUT TIME ZONE,
    phase JSONB,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);

CREATE INDEX ix_pipeline_runs_started ON pipeline_runs (started_at);
CREATE INDEX ix_pipeline_runs_workflow ON pipeline_runs (workflow_run_id);

CREATE TABLE digest_episode_links (
    id SERIAL NOT NULL,
    digest_id INTEGER NOT NULL,
    episode_id INTEGER NOT NULL,
    topic VARCHAR(256),
    score DOUBLE PRECISION,
    position INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT uq_digest_episode UNIQUE (digest_id, episode_id),
    PRIMARY KEY (id)
);

CREATE INDEX ix_digest_episode_digest ON digest_episode_links (digest_id);
CREATE INDEX ix_digest_episode_episode ON digest_episode_links (episode_id);

INSERT INTO alembic_version (version_num) VALUES ('5f1c9f0c9e4b') RETURNING alembic_version.version_num;

COMMIT;
