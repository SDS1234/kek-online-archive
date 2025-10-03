# Historical Data Tracking

This feature allows you to track how media ownership data has changed over time by leveraging the git commit history.

## Overview

The KEK database is updated daily with snapshots committed to git. The historical data tracking feature imports these snapshots into PostgreSQL, enabling:

- **Time-series analysis** of media ownership changes
- **Comparison** of ownership structures between different dates
- **Tracking** of specific media entities or shareholders over time
- **Detection** of ownership transitions and portfolio changes

## Database Schema

The historical tracking adds the following tables to the PostgreSQL schema:

### Core Tables

- **`data_snapshots`** - Git commits that correspond to data snapshots
- **`media_history`** - Historical snapshots of media entities
- **`shareholders_history`** - Historical snapshots of shareholder entities
- **`ownership_relations_history`** - Historical ownership relationships
- **`operation_relations_history`** - Historical operation relationships

### Helper Views and Functions

- **`snapshot_timeline`** - View showing all snapshots with metadata
- **`get_media_ownership_timeline(uuid)`** - Function to get ownership changes for a media entity
- **`get_shareholder_portfolio_timeline(uuid)`** - Function to get portfolio changes for a shareholder
- **`get_ownership_change_timeline(holder_uuid, held_uuid)`** - Function to track specific ownership relationships

## Setup

### 1. Create the Database Schema

First, create the database and apply the schema:

```bash
# Create database
createdb kek

# Apply schema (includes historical tables)
psql -d kek -f schemas/postgresql-schema.sql
```

### 2. Import Current Data

Import the current snapshot of data:

```bash
python import_to_postgres.py --db kek --user postgres
```

### 3. Import Historical Data

Import historical snapshots from git commits:

```bash
# Import data from the last 10 commits
python import_historical_data.py --db kek --commits 10

# Import data from commits since a specific date
python import_historical_data.py --db kek --since 2024-01-01

# Import data from a date range
python import_historical_data.py --db kek --since 2024-01-01 --until 2024-12-31

# For testing, use --sample to limit the number of entities per commit
python import_historical_data.py --db kek --commits 5 --sample 50
```

## Usage Examples

### View All Available Snapshots

```sql
SELECT * FROM snapshot_timeline ORDER BY commit_date DESC;
```

### Track Media Ownership Over Time

```sql
-- Get ownership timeline for a specific media entity
SELECT * FROM get_media_ownership_timeline('67068646-76fa-4f3d-92e2-cbeb87adbb26');
```

For more complex queries, see `schemas/queries/media_ownership_history.sql`.

### Track Shareholder Portfolio Changes

```sql
-- Get portfolio timeline for a specific shareholder
SELECT * FROM get_shareholder_portfolio_timeline('5be1a6b6-5c1b-48b1-ad15-85241452bf42');
```

For more complex queries, see `schemas/queries/shareholder_portfolio_history.sql`.

### Compare Two Snapshots

```sql
-- See what changed between the two most recent snapshots
-- See schemas/queries/compare_snapshots.sql for detailed examples
```

### Track Ownership Percentage Changes

```sql
-- Track how ownership share changed over time
SELECT * FROM get_ownership_change_timeline(
    '5be1a6b6-5c1b-48b1-ad15-85241452bf42',  -- holder_squuid
    '5be1a6b6-0a00-491b-9229-bfd0da590573'   -- held_squuid
);
```

For more complex queries, see `schemas/queries/ownership_changes_history.sql`.

## Query Files

Example queries are provided in the `schemas/queries/` directory:

- **`media_ownership_history.sql`** - Query media ownership changes over time
- **`shareholder_portfolio_history.sql`** - Query shareholder portfolio changes
- **`compare_snapshots.sql`** - Compare data between two snapshots
- **`ownership_changes_history.sql`** - Track ownership percentage changes

## Architecture

### How It Works

1. **Data Snapshots**: Each git commit that modifies data files is recorded in the `data_snapshots` table with its commit hash, date, and message.

2. **Historical Tables**: The `_history` tables store complete snapshots of entities and relationships as they existed at each commit.

3. **JSONB Storage**: Media and shareholder history tables include a `data` JSONB column that stores the complete JSON representation of the entity, allowing flexible querying of any field from historical snapshots.

4. **Git Integration**: The import scripts use git commands to:
   - Identify commits that changed data files
   - Extract commit metadata (hash, date, message)
   - Checkout specific commits to import their data

### Design Decisions

- **Snapshot-based**: Each commit creates a complete snapshot rather than storing deltas, making queries simpler and faster.
- **Immutable History**: Historical tables are append-only; past snapshots are never modified.
- **JSONB Flexibility**: Full JSON storage enables ad-hoc queries without schema changes.
- **Indexed Efficiently**: Multiple indexes support common query patterns (by snapshot, by entity, by relationship).

## Performance Considerations

- **Storage**: Historical tables grow with each snapshot. Plan storage accordingly.
- **Indexes**: The schema includes indexes for common query patterns. Add more indexes based on your specific needs.
- **Batch Imports**: Use `import_historical_data.py` to import multiple snapshots efficiently.
- **Sampling**: Use `--sample` option during testing to import fewer entities per snapshot.

## Maintenance

### Importing New Snapshots

After daily data updates are committed to git, import the new snapshot:

```bash
# Import with historical data
python import_to_postgres.py --db kek --historical
```

Or use the dedicated historical import script to catch up on multiple commits:

```bash
python import_historical_data.py --db kek --commits 1
```

### Cleaning Up Old Snapshots

If you need to remove old snapshots:

```sql
-- Delete snapshots older than a specific date
DELETE FROM data_snapshots WHERE commit_date < '2024-01-01';
-- This will cascade delete all associated historical records
```

## Troubleshooting

### "Could not get git commit information"

This error occurs when running the import outside a git repository. Make sure:
- You're running the script in the repository root
- The directory contains a valid git repository
- The repository has commit history

### "Snapshot already exists"

This is normal when re-running imports. The script skips commits that have already been imported.

### Memory Issues with Large Imports

If importing many commits causes memory issues:
- Use the `--sample` option to import fewer entities per commit
- Import commits in smaller batches using `--commits`
- Increase available memory for PostgreSQL

## Future Enhancements

Potential improvements for this feature:

- Incremental delta storage to reduce space usage
- Automated daily import via cron job or GitHub Actions
- Web API to query historical data
- Visualization of ownership changes over time
- Diff views showing exactly what changed between snapshots
- Time-travel queries to see the database state at any past date

## Copyright

All data is copyright [Kommission zur Ermittlung der Konzentration im Medienbereich (KEK)](https://www.kek-online.de/impressum).
