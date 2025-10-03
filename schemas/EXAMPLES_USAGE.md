# Historical Data Feature - Usage Examples

This document provides practical examples of using the historical data tracking feature.

## Example 1: Daily Data Import with Historical Tracking

This is the most common use case - importing daily data updates.

```bash
#!/bin/bash
# daily_import.sh - Run this daily after data is updated

cd /path/to/kek-online-archive

# Import current data to main tables
python import_to_postgres.py --db kek --historical

# This will:
# 1. Import data to main tables (media, shareholders, etc.)
# 2. Create a snapshot entry with current git commit
# 3. Import same data to historical tables
# 4. Link historical data to the snapshot
```

## Example 2: Catch Up on Historical Data

Import multiple days of historical data at once:

```bash
# Import last 30 days of data
python import_historical_data.py --db kek --commits 30

# Import data from a specific date range
python import_historical_data.py --db kek --since 2024-01-01 --until 2024-12-31

# For testing with limited data
python import_historical_data.py --db kek --commits 10 --sample 100
```

## Example 3: Track a Specific Media Entity

Find out how ownership of a specific newspaper or TV station has changed:

```sql
-- Get the UUID of a media entity (e.g., search by name)
SELECT squuid, name, type FROM media WHERE name ILIKE '%Volksstimme%';

-- Track ownership changes using the timeline function
SELECT 
    commit_date,
    git_commit_hash,
    operator_name,
    ownership_chain->0->'holder'->>'name' as ultimate_owner
FROM get_media_ownership_timeline('5be1a6b1-c47a-4cf2-8f64-f1f6583ec990')
ORDER BY commit_date DESC;
```

Output shows:
- When operators changed
- Who owns the operators (ownership chain)
- Git commit where each change was recorded

## Example 4: Track a Shareholder's Portfolio

See how a shareholder's media holdings have evolved:

```sql
-- Find a shareholder
SELECT squuid, name FROM shareholders 
WHERE name ILIKE '%Springer%' 
LIMIT 5;

-- Get their portfolio over time
SELECT 
    commit_date,
    media_name,
    media_type,
    market_reach,
    CASE 
        WHEN LAG(media_squuid) OVER (PARTITION BY media_squuid ORDER BY commit_date) IS NULL 
        THEN 'ACQUIRED'
        ELSE 'HELD'
    END as status
FROM get_shareholder_portfolio_timeline('5be1a6b6-0a00-491b-9229-bfd0da590573')
ORDER BY commit_date DESC, media_name;
```

This shows:
- All media controlled by the shareholder
- When each media was acquired
- Changes in market reach over time

## Example 5: Detect Recent Changes

Find what changed in the last data update:

```sql
-- Compare the two most recent snapshots
WITH latest_snapshots AS (
    SELECT id, commit_date, git_commit_hash,
           ROW_NUMBER() OVER (ORDER BY commit_date DESC) as rn
    FROM data_snapshots
)
SELECT 
    'Ownership changes' as change_type,
    COUNT(*) as count
FROM ownership_relations_history oh1
JOIN latest_snapshots s1 ON s1.id = oh1.snapshot_id AND s1.rn = 1
LEFT JOIN ownership_relations_history oh2 
    ON oh2.snapshot_id = (SELECT id FROM latest_snapshots WHERE rn = 2)
    AND oh2.holder_squuid = oh1.holder_squuid
    AND oh2.held_squuid = oh1.held_squuid
WHERE oh2.squuid IS NULL 
   OR oh1.capital_shares != oh2.capital_shares

UNION ALL

SELECT 
    'New media entities',
    COUNT(*)
FROM media_history mh
WHERE mh.snapshot_id = (SELECT id FROM latest_snapshots WHERE rn = 1)
  AND NOT EXISTS (
    SELECT 1 FROM media_history mh2
    WHERE mh2.snapshot_id = (SELECT id FROM latest_snapshots WHERE rn = 2)
      AND mh2.squuid = mh.squuid
  );
```

