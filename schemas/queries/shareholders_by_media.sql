-- Find all shareholders (direct and indirect) controlling a media, including ownership percentage
WITH RECURSIVE controlling_shareholders AS (
    -- Start with the media
    SELECT m.squuid as media_squuid, op.holder_squuid as shareholder_squuid, 1 as depth, 1.0 as ownership_share
    FROM media m
    JOIN operation_relations op ON m.squuid = op.held_squuid
    WHERE m.squuid = '67068646-76fa-4f3d-92e2-cbeb87adbb26' AND m.state = 'active' AND op.state = 'active'

    UNION ALL

    -- Traverse up the ownership tree
    SELECT cs.media_squuid, o.holder_squuid as shareholder_squuid, cs.depth + 1, cs.ownership_share * (o.capital_shares / 100.0) as ownership_share
    FROM controlling_shareholders cs
    JOIN ownership_relations o ON cs.shareholder_squuid = o.held_squuid
    WHERE o.state = 'active' AND cs.depth < 10
)
SELECT
    s.squuid as shareholder_squuid,
    s.name as shareholder_name,
    s.natural_person,
    CASE
        WHEN MAX(cs.ownership_share) = 1 THEN 100
        ELSE ROUND((1 - EXP(SUM(CASE WHEN cs.ownership_share = 1 THEN NULL ELSE LN(1 - COALESCE(cs.ownership_share, 0)) END))) * 100, 2)
    END as ownership_percent
FROM controlling_shareholders cs
JOIN shareholders s ON cs.shareholder_squuid = s.squuid
GROUP BY s.squuid, s.name, s.natural_person
ORDER BY ownership_percent DESC NULLS LAST;

