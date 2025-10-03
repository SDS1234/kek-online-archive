# KEK Data Schema Documentation

This directory contains the schema definitions for the KEK (Kommission zur Ermittlung der Konzentration im Medienbereich) media concentration database.

## Overview

The KEK database tracks media entities (newspapers, magazines, radio stations, TV channels, and online media) and their ownership/operation relationships with shareholders (both natural persons and companies).

## Files

- **`media.schema.json`** - JSON Schema for media entities
- **`shareholder.schema.json`** - JSON Schema for shareholder entities
- **`postgresql-schema.sql`** - Complete PostgreSQL database schema

## Data Model

### Entity Types

1. **Media** - Media entities with types:
   - `print` - Newspapers and magazines
   - `online` - Online media services
   - `radio` - Radio stations
   - `tv` - Television channels

2. **Shareholders** - Owners and operators:
   - Natural persons (individuals)
   - Companies and organizations

3. **Organizations** - Supervising authorities and regulatory bodies

### Relationships

1. **Ownership** (`owns`/`ownedBy`)
   - Shareholders can own other shareholders
   - Includes capital share percentages (0-100%)
   - Can indicate complementary partnerships

2. **Operation** (`operates`/`operatedBy`)
   - Shareholders can operate media entities
   - Represents editorial/operational control

## Media Entity Schema

### Common Fields

All media types share these core fields:

```json
{
  "squuid": "UUID",           // Unique identifier
  "name": "string",           // Media name
  "type": "print|online|radio|tv",
  "state": "active|archived",
  "controlDate": "ISO 8601",  // Last update date
  "marketReach": "number",    // Market reach percentage
  "organization": {...}       // Supervising organization
}
```

### Type-Specific Fields

#### Print Media
- `pressType` - Type (newspaper/magazine)
- `pressMagazineType` - Magazine classification
- `pressPublishingIntervals` - Issues per year
- `pressEditionsSold` - Circulation numbers
- `pressDistributionArea` - Distribution region
- `pressEditionsIVW` - IVW verified

#### Online Media
- `onlineOfferType` - Type of online service
- `onlineIVWPI` - Page impressions (IVW)
- `onlineVisitsIVW` - Visit counts
- `onlineAGOF` - AGOF metrics

#### Radio/TV
- `rfBroadcastStatus` - Broadcasting status
- `rfCategory` - Program category
- `rfPublicPrivate` - Public vs. private broadcaster
- `rfStatewide` - Statewide coverage
- `rfLicenseFrom`/`rfLicenseUntil` - License period
- `rfSupervisingAuthority` - Regulatory authority
- `rfShoppingChannel` - Shopping channel flag

### Relationships in Media

```json
{
  "operatedBy": [
    {
      "type": "operate",
      "holder": {
        "squuid": "UUID",
        "name": "string"
      },
      "state": "active"
    }
  ]
}
```

## Shareholder Entity Schema

### Core Fields

```json
{
  "squuid": "UUID",
  "name": "string",
  "state": "active|archived",
  "naturalPerson": "boolean",  // true for individuals
  "pseudoCompany": "boolean"
}
```

### Address Information

- `corporationName` - Official corporation name
- `street`, `streetNumber` - Street address
- `zipcode`, `city` - Postal address
- `co` - Care of address

### Company Types

- `limitedPartnership` - KG (Kommanditgesellschaft)
- `supplierConsortium` - Supplier consortium

### Relationships in Shareholders

```json
{
  "ownedBy": [
    {
      "type": "own",
      "capitalShares": 50.0,        // Percentage
      "complementaryPartner": false,
      "holder": {
        "squuid": "UUID",
        "name": "string"
      },
      "state": "active"
    }
  ],
  "owns": [
    {
      "type": "own",
      "capitalShares": 100.0,
      "held": {
        "squuid": "UUID",
        "name": "string"
      },
      "state": "active"
    }
  ],
  "operates": [
    {
      "type": "operate",
      "held": {
        "squuid": "UUID",
        "name": "string"
      },
      "state": "active"
    }
  ]
}
```

## PostgreSQL Schema

### Main Tables

1. **`media`** - All media entities
2. **`shareholders`** - All shareholders and operators
3. **`organizations`** - Supervising organizations
4. **`ownership_relations`** - Who owns whom (shareholder ↔ shareholder)
5. **`operation_relations`** - Who operates what (shareholder → media)

### Support Tables

