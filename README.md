# GhostWriter AI

Initial full-stack MVP for AI-assisted social media profile analysis, audience analysis, content planning, and post generation.

## What Was Inspected

- `social_analyzer/` legacy AI logic and outputs:
  - onboarding questions: `onboarding/dialog.py`
  - source parsers: `parsers/*`
  - trend analysis: `analyzer/trend_analyzer.py`
  - SQLite/export layer: `storage/database.py`, `storage/exporter.py`
  - Agent 2 planner/generator: `agent2/planner/content_planner.py`, `agent2/generator/*`, `agent2/platforms/adapter.py`
  - saved output examples: `data/user_profile_export.json`, `data/trends_export.json`, `data/content_plan.json`, `data/generated_posts.json`, `data/merged_posts.json`
- Provided PostgreSQL schema: `schema.sql`
- Provided ERD: `db_schema_erd.html`
- Website plan: `Общий план веб сайта.docx`
- UI sketch: copied to `frontend/public/ui-sketch.jpg`

## Architecture

- `backend/`: FastAPI, async SQLAlchemy, Pydantic v2, Alembic.
- `frontend/`: React, TypeScript, Vite, Tailwind CSS.
- `db`: PostgreSQL with pgvector through `pgvector/pgvector:pg16`.
- `social_analyzer` remains an external/internal dependency mounted read-only in Docker.
- `backend/app/services/social_analyzer_adapter.py` is the integration boundary for legacy model functions.

## Database

The MVP uses the provided 8-table schema:

- `users`
- `user_profiles`
- `interview_sessions`
- `raw_posts`
- `trends`
- `content_plans`
- `content_plan_items`
- `generated_posts`

The schema keeps:

- `JSONB` fields for flexible model outputs.
- `VECTOR(384)` for future semantic search.
- `active_trends` view.
- `cleanup_expired_trends()` function.
- timestamp triggers.
- `SET NULL` for trend links used by content plan items and generated posts.

## Run With Docker

From `D:/AIAs/GhostWriterAi`:

```bash
copy .env.example .env
docker compose up --build
```

Before starting Docker, edit `.env` locally and replace placeholder values:

- `OPENAI_API_KEY`
- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`
- optional `REDIS_URL`

Do not commit `.env`. The frontend must only use `VITE_API_URL`; model provider keys such as `OPENAI_API_KEY` are backend-only.

Then open:

- Frontend: `http://localhost:5173`
- Backend API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Backend API Areas

Implemented route groups:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/onboarding/start`
- `POST /api/onboarding/{session_id}/answers`
- `POST /api/onboarding/{session_id}/finish`
- `GET/PATCH /api/profiles/me`
- `POST /api/social-parser/links`
- `POST /api/social-parser/run`
- `GET /api/social-parser/raw-posts`
- `GET /api/trends`
- `POST /api/trends/cleanup`
- `POST /api/content-plans`
- `GET /api/content-plans`
- `GET /api/content-plans/{plan_id}`
- `PATCH /api/content-plans/items/{item_id}`
- `POST /api/generated-posts/from-plan/{plan_id}`
- `GET/PATCH /api/generated-posts`
- `POST /api/chat`
- `GET /api/analytics/profile`
- `GET /api/analytics/social`
- `GET /api/analytics/trends`

## Frontend Pages

- Landing page
- Auth page
- Onboarding/interview page
- AI chat page
- Main menu/dashboard
- History page
- Profile page
- Profile analytics page
- Social media analytics page
- Content plans list
- Content plan detail/editor
- Generated posts editor

## Implemented

- Full project scaffold inside `GhostWriterAi`.
- PostgreSQL schema integration from provided `schema.sql`.
- Docker Compose for frontend, backend, PostgreSQL/pgvector.
- Auth with password hashing and JWT bearer token.
- Onboarding sessions persisted to `interview_sessions`.
- Profile creation/update in `user_profiles`.
- Content plan creation using existing `social_analyzer.agent2.planner.content_planner.build_content_plan`.
- Post generation using existing template generator, optional LLM polisher hook, and platform adapter.
- Analytics endpoints from MVP tables.
- Frontend workflow based on the website plan and sketch.

## Explicit TODO

- Port or bridge `social_analyzer.analyzer.trend_analyzer` so it reads/writes PostgreSQL instead of legacy SQLite.
- Replace chat placeholder response with a real LLM/tool workflow.
- Add optional tables after MVP pressure is clear:
  - `audience_profiles`
  - `post_assets`
  - `generation_runs`
  - `post_versions`
  - `content_plan_versions`
- Add asset upload/storage and image generation/download flow.
- Add background jobs for parser/trend runs.
- Add tests and stricter status transition validation.
- Add production OAuth/social network integrations.