## Example 6: Market Concentration Analysis Over Time

Track media concentration trends:

```sql
-- Calculate market concentration for top shareholders over time
SELECT 
    ds.commit_date,
    sh.name as shareholder_name,
    COUNT(DISTINCT m.squuid) as media_count,
    SUM(m.market_reach) as total_market_reach,
    COUNT(DISTINCT CASE WHEN m.type = 'tv' THEN m.squuid END) as tv_count,
    COUNT(DISTINCT CASE WHEN m.type = 'print' THEN m.squuid END) as print_count
FROM data_snapshots ds
JOIN shareholders_history sh ON sh.snapshot_id = ds.id
JOIN operation_relations_history opr 
    ON opr.holder_squuid = sh.squuid 
    AND opr.snapshot_id = ds.id 
    AND opr.state = 'active'
JOIN media_history m 
    ON m.squuid = opr.held_squuid 
    AND m.snapshot_id = ds.id 
    AND m.state = 'active'
WHERE sh.natural_person = false  -- Focus on companies
GROUP BY ds.commit_date, sh.squuid, sh.name
HAVING COUNT(DISTINCT m.squuid) >= 5  -- Only major players
ORDER BY ds.commit_date DESC, total_market_reach DESC;
```

## Example 7: Find Media That Changed Operators

Identify media entities that switched operators:

```sql
WITH operator_changes AS (
    SELECT 
        m.squuid as media_squuid,
        m.name as media_name,
        ds.commit_date,
        sh.name as operator_name,
        LAG(sh.squuid) OVER (PARTITION BY m.squuid ORDER BY ds.commit_date) as prev_operator_squuid
    FROM data_snapshots ds
    JOIN media_history m ON m.snapshot_id = ds.id
    JOIN operation_relations_history opr 
        ON opr.held_squuid = m.squuid 
        AND opr.snapshot_id = ds.id
        AND opr.state = 'active'
    JOIN shareholders_history sh 
        ON sh.squuid = opr.holder_squuid 
        AND sh.snapshot_id = ds.id
)
SELECT 
    media_name,
    commit_date as change_date,
    operator_name as new_operator,
    LAG(operator_name) OVER (PARTITION BY media_squuid ORDER BY commit_date) as previous_operator
FROM operator_changes
WHERE prev_operator_squuid IS NOT NULL 
  AND prev_operator_squuid != (
    SELECT holder_squuid FROM operation_relations_history opr2
    WHERE opr2.held_squuid = media_squuid
      AND opr2.snapshot_id = (
        SELECT id FROM data_snapshots 
        WHERE commit_date < operator_changes.commit_date
        ORDER BY commit_date DESC LIMIT 1
      )
    LIMIT 1
  )
ORDER BY commit_date DESC;
```

## Example 8: Export Historical Data for Analysis

Export data for external analysis (e.g., in R or Python):

```bash
# Export snapshot timeline
psql -d kek -c "COPY (SELECT * FROM snapshot_timeline) TO STDOUT CSV HEADER" > snapshots.csv

# Export media history for a specific period
psql -d kek -c "COPY (
    SELECT 
        ds.commit_date,
        m.squuid,
        m.name,
        m.type,
        m.market_reach
    FROM data_snapshots ds
    JOIN media_history m ON m.snapshot_id = ds.id
    WHERE ds.commit_date >= '2024-01-01'
      AND m.state = 'active'
) TO STDOUT CSV HEADER" > media_history_2024.csv

# Export ownership relationships over time
psql -d kek -c "COPY (
    SELECT 
        ds.commit_date,
        sh_holder.name as holder_name,
        sh_held.name as held_name,
        owr.capital_shares
    FROM data_snapshots ds
    JOIN ownership_relations_history owr ON owr.snapshot_id = ds.id
    JOIN shareholders_history sh_holder 
        ON sh_holder.squuid = owr.holder_squuid 
        AND sh_holder.snapshot_id = ds.id
    JOIN shareholders_history sh_held 
        ON sh_held.squuid = owr.held_squuid 
        AND sh_held.snapshot_id = ds.id
    WHERE owr.state = 'active'
) TO STDOUT CSV HEADER" > ownership_history.csv
```

