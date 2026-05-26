-- ============================================================
--  Social Media Analyzer — PostgreSQL DDL
--  Три агента: Анализатор → Планировщик → Генератор постов
--
--  Запуск:
--    psql -U postgres -d your_db -f schema.sql
--
--  Зависимости:
--    pgvector  — для векторных эмбеддингов (поиск похожих трендов)
--    Установка: CREATE EXTENSION IF NOT EXISTS vector;
-- ============================================================

-- Расширения
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- VECTOR тип для эмбеддингов

-- ============================================================
--  1. USERS — аккаунты пользователей
-- ============================================================
CREATE TABLE users (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email          TEXT        NOT NULL UNIQUE,
    password_hash  TEXT,                          -- NULL если вход через OAuth
    plan           TEXT        NOT NULL DEFAULT 'free',  -- free / pro / team
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  users              IS 'Аккаунты пользователей системы';
COMMENT ON COLUMN users.plan         IS 'Тарифный план: free, pro, team';
COMMENT ON COLUMN users.password_hash IS 'NULL при OAuth-авторизации';

-- ============================================================
--  2. USER_PROFILES — цифровой портрет (образ) пользователя
--     Заполняется либо через онбординг-диалог,
--     либо через анализ соцсетей пользователя.
--     Агент 1 пишет, Агент 2 и 3 читают.
-- ============================================================
CREATE TABLE user_profiles (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Базовая информация
    name         TEXT,
    niche        TEXT,        -- IT, маркетинг, финансы, карьера...
    profession   TEXT,        -- Python-разработчик, SMM-менеджер...
    goal         TEXT,        -- повысить зарплату, найти клиентов...

    -- Tone of voice и аудитория
    tone         TEXT,        -- экспертный, дружелюбный, провокационный...
    audience     TEXT,        -- HR IT-компаний, начинающие разработчики...
    avoid        TEXT,        -- что НЕ публиковать

    -- Гибкие поля (JSON)
    user_values  JSONB        NOT NULL DEFAULT '[]',   -- ["честность","рост"]
    platforms    JSONB        NOT NULL DEFAULT '[]',   -- ["LinkedIn","Telegram"]
    raw_answers  JSONB        NOT NULL DEFAULT '{}',   -- полные ответы онбординга

    profile_confirmation_status  TEXT        NOT NULL DEFAULT 'draft',
    audience_confirmation_status TEXT        NOT NULL DEFAULT 'draft',
    profile_confirmed_at         TIMESTAMPTZ,
    audience_confirmed_at        TIMESTAMPTZ,
    lifecycle_notes              JSONB       NOT NULL DEFAULT '{}',

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_profile UNIQUE (user_id),  -- один профиль на юзера
    CONSTRAINT chk_user_profiles_profile_confirmation_status
        CHECK (profile_confirmation_status IN ('draft', 'needs_confirmation', 'confirmed')),
    CONSTRAINT chk_user_profiles_audience_confirmation_status
        CHECK (audience_confirmation_status IN ('draft', 'needs_confirmation', 'confirmed'))
);

COMMENT ON TABLE  user_profiles             IS 'Цифровой портрет пользователя — читают все три агента';
COMMENT ON COLUMN user_profiles.user_values IS 'JSON-массив ценностей: ["честность","рост"]';
COMMENT ON COLUMN user_profiles.platforms   IS 'JSON-массив платформ: ["LinkedIn","Telegram"]';
COMMENT ON COLUMN user_profiles.raw_answers IS 'Полные ответы из онбординг-диалога';

-- ============================================================
--  3. INTERVIEW_SESSIONS — сессии диалога с Агентом 1
--     Используется когда у пользователя нет соцсетей.
--     Агент ведёт диалог, собирает образ, формирует профиль.
-- ============================================================
CREATE TABLE interview_sessions (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    status      TEXT        NOT NULL DEFAULT 'in_progress',
                                     -- in_progress / completed / abandoned

    -- Весь диалог в одном JSONB-массиве
    -- Структура: [{"role":"agent","text":"..."},{"role":"user","text":"..."},...]
    dialogues   JSONB       NOT NULL DEFAULT '[]',

    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

COMMENT ON TABLE  interview_sessions          IS 'Диалог-интервью Агента 1 с пользователем без соцсетей';
COMMENT ON COLUMN interview_sessions.dialogues IS 'JSON-массив пар вопрос-ответ: [{role, text, ts}]';
COMMENT ON COLUMN interview_sessions.status    IS 'in_progress | completed | abandoned';

-- ============================================================
--  4. RAW_POSTS — сырые посты из соцсетей
--     Агент 1 пишет (парсеры: RSS, DDG, Reddit, YouTube, Google Trends).
--     Агент 1 читает для анализа трендов (TF-IDF + KMeans).
--     TTL не фиксирован — чистка по collected_at через cron.
-- ============================================================
-- ============================================================
--  3A. TREND_RUNS - user-owned parser/analyzer runs
-- ============================================================
CREATE TABLE trend_runs (
    id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status                 TEXT        NOT NULL DEFAULT 'running',
    input_profile_snapshot JSONB       NOT NULL DEFAULT '{}',
    queries_used           JSONB       NOT NULL DEFAULT '[]',
    raw_posts_found        INTEGER     NOT NULL DEFAULT 0,
    trends_found           INTEGER     NOT NULL DEFAULT 0,
    started_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at            TIMESTAMPTZ,
    error_message          TEXT
);

COMMENT ON TABLE trend_runs IS 'User-owned trend search/parser/analyzer runs';

CREATE TABLE raw_posts (
    id               BIGSERIAL   PRIMARY KEY,
    user_id          UUID        REFERENCES users(id) ON DELETE SET NULL,

    -- Источник и содержимое
    source           TEXT        NOT NULL,  -- reddit, rss, ddg, youtube, google_trends
    title            TEXT,
    content          TEXT,
    url              TEXT,
    media_type       TEXT        NOT NULL DEFAULT 'text',  -- text / video / image

    -- Метрики вовлечённости
    score            INTEGER     NOT NULL DEFAULT 0,  -- лайки / просмотры
    comments         INTEGER     NOT NULL DEFAULT 0,
    engagement_rate  REAL        NOT NULL DEFAULT 0,  -- (likes + comments*3) / views * 100

    -- Классификация
    niche            TEXT,  -- IT, маркетинг, карьера...
    platform_tags    JSONB  NOT NULL DEFAULT '[]',  -- доп. теги/хэштеги из поста

    -- Временны́е метки
    published_at     TIMESTAMPTZ,
    collected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Векторный эмбеддинг для семантического поиска похожих постов
    -- Заполняется отдельным процессом (sentence-transformers / OpenAI Embeddings)
    embedding        VECTOR(384)  -- 384-мерный вектор (all-MiniLM-L6-v2)
);

COMMENT ON TABLE  raw_posts           IS 'Сырые посты со всех источников — основа для анализа трендов';
COMMENT ON COLUMN raw_posts.embedding IS 'Вектор 384-dim (all-MiniLM-L6-v2) для семантического поиска';
COMMENT ON COLUMN raw_posts.media_type IS 'text | video | image';

-- ============================================================
--  5. TRENDS — выявленные тренды
--     Агент 1 пишет (TF-IDF + YAKE + KMeans + Google Trends).
--     Агент 2 читает для построения контент-плана.
--     Агент 3 читает для генерации постов.
--     TTL: expires_at — через 14 дней запись помечается устаревшей.
-- ============================================================
CREATE TABLE trends (
    id               BIGSERIAL   PRIMARY KEY,
    user_id          UUID        REFERENCES users(id) ON DELETE CASCADE,
    trend_run_id     UUID        REFERENCES trend_runs(id) ON DELETE SET NULL,

    source           TEXT        NOT NULL,  -- reddit, rss, ddg, youtube, mixed
    topic            TEXT        NOT NULL,  -- заголовок темы (топ-пост кластера)
    keywords         JSONB       NOT NULL DEFAULT '[]',  -- ["salary","linkedin",...]
    posts_count      INTEGER     NOT NULL DEFAULT 0,

    -- Данные Google Trends (заполняет google_trends_parser.py)
    google_score     REAL        NOT NULL DEFAULT 0,   -- средний интерес 0–100
    google_trend     TEXT        NOT NULL DEFAULT 'stable',  -- rising / stable
    final_score      REAL        NOT NULL DEFAULT 0,   -- взвешенный рейтинг

    -- YouTube инсайты (заполняет youtube_parser.py)
    youtube_insights JSONB       NOT NULL DEFAULT '{}',
    -- Структура: {best_format, avg_engagement_by_format, top_tags, best_posting_day}

    summary          TEXT,       -- краткое саммари темы (1-2 предложения)

    collected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at       TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '14 days',

    -- Вектор темы для семантического поиска похожих трендов
    embedding        VECTOR(384)
);

COMMENT ON TABLE  trends                  IS 'Тренды недели — живут 14 дней, читают Агент 2 и 3';
COMMENT ON COLUMN trends.google_score     IS 'Средний интерес в Google Trends (0–100)';
COMMENT ON COLUMN trends.final_score      IS 'posts_count*0.6 + google_score*0.4 + rising_bonus';
COMMENT ON COLUMN trends.youtube_insights IS 'JSON: {best_format, avg_engagement, top_tags, best_day}';
COMMENT ON COLUMN trends.expires_at       IS 'Через 14 дней тренд помечается устаревшим';

-- ============================================================
--  6. CONTENT_PLANS — контент-планы на неделю
--     Агент 2 создаёт, пользователь просматривает и утверждает.
-- ============================================================
-- ============================================================
--  5A. TREND_SOURCES - link trends back to raw source posts
-- ============================================================
CREATE TABLE trend_sources (
    id              BIGSERIAL   PRIMARY KEY,
    trend_id        BIGINT      NOT NULL REFERENCES trends(id) ON DELETE CASCADE,
    raw_post_id     BIGINT      NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    relevance_score REAL        NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_trend_source UNIQUE (trend_id, raw_post_id)
);

COMMENT ON TABLE trend_sources IS 'Links saved trends to raw_posts used as evidence/source material';

CREATE TABLE content_plans (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    title       TEXT        NOT NULL DEFAULT 'Контент-план',
    week_start  DATE        NOT NULL,  -- понедельник недели плана
    status      TEXT        NOT NULL DEFAULT 'draft',
                                       -- draft / approved / active / archived

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  content_plans        IS 'Контент-планы — создаёт Агент 2, утверждает пользователь';
COMMENT ON COLUMN content_plans.status IS 'draft | approved | active | archived';

-- ============================================================
--  7. CONTENT_PLAN_ITEMS — строки контент-плана (слоты)
--     Каждый слот = один пост: дата, платформа, формат, идея.
--     Агент 2 пишет. Агент 3 читает и генерирует пост.
-- ============================================================
CREATE TABLE content_plan_items (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id        UUID        NOT NULL REFERENCES content_plans(id) ON DELETE CASCADE,
    trend_id       BIGINT      REFERENCES trends(id) ON DELETE SET NULL,

    platform       TEXT        NOT NULL,  -- LinkedIn, Telegram, Instagram
    format         TEXT        NOT NULL,  -- кейс, совет, история, список...
    post_idea      TEXT,                  -- краткая идея поста

    scheduled_date DATE        NOT NULL,
    scheduled_time TIME        NOT NULL DEFAULT '09:00',
    slot_order     INTEGER     NOT NULL DEFAULT 0,  -- порядок внутри дня

    status         TEXT        NOT NULL DEFAULT 'planned',
                                          -- planned / generating / generated / skipped

    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  content_plan_items        IS 'Слоты контент-плана — один слот = один будущий пост';
COMMENT ON COLUMN content_plan_items.status IS 'planned | generating | generated | skipped';

-- ============================================================
--  8. GENERATED_POSTS — сгенерированные посты
--     Агент 3 пишет. Пользователь просматривает и публикует.
-- ============================================================
CREATE TABLE generated_posts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_item_id  UUID        REFERENCES content_plan_items(id) ON DELETE SET NULL,
    trend_id      BIGINT      REFERENCES trends(id) ON DELETE SET NULL,

    platform      TEXT        NOT NULL,
    format        TEXT        NOT NULL,

    draft_text    TEXT        NOT NULL,  -- выход шаблонного генератора
    final_text    TEXT        NOT NULL,  -- после LLM-полировки

    -- Статус жизненного цикла
    status        TEXT        NOT NULL DEFAULT 'draft',
                                         -- draft / approved / scheduled / published / rejected

    -- Метаданные LLM и публикации
    llm_provider  TEXT,                  -- ollama, groq, gemini, template
    stats         JSONB       NOT NULL DEFAULT '{}',
    -- Структура: {chars, limit, used_pct, hashtags, fits}

    generated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at  TIMESTAMPTZ           -- NULL пока не опубликован
);

COMMENT ON TABLE  generated_posts             IS 'Готовые посты — Агент 3 пишет, пользователь публикует';
COMMENT ON COLUMN generated_posts.draft_text  IS 'Черновик из шаблонного генератора (без LLM)';
COMMENT ON COLUMN generated_posts.final_text  IS 'Финальный текст после LLM-полировки';
COMMENT ON COLUMN generated_posts.llm_provider IS 'Провайдер: ollama | groq | gemini | template';
COMMENT ON COLUMN generated_posts.status       IS 'draft | approved | scheduled | published | rejected';

-- ============================================================
--  8B. POST_ASSETS - visual ideas and image metadata for posts
-- ============================================================
CREATE TABLE post_assets (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id       UUID        NOT NULL REFERENCES generated_posts(id) ON DELETE CASCADE,
    asset_type    TEXT        NOT NULL DEFAULT 'image',
    provider      TEXT,
    status        TEXT        NOT NULL DEFAULT 'idea',
    image_prompt  TEXT,
    search_query  TEXT,
    preview_url   TEXT,
    source_url    TEXT,
    author        TEXT,
    alt_text      TEXT,
    local_path    TEXT,
    metadata      JSONB       NOT NULL DEFAULT '{}',
    is_selected   BOOLEAN     NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE post_assets IS 'Visual ideas and remote image metadata for generated posts';

-- ============================================================
--  8C. SOCIAL_ACCOUNTS - manual/future connected destinations
-- ============================================================
CREATE TABLE social_accounts (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform            TEXT        NOT NULL,
    display_name        TEXT        NOT NULL,
    external_account_id TEXT,
    account_url         TEXT,
    connection_status   TEXT        NOT NULL DEFAULT 'manual',
    scopes              JSONB       NOT NULL DEFAULT '[]',
    token_ref           TEXT,
    token_metadata      JSONB       NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE social_accounts IS 'Manual social destinations now; token_ref placeholder for future OAuth/secret storage';

-- ============================================================
--  8D. SCHEDULED_POSTS - queue-ready publishing schedule
-- ============================================================
CREATE TABLE scheduled_posts (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generated_post_id  UUID        NOT NULL REFERENCES generated_posts(id) ON DELETE CASCADE,
    social_account_id  UUID        REFERENCES social_accounts(id) ON DELETE SET NULL,
    selected_asset_id  UUID        REFERENCES post_assets(id) ON DELETE SET NULL,
    platform           TEXT        NOT NULL,
    scheduled_for      TIMESTAMPTZ NOT NULL,
    status             TEXT        NOT NULL DEFAULT 'scheduled',
    payload            JSONB       NOT NULL DEFAULT '{}',
    attempt_count      INTEGER     NOT NULL DEFAULT 0,
    last_attempt_at    TIMESTAMPTZ,
    published_at       TIMESTAMPTZ,
    external_post_id   TEXT,
    external_post_url  TEXT,
    error_message      TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE scheduled_posts IS 'Persistent schedule queue; real platform publishing is intentionally future work';

-- ============================================================
--  8E. POST_METRICS - manual/future platform performance metrics
-- ============================================================
CREATE TABLE post_metrics (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generated_post_id UUID        NOT NULL REFERENCES generated_posts(id) ON DELETE CASCADE,
    scheduled_post_id UUID        REFERENCES scheduled_posts(id) ON DELETE SET NULL,
    platform          TEXT        NOT NULL,
    metric_date       DATE        NOT NULL,
    source            TEXT        NOT NULL DEFAULT 'manual',
    impressions       INTEGER     NOT NULL DEFAULT 0,
    reach             INTEGER     NOT NULL DEFAULT 0,
    views             INTEGER     NOT NULL DEFAULT 0,
    likes             INTEGER     NOT NULL DEFAULT 0,
    comments          INTEGER     NOT NULL DEFAULT 0,
    shares            INTEGER     NOT NULL DEFAULT 0,
    saves             INTEGER     NOT NULL DEFAULT 0,
    clicks            INTEGER     NOT NULL DEFAULT 0,
    reactions         INTEGER     NOT NULL DEFAULT 0,
    engagement_rate   REAL        NOT NULL DEFAULT 0,
    raw_metrics       JSONB       NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE post_metrics IS 'Manual post performance metrics now; future platform metrics can reuse source/raw_metrics';

-- ============================================================
--  ИНДЕКСЫ — ускорение запросов агентов
-- ============================================================

-- users
-- ============================================================
--  8A. GENERATION_RUNS - AI/action run metadata
-- ============================================================
CREATE TABLE generation_runs (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    run_type       TEXT        NOT NULL,
    provider       TEXT,
    agent_name     TEXT,
    input_payload  JSONB       NOT NULL DEFAULT '{}',
    output_payload JSONB       NOT NULL DEFAULT '{}',
    status         TEXT        NOT NULL DEFAULT 'completed',
    error_message  TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE generation_runs IS 'Audit trail for AI/action runs such as trend search, planning, and post generation';

CREATE INDEX ix_users_email        ON users (email);

-- user_profiles
CREATE INDEX ix_profiles_user      ON user_profiles (user_id);
CREATE INDEX ix_profiles_niche     ON user_profiles (niche);

-- interview_sessions
CREATE INDEX ix_interviews_user    ON interview_sessions (user_id);
CREATE INDEX ix_interviews_status  ON interview_sessions (status);
CREATE INDEX ix_trend_runs_user_started ON trend_runs (user_id, started_at DESC);

-- raw_posts — Агент 1 часто фильтрует по времени и нише
CREATE INDEX ix_rawposts_collected ON raw_posts (collected_at DESC);
CREATE INDEX ix_rawposts_niche     ON raw_posts (niche);
CREATE INDEX ix_rawposts_source    ON raw_posts (source);
CREATE INDEX ix_rawposts_score     ON raw_posts (score DESC);
-- GIN-индекс для поиска по тегам внутри JSONB
CREATE INDEX ix_rawposts_tags_gin  ON raw_posts USING GIN (platform_tags);
-- IVFFlat-индекс для быстрого приближённого поиска по вектору
-- (создавать ПОСЛЕ загрузки данных, когда есть хотя бы 1000 строк)
-- CREATE INDEX ix_rawposts_vec ON raw_posts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- trends — Агент 2 фильтрует по актуальности и рейтингу
CREATE INDEX ix_trends_expires     ON trends (expires_at);
CREATE INDEX ix_trends_score       ON trends (final_score DESC);
CREATE INDEX ix_trends_collected   ON trends (collected_at DESC);
CREATE INDEX ix_trends_source      ON trends (source);
CREATE INDEX ix_trends_user_active ON trends (user_id, expires_at, final_score DESC);
CREATE INDEX ix_trends_run         ON trends (trend_run_id);
-- GIN для поиска по ключевым словам
CREATE INDEX ix_trends_kw_gin      ON trends USING GIN (keywords);
-- Векторный поиск похожих трендов
-- CREATE INDEX ix_trends_vec ON trends USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX ix_trend_sources_trend    ON trend_sources (trend_id);
CREATE INDEX ix_trend_sources_raw_post ON trend_sources (raw_post_id);

-- content_plans
CREATE INDEX ix_plans_user         ON content_plans (user_id);
CREATE INDEX ix_plans_week         ON content_plans (week_start);
CREATE INDEX ix_plans_status       ON content_plans (status);

-- content_plan_items — Агент 3 выбирает ближайшие запланированные слоты
CREATE INDEX ix_items_plan         ON content_plan_items (plan_id);
CREATE INDEX ix_items_date         ON content_plan_items (scheduled_date);
CREATE INDEX ix_items_status       ON content_plan_items (status);
CREATE INDEX ix_items_trend        ON content_plan_items (trend_id);

-- generated_posts — пользователь фильтрует по статусу и платформе
CREATE INDEX ix_posts_user         ON generated_posts (user_id);
CREATE INDEX ix_posts_status       ON generated_posts (status);
CREATE INDEX ix_posts_platform     ON generated_posts (platform);
CREATE INDEX ix_posts_generated    ON generated_posts (generated_at DESC);
CREATE INDEX ix_posts_plan_item    ON generated_posts (plan_item_id);
CREATE INDEX ix_generation_runs_user_created ON generation_runs (user_id, created_at DESC);
CREATE INDEX ix_generation_runs_user_type    ON generation_runs (user_id, run_type, created_at DESC);
CREATE INDEX ix_post_assets_user_created ON post_assets (user_id, created_at DESC);
CREATE INDEX ix_post_assets_post_selected ON post_assets (post_id, is_selected);
CREATE UNIQUE INDEX uq_post_assets_one_selected ON post_assets (post_id) WHERE is_selected = true;
CREATE INDEX ix_social_accounts_user_platform ON social_accounts (user_id, platform);
CREATE INDEX ix_scheduled_posts_user_for ON scheduled_posts (user_id, scheduled_for DESC);
CREATE INDEX ix_scheduled_posts_status_for ON scheduled_posts (status, scheduled_for);
CREATE INDEX ix_scheduled_posts_generated_post ON scheduled_posts (generated_post_id);
CREATE UNIQUE INDEX uq_scheduled_posts_active_post_platform ON scheduled_posts (generated_post_id, platform)
    WHERE status IN ('scheduled', 'publishing');
CREATE INDEX ix_post_metrics_user_date ON post_metrics (user_id, metric_date DESC);
CREATE INDEX ix_post_metrics_generated_post ON post_metrics (generated_post_id);
CREATE INDEX ix_post_metrics_scheduled_post ON post_metrics (scheduled_post_id);
CREATE UNIQUE INDEX uq_post_metrics_manual_post_platform_date
    ON post_metrics (user_id, generated_post_id, platform, metric_date, source);

-- ============================================================
--  ТРИГГЕР — автообновление updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_profiles_updated
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_plans_updated
    BEFORE UPDATE ON content_plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_post_assets_updated
    BEFORE UPDATE ON post_assets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_social_accounts_updated
    BEFORE UPDATE ON social_accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_scheduled_posts_updated
    BEFORE UPDATE ON scheduled_posts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_post_metrics_updated
    BEFORE UPDATE ON post_metrics
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
--  ВЬЮХА — активные тренды (для удобства Агента 2 и 3)
-- ============================================================
CREATE OR REPLACE VIEW active_trends AS
SELECT *
FROM   trends
WHERE  expires_at > NOW()
ORDER  BY final_score DESC;

COMMENT ON VIEW active_trends IS 'Тренды которые ещё не устарели, отсортированные по рейтингу';

-- ============================================================
--  ВЬЮХА — дашборд постов пользователя
-- ============================================================
CREATE OR REPLACE VIEW user_posts_dashboard AS
SELECT
    gp.id,
    gp.user_id,
    gp.platform,
    gp.format,
    gp.status,
    gp.generated_at,
    gp.published_at,
    gp.llm_provider,
    (gp.stats->>'chars')::INT        AS chars,
    (gp.stats->>'hashtags')::INT     AS hashtags,
    t.topic                          AS trend_topic,
    t.final_score                    AS trend_score,
    cpi.scheduled_date,
    cpi.scheduled_time
FROM  generated_posts gp
LEFT  JOIN trends             t   ON t.id  = gp.trend_id
LEFT  JOIN content_plan_items cpi ON cpi.id = gp.plan_item_id;

COMMENT ON VIEW user_posts_dashboard IS 'Сводная вьюха постов с данными тренда и расписания';

-- ============================================================
--  ФУНКЦИЯ — очистка устаревших трендов
--  Вызывать из cron раз в сутки:
--    SELECT cleanup_expired_trends();
-- ============================================================
CREATE OR REPLACE FUNCTION cleanup_expired_trends()
RETURNS INTEGER LANGUAGE plpgsql AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM trends
    WHERE  expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    IF deleted_count > 0 THEN
        RAISE NOTICE 'Удалено устаревших трендов: %', deleted_count;
    END IF;

    RETURN deleted_count;
END;
$$;

COMMENT ON FUNCTION cleanup_expired_trends IS 'Удаляет тренды старше 14 дней. Запускать из cron раз в сутки.';
