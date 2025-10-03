-- PostgreSQL Schema for KEK (Kommission zur Ermittlung der Konzentration im Medienbereich) Database
-- This schema represents media entities, shareholders, and their relationships

-- ============================================================================
-- ENUM TYPES (for truly stable, schema-level types)
-- ============================================================================

CREATE TYPE media_type AS ENUM ('print', 'online', 'radio', 'tv');
CREATE TYPE entity_state AS ENUM ('active', 'archived');
CREATE TYPE relation_type AS ENUM ('own', 'operate');

-- ============================================================================
-- LOOKUP TABLES (for KEK-controlled value sets that may change)
-- ============================================================================
-- Using lookup tables instead of ENUMs for better adaptability to changes
-- in the source KEK database which is outside our control

CREATE TABLE press_types (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE press_types IS 'Press types (Zeitung, Zeitschrift, E-Paper) - lookup table for flexibility';

-- Insert with actual squuids from KEK source
INSERT INTO press_types (squuid, name) VALUES
    ('5be1a6b0-4e68-459d-a5ee-da3974114c2a', 'E-Paper'),
    ('5be1a6b0-8202-4312-8190-cd96a1973f23', 'Zeitschrift'),
    ('5be1a6b0-e4cc-4064-9625-597855abfd7c', 'Zeitung');

CREATE TABLE press_magazine_types (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE press_magazine_types IS 'Magazine types (Publikumszeitschrift, Fachzeitschrift) - lookup table for flexibility';

-- Insert with actual squuids from KEK source
INSERT INTO press_magazine_types (squuid, name) VALUES
    ('5be1a6b0-015d-43da-8228-4bcff73d397c', 'Fachzeitschrift'),
    ('5be1a6b0-bff8-40db-a254-72d8fa6d3386', 'Publikumszeitschrift');

CREATE TABLE online_offer_types (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE online_offer_types IS 'Online offer types - lookup table for flexibility';

-- Insert with actual squuids from KEK source
INSERT INTO online_offer_types (squuid, name) VALUES
    ('5be1a6b0-e359-4db0-9c54-8ab7d725db5e', 'Online Medienangebot');

CREATE TABLE rf_broadcast_statuses (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rf_broadcast_statuses IS 'Radio/TV broadcast statuses - lookup table for flexibility';

-- Insert with actual squuids from KEK source
INSERT INTO rf_broadcast_statuses (squuid, name) VALUES
    ('5be1a6ad-52de-429b-89ff-5a6ce723e4ab', 'Noch nicht auf Sendung'),
    ('5be1a6ad-32b3-4ae8-b086-34ac62794f08', 'Sendebetrieb eingestellt'),
    ('5be1a6ad-6a90-49bf-9940-ae4616389a88', 'auf Sendung');

CREATE TABLE rf_categories (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rf_categories IS 'Radio/TV program categories (e.g., Vollprogramm, Spartenprogramm)';

-- Insert with actual squuids from KEK source
INSERT INTO rf_categories (squuid, name) VALUES
    ('5be1a6ad-063c-4208-94e1-5216fef7a724', 'Vollprogramm'),
    ('5be1a6ad-88f5-40c4-8a67-1f29db7c9aa8', 'Spartenprogramm (Information/Dokumentation)'),
    ('5be1a6ad-59ef-453a-9d47-fa4b4ab0b1a4', 'Spartenprogramm (Kinder)'),
    ('5be1a6ad-10a1-4d0f-be3f-dc7e8cdd350a', 'Spartenprogramm (Musik)'),
    ('5be1a6ad-5d06-4b68-96e4-33a2746127f9', 'Spartenprogramm (Nachrichten)'),
    ('5be1a6ad-bc95-453f-89a7-4577b71d9c46', 'Spartenprogramm (Sport)'),
    ('5be1a6ad-211a-4a65-b05a-b318333ba3f5', 'Spartenprogramm (Unterhaltung)'),
    ('5be1a6ad-f2e6-4d45-9ffd-1be10a57e0b0', 'Spartenprogramm (Sonstiges)'),
    ('5be1a6ad-6b1a-4de6-924f-727ccb20e81b', 'Teleshopping');

-- ============================================================================
-- ORGANIZATIONS TABLE
-- ============================================================================

CREATE TABLE organizations (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(500),
    type VARCHAR(50) DEFAULT 'organization',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE organizations IS 'Supervising organizations and authorities (e.g., KEK, state media authorities)';

-- ============================================================================
-- MEDIA TABLE
-- ============================================================================

CREATE TABLE media (
    squuid UUID PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    type media_type NOT NULL,
    state entity_state NOT NULL DEFAULT 'active',
    control_date TIMESTAMP,
    
    -- General information
    description TEXT,
    market_reach DECIMAL(10, 6),
    matched_names TEXT[], -- Array of alternative names
    
    -- Organization reference
    organization_squuid UUID REFERENCES organizations(squuid),
    
    -- Accessibility
    accessibility_email VARCHAR(255),
    accessibility_url VARCHAR(500),
    
    -- Press-specific fields
    press_type_squuid UUID REFERENCES press_types(squuid),
    press_magazine_type_squuid UUID REFERENCES press_magazine_types(squuid),
    press_as_of_date VARCHAR(50),
    press_distribution_area TEXT,
    press_editions_comments TEXT,
    press_editions_epaper INTEGER,
    press_editions_ivw BOOLEAN,
    press_editions_sold INTEGER,
    press_kind VARCHAR(255),
    press_publishing_intervals INTEGER,
    
    -- Online-specific fields
    online_offer_type_squuid UUID REFERENCES online_offer_types(squuid),
    online_agof DECIMAL(15, 3),
    online_as_of_date_agof VARCHAR(50),
    online_as_of_date_ivw VARCHAR(50),
    online_comments TEXT,
    online_ivwpi DECIMAL(15, 3),
    online_visits_ivw BIGINT,
    
    -- Radio/TV-specific fields
    rf_address TEXT,
    rf_broadcast_status_squuid UUID REFERENCES rf_broadcast_statuses(squuid),
    rf_category_squuid UUID REFERENCES rf_categories(squuid),
    rf_director VARCHAR(255),
    rf_free_pay BOOLEAN,
    rf_license_from VARCHAR(50),
    rf_license_until VARCHAR(50),
    rf_licensed VARCHAR(50),
    rf_parental_advisor VARCHAR(255),
    rf_public_private BOOLEAN,
    rf_representative VARCHAR(255),
    rf_shopping_channel BOOLEAN,
    rf_start_date VARCHAR(50),
    rf_statewide BOOLEAN,
    rf_supervising_authority_squuid UUID REFERENCES organizations(squuid),
    
    -- Additional information
    shares_info TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE media IS 'Media entities including print, online, radio, and TV';
COMMENT ON COLUMN media.market_reach IS 'Market reach percentage';
COMMENT ON COLUMN media.press_publishing_intervals IS 'Number of publishing intervals per year';
COMMENT ON COLUMN media.press_type_squuid IS 'Type of press - uses lookup table for adaptability to KEK source changes';
COMMENT ON COLUMN media.press_magazine_type_squuid IS 'Magazine type - uses lookup table for adaptability';
COMMENT ON COLUMN media.online_offer_type_squuid IS 'Type of online offer - uses lookup table for adaptability';
COMMENT ON COLUMN media.rf_broadcast_status_squuid IS 'Broadcast status - uses lookup table for adaptability';
COMMENT ON COLUMN media.rf_category_squuid IS 'Radio/TV category - uses lookup table for adaptability';
COMMENT ON COLUMN media.rf_public_private IS 'True for public broadcaster, false for private';

-- ============================================================================
-- SHAREHOLDERS TABLE
-- ============================================================================

CREATE TABLE shareholders (
    squuid UUID PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    state entity_state NOT NULL DEFAULT 'active',
    control_date TIMESTAMP,
    
    -- Type information
    natural_person BOOLEAN DEFAULT false,
    pseudo_company BOOLEAN DEFAULT false,
    limited_partnership BOOLEAN DEFAULT false,
    supplier_consortium BOOLEAN DEFAULT false,
    
    -- Address information
    corporation_name VARCHAR(500),
    co VARCHAR(255), -- Care of
    street VARCHAR(255),
    street_number VARCHAR(50),
    zipcode VARCHAR(20),
    city VARCHAR(255),
    place_of_business VARCHAR(255),
    
    -- Additional information
    other_media_activities TEXT,
    note TEXT,
    credits TEXT, -- References to KEK decisions
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE shareholders IS 'Shareholders and operators (natural persons and companies)';
COMMENT ON COLUMN shareholders.natural_person IS 'True for natural person, false for company';
COMMENT ON COLUMN shareholders.credits IS 'References to KEK decisions (e.g., "Beschluss der KEK vom 09.08.2011, Az.: KEK 659")';

-- ============================================================================
-- SHAREHOLDER-ORGANIZATION RELATIONSHIPS
-- ============================================================================

CREATE TABLE shareholder_organizations (
    shareholder_squuid UUID REFERENCES shareholders(squuid) ON DELETE CASCADE,
    organization_squuid UUID REFERENCES organizations(squuid) ON DELETE CASCADE,
    PRIMARY KEY (shareholder_squuid, organization_squuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE shareholder_organizations IS 'Many-to-many relationship between shareholders and supervising organizations';

-- ============================================================================
-- OWNERSHIP RELATIONSHIPS
-- ============================================================================

CREATE TABLE ownership_relations (
    squuid UUID PRIMARY KEY,
    holder_squuid UUID REFERENCES shareholders(squuid) ON DELETE CASCADE,
    held_squuid UUID REFERENCES shareholders(squuid) ON DELETE CASCADE,
    state entity_state NOT NULL DEFAULT 'active',
    capital_shares DECIMAL(5, 2), -- Percentage (0-100)
    complementary_partner BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT ownership_not_self CHECK (holder_squuid != held_squuid)
);

COMMENT ON TABLE ownership_relations IS 'Ownership relationships between shareholders (who owns whom)';
COMMENT ON COLUMN ownership_relations.capital_shares IS 'Percentage of capital shares (0-100)';
COMMENT ON COLUMN ownership_relations.complementary_partner IS 'Indicates partnership vs ownership';

CREATE INDEX idx_ownership_holder ON ownership_relations(holder_squuid);
CREATE INDEX idx_ownership_held ON ownership_relations(held_squuid);

-- ============================================================================
-- OPERATION RELATIONSHIPS
-- ============================================================================

CREATE TABLE operation_relations (
    squuid UUID PRIMARY KEY,
    holder_squuid UUID REFERENCES shareholders(squuid) ON DELETE CASCADE,
    held_squuid UUID REFERENCES media(squuid) ON DELETE CASCADE,
    state entity_state NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE operation_relations IS 'Operation relationships (which shareholders operate which media)';

CREATE INDEX idx_operation_holder ON operation_relations(holder_squuid);
CREATE INDEX idx_operation_held ON operation_relations(held_squuid);

-- ============================================================================
-- DISTRIBUTION TYPES (for platform operators)
-- ============================================================================

CREATE TABLE distribution_types (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE distribution_types IS 'Distribution types for platform operators (IPTV, Kabel, OTT, Satellit, etc.) - lookup table for flexibility';

-- Insert with actual squuids from KEK source
INSERT INTO distribution_types (squuid, name) VALUES
    ('5be1a6b0-951c-4614-9f9c-49bd5d814a60', 'IPTV'),
    ('5be1a6b0-6010-48d9-8f4c-8d0a8329d4e6', 'Kabel'),
    ('5be1a6b0-eeba-4517-af4c-ee038a5da882', 'OTT'),
    ('5be1a6b0-3401-437f-a41b-7d040eaa1e28', 'Programmplattform'),
    ('5be1a6b0-e8af-46c2-aeeb-fb68d2d314b0', 'Satellit'),
    ('5be1a6b0-4dbe-45ef-ab98-fcd1599e57f0', 'Terrestrik');

-- ============================================================================
-- LANGUAGES
-- ============================================================================

CREATE TABLE languages (
    squuid UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE languages IS 'Available languages for media - lookup table for flexibility';

-- Insert with actual squuids from KEK source
INSERT INTO languages (squuid, name) VALUES
    ('5be1a6ae-6473-44d1-97eb-d7ff6e27a248', 'Deutsch'),
    ('5be1a6ae-7330-4aba-9ec4-17828ecdb084', 'Englisch');

CREATE TABLE media_languages (
    media_squuid UUID REFERENCES media(squuid) ON DELETE CASCADE,
    language_squuid UUID REFERENCES languages(squuid) ON DELETE CASCADE,
    PRIMARY KEY (media_squuid, language_squuid)
);

COMMENT ON TABLE media_languages IS 'Languages available for each media';

-- ============================================================================
-- PLATFORM OPERATORS
-- ============================================================================

CREATE TABLE platform_operators (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) DEFAULT 'platform-operator',
    state entity_state DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE platform_operators IS 'Platform operators for media distribution - preserves KEK source squuids';

CREATE TABLE media_platform_operators (
    media_squuid UUID REFERENCES media(squuid) ON DELETE CASCADE,
    platform_operator_squuid UUID REFERENCES platform_operators(squuid) ON DELETE CASCADE,
    distribution_type_squuid UUID REFERENCES distribution_types(squuid),
    PRIMARY KEY (media_squuid, platform_operator_squuid, distribution_type_squuid)
);

COMMENT ON TABLE media_platform_operators IS 'Platform operators associated with each media and their distribution types';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX idx_media_type ON media(type);
CREATE INDEX idx_media_state ON media(state);
CREATE INDEX idx_media_organization ON media(organization_squuid);
CREATE INDEX idx_media_market_reach ON media(market_reach);

CREATE INDEX idx_shareholders_state ON shareholders(state);
CREATE INDEX idx_shareholders_natural_person ON shareholders(natural_person);
CREATE INDEX idx_shareholders_name ON shareholders(name);

-- ============================================================================
-- VIEWS FOR EASIER QUERYING
-- ============================================================================

-- View to get all owners of a shareholder with share percentages
CREATE VIEW shareholder_owners AS
SELECT 
    o.held_squuid AS shareholder_squuid,
    o.holder_squuid AS owner_squuid,
    o.capital_shares,
    o.complementary_partner,
    o.state,
    h.name AS owner_name,
    h.natural_person AS owner_is_natural_person
FROM ownership_relations o
JOIN shareholders h ON o.holder_squuid = h.squuid;

COMMENT ON VIEW shareholder_owners IS 'View showing all ownership relationships with owner details';

-- View to get all media operated by each shareholder
CREATE VIEW shareholder_media_operations AS
SELECT 
    o.holder_squuid AS shareholder_squuid,
    o.held_squuid AS media_squuid,
    o.state,
    m.name AS media_name,
    m.type AS media_type,
    s.name AS shareholder_name
FROM operation_relations o
JOIN media m ON o.held_squuid = m.squuid
JOIN shareholders s ON o.holder_squuid = s.squuid;

COMMENT ON VIEW shareholder_media_operations IS 'View showing which shareholders operate which media';

-- View for active media with market reach
CREATE VIEW active_media_with_reach AS
SELECT 
    squuid,
    name,
    type,
    market_reach,
    organization_squuid
FROM media
WHERE state = 'active' AND market_reach IS NOT NULL
ORDER BY market_reach DESC;

COMMENT ON VIEW active_media_with_reach IS 'Active media sorted by market reach';

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_media_updated_at BEFORE UPDATE ON media
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_shareholders_updated_at BEFORE UPDATE ON shareholders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ownership_updated_at BEFORE UPDATE ON ownership_relations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_operation_updated_at BEFORE UPDATE ON operation_relations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
