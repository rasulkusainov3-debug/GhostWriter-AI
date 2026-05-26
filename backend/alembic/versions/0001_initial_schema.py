"""Initial schema from provided schema.sql."""

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    i = 0
    quote: str | None = None
    dollar_quote: str | None = None
    line_comment = False
    block_comment = False
    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if line_comment:
            current.append(char)
            if char == "\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                current.append(next_char)
                block_comment = False
                i += 2
            else:
                i += 1
            continue

        if quote:
            current.append(char)
            if char == quote and next_char == quote:
                current.append(next_char)
                i += 2
                continue
            if char == quote:
                quote = None
            i += 1
            continue

        if dollar_quote:
            if sql.startswith(dollar_quote, i):
                current.append(dollar_quote)
                i += len(dollar_quote)
                dollar_quote = None
            else:
                current.append(char)
                i += 1
            continue

        if char == "-" and next_char == "-":
            current.extend([char, next_char])
            line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            current.extend([char, next_char])
            block_comment = True
            i += 2
            continue

        if char in {"'", '"'}:
            current.append(char)
            quote = char
            i += 1
            continue

        if char == "$":
            end = sql.find("$", i + 1)
            if end != -1:
                tag = sql[i : end + 1]
                if tag == "$$" or tag[1:-1].replace("_", "").isalnum():
                    current.append(tag)
                    dollar_quote = tag
                    i = end + 1
                    continue

        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue

        current.append(char)
        i += 1

    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def upgrade() -> None:
    bind = op.get_bind()
    if bind.execute(text("SELECT to_regclass('public.users')")).scalar():
        return
    schema_path = Path(__file__).parents[2] / "app" / "db" / "schema.sql"
    for statement in _split_sql_statements(schema_path.read_text(encoding="utf-8")):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS user_posts_dashboard")
    op.execute("DROP VIEW IF EXISTS active_trends")
    op.execute("DROP TABLE IF EXISTS generation_runs")
    op.execute("DROP TABLE IF EXISTS post_assets")
    op.execute("DROP TABLE IF EXISTS generated_posts")
    op.execute("DROP TABLE IF EXISTS content_plan_items")
    op.execute("DROP TABLE IF EXISTS content_plans")
    op.execute("DROP TABLE IF EXISTS trend_sources")
    op.execute("DROP TABLE IF EXISTS trends")
    op.execute("DROP TABLE IF EXISTS trend_runs")
    op.execute("DROP TABLE IF EXISTS raw_posts")
    op.execute("DROP TABLE IF EXISTS interview_sessions")
    op.execute("DROP TABLE IF EXISTS user_profiles")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_trends()")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
