-- Query to analyze capital share changes for a specific ownership relationship over time

-- Example: Track how ownership percentage changed over time
SELECT * FROM get_ownership_change_timeline(
    '5be1a6b6-5c1b-48b1-ad15-85241452bf42',  -- holder_squuid
    '5be1a6b6-0a00-491b-9229-bfd0da590573'   -- held_squuid
);

-- Alternative: Manual query with additional analysis
WITH ownership_timeline AS (
    SELECT 
        ds.commit_date,
        ds.git_commit_hash,
        ds.commit_message,
        owr.capital_shares,
        owr.state,
        owr.complementary_partner,
        sh_holder.name as holder_name,
        sh_held.name as held_name,
        LAG(owr.capital_shares) OVER (ORDER BY ds.commit_date) as prev_shares,
        LAG(owr.state) OVER (ORDER BY ds.commit_date) as prev_state
    FROM data_snapshots ds
    JOIN ownership_relations_history owr ON owr.snapshot_id = ds.id
    JOIN shareholders_history sh_holder ON sh_holder.squuid = owr.holder_squuid AND sh_holder.snapshot_id = ds.id
    JOIN shareholders_history sh_held ON sh_held.squuid = owr.held_squuid AND sh_held.snapshot_id = ds.id
    WHERE owr.holder_squuid = '5be1a6b6-5c1b-48b1-ad15-85241452bf42'
        AND owr.held_squuid = '5be1a6b6-0a00-491b-9229-bfd0da590573'
)
SELECT 
    commit_date,
    git_commit_hash,
    holder_name,
    held_name,
    capital_shares,
    prev_shares,
    capital_shares - COALESCE(prev_shares, 0) as shares_change,
    state,
    prev_state,
    complementary_partner,
    CASE 
        WHEN prev_shares IS NULL THEN 'RELATIONSHIP CREATED'
        WHEN capital_shares != prev_shares THEN 'SHARES CHANGED'
        WHEN state != prev_state THEN 'STATE CHANGED'
        ELSE 'NO CHANGE'
    END as change_type
FROM ownership_timeline
ORDER BY commit_date DESC;

-- Query to find all ownership relationships that changed between two snapshots
WITH recent_snapshots AS (
    SELECT 
        id as snapshot_id,
        commit_date,
        git_commit_hash,
        ROW_NUMBER() OVER (ORDER BY commit_date DESC) as rn
    FROM data_snapshots
),
snapshot_current AS (
    SELECT snapshot_id, commit_date, git_commit_hash
    FROM recent_snapshots WHERE rn = 1
),
snapshot_previous AS (
    SELECT snapshot_id, commit_date, git_commit_hash
    FROM recent_snapshots WHERE rn = 2
)
SELECT 
    sh_holder.name as holder_name,
    sh_held.name as held_name,
    owr_prev.capital_shares as previous_shares,
    owr_curr.capital_shares as current_shares,
    owr_curr.capital_shares - COALESCE(owr_prev.capital_shares, 0) as shares_change_percentage,
    owr_prev.state as previous_state,
    owr_curr.state as current_state,
    sc.commit_date as current_date,
    sp.commit_date as previous_date,
    CASE 
        WHEN owr_prev.squuid IS NULL THEN 'NEW'
        WHEN owr_curr.squuid IS NULL THEN 'REMOVED'
        WHEN owr_prev.capital_shares != owr_curr.capital_shares THEN 'SHARES CHANGED'
        WHEN owr_prev.state != owr_curr.state THEN 'STATE CHANGED'
        ELSE 'NO CHANGE'
    END as change_type
FROM snapshot_current sc
CROSS JOIN snapshot_previous sp
FULL OUTER JOIN ownership_relations_history owr_curr 
    ON owr_curr.snapshot_id = sc.snapshot_id
FULL OUTER JOIN ownership_relations_history owr_prev
    ON owr_prev.snapshot_id = sp.snapshot_id
    AND owr_prev.holder_squuid = owr_curr.holder_squuid
    AND owr_prev.held_squuid = owr_curr.held_squuid
LEFT JOIN shareholders_history sh_holder 
    ON sh_holder.squuid = COALESCE(owr_curr.holder_squuid, owr_prev.holder_squuid)
    AND sh_holder.snapshot_id = sc.snapshot_id
LEFT JOIN shareholders_history sh_held
    ON sh_held.squuid = COALESCE(owr_curr.held_squuid, owr_prev.held_squuid)
    AND sh_held.snapshot_id = sc.snapshot_id
WHERE owr_prev.squuid IS NULL 
    OR owr_curr.squuid IS NULL 
    OR owr_prev.capital_shares != owr_curr.capital_shares
    OR owr_prev.state != owr_curr.state
ORDER BY change_type, holder_name, held_name;

-- Query to show top shareholders with most ownership changes over time
SELECT 
    sh.name as shareholder_name,
    sh.natural_person,
    COUNT(DISTINCT ds.id) as snapshots_with_changes,
    COUNT(DISTINCT owr.held_squuid) as unique_owned_entities,
    AVG(owr.capital_shares) as avg_capital_shares,
    MIN(ds.commit_date) as first_seen,
    MAX(ds.commit_date) as last_seen
FROM data_snapshots ds
JOIN ownership_relations_history owr ON owr.snapshot_id = ds.id
JOIN shareholders_history sh ON sh.squuid = owr.holder_squuid AND sh.snapshot_id = ds.id
WHERE owr.state = 'active'
GROUP BY sh.squuid, sh.name, sh.natural_person
HAVING COUNT(DISTINCT ds.id) > 1
ORDER BY snapshots_with_changes DESC, unique_owned_entities DESC
LIMIT 50;
