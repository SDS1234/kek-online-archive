-- Find all media controlled by a shareholder (directly and indirectly), including ownership percentage
WITH RECURSIVE controlled_entities AS (
    -- Start with the main shareholder
    SELECT squuid, name, 1 as depth, 1.0 as ownership_share
    FROM shareholders
    WHERE squuid = '5be1a6b6-5c1b-48b1-ad15-85241452bf42'

    UNION ALL

    -- Add all owned shareholders, multiplying ownership shares
    SELECT s.squuid, s.name, ce.depth + 1, ce.ownership_share * (o.capital_shares / 100.0) as ownership_share
    FROM shareholders s
             JOIN ownership_relations o ON s.squuid = o.held_squuid
             JOIN controlled_entities ce ON o.holder_squuid = ce.squuid
    WHERE o.state = 'active' AND ce.depth < 10
)
SELECT
    m.squuid as media_squuid,
    m.name as media_name,
    m.type as media_type,
    m.market_reach,
    CASE
        WHEN MAX(ce.ownership_share) = 1 THEN 100
        ELSE ROUND((1 - EXP(SUM(CASE WHEN ce.ownership_share = 1 THEN NULL ELSE LN(1 - COALESCE(ce.ownership_share, 0)) END))) * 100, 2)
        END as ownership
FROM media m
         JOIN operation_relations op ON m.squuid = op.held_squuid
         JOIN controlled_entities ce ON op.holder_squuid = ce.squuid
         JOIN shareholders s ON ce.squuid = s.squuid
WHERE m.state = 'active' AND op.state = 'active'
GROUP BY m.squuid, m.name, m.type, m.market_reach
ORDER BY ownership DESC NULLS LAST, m.market_reach DESC NULLS LAST;