- **`languages`** / **`media_languages`** - Available languages for media
- **`platform_operators`** - Platform distribution information
- **`shareholder_organizations`** - Shareholder-organization associations

### Useful Views

1. **`shareholder_owners`** - Ownership relationships with details
2. **`shareholder_media_operations`** - Operation relationships with details
3. **`active_media_with_reach`** - Active media sorted by market reach

### Design Decisions: ENUMs vs Lookup Tables

The PostgreSQL schema uses a hybrid approach for lookup values:

**ENUMs (for small, stable value sets):**
- `press_type` - 3 values (Zeitung, Zeitschrift, E-Paper)
- `press_magazine_type` - 2 values (Publikumszeitschrift, Fachzeitschrift)
- `online_offer_type` - 1 value (Online Medienangebot)
- `rf_broadcast_status` - 3 values (auf Sendung, Noch nicht auf Sendung, Sendebetrieb eingestellt)

**Lookup Tables (for larger, potentially growing sets):**
- `rf_categories` - 7+ values (Vollprogramm, various Spartenprogramm types, Teleshopping)

This approach provides:
- Type safety and data integrity for stable values (ENUMs)
- Flexibility for categories that may expand (lookup tables)
- Better query performance (no joins needed for ENUMs)
- Easy extensibility (new categories can be added without schema changes)

### Example Queries

#### Find all owners of a media entity (indirect via operators)

```sql
SELECT DISTINCT s.*
FROM media m
JOIN operation_relations op ON m.squuid = op.held_squuid
JOIN shareholders s ON op.holder_squuid = s.squuid
WHERE m.squuid = 'media-uuid-here';
```

#### Get ownership chain for a shareholder

```sql
WITH RECURSIVE ownership_chain AS (
    -- Base case: direct owners
    SELECT 
        holder_squuid AS owner_squuid,
        held_squuid AS shareholder_squuid,
        capital_shares,
        1 AS depth
    FROM ownership_relations
    WHERE held_squuid = 'shareholder-uuid-here'
    
    UNION ALL
    
    -- Recursive case: owners of owners
    SELECT 
        o.holder_squuid,
        oc.shareholder_squuid,
        o.capital_shares * oc.capital_shares / 100.0,
        oc.depth + 1
    FROM ownership_relations o
    JOIN ownership_chain oc ON o.held_squuid = oc.owner_squuid
    WHERE oc.depth < 10  -- Prevent infinite recursion
)
SELECT DISTINCT 
    s.name,
    oc.capital_shares,
    oc.depth
FROM ownership_chain oc
JOIN shareholders s ON oc.owner_squuid = s.squuid
ORDER BY oc.depth, oc.capital_shares DESC;
```

#### Find media with highest market reach by type

```sql
SELECT type, name, market_reach
FROM media
WHERE state = 'active' AND market_reach IS NOT NULL
ORDER BY type, market_reach DESC;
```

## Data Source

The data comes from the KEK's undocumented JSON API:

- Media list: `https://medienvielfaltsmonitor.de/api/v1/media/`
- Shareholders list: `https://medienvielfaltsmonitor.de/api/v1/shareholders/`
- Individual entities: `https://medienvielfaltsmonitor.de/api/v1/media/{uuid}` and `https://medienvielfaltsmonitor.de/api/v1/shareholders/{uuid}`

## Validation

You can validate JSON files against the schemas using tools like:

```bash
# Using ajv-cli
ajv validate -s schemas/media.schema.json -d "docs/data/media/*.json"
ajv validate -s schemas/shareholder.schema.json -d "docs/data/shareholders/*.json"
```

```python
# Using Python jsonschema
import json
from jsonschema import validate

with open('schemas/media.schema.json') as f:
    media_schema = json.load(f)

with open('docs/data/media/some-uuid.json') as f:
    media_data = json.load(f)

validate(instance=media_data, schema=media_schema)
```

## Notes

1. **UUIDs**: All entities use UUID v4 as unique identifiers (`squuid`)
2. **Relationships**: Always include a `squuid` for the relationship itself, separate from the entity UUIDs
3. **Capital Shares**: Can exceed 100% in total when multiple owners exist (represents individual stakes)
4. **State**: Both entities and relationships have states (`active` or `archived`)
5. **Complementary Partners**: In German law (GbR, KG), complementary partners have special status
6. **Market Reach**: Calculated/measured reach as a percentage, methodology not documented in API

## Copyright

All data is copyright [Kommission zur Ermittlung der Konzentration im Medienbereich (KEK)](https://www.kek-online.de/impressum).
