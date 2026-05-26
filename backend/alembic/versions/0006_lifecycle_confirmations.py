"""Lifecycle profile confirmation fields."""

from alembic import op

revision = "0006_lifecycle_confirmations"
down_revision = "0005_post_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS profile_confirmation_status TEXT NOT NULL DEFAULT 'draft'")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS audience_confirmation_status TEXT NOT NULL DEFAULT 'draft'")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS profile_confirmed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS audience_confirmed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS lifecycle_notes JSONB NOT NULL DEFAULT '{}'")
    op.execute(
        """
        UPDATE user_profiles
        SET profile_confirmation_status = 'needs_confirmation'
        WHERE profile_confirmation_status = 'draft'
          AND (
            NULLIF(TRIM(COALESCE(niche, '')), '') IS NOT NULL
            OR NULLIF(TRIM(COALESCE(profession, '')), '') IS NOT NULL
            OR NULLIF(TRIM(COALESCE(goal, '')), '') IS NOT NULL
            OR NULLIF(TRIM(COALESCE(tone, '')), '') IS NOT NULL
            OR NULLIF(TRIM(COALESCE(avoid, '')), '') IS NOT NULL
            OR jsonb_array_length(COALESCE(platforms, '[]'::jsonb)) > 0
            OR jsonb_array_length(COALESCE(user_values, '[]'::jsonb)) > 0
          )
        """
    )
    op.execute(
        """
        UPDATE user_profiles
        SET audience_confirmation_status = 'needs_confirmation'
        WHERE audience_confirmation_status = 'draft'
          AND NULLIF(TRIM(COALESCE(audience, '')), '') IS NOT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_user_profiles_profile_confirmation_status'
            ) THEN
                ALTER TABLE user_profiles
                ADD CONSTRAINT chk_user_profiles_profile_confirmation_status
                CHECK (profile_confirmation_status IN ('draft', 'needs_confirmation', 'confirmed'));
            END IF;
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_user_profiles_audience_confirmation_status'
            ) THEN
                ALTER TABLE user_profiles
                ADD CONSTRAINT chk_user_profiles_audience_confirmation_status
                CHECK (audience_confirmation_status IN ('draft', 'needs_confirmation', 'confirmed'));
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_profiles DROP CONSTRAINT IF EXISTS chk_user_profiles_audience_confirmation_status")
    op.execute("ALTER TABLE user_profiles DROP CONSTRAINT IF EXISTS chk_user_profiles_profile_confirmation_status")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS lifecycle_notes")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS audience_confirmed_at")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS profile_confirmed_at")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS audience_confirmation_status")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS profile_confirmation_status")