## Example 9: Monitor Specific Relationships

Set up monitoring for critical ownership relationships:

```sql
-- Create a view for monitoring key relationships
CREATE VIEW monitored_ownership AS
SELECT 
    ds.commit_date,
    ds.git_commit_hash,
    sh_holder.name as holder_name,
    sh_held.name as held_name,
    owr.capital_shares,
    owr.state
FROM data_snapshots ds
JOIN ownership_relations_history owr ON owr.snapshot_id = ds.id
JOIN shareholders_history sh_holder 
    ON sh_holder.squuid = owr.holder_squuid 
    AND sh_holder.snapshot_id = ds.id
JOIN shareholders_history sh_held 
    ON sh_held.squuid = owr.held_squuid 
    AND sh_held.snapshot_id = ds.id
WHERE sh_holder.name IN ('Axel Springer SE', 'Bertelsmann SE & Co. KGaA')
   OR sh_held.name IN ('ProSiebenSat.1 Media SE', 'RTL Group')
ORDER BY ds.commit_date DESC;

-- Query to detect changes in monitored relationships
SELECT * FROM monitored_ownership WHERE commit_date >= CURRENT_DATE - INTERVAL '7 days';
```

## Example 10: Integration with Automated Reports

Generate automated reports:

```python
#!/usr/bin/env python3
"""
Generate weekly ownership change report
"""
import psycopg2
from datetime import datetime, timedelta

conn = psycopg2.connect(dbname='kek', user='postgres')
cursor = conn.cursor()

# Get changes from last week
week_ago = datetime.now() - timedelta(days=7)

cursor.execute("""
    WITH recent_snapshots AS (
        SELECT id, commit_date 
        FROM data_snapshots 
        WHERE commit_date >= %s
        ORDER BY commit_date
    )
    SELECT 
        ds.commit_date,
        COUNT(DISTINCT mh.squuid) as media_count,
        COUNT(DISTINCT sh.squuid) as shareholder_count,
        COUNT(DISTINCT owr.squuid) as ownership_relations
    FROM recent_snapshots rs
    JOIN data_snapshots ds ON ds.id = rs.id
    LEFT JOIN media_history mh ON mh.snapshot_id = ds.id
    LEFT JOIN shareholders_history sh ON sh.snapshot_id = ds.id
    LEFT JOIN ownership_relations_history owr ON owr.snapshot_id = ds.id
    GROUP BY ds.commit_date
    ORDER BY ds.commit_date DESC
""", (week_ago,))

print("KEK Database Weekly Report")
print("=" * 60)
print(f"Report generated: {datetime.now()}")
print(f"Period: {week_ago.date()} to {datetime.now().date()}")
print("=" * 60)
print()

for row in cursor.fetchall():
    commit_date, media_count, shareholder_count, ownership_count = row
    print(f"Date: {commit_date}")
    print(f"  Media entities: {media_count}")
    print(f"  Shareholders: {shareholder_count}")
    print(f"  Ownership relations: {ownership_count}")
    print()

cursor.close()
conn.close()
```

## Tips and Best Practices

1. **Regular Imports**: Run the historical import daily to keep data up-to-date
2. **Sample Data**: Use `--sample` for testing to avoid long import times
3. **Indexing**: The provided indexes cover common queries; add more based on your specific needs
4. **Storage**: Monitor database size as historical tables grow over time
5. **Partitioning**: For very large datasets, consider partitioning history tables by date
6. **Backup**: Regular backups are essential since historical data is valuable for analysis
7. **Git History**: Preserve git history to enable historical imports for any time period

## Performance Notes

- Timeline functions are optimized for single entity lookups
- Bulk analysis queries may need additional indexes
- Consider materialized views for frequently-run complex queries
- The JSONB columns enable flexible queries but may be slower than structured columns
