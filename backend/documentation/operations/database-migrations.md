# Database Migrations

## Source of truth

All new schema changes belong in `migrations/`. Run migration files in filename
order through Supabase SQL Editor or `psql`. Each migration records its version
in `public.app_schema_migrations` and is designed to be safe to run once.

## Safe workflow

1. Read the entire migration and identify schema, index, data-backfill, and
   permission changes.
2. Back up or verify the relevant data when the migration transforms rows.
3. Run the migration once in the target Supabase project.
4. Confirm `app_schema_migrations` contains its version.
5. Exercise the affected API path and inspect its log or dashboard result.

## Pending migration

`2026092101_evaluation_soft_failures.sql` is intentionally pending. It adds a
queue reason for evaluation cases and backfills historical answer-abstention
cases. It does not modify chat messages, chunks, or embeddings.

## Chunk publishing

`2026091601_chunk_quality.sql` is required before publishing lossless PI/KKP
chunks. The publish utility can call OpenAI to create embeddings and write to
Supabase, so inspect its plan before using `--apply`.

See `scripts/README.md` for the supported maintenance commands.
