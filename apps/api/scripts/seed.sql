-- ============================================================================
-- AI News Scraper — idempotent dev seed data
-- ----------------------------------------------------------------------------
-- Purpose: bootstrap a freshly-migrated database with one admin user,
--          two RSS feeds, four articles, and four feed_items (two per feed).
-- Idempotent: every insert uses ON CONFLICT DO NOTHING keyed on the model's
--             unique constraints, so re-running this file is safe.
--
-- Run:
--     psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f apps/api/scripts/seed.sql
--
-- DEV-ONLY -- DO NOT USE IN PRODUCTION.
-- The bcrypt hash below is for password 'dev-only-do-not-use-in-prod'.
-- It is committed to the public repo for local-dev convenience only.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Seed user
-- ----------------------------------------------------------------------------
-- DEV-ONLY -- DO NOT USE IN PRODUCTION.
-- bcrypt cost=12 hash of the password: dev-only-do-not-use-in-prod
-- Generated via: python -c "import bcrypt; print(bcrypt.hashpw(b'dev-only-do-not-use-in-prod', bcrypt.gensalt()).decode())"
INSERT INTO users (id, email, hashed_password, created_at) VALUES
    (
        '11111111-1111-1111-1111-111111111111',
        'alex@example.com',
        '$2b$12$.Yf7mxQIA9dCnzD2Cvde4O9xCLuEWmoBy5BV0wQVLTbkVay4wqNl6',
        now()
    )
ON CONFLICT (email) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. Seed feeds (RSS subscriptions for the dev user)
-- ----------------------------------------------------------------------------
INSERT INTO feeds (id, user_id, feed_url, title, description, active, created_at) VALUES
    (
        '22222222-2222-2222-2222-222222222222',
        '11111111-1111-1111-1111-111111111111',
        'https://hnrss.org/newest',
        'Hacker News — Newest',
        'Newest stories from Hacker News, scraped via hnrss.org.',
        true,
        now()
    ),
    (
        '33333333-3333-3333-3333-333333333333',
        '11111111-1111-1111-1111-111111111111',
        'https://www.theverge.com/rss/index.xml',
        'The Verge',
        'The Verge — technology, science, art, and culture.',
        true,
        now()
    )
ON CONFLICT (user_id, feed_url) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 3. Seed articles
-- ----------------------------------------------------------------------------
-- Topics stored as Postgres text[] literals.
INSERT INTO articles (id, user_id, url, headline, body, summary, topics, source_domain, publish_date, indexed_at) VALUES
    (
        'aaaaaaaa-0000-0000-0000-000000000001',
        '11111111-1111-1111-1111-111111111111',
        'https://hnrss.org/newest/item-001',
        'Show HN: A faster async Python ORM built on top of SQLAlchemy 2.0',
        'Full HN thread body — omitted in seed.',
        'A solo developer published a thin async wrapper around SQLAlchemy 2.0 that promises 30 percent faster bulk inserts by bypassing the unit-of-work pattern and streaming rows directly to asyncpg. Early benchmarks on a 1M-row dataset show a 1.4x speedup at the cost of an opinionated API surface. The author has open-sourced the project and is asking for feedback on whether to upstream the ideas into SQLAlchemy itself or keep it as a separate package.',
        ARRAY['python','sqlalchemy','orm','async','performance','open-source','databases'],
        'news.ycombinator.com',
        now() - interval '3 hours',
        now()
    ),
    (
        'aaaaaaaa-0000-0000-0000-000000000002',
        '11111111-1111-1111-1111-111111111111',
        'https://hnrss.org/newest/item-002',
        'Postgres 17 adds logical replication failover slots',
        'Full HN thread body — omitted in seed.',
        'Postgres 17 ships a long-awaited feature: failover-enabled logical replication slots. Operators can now promote a standby without losing replication state, closing a gap that has forced many shops to script their own failover flows. The release also tightens the contract around replication origin tracking, making it safer to mix physical and logical replication in the same cluster.',
        ARRAY['postgres','databases','replication','devops','reliability','release-notes'],
        'news.ycombinator.com',
        now() - interval '6 hours',
        now()
    ),
    (
        'aaaaaaaa-0000-0000-0000-000000000003',
        '11111111-1111-1111-1111-111111111111',
        'https://www.theverge.com/item-003',
        'OpenAI unveils a smaller, cheaper embedding model aimed at retrieval-heavy apps',
        'Full Verge article body — omitted in seed.',
        'OpenAI introduced a new embedding model positioned between text-embedding-3-small and text-embedding-3-large. The new tier targets retrieval-augmented generation pipelines that need higher fidelity than the small model offers but cannot justify the cost or latency of the large one. Pricing lands at roughly half the cost of the large model, with a 256-dimension option for teams that want to compress vector storage further.',
        ARRAY['openai','embeddings','rag','ai','llm','retrieval','pricing','vector-search'],
        'www.theverge.com',
        now() - interval '12 hours',
        now()
    ),
    (
        'aaaaaaaa-0000-0000-0000-000000000004',
        '11111111-1111-1111-1111-111111111111',
        'https://www.theverge.com/item-004',
        'Apple silicon Macs now officially boot Fedora Asahi Remix 41',
        'Full Verge article body — omitted in seed.',
        'The Asahi Linux project released Fedora Asahi Remix 41, the first distribution to ship full mainline kernel support for M3-series Apple silicon. The release includes GPU drivers that accelerate Wayland compositing and a working Wi-Fi stack. It is a milestone for hobbyists who want a fully open-source operating system on Mac hardware without giving up modern chipsets.',
        ARRAY['linux','apple','fedora','asahi','open-source','hardware','drivers'],
        'www.theverge.com',
        now() - interval '1 day',
        now()
    )
ON CONFLICT (user_id, url) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. Seed feed_items (two items per feed, referencing the articles above)
-- ----------------------------------------------------------------------------
INSERT INTO feed_items (id, feed_id, article_id, guid, title, url, fetched_at) VALUES
    -- Hacker News feed items
    (
        'bbbbbbbb-0000-0000-0000-000000000001',
        '22222222-2222-2222-2222-222222222222',
        'aaaaaaaa-0000-0000-0000-000000000001',
        'hn-newest-001',
        'Show HN: A faster async Python ORM built on top of SQLAlchemy 2.0',
        'https://hnrss.org/newest/item-001',
        now()
    ),
    (
        'bbbbbbbb-0000-0000-0000-000000000002',
        '22222222-2222-2222-2222-222222222222',
        'aaaaaaaa-0000-0000-0000-000000000002',
        'hn-newest-002',
        'Postgres 17 adds logical replication failover slots',
        'https://hnrss.org/newest/item-002',
        now()
    ),
    -- The Verge feed items
    (
        'bbbbbbbb-0000-0000-0000-000000000003',
        '33333333-3333-3333-3333-333333333333',
        'aaaaaaaa-0000-0000-0000-000000000003',
        'verge-003',
        'OpenAI unveils a smaller, cheaper embedding model aimed at retrieval-heavy apps',
        'https://www.theverge.com/item-003',
        now()
    ),
    (
        'bbbbbbbb-0000-0000-0000-000000000004',
        '33333333-3333-3333-3333-333333333333',
        'aaaaaaaa-0000-0000-0000-000000000004',
        'verge-004',
        'Apple silicon Macs now officially boot Fedora Asahi Remix 41',
        'https://www.theverge.com/item-004',
        now()
    )
ON CONFLICT (feed_id, guid) DO NOTHING;

COMMIT;
