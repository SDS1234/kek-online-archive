-- PostgreSQL Schema for KEK (Kommission zur Ermittlung der Konzentration im Medienbereich) Database
-- This schema represents media entities, shareholders, and their relationships

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE media_type AS ENUM ('print', 'online', 'radio', 'tv');
CREATE TYPE entity_state AS ENUM ('active', 'archived');
CREATE TYPE relation_type AS ENUM ('own', 'operate');

-- Press-specific enums (small, stable value sets)
CREATE TYPE press_type_enum AS ENUM ('Zeitung', 'Zeitschrift', 'E-Paper');
CREATE TYPE press_magazine_type_enum AS ENUM ('Publikumszeitschrift', 'Fachzeitschrift');
CREATE TYPE online_offer_type_enum AS ENUM ('Online Medienangebot');
CREATE TYPE rf_broadcast_status_enum AS ENUM (
    'auf Sendung', 
    'Noch nicht auf Sendung', 
    'Sendebetrieb eingestellt'
);

-- ============================================================================
-- LOOKUP TABLES (for larger, potentially dynamic value sets)
-- ============================================================================

CREATE TABLE rf_categories (
    squuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rf_categories IS 'Radio/TV program categories (e.g., Vollprogramm, Spartenprogramm)';

-- Insert known categories
INSERT INTO rf_categories (squuid, name) VALUES
    (gen_random_uuid(), 'Vollprogramm'),
    (gen_random_uuid(), 'Spartenprogramm (Information/Dokumentation)'),
    (gen_random_uuid(), 'Spartenprogramm (Musik)'),
    (gen_random_uuid(), 'Spartenprogramm (Sport)'),
    (gen_random_uuid(), 'Spartenprogramm (Unterhaltung)'),
    (gen_random_uuid(), 'Spartenprogramm (Sonstiges)'),
    (gen_random_uuid(), 'Teleshopping');

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
    press_type press_type_enum,
    press_magazine_type press_magazine_type_enum,
    press_as_of_date VARCHAR(50),
    press_distribution_area TEXT,
    press_editions_comments TEXT,
    press_editions_epaper INTEGER,
    press_editions_ivw BOOLEAN,
    press_editions_sold INTEGER,
    press_kind VARCHAR(255),
    press_publishing_intervals INTEGER,
    
    -- Online-specific fields
    online_offer_type online_offer_type_enum,
    online_agof DECIMAL(15, 3),
    online_as_of_date_agof VARCHAR(50),
    online_as_of_date_ivw VARCHAR(50),
    online_comments TEXT,
    online_ivwpi DECIMAL(15, 3),
    online_visits_ivw BIGINT,
    
    -- Radio/TV-specific fields
    rf_address TEXT,
    rf_broadcast_status rf_broadcast_status_enum,
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
COMMENT ON COLUMN media.press_type IS 'Type of press (Zeitung, Zeitschrift, E-Paper) - uses ENUM for small, stable set';
COMMENT ON COLUMN media.press_magazine_type IS 'Magazine type (Publikumszeitschrift, Fachzeitschrift) - uses ENUM for small set';
COMMENT ON COLUMN media.online_offer_type IS 'Type of online offer - uses ENUM (currently only one value)';
COMMENT ON COLUMN media.rf_broadcast_status IS 'Broadcast status - uses ENUM for small, controlled set';
COMMENT ON COLUMN media.rf_category_squuid IS 'Radio/TV category - uses lookup table for larger, potentially growing set';
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
-- LANGUAGES
-- ============================================================================

CREATE TABLE languages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE media_languages (
    media_squuid UUID REFERENCES media(squuid) ON DELETE CASCADE,
    language_id INTEGER REFERENCES languages(id) ON DELETE CASCADE,
    PRIMARY KEY (media_squuid, language_id)
);

COMMENT ON TABLE languages IS 'Available languages for media';
COMMENT ON TABLE media_languages IS 'Languages available for each media';

-- ============================================================================
-- PLATFORM OPERATORS
-- ============================================================================

CREATE TABLE platform_operators (
    id SERIAL PRIMARY KEY,
    media_squuid UUID REFERENCES media(squuid) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    distribution_type_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE platform_operators IS 'Platform operators for media distribution';

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
