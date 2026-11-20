# KEK Database Schema Diagram

## Entity Relationship Overview

```
┌─────────────────┐
│  Organizations  │
│  (Authorities)  │
└────────┬────────┘
         │
         │ supervises
         ▼
┌─────────────────┐                    ┌─────────────────┐
│  Shareholders   │◄───────────────────┤      Media      │
│   (Holders)     │   operated by      │  (Print/Radio/  │
│                 │                    │   TV/Online)    │
│  - Natural      │                    │                 │
│    Person       │                    │  - Print        │
│  - Company      │                    │  - Online       │
└────────┬────────┘                    │  - Radio        │
         │                             │  - TV           │
         │                             └─────────────────┘
         │ owns
         │ (capital shares %)
         │
         ▼
┌─────────────────┐
│  Shareholders   │
│   (Held)        │
└─────────────────┘
```

## Detailed Schema Structure

### Core Entities

```
organizations
├── squuid (PK, UUID)
├── name
├── full_name
└── type

media
├── squuid (PK, UUID)
├── name
├── type (print|online|radio|tv)
├── state (active|archived)
├── control_date
├── organization_squuid (FK → organizations)
│
├── [General Fields]
│   ├── description
│   ├── market_reach
│   └── matched_names[]
│
├── [Press Fields]
│   ├── press_type_squuid (FK → press_types)
│   ├── press_magazine_type_squuid (FK → press_magazine_types)
│   ├── press_publishing_intervals
│   ├── press_editions_sold
│   └── press_distribution_area
│
├── [Online Fields]
│   ├── online_offer_type_squuid (FK → online_offer_types)
│   ├── online_ivwpi
│   ├── online_visits_ivw
│   └── online_agof
│
└── [Radio/TV Fields]
    ├── rf_broadcast_status_squuid (FK → rf_broadcast_statuses)
    ├── rf_category_squuid (FK → rf_categories)
    ├── rf_public_private
    ├── rf_statewide
    └── rf_supervising_authority_squuid (FK → organizations)

shareholders
├── squuid (PK, UUID)
├── name
├── state (active|archived)
├── natural_person (boolean)
├── pseudo_company (boolean)
├── control_date
│
├── [Address]
│   ├── corporation_name
│   ├── street / street_number
│   ├── zipcode / city
│   └── co
│
└── [Additional Info]
    ├── other_media_activities
    ├── note
    └── credits
```

### Relationship Tables

```
ownership_relations
├── squuid (PK, UUID)
├── holder_squuid (FK → shareholders)
├── held_squuid (FK → shareholders)
├── capital_shares (0-100%)
├── complementary_partner
└── state

operation_relations
├── squuid (PK, UUID)
├── holder_squuid (FK → shareholders)
├── held_squuid (FK → media)
└── state
```

### Support Tables

```
Lookup Tables (for KEK-controlled values):

press_types
├── squuid (PK, UUID)
└── name (UNIQUE)

press_magazine_types
├── squuid (PK, UUID)
└── name (UNIQUE)

online_offer_types
├── squuid (PK, UUID)
└── name (UNIQUE)

rf_broadcast_statuses
├── squuid (PK, UUID)
└── name (UNIQUE)

rf_categories
├── squuid (PK, UUID)
└── name (UNIQUE)

shareholder_organizations
├── shareholder_squuid (FK → shareholders)
└── organization_squuid (FK → organizations)

languages
├── id (PK)
└── name

media_languages
├── media_squuid (FK → media)
└── language_id (FK → languages)

platform_operators
├── id (PK)
├── media_squuid (FK → media)
├── name
└── distribution_type_name
```

## Relationship Cardinalities

```
Shareholder ──1:N─► Ownership Relations ◄─N:1── Shareholder
    (holder)                                      (held)

Shareholder ──1:N─► Operation Relations ◄─N:1── Media
    (holder)                                      (held)

Shareholder ──N:M─► Organizations
                (via shareholder_organizations)

Media ──N:1─► Organizations
         (supervising authority)

Media ──N:1─► Press Types
         (press type lookup)

Media ──N:1─► Press Magazine Types
         (magazine type lookup)

Media ──N:1─► Online Offer Types
         (online offer type lookup)

Media ──N:1─► RF Broadcast Statuses
         (broadcast status lookup)

Media ──N:1─► RF Categories
         (radio/TV category lookup)

Media ──N:M─► Languages
         (via media_languages)

Media ──1:N─► Platform Operators
```

## Example Data Flow

### Ownership Chain Example

```
Natural Person: "Schmidt, Hans"
    │
    │ owns 100%
    ▼
Company: "Schmidt Media GmbH"
    │
    │ owns 60%
    ▼
Company: "Regional Verlag AG"
    │
    │ operates
    ▼
Media: "Tageszeitung Nord" (print)
```

