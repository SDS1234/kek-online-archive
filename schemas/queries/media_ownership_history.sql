-- Query to view how ownership of a specific media entity has changed over time
-- Replace the UUID with the actual media squuid you want to track

-- Example: Get all ownership changes for a media entity
SELECT * FROM get_media_ownership_timeline('67068646-76fa-4f3d-92e2-cbeb87adbb26');

-- Alternative: Manual query showing more details
SELECT 
    ds.commit_date,
    ds.git_commit_hash,
    ds.commit_message,
    m.name as media_name,
    m.type as media_type,
    m.market_reach,
    sh.name as operator_name,
    sh.natural_person as operator_is_person,
    opr.state as operation_state
FROM data_snapshots ds
JOIN media_history m ON m.snapshot_id = ds.id
JOIN operation_relations_history opr ON opr.held_squuid = m.squuid AND opr.snapshot_id = ds.id
JOIN shareholders_history sh ON sh.squuid = opr.holder_squuid AND sh.snapshot_id = ds.id
WHERE m.squuid = '67068646-76fa-4f3d-92e2-cbeb87adbb26'
ORDER BY ds.commit_date DESC, sh.name;

-- Query to detect when a media's operator changed
WITH operator_changes AS (
    SELECT 
        ds.commit_date,
        ds.git_commit_hash,
        m.squuid as media_squuid,
        m.name as media_name,
        sh.squuid as operator_squuid,
        sh.name as operator_name,
        LAG(sh.squuid) OVER (PARTITION BY m.squuid ORDER BY ds.commit_date) as prev_operator_squuid,
        LAG(sh.name) OVER (PARTITION BY m.squuid ORDER BY ds.commit_date) as prev_operator_name
    FROM data_snapshots ds
    JOIN media_history m ON m.snapshot_id = ds.id
    JOIN operation_relations_history opr ON opr.held_squuid = m.squuid AND opr.snapshot_id = ds.id AND opr.state = 'active'
    JOIN shareholders_history sh ON sh.squuid = opr.holder_squuid AND sh.snapshot_id = ds.id
    WHERE m.squuid = '67068646-76fa-4f3d-92e2-cbeb87adbb26'
)
SELECT 
    commit_date,
    git_commit_hash,
    media_name,
    operator_name as new_operator,
    prev_operator_name as previous_operator
FROM operator_changes
WHERE prev_operator_squuid IS NULL OR operator_squuid != prev_operator_squuid
ORDER BY commit_date DESC;
