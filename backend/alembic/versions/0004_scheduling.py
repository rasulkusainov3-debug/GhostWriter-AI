"""Scheduling and manual social account persistence."""

from alembic import op

revision = "0004_scheduling"
down_revision = "0003_post_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS social_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            display_name TEXT NOT NULL,
            external_account_id TEXT,
            account_url TEXT,
            connection_status TEXT NOT NULL DEFAULT 'manual',
            scopes JSONB NOT NULL DEFAULT '[]',
            token_ref TEXT,
            token_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            generated_post_id UUID NOT NULL REFERENCES generated_posts(id) ON DELETE CASCADE,
            social_account_id UUID REFERENCES social_accounts(id) ON DELETE SET NULL,
            selected_asset_id UUID REFERENCES post_assets(id) ON DELETE SET NULL,
            platform TEXT NOT NULL,
            scheduled_for TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled',
            payload JSONB NOT NULL DEFAULT '{}',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TIMESTAMPTZ,
            published_at TIMESTAMPTZ,
            external_post_id TEXT,
            external_post_url TEXT,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_social_accounts_user_platform ON social_accounts (user_id, platform)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scheduled_posts_user_for ON scheduled_posts (user_id, scheduled_for DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scheduled_posts_status_for ON scheduled_posts (status, scheduled_for)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scheduled_posts_generated_post ON scheduled_posts (generated_post_id)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_scheduled_posts_active_post_platform
        ON scheduled_posts (generated_post_id, platform)
        WHERE status IN ('scheduled', 'publishing')
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = 'trg_social_accounts_updated'
            ) THEN
                CREATE TRIGGER trg_social_accounts_updated
                    BEFORE UPDATE ON social_accounts
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            END IF;
            IF NOT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = 'trg_scheduled_posts_updated'
            ) THEN
                CREATE TRIGGER trg_scheduled_posts_updated
                    BEFORE UPDATE ON scheduled_posts
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_scheduled_posts_updated ON scheduled_posts")
    op.execute("DROP TRIGGER IF EXISTS trg_social_accounts_updated ON social_accounts")
    op.execute("DROP INDEX IF EXISTS uq_scheduled_posts_active_post_platform")
    op.execute("DROP INDEX IF EXISTS ix_scheduled_posts_generated_post")
    op.execute("DROP INDEX IF EXISTS ix_scheduled_posts_status_for")
    op.execute("DROP INDEX IF EXISTS ix_scheduled_posts_user_for")
    op.execute("DROP INDEX IF EXISTS ix_social_accounts_user_platform")
    op.execute("DROP TABLE IF EXISTS scheduled_posts")
    op.execute("DROP TABLE IF EXISTS social_accounts")
