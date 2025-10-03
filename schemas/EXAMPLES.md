# Schema Usage Examples

This document provides practical examples of using the KEK database schemas.

## Table of Contents
- [JSON Schema Validation](#json-schema-validation)
- [PostgreSQL Setup](#postgresql-setup)
- [Sample Queries](#sample-queries)
- [Data Import](#data-import)

## JSON Schema Validation

### Python Example

```python
import json
from jsonschema import validate

# Load schema
with open('schemas/media.schema.json') as f:
    media_schema = json.load(f)

# Load and validate data
with open('docs/data/media/5be1a6b1-c47a-4cf2-8f64-f1f6583ec990.json') as f:
    media_data = json.load(f)

# Validate - will raise ValidationError if invalid
validate(instance=media_data, schema=media_schema)
print("✓ Valid media entity")
```

### JavaScript Example

```javascript
const Ajv = require('ajv');
const fs = require('fs');

// Load schema
const mediaSchema = JSON.parse(fs.readFileSync('schemas/media.schema.json'));

// Create validator
const ajv = new Ajv();
const validate = ajv.compile(mediaSchema);

// Load and validate data
const mediaData = JSON.parse(fs.readFileSync('docs/data/media/5be1a6b1-c47a-4cf2-8f64-f1f6583ec990.json'));

if (validate(mediaData)) {
    console.log('✓ Valid media entity');
} else {
    console.error('Validation errors:', validate.errors);
}
```

### Command Line (ajv-cli)

```bash
# Install ajv-cli
npm install -g ajv-cli

# Validate single file
ajv validate -s schemas/media.schema.json -d docs/data/media/some-uuid.json

# Validate all media files
ajv validate -s schemas/media.schema.json -d "docs/data/media/*.json"

# Validate all shareholder files
ajv validate -s schemas/shareholder.schema.json -d "docs/data/shareholders/*.json"
```

## PostgreSQL Setup

### 1. Create Database

```bash
# Create database
sudo -u postgres createdb kek

# Initialize schema
sudo -u postgres psql kek < schemas/postgresql-schema.sql
```

### 2. Verify Setup

```sql
-- Connect to database
psql kek

-- List tables
\dt

-- Check table structure
\d media
\d shareholders
\d ownership_relations
\d operation_relations

-- List views
\dv
```

### 3. Basic Data Check

```sql
-- Count entities
SELECT COUNT(*) FROM media;
SELECT COUNT(*) FROM shareholders;
SELECT COUNT(*) FROM ownership_relations;
SELECT COUNT(*) FROM operation_relations;

-- Check media distribution by type
SELECT type, COUNT(*) 
FROM media 
GROUP BY type;

-- Check active vs archived
SELECT state, COUNT(*) 
FROM media 
GROUP BY state;
```

## Sample Queries

### Media Queries

#### Top 10 Media by Market Reach
```sql
SELECT name, type, market_reach
FROM media
WHERE state = 'active' AND market_reach IS NOT NULL
ORDER BY market_reach DESC
LIMIT 10;
```

#### All Print Media with IVW Verification
```sql
SELECT name, press_editions_sold, press_distribution_area
FROM media
WHERE type = 'print' 
  AND press_editions_ivw = TRUE
  AND state = 'active'
ORDER BY press_editions_sold DESC;
```

#### Radio Stations by State Coverage
```sql
SELECT 
    name,
    rf_statewide,
    rf_broadcast_status_name,
    market_reach
FROM media
WHERE type = 'radio' AND state = 'active'
ORDER BY rf_statewide DESC, market_reach DESC;
```

### Shareholder Queries

#### Natural Persons vs Companies
```sql
SELECT 
    natural_person,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM shareholders
WHERE state = 'active'
GROUP BY natural_person;
```

#### Top Shareholders by Number of Owned Entities
```sql
SELECT 
    s.name,
    s.natural_person,
    COUNT(DISTINCT o.held_squuid) as entities_owned,
    SUM(o.capital_shares) as total_shares
FROM shareholders s
JOIN ownership_relations o ON s.squuid = o.holder_squuid
WHERE s.state = 'active' AND o.state = 'active'
GROUP BY s.squuid, s.name, s.natural_person
ORDER BY entities_owned DESC
LIMIT 20;
```

### Relationship Queries

#### Find Direct Owners of a Media (via Operators)
```sql
-- Example: Find who operates and potentially owns a specific media
WITH media_operators AS (
    SELECT holder_squuid
    FROM operation_relations
    WHERE held_squuid = '5be1a6b1-c47a-4cf2-8f64-f1f6583ec990'
      AND state = 'active'
)
SELECT 
    s.name,
    s.natural_person,
    s.city
FROM shareholders s
WHERE s.squuid IN (SELECT holder_squuid FROM media_operators);
```

#### Ownership Chain (Recursive)
```sql
-- Find all ultimate owners of a shareholder
WITH RECURSIVE ownership_chain AS (
    -- Base case: direct owners
    SELECT 
        holder_squuid,
        held_squuid,
        capital_shares,
        1 as depth,
        ARRAY[held_squuid] as path
    FROM ownership_relations
    WHERE held_squuid = 'target-shareholder-uuid'
      AND state = 'active'
    
    UNION ALL
    
    -- Recursive case: owners of owners
    SELECT 
        o.holder_squuid,
        oc.held_squuid,
        o.capital_shares * oc.capital_shares / 100.0 as capital_shares,
        oc.depth + 1,
        oc.path || o.holder_squuid
    FROM ownership_relations o
    JOIN ownership_chain oc ON o.held_squuid = oc.holder_squuid
    WHERE o.state = 'active'
      AND oc.depth < 10  -- Prevent infinite loops
      AND NOT (o.holder_squuid = ANY(oc.path))  -- Prevent cycles
)
SELECT DISTINCT
    s.name,
    s.natural_person,
    oc.capital_shares as effective_ownership,
    oc.depth
FROM ownership_chain oc
JOIN shareholders s ON oc.holder_squuid = s.squuid
ORDER BY oc.capital_shares DESC, oc.depth;
```

#### Media Empire Analysis
```sql
-- Find all media controlled by a shareholder (directly and indirectly)
WITH RECURSIVE controlled_entities AS (
    -- Start with the main shareholder
    SELECT squuid, name, 1 as depth
    FROM shareholders
    WHERE squuid = 'main-shareholder-uuid'
    
    UNION
    
    -- Add all owned shareholders
    SELECT s.squuid, s.name, ce.depth + 1
    FROM shareholders s
    JOIN ownership_relations o ON s.squuid = o.held_squuid
    JOIN controlled_entities ce ON o.holder_squuid = ce.squuid
    WHERE o.state = 'active' AND ce.depth < 10
)
SELECT DISTINCT
    m.name as media_name,
    m.type as media_type,
    m.market_reach,
    s.name as operated_by
FROM media m
JOIN operation_relations op ON m.squuid = op.held_squuid
JOIN controlled_entities ce ON op.holder_squuid = ce.squuid
JOIN shareholders s ON ce.squuid = s.squuid
WHERE m.state = 'active' AND op.state = 'active'
ORDER BY m.market_reach DESC NULLS LAST;
```

#### Cross-Ownership Network
```sql
-- Find shareholders that own each other (potential circular ownership)
SELECT 
    s1.name as shareholder_1,
    s2.name as shareholder_2,
    o1.capital_shares as s1_owns_s2,
    o2.capital_shares as s2_owns_s1
FROM ownership_relations o1
JOIN ownership_relations o2 ON o1.holder_squuid = o2.held_squuid 
                             AND o1.held_squuid = o2.holder_squuid
JOIN shareholders s1 ON o1.holder_squuid = s1.squuid
JOIN shareholders s2 ON o1.held_squuid = s2.squuid
WHERE o1.state = 'active' AND o2.state = 'active'
  AND o1.holder_squuid < o1.held_squuid  -- Avoid duplicates
ORDER BY o1.capital_shares DESC;
```

### Advanced Analytics

#### Market Concentration by Type
```sql
SELECT 
    type,
    COUNT(*) as total_media,
    SUM(market_reach) as total_market_reach,
    AVG(market_reach) as avg_market_reach,
    MAX(market_reach) as max_market_reach
FROM media
WHERE state = 'active' AND market_reach IS NOT NULL
GROUP BY type
ORDER BY total_market_reach DESC;
```

#### Top Media Groups
```sql
-- Group media by their operators and calculate total reach
SELECT 
    s.name as operator,
    s.natural_person,
    COUNT(DISTINCT m.squuid) as media_count,
    SUM(m.market_reach) as total_market_reach,
    ARRAY_AGG(DISTINCT m.type) as media_types
FROM shareholders s
JOIN operation_relations op ON s.squuid = op.holder_squuid
JOIN media m ON op.held_squuid = m.squuid
WHERE s.state = 'active' 
  AND op.state = 'active' 
  AND m.state = 'active'
  AND m.market_reach IS NOT NULL
GROUP BY s.squuid, s.name, s.natural_person
HAVING COUNT(DISTINCT m.squuid) >= 2
ORDER BY total_market_reach DESC
LIMIT 20;
```

## Data Import

### Using the Import Script

```bash
# Install requirements
pip install psycopg2-binary

# Import all data
python import_to_postgres.py --db kek --user postgres

# Import sample for testing
python import_to_postgres.py --db kek_test --user postgres --sample 10

# With authentication
python import_to_postgres.py --db kek --user myuser --password mypass --host localhost
```

### Manual Import Examples

#### Import Single Media Entity
```python
import json
import psycopg2

# Connect
conn = psycopg2.connect(dbname='kek', user='postgres')
cursor = conn.cursor()

# Load data
with open('docs/data/media/some-uuid.json') as f:
    data = json.load(f)

# Insert
cursor.execute("""
    INSERT INTO media (squuid, name, type, state)
    VALUES (%s, %s, %s, %s)
""", (data['squuid'], data['name'], data['type'], data['state']))

conn.commit()
```

#### Bulk Import with COPY
```sql
-- Create temporary staging table
CREATE TEMP TABLE media_staging (data JSONB);

-- Load JSON files (PostgreSQL 11+)
\copy media_staging FROM PROGRAM 'cat docs/data/media/*.json | jq -c .' WITH (FORMAT csv, QUOTE e'\x01', DELIMITER e'\x02');

-- Insert from staging
INSERT INTO media (squuid, name, type, state, market_reach)
SELECT 
    data->>'squuid',
    data->>'name',
    data->>'type',
    data->>'state',
    (data->>'marketReach')::decimal
FROM media_staging;
```

## Performance Tips

### Indexes
The schema includes indexes for common queries. Add more as needed:

```sql
-- For text search
CREATE INDEX idx_media_name_gin ON media USING gin(to_tsvector('german', name));

-- For date range queries
CREATE INDEX idx_media_control_date ON media(control_date);

-- For specific type queries
CREATE INDEX idx_media_print_sold ON media(press_editions_sold) 
WHERE type = 'print';
```

### Query Optimization

```sql
-- Use EXPLAIN ANALYZE to understand query performance
EXPLAIN ANALYZE
SELECT name, market_reach 
FROM media 
WHERE type = 'print' AND state = 'active'
ORDER BY market_reach DESC;

-- Materialize recursive queries for better performance
CREATE MATERIALIZED VIEW ownership_chains AS
WITH RECURSIVE ... ;

-- Refresh when data changes
REFRESH MATERIALIZED VIEW ownership_chains;
```

## Monitoring

### Data Quality Checks
```sql
-- Find media without operators
SELECT m.name, m.type
FROM media m
LEFT JOIN operation_relations op ON m.squuid = op.held_squuid
WHERE m.state = 'active' AND op.squuid IS NULL;

-- Find orphaned relationships
SELECT COUNT(*)
FROM ownership_relations o
LEFT JOIN shareholders s ON o.held_squuid = s.squuid
WHERE s.squuid IS NULL;

-- Check for circular ownership
WITH RECURSIVE cycles AS (
    SELECT holder_squuid, held_squuid, ARRAY[holder_squuid, held_squuid] as path
    FROM ownership_relations
    
    UNION
    
    SELECT c.holder_squuid, o.held_squuid, c.path || o.held_squuid
    FROM cycles c
    JOIN ownership_relations o ON c.held_squuid = o.holder_squuid
    WHERE NOT (o.held_squuid = ANY(c.path))
      AND array_length(c.path, 1) < 20
)
SELECT DISTINCT path
FROM cycles
WHERE held_squuid = holder_squuid;
```
