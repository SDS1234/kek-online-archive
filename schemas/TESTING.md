# Testing the Historical Data Feature

## Overview

This document describes how to test the historical data tracking feature implementation.

## Prerequisites

- PostgreSQL 12 or higher installed
- Python 3.7 or higher
- psycopg2-binary Python package (`pip install psycopg2-binary`)
- Git repository with commit history

## Test Environment Setup

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install psycopg2-binary

# Verify PostgreSQL is running
pg_isready
```

### 2. Create Test Database

```bash
# Create a test database
createdb kek_test

# Apply the schema
psql -d kek_test -f schemas/postgresql-schema.sql

# Verify tables were created
psql -d kek_test -c "\dt"
```

Expected output should include:
- `data_snapshots`
- `media_history`
- `shareholders_history`
- `ownership_relations_history`
- `operation_relations_history`
- Plus all the regular tables from the base schema

## Test Cases

### Test 1: Basic Data Import (Current Snapshot)

Test importing current data without historical tracking:

```bash
# Import a small sample for testing
python import_to_postgres.py --db kek_test --sample 10

# Verify data was imported
psql -d kek_test -c "SELECT COUNT(*) FROM media;"
psql -d kek_test -c "SELECT COUNT(*) FROM shareholders;"
```

Expected:
- ~10 media entities
- ~10 shareholders
- Related relationships imported

### Test 2: Historical Import with Git Metadata

Test importing current data WITH historical tracking:

```bash
# Import with historical flag
python import_to_postgres.py --db kek_test --sample 10 --historical

# Verify snapshot was created
psql -d kek_test -c "SELECT * FROM data_snapshots;"

# Verify historical data was imported
psql -d kek_test -c "SELECT COUNT(*) FROM media_history;"
psql -d kek_test -c "SELECT COUNT(*) FROM shareholders_history;"
```

Expected:
- 1 snapshot entry with current git commit
- Historical tables populated with same entities
- Full JSON stored in JSONB columns

### Test 3: Bulk Historical Import

Test importing multiple historical snapshots:

```bash
# Import last 3 commits with sample data
python import_historical_data.py --db kek_test --commits 3 --sample 10

# View all snapshots
psql -d kek_test -c "SELECT * FROM snapshot_timeline ORDER BY commit_date DESC;"

# Count total historical records
psql -d kek_test -c "
SELECT 
    (SELECT COUNT(*) FROM media_history) as media_history,
    (SELECT COUNT(*) FROM shareholders_history) as shareholders_history,
    (SELECT COUNT(*) FROM ownership_relations_history) as ownership_history,
    (SELECT COUNT(*) FROM operation_relations_history) as operation_history;
"
```

Expected:
- 3 snapshot entries (or fewer if there are fewer commits)
- Each snapshot has corresponding historical records
- No duplicate snapshots if run multiple times

### Test 4: Query Historical Data

Test the query functions and views:

```bash
# Get a media UUID from the database
MEDIA_UUID=$(psql -d kek_test -t -c "SELECT squuid FROM media LIMIT 1;" | tr -d ' ')

# Test media ownership timeline function
psql -d kek_test -c "SELECT * FROM get_media_ownership_timeline('${MEDIA_UUID}');"

# Get a shareholder UUID
SHAREHOLDER_UUID=$(psql -d kek_test -t -c "SELECT squuid FROM shareholders LIMIT 1;" | tr -d ' ')

# Test shareholder portfolio timeline function
psql -d kek_test -c "SELECT * FROM get_shareholder_portfolio_timeline('${SHAREHOLDER_UUID}');"
```

Expected:
- Functions return results showing historical changes
- Results ordered by commit date
- All referenced entities exist in historical tables

### Test 5: Compare Snapshots

Test snapshot comparison queries:

```bash
# Run the comparison queries
psql -d kek_test -f schemas/queries/compare_snapshots.sql > /tmp/comparison_results.txt

