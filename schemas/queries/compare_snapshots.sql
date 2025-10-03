-- Query to compare ownership structures between two specific dates/commits
-- Useful for seeing what changed between two points in time

-- Example: Compare ownership structure between two commits
WITH snapshot1 AS (
    SELECT ds.id as snapshot_id, ds.commit_date, ds.git_commit_hash
    FROM data_snapshots ds
    ORDER BY ds.commit_date DESC
    LIMIT 1 OFFSET 0  -- Most recent snapshot
),
snapshot2 AS (
    SELECT ds.id as snapshot_id, ds.commit_date, ds.git_commit_hash
    FROM data_snapshots ds
    ORDER BY ds.commit_date DESC
    LIMIT 1 OFFSET 1  -- Previous snapshot
),
ownership_current AS (
    SELECT 
        owr.holder_squuid,
        owr.held_squuid,
        owr.capital_shares,
        owr.state,
        sh_holder.name as holder_name,
        sh_held.name as held_name
    FROM snapshot1 s1
    JOIN ownership_relations_history owr ON owr.snapshot_id = s1.snapshot_id
    JOIN shareholders_history sh_holder ON sh_holder.squuid = owr.holder_squuid AND sh_holder.snapshot_id = s1.snapshot_id
    JOIN shareholders_history sh_held ON sh_held.squuid = owr.held_squuid AND sh_held.snapshot_id = s1.snapshot_id
),
ownership_previous AS (
    SELECT 
        owr.holder_squuid,
        owr.held_squuid,
        owr.capital_shares,
        owr.state,
        sh_holder.name as holder_name,
        sh_held.name as held_name
    FROM snapshot2 s2
    JOIN ownership_relations_history owr ON owr.snapshot_id = s2.snapshot_id
    JOIN shareholders_history sh_holder ON sh_holder.squuid = owr.holder_squuid AND sh_holder.snapshot_id = s2.snapshot_id
    JOIN shareholders_history sh_held ON sh_held.squuid = owr.held_squuid AND sh_held.snapshot_id = s2.snapshot_id
)
SELECT 
    COALESCE(oc.holder_name, op.holder_name) as holder_name,
    COALESCE(oc.held_name, op.held_name) as held_name,
    op.capital_shares as previous_shares,
    oc.capital_shares as current_shares,
    op.state as previous_state,
    oc.state as current_state,
    CASE 
        WHEN op.holder_squuid IS NULL THEN 'NEW OWNERSHIP'
        WHEN oc.holder_squuid IS NULL THEN 'OWNERSHIP REMOVED'
        WHEN op.capital_shares != oc.capital_shares THEN 'SHARES CHANGED'
        WHEN op.state != oc.state THEN 'STATE CHANGED'
        ELSE 'NO CHANGE'
    END as change_type,
    (SELECT commit_date FROM snapshot1) as current_date,
    (SELECT commit_date FROM snapshot2) as previous_date
FROM ownership_current oc
FULL OUTER JOIN ownership_previous op 
    ON oc.holder_squuid = op.holder_squuid 
    AND oc.held_squuid = op.held_squuid
WHERE op.holder_squuid IS NULL 
    OR oc.holder_squuid IS NULL 
    OR op.capital_shares != oc.capital_shares
    OR op.state != oc.state
ORDER BY change_type, holder_name, held_name;

-- Query to compare media operations between two snapshots
WITH snapshot1 AS (
    SELECT ds.id as snapshot_id, ds.commit_date, ds.git_commit_hash
    FROM data_snapshots ds
    ORDER BY ds.commit_date DESC
    LIMIT 1 OFFSET 0  -- Most recent snapshot
),
snapshot2 AS (
    SELECT ds.id as snapshot_id, ds.commit_date, ds.git_commit_hash
    FROM data_snapshots ds
    ORDER BY ds.commit_date DESC
    LIMIT 1 OFFSET 1  -- Previous snapshot
),
operations_current AS (
    SELECT 
        opr.holder_squuid,
        opr.held_squuid,
        opr.state,
        sh.name as holder_name,
        m.name as media_name,
        m.type as media_type
    FROM snapshot1 s1
    JOIN operation_relations_history opr ON opr.snapshot_id = s1.snapshot_id
    JOIN shareholders_history sh ON sh.squuid = opr.holder_squuid AND sh.snapshot_id = s1.snapshot_id
    JOIN media_history m ON m.squuid = opr.held_squuid AND m.snapshot_id = s1.snapshot_id
),
operations_previous AS (
    SELECT 
        opr.holder_squuid,
        opr.held_squuid,
        opr.state,
        sh.name as holder_name,
        m.name as media_name,
        m.type as media_type
    FROM snapshot2 s2
    JOIN operation_relations_history opr ON opr.snapshot_id = s2.snapshot_id
    JOIN shareholders_history sh ON sh.squuid = opr.holder_squuid AND sh.snapshot_id = s2.snapshot_id
    JOIN media_history m ON m.squuid = opr.held_squuid AND m.snapshot_id = s2.snapshot_id
)
SELECT 
    COALESCE(oc.holder_name, op.holder_name) as operator_name,
    COALESCE(oc.media_name, op.media_name) as media_name,
    COALESCE(oc.media_type, op.media_type) as media_type,
    op.state as previous_state,
    oc.state as current_state,
    CASE 
        WHEN op.holder_squuid IS NULL THEN 'NEW OPERATION'
        WHEN oc.holder_squuid IS NULL THEN 'OPERATION ENDED'
        WHEN op.state != oc.state THEN 'STATE CHANGED'
        ELSE 'NO CHANGE'
    END as change_type,
    (SELECT commit_date FROM snapshot1) as current_date,
    (SELECT commit_date FROM snapshot2) as previous_date
FROM operations_current oc
FULL OUTER JOIN operations_previous op 
    ON oc.holder_squuid = op.holder_squuid 
    AND oc.held_squuid = op.held_squuid
WHERE op.holder_squuid IS NULL 
    OR oc.holder_squuid IS NULL 
    OR op.state != oc.state
ORDER BY change_type, operator_name, media_name;

-- Query to list all available snapshots for comparison
SELECT 
    id,
    commit_date,
    git_commit_hash,
    commit_message,
    media_count,
    shareholders_count,
    ownership_relations_count,
    operation_relations_count
FROM snapshot_timeline
ORDER BY commit_date DESC;
