-- ============================================================
-- Supabase Schema — Canadian Immigration Pain Points
-- ============================================================
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- or via psql against your Supabase Postgres connection string.
--
-- Free tier: https://supabase.com/pricing
--   • 500 MB database space
--   • 2 free projects
--   • Unlimited API requests
--   • Auto-generated REST + GraphQL API
-- ============================================================

-- Enable UUID extension (available by default on Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ------------------------------------------------------------
-- scrape_runs: one row per pipeline execution
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id                TEXT        PRIMARY KEY,
    started_at            TIMESTAMPTZ NOT NULL,
    completed_at          TIMESTAMPTZ,
    sections_scraped      INTEGER     NOT NULL DEFAULT 0,
    total_threads         INTEGER     NOT NULL DEFAULT 0,
    total_posts           INTEGER     NOT NULL DEFAULT 0,
    total_pain_points     INTEGER     NOT NULL DEFAULT 0,
    cross_section_themes  JSONB       DEFAULT '[]'::jsonb,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scrape_runs_started_at
    ON scrape_runs (started_at DESC);


-- ------------------------------------------------------------
-- forum_sections: metadata per scraped forum section
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forum_sections (
    section_id              TEXT        PRIMARY KEY,
    run_id                  TEXT        NOT NULL REFERENCES scrape_runs(run_id) ON DELETE CASCADE,
    forum_name              TEXT        NOT NULL,
    forum_slug              TEXT        NOT NULL,
    forum_url               TEXT        NOT NULL,
    description             TEXT,
    threads_scraped         INTEGER     NOT NULL DEFAULT 0,
    posts_scraped           INTEGER     NOT NULL DEFAULT 0,
    pain_points_extracted   INTEGER     NOT NULL DEFAULT 0,
    severity_breakdown      JSONB       DEFAULT '{}'::jsonb,
    category_breakdown      JSONB       DEFAULT '{}'::jsonb,
    top_categories          TEXT[]      DEFAULT '{}',
    generated_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forum_sections_run_id
    ON forum_sections (run_id);
CREATE INDEX IF NOT EXISTS idx_forum_sections_slug
    ON forum_sections (forum_slug);


-- ------------------------------------------------------------
-- pain_points: individual pain point with solutions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pain_points (
    pain_point_id       TEXT        PRIMARY KEY,
    run_id              TEXT        NOT NULL REFERENCES scrape_runs(run_id) ON DELETE CASCADE,
    forum_slug          TEXT        NOT NULL,
    thread_id           TEXT        NOT NULL,
    thread_title        TEXT        NOT NULL,
    thread_url          TEXT        NOT NULL,

    -- Classification
    title               TEXT        NOT NULL,
    description         TEXT        NOT NULL,
    category            TEXT        NOT NULL,   -- matches Category enum
    severity            TEXT        NOT NULL,   -- critical | high | medium | low
    frequency_signal    TEXT        NOT NULL,   -- isolated | occasional | frequent | widespread

    -- Affected groups (Postgres native arrays → easy filtering)
    affected_user_types TEXT[]      DEFAULT '{}',
    affected_stages     TEXT[]      DEFAULT '{}',
    evidence_quotes     TEXT[]      DEFAULT '{}',
    tags                TEXT[]      DEFAULT '{}',

    -- Solutions stored as JSONB for full flexibility
    solutions           JSONB       NOT NULL DEFAULT '[]'::jsonb,

    extracted_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_pain_points_run_id
    ON pain_points (run_id);
CREATE INDEX IF NOT EXISTS idx_pain_points_forum_slug
    ON pain_points (forum_slug);
CREATE INDEX IF NOT EXISTS idx_pain_points_severity
    ON pain_points (severity);
CREATE INDEX IF NOT EXISTS idx_pain_points_category
    ON pain_points (category);
CREATE INDEX IF NOT EXISTS idx_pain_points_extracted_at
    ON pain_points (extracted_at DESC);

-- GIN index for full-text search on title + description
CREATE INDEX IF NOT EXISTS idx_pain_points_fts
    ON pain_points
    USING gin(to_tsvector('english', title || ' ' || description));

-- GIN index for array containment queries (e.g. "find all FSW pain points")
CREATE INDEX IF NOT EXISTS idx_pain_points_user_types_gin
    ON pain_points USING gin (affected_user_types);
CREATE INDEX IF NOT EXISTS idx_pain_points_tags_gin
    ON pain_points USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_pain_points_solutions_gin
    ON pain_points USING gin (solutions);


-- ------------------------------------------------------------
-- Useful views
-- ------------------------------------------------------------

-- Top pain points by severity and frequency
CREATE OR REPLACE VIEW v_top_pain_points AS
SELECT
    pain_point_id,
    forum_slug,
    title,
    category,
    severity,
    frequency_signal,
    jsonb_array_length(solutions) AS solution_count,
    extracted_at
FROM pain_points
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high'      THEN 2
        WHEN 'medium'    THEN 3
        WHEN 'low'       THEN 4
    END,
    CASE frequency_signal
        WHEN 'widespread' THEN 1
        WHEN 'frequent'   THEN 2
        WHEN 'occasional' THEN 3
        WHEN 'isolated'   THEN 4
    END;


-- Aggregated stats per category
CREATE OR REPLACE VIEW v_category_stats AS
SELECT
    category,
    COUNT(*) AS total_pain_points,
    COUNT(*) FILTER (WHERE severity = 'critical') AS critical_count,
    COUNT(*) FILTER (WHERE severity = 'high')     AS high_count,
    COUNT(*) FILTER (WHERE severity = 'medium')   AS medium_count,
    COUNT(*) FILTER (WHERE severity = 'low')      AS low_count
FROM pain_points
GROUP BY category
ORDER BY total_pain_points DESC;


-- Solutions with no official answer (needs attention)
CREATE OR REPLACE VIEW v_unsolved_pain_points AS
SELECT
    pain_point_id,
    forum_slug,
    title,
    severity,
    category,
    solutions
FROM pain_points
WHERE
    -- No solution has status = 'official'
    NOT EXISTS (
        SELECT 1
        FROM jsonb_array_elements(solutions) AS sol
        WHERE sol->>'status' = 'official'
    )
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high'      THEN 2
        WHEN 'medium'    THEN 3
        WHEN 'low'       THEN 4
    END;


-- ------------------------------------------------------------
-- Row-Level Security (RLS) — recommended for production
-- ------------------------------------------------------------
-- Enable RLS and restrict reads to authenticated users, writes
-- to service_role only (your scraper uses the service_role key).

ALTER TABLE scrape_runs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE forum_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE pain_points    ENABLE ROW LEVEL SECURITY;

-- Allow public read access (remove this if you want private data)
CREATE POLICY "Allow public read on scrape_runs"
    ON scrape_runs FOR SELECT USING (true);

CREATE POLICY "Allow public read on forum_sections"
    ON forum_sections FOR SELECT USING (true);

CREATE POLICY "Allow public read on pain_points"
    ON pain_points FOR SELECT USING (true);

-- service_role bypasses RLS by default — writes work without extra policies.