# Check results
cat /tmp/comparison_results.txt
```

Expected:
- Query executes without errors
- Shows differences between most recent snapshots
- Change types correctly identified (NEW, REMOVED, CHANGED)

### Test 6: Example Query Files

Test all example query files:

```bash
# Test each query file
for query_file in schemas/queries/*_history.sql; do
    echo "Testing $query_file..."
    psql -d kek_test -f "$query_file" > /tmp/query_test.txt 2>&1
    if [ $? -eq 0 ]; then
        echo "  ✓ Success"
    else
        echo "  ✗ Failed"
        cat /tmp/query_test.txt
    fi
done
```

Expected:
- All query files execute successfully
- Results show historical data
- No SQL syntax errors

## Validation Checks

### Schema Validation

Verify the schema is correctly created:

```sql
-- Check historical tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name LIKE '%history%'
ORDER BY table_name;

-- Check indexes on historical tables
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename LIKE '%history%'
ORDER BY tablename, indexname;

-- Check functions exist
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public'
  AND routine_name LIKE '%timeline%'
ORDER BY routine_name;

-- Check views exist
SELECT table_name 
FROM information_schema.views 
WHERE table_schema = 'public'
ORDER BY table_name;
```

### Data Integrity Validation

Verify data integrity:

```sql
-- Check that all historical records reference valid snapshots
SELECT 
    'media_history' as table_name,
    COUNT(*) as orphaned_records
FROM media_history mh
WHERE NOT EXISTS (
    SELECT 1 FROM data_snapshots ds WHERE ds.id = mh.snapshot_id
)
UNION ALL
SELECT 
    'shareholders_history',
    COUNT(*)
FROM shareholders_history sh
WHERE NOT EXISTS (
    SELECT 1 FROM data_snapshots ds WHERE ds.id = sh.snapshot_id
);

-- Verify JSONB data is valid JSON
SELECT 
    squuid,
    snapshot_id,
    CASE 
        WHEN jsonb_typeof(data) = 'object' THEN 'Valid'
        ELSE 'Invalid'
    END as json_validity
FROM media_history
LIMIT 10;
```

### Performance Validation

Check query performance:

```sql
-- Explain plan for timeline query
EXPLAIN ANALYZE
SELECT * FROM get_media_ownership_timeline(
    (SELECT squuid FROM media LIMIT 1)
);

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename LIKE '%history%'
ORDER BY idx_scan DESC;
```

## Expected Test Results

### Success Criteria

All tests should pass with these results:

1. ✓ Schema creates successfully with all tables, indexes, views, and functions
2. ✓ Basic import works and populates main tables
3. ✓ Historical import creates snapshots and populates history tables
4. ✓ Bulk historical import processes multiple commits
5. ✓ Timeline functions return correct historical data
6. ✓ Comparison queries show changes between snapshots
7. ✓ All example query files execute without errors
8. ✓ Data integrity checks pass
9. ✓ No orphaned historical records
10. ✓ JSONB data is valid

### Performance Expectations

- Import of 10 entities should complete in < 5 seconds
- Historical queries should use indexes efficiently
- Timeline functions should return results in < 1 second for typical datasets

## Troubleshooting

### Common Issues

1. **PostgreSQL not running**
   ```bash
   sudo service postgresql start
   # or
   pg_ctl -D /usr/local/var/postgres start
   ```

2. **Permission denied creating database**
   ```bash
   # Connect as postgres superuser
   sudo -u postgres createdb kek_test
   ```

3. **Git command fails**
   - Ensure you're in the git repository directory
   - Check that git history exists: `git log --oneline`

4. **Import script can't find psycopg2**
   ```bash
   pip install psycopg2-binary
   # or
   pip3 install psycopg2-binary
   ```

5. **Historical import finds no commits**
   - Repository might be grafted (shallow clone)
   - Check git log with: `git log --all --oneline -- docs/data/`

## Cleanup

After testing, clean up test database:

```bash
# Drop test database
dropdb kek_test
```

## Automated Testing

For automated testing in CI/CD:

```bash
#!/bin/bash
set -e

# Setup
createdb kek_test
psql -d kek_test -f schemas/postgresql-schema.sql

# Test basic import
python import_to_postgres.py --db kek_test --sample 5

# Test historical import
python import_to_postgres.py --db kek_test --sample 5 --historical

# Verify data
COUNT=$(psql -d kek_test -t -c "SELECT COUNT(*) FROM data_snapshots;")
if [ "$COUNT" -lt 1 ]; then
    echo "ERROR: No snapshots created"
    exit 1
fi

echo "All tests passed!"

# Cleanup
dropdb kek_test
```

## Notes

- The grafted repository in this test environment has limited history (only 2 commits)
- In production, there would be daily commits showing real data changes
- Sample sizes should be adjusted based on available memory and test duration requirements
- Historical tables can grow large; monitor disk space in production
