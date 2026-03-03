-- Metrics tracking tables for observability dashboard
-- Created: 2026-03-03

-- Request-level metrics for each agent invocation
CREATE TABLE IF NOT EXISTS request_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255),
    user_id VARCHAR(255),
    agent_name VARCHAR(100) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    duration_ms INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'error', 'timeout')),
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Daily aggregated statistics for each agent
CREATE TABLE IF NOT EXISTS agent_daily_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    total_requests INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    timeout_count INTEGER DEFAULT 0,
    avg_duration_ms NUMERIC(10, 2) DEFAULT 0,
    total_input_tokens BIGINT DEFAULT 0,
    total_output_tokens BIGINT DEFAULT 0,
    p95_duration_ms INTEGER,
    p99_duration_ms INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(date, agent_name)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_request_metrics_created_at ON request_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_metrics_agent_name ON request_metrics(agent_name);
CREATE INDEX IF NOT EXISTS idx_request_metrics_session_id ON request_metrics(session_id);
CREATE INDEX IF NOT EXISTS idx_request_metrics_user_id ON request_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_request_metrics_status ON request_metrics(status);
CREATE INDEX IF NOT EXISTS idx_request_metrics_created_at_agent ON request_metrics(created_at DESC, agent_name);

CREATE INDEX IF NOT EXISTS idx_agent_daily_stats_date ON agent_daily_stats(date DESC);
CREATE INDEX IF NOT EXISTS idx_agent_daily_stats_agent_name ON agent_daily_stats(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_daily_stats_date_agent ON agent_daily_stats(date DESC, agent_name);

-- Function to update daily stats (triggered by insert/update on request_metrics)
CREATE OR REPLACE FUNCTION update_agent_daily_stats()
RETURNS TRIGGER AS $$
DECLARE
    v_avg_duration NUMERIC(10, 2);
    v_p95_duration INTEGER;
    v_p99_duration INTEGER;
BEGIN
    -- Calculate statistics for the day
    SELECT
        AVG(duration_ms)::NUMERIC(10, 2),
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::INTEGER,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms)::INTEGER
    INTO v_avg_duration, v_p95_duration, v_p99_duration
    FROM request_metrics
    WHERE agent_name = NEW.agent_name
        AND DATE(created_at) = DATE(NEW.created_at);

    -- Upsert daily stats
    INSERT INTO agent_daily_stats (
        date,
        agent_name,
        total_requests,
        success_count,
        error_count,
        timeout_count,
        avg_duration_ms,
        total_input_tokens,
        total_output_tokens,
        p95_duration_ms,
        p99_duration_ms,
        updated_at
    )
    SELECT
        DATE(NEW.created_at),
        NEW.agent_name,
        COUNT(*),
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END),
        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END),
        SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END),
        v_avg_duration,
        COALESCE(SUM(input_tokens), 0),
        COALESCE(SUM(output_tokens), 0),
        v_p95_duration,
        v_p99_duration,
        NOW()
    FROM request_metrics
    WHERE agent_name = NEW.agent_name
        AND DATE(created_at) = DATE(NEW.created_at)
    ON CONFLICT (date, agent_name) DO UPDATE SET
        total_requests = EXCLUDED.total_requests,
        success_count = EXCLUDED.success_count,
        error_count = EXCLUDED.error_count,
        timeout_count = EXCLUDED.timeout_count,
        avg_duration_ms = EXCLUDED.avg_duration_ms,
        total_input_tokens = EXCLUDED.total_input_tokens,
        total_output_tokens = EXCLUDED.total_output_tokens,
        p95_duration_ms = EXCLUDED.p95_duration_ms,
        p99_duration_ms = EXCLUDED.p99_duration_ms,
        updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update daily stats
DROP TRIGGER IF EXISTS trigger_update_agent_daily_stats ON request_metrics;
CREATE TRIGGER trigger_update_agent_daily_stats
    AFTER INSERT ON request_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_daily_stats();

-- Enable Row Level Security (optional - comment out if not needed)
-- ALTER TABLE request_metrics ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE agent_daily_stats ENABLE ROW LEVEL SECURITY;

-- Comments for documentation
COMMENT ON TABLE request_metrics IS 'Individual request-level metrics for agent observability';
COMMENT ON TABLE agent_daily_stats IS 'Daily aggregated statistics for each agent';
COMMENT ON COLUMN request_metrics.metadata IS 'Additional context like tool usage, langsmith run_id, etc.';
COMMENT ON COLUMN agent_daily_stats.p95_duration_ms IS '95th percentile of request duration for the day';
COMMENT ON COLUMN agent_daily_stats.p99_duration_ms IS '99th percentile of request duration for the day';
