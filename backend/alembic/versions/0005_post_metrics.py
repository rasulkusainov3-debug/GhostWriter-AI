"""Manual post performance metrics."""

from alembic import op

revision = "0005_post_metrics"
down_revision = "0004_scheduling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS post_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            generated_post_id UUID NOT NULL REFERENCES generated_posts(id) ON DELETE CASCADE,
            scheduled_post_id UUID REFERENCES scheduled_posts(id) ON DELETE SET NULL,
            platform TEXT NOT NULL,
            metric_date DATE NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            impressions INTEGER NOT NULL DEFAULT 0,
            reach INTEGER NOT NULL DEFAULT 0,
            views INTEGER NOT NULL DEFAULT 0,
            likes INTEGER NOT NULL DEFAULT 0,
            comments INTEGER NOT NULL DEFAULT 0,
            shares INTEGER NOT NULL DEFAULT 0,
            saves INTEGER NOT NULL DEFAULT 0,
            clicks INTEGER NOT NULL DEFAULT 0,
            reactions INTEGER NOT NULL DEFAULT 0,
            engagement_rate REAL NOT NULL DEFAULT 0,
            raw_metrics JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_metrics_user_date ON post_metrics (user_id, metric_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_metrics_generated_post ON post_metrics (generated_post_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_metrics_scheduled_post ON post_metrics (scheduled_post_id)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_post_metrics_manual_post_platform_date
        ON post_metrics (user_id, generated_post_id, platform, metric_date, source)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = 'trg_post_metrics_updated'
            ) THEN
                CREATE TRIGGER trg_post_metrics_updated
                    BEFORE UPDATE ON post_metrics
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_post_metrics_updated ON post_metrics")
    op.execute("DROP INDEX IF EXISTS uq_post_metrics_manual_post_platform_date")
    op.execute("DROP INDEX IF EXISTS ix_post_metrics_scheduled_post")
    op.execute("DROP INDEX IF EXISTS ix_post_metrics_generated_post")
    op.execute("DROP INDEX IF EXISTS ix_post_metrics_user_date")
    op.execute("DROP TABLE IF EXISTS post_metrics")
