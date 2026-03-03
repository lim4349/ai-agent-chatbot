# Supabase Migrations

This directory contains SQL migration files for the Supabase PostgreSQL database.

## Migration Files

Migrations are named with the format: `YYYYMMDD_description.sql`

### 20260303_metrics.sql
Creates the metrics tracking tables for the observability dashboard:
- `request_metrics` - Individual request-level metrics for each agent invocation
- `agent_daily_stats` - Daily aggregated statistics per agent (auto-updated via trigger)

## Applying Migrations

### Via Supabase Dashboard
1. Go to your Supabase project → SQL Editor
2. Copy the contents of the migration file
3. Run the SQL

### Via Supabase CLI
```bash
# Install Supabase CLI first
npm install -g supabase

# Link to your project
supabase link --project-ref YOUR_PROJECT_REF

# Apply migration
supabase db push
```

### Via psql
```bash
psql "$DATABASE_URL" -f supabase/migrations/20260303_metrics.sql
```

## Rollback

To rollback a migration, manually drop the created objects:
```sql
DROP TRIGGER IF EXISTS trigger_update_agent_daily_stats ON request_metrics;
DROP FUNCTION IF EXISTS update_agent_daily_stats();
DROP TABLE IF EXISTS agent_daily_stats;
DROP TABLE IF EXISTS request_metrics;
```
