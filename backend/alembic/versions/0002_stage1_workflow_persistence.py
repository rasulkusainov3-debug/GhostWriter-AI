"""Stage 1 workflow persistence and user-owned trends."""

from alembic import op

revision = "0002_stage1_workflow_persistence"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trend_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'running',
            input_profile_snapshot JSONB NOT NULL DEFAULT '{}',
            queries_used JSONB NOT NULL DEFAULT '[]',
            raw_posts_found INTEGER NOT NULL DEFAULT 0,
            trends_found INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMPTZ,
            error_message TEXT
        )
        """
    )
    op.execute("ALTER TABLE trends ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE trends ADD COLUMN IF NOT EXISTS trend_run_id UUID REFERENCES trend_runs(id) ON DELETE SET NULL")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trend_sources (
            id BIGSERIAL PRIMARY KEY,
            trend_id BIGINT NOT NULL REFERENCES trends(id) ON DELETE CASCADE,
            raw_post_id BIGINT NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
            relevance_score REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_trend_source UNIQUE (trend_id, raw_post_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            run_type TEXT NOT NULL,
            provider TEXT,
            agent_name TEXT,
            input_payload JSONB NOT NULL DEFAULT '{}',
            output_payload JSONB NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'completed',
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_trend_runs_user_started ON trend_runs (user_id, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trends_user_active ON trends (user_id, expires_at, final_score DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trends_run ON trends (trend_run_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trend_sources_trend ON trend_sources (trend_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trend_sources_raw_post ON trend_sources (raw_post_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_generation_runs_user_created ON generation_runs (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_generation_runs_user_type ON generation_runs (user_id, run_type, created_at DESC)")
    op.execute("DROP VIEW IF EXISTS active_trends")
    op.execute(
        """
        CREATE OR REPLACE VIEW active_trends AS
        SELECT *
        FROM trends
        WHERE expires_at > NOW()
        ORDER BY final_score DESC
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS active_trends")
    op.execute("DROP TABLE IF EXISTS generation_runs")
    op.execute("DROP TABLE IF EXISTS trend_sources")
    op.execute("DROP INDEX IF EXISTS ix_trends_run")
    op.execute("DROP INDEX IF EXISTS ix_trends_user_active")
    op.execute("ALTER TABLE trends DROP COLUMN IF EXISTS trend_run_id")
    op.execute("ALTER TABLE trends DROP COLUMN IF EXISTS user_id")
    op.execute("DROP TABLE IF EXISTS trend_runs")
    op.execute(
        """
        CREATE OR REPLACE VIEW active_trends AS
        SELECT *
        FROM trends
        WHERE expires_at > NOW()
        ORDER BY final_score DESC
        """
    )
