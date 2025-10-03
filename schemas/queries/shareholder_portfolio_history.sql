-- Query to view how a shareholder's media portfolio has changed over time
-- Replace the UUID with the actual shareholder squuid you want to track

-- Example: Get all portfolio changes for a shareholder
SELECT * FROM get_shareholder_portfolio_timeline('5be1a6b6-5c1b-48b1-ad15-85241452bf42');

-- Alternative: Manual query showing more details with comparison to current
SELECT 
    ds.commit_date,
    ds.git_commit_hash,
    ds.commit_message,
    sh.name as shareholder_name,
    m.name as media_name,
    m.type as media_type,
    m.market_reach,
    opr.state as operation_state,
    -- Check if this relationship still exists in current data
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM operation_relations curr_opr 
            WHERE curr_opr.holder_squuid = sh.squuid 
            AND curr_opr.held_squuid = m.squuid
            AND curr_opr.state = 'active'
        ) THEN 'CURRENT'
        ELSE 'HISTORICAL'
    END as status
FROM data_snapshots ds
JOIN shareholders_history sh ON sh.snapshot_id = ds.id
JOIN operation_relations_history opr ON opr.holder_squuid = sh.squuid AND opr.snapshot_id = ds.id
JOIN media_history m ON m.squuid = opr.held_squuid AND m.snapshot_id = ds.id
WHERE sh.squuid = '5be1a6b6-5c1b-48b1-ad15-85241452bf42'
    AND opr.state = 'active'
    AND m.state = 'active'
ORDER BY ds.commit_date DESC, m.name;

-- Query to detect when a shareholder acquired or divested media
WITH portfolio_changes AS (
    SELECT 
        ds.commit_date,
        ds.git_commit_hash,
        sh.squuid as shareholder_squuid,
        sh.name as shareholder_name,
        m.squuid as media_squuid,
        m.name as media_name,
        m.type as media_type,
        LAG(m.squuid) OVER (PARTITION BY sh.squuid, m.squuid ORDER BY ds.commit_date) as prev_media_squuid
    FROM data_snapshots ds
    JOIN shareholders_history sh ON sh.snapshot_id = ds.id
    LEFT JOIN operation_relations_history opr ON opr.holder_squuid = sh.squuid AND opr.snapshot_id = ds.id AND opr.state = 'active'
    LEFT JOIN media_history m ON m.squuid = opr.held_squuid AND m.snapshot_id = ds.id AND m.state = 'active'
    WHERE sh.squuid = '5be1a6b6-5c1b-48b1-ad15-85241452bf42'
)
SELECT 
    commit_date,
    git_commit_hash,
    shareholder_name,
    media_name,
    media_type,
    CASE 
        WHEN prev_media_squuid IS NULL AND media_squuid IS NOT NULL THEN 'ACQUIRED'
        WHEN prev_media_squuid IS NOT NULL AND media_squuid IS NULL THEN 'DIVESTED'
        ELSE 'NO CHANGE'
    END as change_type
FROM portfolio_changes
WHERE media_squuid IS NOT NULL OR prev_media_squuid IS NOT NULL
ORDER BY commit_date DESC, media_name;

-- Query to show portfolio statistics over time
SELECT 
    ds.commit_date,
    ds.git_commit_hash,
    sh.name as shareholder_name,
    COUNT(DISTINCT m.squuid) as total_media,
    COUNT(DISTINCT CASE WHEN m.type = 'print' THEN m.squuid END) as print_media,
    COUNT(DISTINCT CASE WHEN m.type = 'online' THEN m.squuid END) as online_media,
    COUNT(DISTINCT CASE WHEN m.type = 'radio' THEN m.squuid END) as radio_media,
    COUNT(DISTINCT CASE WHEN m.type = 'tv' THEN m.squuid END) as tv_media,
    SUM(m.market_reach) as total_market_reach
FROM data_snapshots ds
JOIN shareholders_history sh ON sh.snapshot_id = ds.id
LEFT JOIN operation_relations_history opr ON opr.holder_squuid = sh.squuid AND opr.snapshot_id = ds.id AND opr.state = 'active'
LEFT JOIN media_history m ON m.squuid = opr.held_squuid AND m.snapshot_id = ds.id AND m.state = 'active'
WHERE sh.squuid = '5be1a6b6-5c1b-48b1-ad15-85241452bf42'
GROUP BY ds.commit_date, ds.git_commit_hash, sh.name
ORDER BY ds.commit_date DESC;
