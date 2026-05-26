"""Post assets for visual ideas and image metadata."""

from alembic import op

revision = "0003_post_assets"
down_revision = "0002_stage1_workflow_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS post_assets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            post_id UUID NOT NULL REFERENCES generated_posts(id) ON DELETE CASCADE,
            asset_type TEXT NOT NULL DEFAULT 'image',
            provider TEXT,
            status TEXT NOT NULL DEFAULT 'idea',
            image_prompt TEXT,
            search_query TEXT,
            preview_url TEXT,
            source_url TEXT,
            author TEXT,
            alt_text TEXT,
            local_path TEXT,
            metadata JSONB NOT NULL DEFAULT '{}',
            is_selected BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_assets_user_created ON post_assets (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_assets_post_selected ON post_assets (post_id, is_selected)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_post_assets_one_selected
        ON post_assets (post_id)
        WHERE is_selected = true
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = 'trg_post_assets_updated'
            ) THEN
                CREATE TRIGGER trg_post_assets_updated
                    BEFORE UPDATE ON post_assets
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_post_assets_updated ON post_assets")
    op.execute("DROP INDEX IF EXISTS uq_post_assets_one_selected")
    op.execute("DROP INDEX IF EXISTS ix_post_assets_post_selected")
    op.execute("DROP INDEX IF EXISTS ix_post_assets_user_created")
    op.execute("DROP TABLE IF EXISTS post_assets")
