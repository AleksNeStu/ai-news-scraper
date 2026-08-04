-- Create the secondary database used by the test suite. The default
-- POSTGRES_DB (ai_news) is what alembic upgrade head + seed.sql target
-- in the migrate service. Tests connect to ai_news_test via the
-- conftest's _settings.database_url which defaults to that name.
CREATE DATABASE ai_news_test;
