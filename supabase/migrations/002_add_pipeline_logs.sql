-- Create table for pipeline logs captured by workflow phases
CREATE TABLE IF NOT EXISTS pipeline_logs (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL,
    phase VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    level VARCHAR(16) NOT NULL,
    logger_name VARCHAR(256) NOT NULL,
    module VARCHAR(256),
    function VARCHAR(256),
    line INTEGER,
    message TEXT NOT NULL,
    extra JSONB
);

CREATE INDEX IF NOT EXISTS ix_pipeline_logs_run_phase_time
    ON pipeline_logs (run_id, phase, timestamp);

CREATE INDEX IF NOT EXISTS ix_pipeline_logs_level
    ON pipeline_logs (level);