SQL Representation:
```sql
-- Shareholders
INSERT INTO shareholders (squuid, name, natural_person) VALUES
  ('uuid-1', 'Schmidt, Hans', true),
  ('uuid-2', 'Schmidt Media GmbH', false),
  ('uuid-3', 'Regional Verlag AG', false);

-- Ownership
INSERT INTO ownership_relations (squuid, holder_squuid, held_squuid, capital_shares) VALUES
  ('uuid-o1', 'uuid-1', 'uuid-2', 100.0),
  ('uuid-o2', 'uuid-2', 'uuid-3', 60.0);

-- Media
INSERT INTO media (squuid, name, type) VALUES
  ('uuid-m1', 'Tageszeitung Nord', 'print');

-- Operation
INSERT INTO operation_relations (squuid, holder_squuid, held_squuid) VALUES
  ('uuid-op1', 'uuid-3', 'uuid-m1');
```

## Key Design Decisions

### 1. UUID as Primary Keys
- All entities use UUIDs (`squuid`) as primary keys
- Enables distributed data collection without conflicts
- Matches the KEK API structure

### 2. Nullable Type-Specific Fields
- Media table contains all fields for all types
- Type-specific fields are nullable
- Alternative: Separate tables per type (more normalized but more complex)

### 3. Separate Relationship Tables
- `ownership_relations`: shareholder → shareholder
- `operation_relations`: shareholder → media
- Each relationship has its own UUID
- Enables temporal tracking and metadata

### 4. Lookup Tables for KEK-Controlled Values
**Design priority: Adaptability to external data source**

The KEK source database is **outside our control**, so the schema prioritizes adaptability:

**ENUMs (only for schema-level types):**
- Core structural types: `media_type`, `entity_state`, `relation_type`
- These are fundamental to the schema design itself
- Extremely unlikely to change

**Lookup Tables (for all KEK data):**
- All KEK-controlled value sets use lookup tables
- `press_types`, `press_magazine_types`, `online_offer_types`, `rf_broadcast_statuses`, `rf_categories`
- Import script automatically creates new lookup values
- No schema changes needed when KEK adds new types
- Ensures forward compatibility with KEK source changes

**Benefits:**
- **Adaptability**: New values added automatically during import
- **No Downtime**: No ALTER TYPE operations required
- **Forward Compatible**: Handles unexpected changes gracefully
- **Minimal Maintenance**: Schema evolves with the data

This approach trades minor query performance (join vs enum) for significant operational flexibility and reliability when dealing with an external data source.

### 5. State on Relationships
- Both entities and relationships have `state` field
- Enables archiving without deletion
- Preserves historical data

## Indexes Strategy

Performance-critical indexes:
- Entity primary keys (automatic)
- Foreign keys in relationship tables
- `media.type` and `media.state` (filtering)
- `shareholders.natural_person` (filtering)
- `media.market_reach` (sorting)

## Query Patterns

### Find all ultimate owners of a media
```sql
WITH RECURSIVE operators AS (
  SELECT holder_squuid FROM operation_relations
  WHERE held_squuid = 'media-uuid'
),
ownership_chain AS (
  SELECT holder_squuid, held_squuid, capital_shares, 1 as depth
  FROM ownership_relations
  WHERE held_squuid IN (SELECT holder_squuid FROM operators)
  
  UNION ALL
  
  SELECT o.holder_squuid, oc.held_squuid, 
         o.capital_shares * oc.capital_shares / 100, 
         oc.depth + 1
  FROM ownership_relations o
  JOIN ownership_chain oc ON o.held_squuid = oc.holder_squuid
  WHERE oc.depth < 10
)
SELECT DISTINCT s.name, MAX(oc.capital_shares) as effective_share
FROM ownership_chain oc
JOIN shareholders s ON oc.holder_squuid = s.squuid
GROUP BY s.name;
```

### Find all media controlled by a shareholder
```sql
WITH RECURSIVE owned_entities AS (
  SELECT squuid FROM shareholders WHERE squuid = 'shareholder-uuid'
  
  UNION
  
  SELECT or2.held_squuid
  FROM ownership_relations or2
  JOIN owned_entities oe ON or2.holder_squuid = oe.squuid
)
SELECT DISTINCT m.*
FROM media m
JOIN operation_relations op ON m.squuid = op.held_squuid
WHERE op.holder_squuid IN (SELECT squuid FROM owned_entities);
```

## Normalization Level

The schema is at **3rd Normal Form (3NF)** with some pragmatic denormalization:

**Normalized aspects:**
- No repeating groups
- All non-key attributes depend on the primary key
- No transitive dependencies

**Denormalized aspects:**
- Type-specific fields in single media table
- Name fields duplicated alongside UUIDs
- Lookup table references stored with names

This provides a good balance between:
- Data integrity (normalization)
- Query performance (denormalization)
- Schema simplicity (single media table)
