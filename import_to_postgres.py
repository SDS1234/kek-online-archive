#!/usr/bin/env python3
"""
Import KEK JSON data into PostgreSQL database.

This script reads the JSON files from docs/data/ and imports them into
a PostgreSQL database using the schema defined in schemas/postgresql-schema.sql

Usage:
    python import_to_postgres.py --help
    python import_to_postgres.py --db kek --user postgres
    python import_to_postgres.py --sample 10  # Import only 10 of each type for testing

Requirements:
    pip install psycopg2-binary
"""

import json
import sys
from pathlib import Path
from argparse import ArgumentParser
from datetime import datetime
from typing import Optional


def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except:
        return None


def get_lookup_squuid(cursor, table_name: str, lookup_data: Optional[dict]) -> Optional[str]:
    """Get or create lookup table entry using squuid from KEK source. 
    
    This function strictly uses squuids from the KEK source data. It will raise
    an error if the KEK source data doesn't include a squuid, ensuring we always
    maintain referential integrity with the KEK source identifiers.
    
    Args:
        cursor: Database cursor
        table_name: Name of the lookup table
        lookup_data: Dict from KEK source with 'squuid' and 'name' fields
    
    Returns:
        The squuid for the lookup value
        
    Raises:
        ValueError: If lookup_data doesn't contain a squuid
    """
    if not lookup_data or not lookup_data.get('name'):
        return None
    
    name = lookup_data['name']
    source_squuid = lookup_data.get('squuid')
    
    # Try to find existing value by name
    cursor.execute(f"SELECT squuid FROM {table_name} WHERE name = %s", (name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # If not found, insert new value using squuid from KEK source
    # This preserves the KEK source squuid for lookup values
    if not source_squuid:
        raise ValueError(f"Missing squuid in KEK source data for {table_name} entry: {name}")
    
    cursor.execute(f"""
        INSERT INTO {table_name} (squuid, name)
        VALUES (%s, %s)
        ON CONFLICT (squuid) DO NOTHING
        RETURNING squuid
    """, (source_squuid, name))
    result = cursor.fetchone()
    if result:
        return result[0]
    # If conflict occurred, fetch the existing record
    cursor.execute(f"SELECT squuid FROM {table_name} WHERE squuid = %s", (source_squuid,))
    return cursor.fetchone()[0]


def get_category_squuid(cursor, category_name: Optional[str]) -> Optional[str]:
    """Get or create rf_category squuid by name."""
    return get_lookup_squuid(cursor, 'rf_categories', category_name)


def import_organizations(cursor, seen_orgs):
    """Import unique organizations."""
    print("Importing organizations...")
    count = 0
    
    for org_data in seen_orgs.values():
        cursor.execute("""
            INSERT INTO organizations (squuid, name, full_name, type)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (squuid) DO NOTHING
        """, (
            org_data['squuid'],
            org_data['name'],
            org_data.get('fullName'),
            org_data.get('type', 'organization')
        ))
        count += 1
    
    print(f"  ✓ Imported {count} organizations")
    return count


def collect_organizations_from_media(cursor, data_dir, limit=None):
    """Collect all organization references from media files."""
    media_files = list(Path(data_dir / "media").glob("*.json"))
    if limit:
        media_files = media_files[:limit]
    
    seen_orgs = {}
    
    for media_file in media_files:
        with open(media_file) as f:
            data = json.load(f)
        
        # Collect organizations
        if 'organization' in data:
            org = data['organization']
            seen_orgs[org['squuid']] = org
        
        if 'rfSupervisingAuthority' in data:
            org = data['rfSupervisingAuthority']
            seen_orgs[org['squuid']] = org
    
    print(f"  Found {len(seen_orgs)} unique organizations in media files")
    return seen_orgs


def import_media(cursor, data_dir, limit=None):
    """Import media entities."""
    print("Importing media...")
    
    media_files = list(Path(data_dir / "media").glob("*.json"))
    if limit:
        media_files = media_files[:limit]
    
    count = 0
    
    for media_file in media_files:
        with open(media_file) as f:
            data = json.load(f)
        
        # Insert media
        cursor.execute("""
            INSERT INTO media (
                squuid, name, type, state, control_date,
                description, market_reach, matched_names,
                organization_squuid,
                accessibility_email, accessibility_url,
                press_type_squuid, press_magazine_type_squuid,
                press_as_of_date, press_distribution_area,
                press_editions_comments, press_editions_epaper,
                press_editions_ivw, press_editions_sold,
                press_kind, press_publishing_intervals,
                online_offer_type_squuid, online_agof,
                online_as_of_date_agof, online_as_of_date_ivw,
                online_comments, online_ivwpi, online_visits_ivw,
                rf_address, rf_broadcast_status_squuid, rf_category_squuid,
                rf_director, rf_free_pay, rf_license_from, rf_license_until,
                rf_licensed, rf_parental_advisor, rf_public_private,
                rf_representative, rf_shopping_channel, rf_start_date,
                rf_statewide, rf_supervising_authority_squuid, shares_info
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            ) ON CONFLICT (squuid) DO UPDATE SET
                name = EXCLUDED.name,
                control_date = EXCLUDED.control_date,
                state = EXCLUDED.state
        """, (
            data['squuid'],
            data['name'],
            data['type'],
            data['state'],
            parse_datetime(data.get('controlDate')),
            data.get('description'),
            data.get('marketReach'),
            data.get('matchedNames', []),
            data.get('organization', {}).get('squuid'),
            data.get('accessibilityEmail'),
            data.get('accessibilityUrl'),
            get_lookup_squuid(cursor, 'press_types', data.get('pressType')) if data.get('pressType') else None,
            get_lookup_squuid(cursor, 'press_magazine_types', data.get('pressMagazineType')) if data.get('pressMagazineType') else None,
            data.get('pressAsOfDate'),
            data.get('pressDistributionArea'),
            data.get('pressEditionsComments'),
            data.get('pressEditionsEpaper'),
            data.get('pressEditionsIVW'),
            data.get('pressEditionsSold'),
            data.get('pressKind'),
            data.get('pressPublishingIntervals'),
            get_lookup_squuid(cursor, 'online_offer_types', data.get('onlineOfferType')) if data.get('onlineOfferType') else None,
            data.get('onlineAGOF'),
            data.get('onlineAsOfDateAGOF'),
            data.get('onlineAsOfDateIVW'),
            data.get('onlineComments'),
            data.get('onlineIVWPI'),
            data.get('onlineVisitsIVW'),
            data.get('rfAddress'),
            get_lookup_squuid(cursor, 'rf_broadcast_statuses', data.get('rfBroadcastStatus')) if data.get('rfBroadcastStatus') else None,
            get_lookup_squuid(cursor, 'rf_categories', data.get('rfCategory')) if data.get('rfCategory') else None,
            data.get('rfDirector'),
            data.get('rfFreePay'),
            data.get('rfLicenseFrom'),
            data.get('rfLicenseUntil'),
            data.get('rfLicensed'),
            data.get('rfParentalAdvisor'),
            data.get('rfPublicPrivate'),
            data.get('rfRepresentative'),
            data.get('rfShoppingChannel'),
            data.get('rfStartDate'),
            data.get('rfStatewide'),
            data.get('rfSupervisingAuthority', {}).get('squuid'),
            data.get('sharesInfo')
        ))
        count += 1
        
        if count % 100 == 0:
            print(f"  ... imported {count} media")
    
    print(f"  ✓ Imported {count} media")
    return count, {}  # Return empty dict since orgs are handled separately


def collect_organizations_from_shareholders(cursor, data_dir, limit=None):
    """Collect all organization references from shareholder files."""
    shareholder_files = list(Path(data_dir / "shareholders").glob("*.json"))
    if limit:
        shareholder_files = shareholder_files[:limit]
    
    seen_orgs = {}
    
    for shareholder_file in shareholder_files:
        with open(shareholder_file) as f:
            data = json.load(f)
        
        # Collect organizations
        for org in data.get('organizations', []):
            seen_orgs[org['squuid']] = org
    
    print(f"  Found {len(seen_orgs)} unique organizations in shareholder files")
    return seen_orgs


def import_shareholders(cursor, data_dir, limit=None):
    """Import shareholder entities."""
    print("Importing shareholders...")
    
    shareholder_files = list(Path(data_dir / "shareholders").glob("*.json"))
    if limit:
        shareholder_files = shareholder_files[:limit]
    
    count = 0
    
    for shareholder_file in shareholder_files:
        with open(shareholder_file) as f:
            data = json.load(f)
        
        # Insert shareholder
        cursor.execute("""
            INSERT INTO shareholders (
                squuid, name, state, control_date,
                natural_person, pseudo_company, limited_partnership, supplier_consortium,
                corporation_name, co, street, street_number, zipcode, city, place_of_business,
                other_media_activities, note, credits
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            ) ON CONFLICT (squuid) DO UPDATE SET
                name = EXCLUDED.name,
                control_date = EXCLUDED.control_date,
                state = EXCLUDED.state
        """, (
            data['squuid'],
            data['name'],
            data['state'],
            parse_datetime(data.get('controlDate')),
            data.get('naturalPerson', False),
            data.get('pseudoCompany', False),
            data.get('limitedPartnership', False),
            data.get('supplierConsortium', False),
            data.get('corporationName'),
            data.get('co'),
            data.get('street'),
            data.get('streetNumber'),
            data.get('zipcode'),
            data.get('city'),
            data.get('placeOfBusiness'),
            data.get('otherMediaActivities'),
            data.get('note'),
            data.get('credits')
        ))
        count += 1
        
        # Import shareholder-organization relationships
        for org in data.get('organizations', []):
            cursor.execute("""
                INSERT INTO shareholder_organizations (shareholder_squuid, organization_squuid)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (data['squuid'], org['squuid']))
        
        if count % 100 == 0:
            print(f"  ... imported {count} shareholders")
    
    print(f"  ✓ Imported {count} shareholders")
    return count, {}  # Return empty dict since orgs are handled separately


def import_relationships(cursor, data_dir, limit=None):
    """Import ownership and operation relationships."""
    print("Importing relationships...")
    
    shareholder_files = list(Path(data_dir / "shareholders").glob("*.json"))
    media_files = list(Path(data_dir / "media").glob("*.json"))
    
    if limit:
        shareholder_files = shareholder_files[:limit]
        media_files = media_files[:limit]
    
    ownership_count = 0
    operation_count = 0
    
    # Import ownership relationships from shareholders
    for shareholder_file in shareholder_files:
        with open(shareholder_file) as f:
            data = json.load(f)
        
        for own in data.get('owns', []):
            cursor.execute("""
                INSERT INTO ownership_relations (
                    squuid, holder_squuid, held_squuid, state, capital_shares, complementary_partner
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (squuid) DO UPDATE SET
                    state = EXCLUDED.state,
                    capital_shares = EXCLUDED.capital_shares
            """, (
                own['squuid'],
                data['squuid'],
                own['held']['squuid'],
                own['state'],
                own.get('capitalShares'),
                own.get('complementaryPartner', False)
            ))
            ownership_count += 1
        
        for operate in data.get('operates', []):
            cursor.execute("""
                INSERT INTO operation_relations (
                    squuid, holder_squuid, held_squuid, state
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (squuid) DO UPDATE SET
                    state = EXCLUDED.state
            """, (
                operate['squuid'],
                data['squuid'],
                operate['held']['squuid'],
                operate['state']
            ))
            operation_count += 1
    
    # Import operation relationships from media (operatedBy)
    for media_file in media_files:
        with open(media_file) as f:
            data = json.load(f)
        
        for operated_by in data.get('operatedBy', []):
            cursor.execute("""
                INSERT INTO operation_relations (
                    squuid, holder_squuid, held_squuid, state
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (squuid) DO UPDATE SET
                    state = EXCLUDED.state
            """, (
                operated_by['squuid'],
                operated_by['holder']['squuid'],
                data['squuid'],
                operated_by['state']
            ))
            operation_count += 1
    
    print(f"  ✓ Imported {ownership_count} ownership relations")
    print(f"  ✓ Imported {operation_count} operation relations")
    return ownership_count, operation_count


def import_languages_and_platform_operators(cursor, data_dir, limit=None):
    """Import languages, distribution types, platform operators, and their relationships with media."""
    print("Importing languages, platform operators, and distribution types...")
    
    media_files = list(Path(data_dir / "media").glob("*.json"))
    if limit:
        media_files = media_files[:limit]
    
    language_count = 0
    platform_operator_count = 0
    distribution_type_count = 0
    media_language_count = 0
    media_platform_operator_count = 0
    
    seen_languages = set()
    seen_platform_operators = set()
    seen_distribution_types = set()
    
    for media_file in media_files:
        with open(media_file) as f:
            data = json.load(f)
        
        media_squuid = data['squuid']
        
        # Handle languages
        if 'languages' in data:
            for lang in data['languages']:
                if 'squuid' in lang and 'name' in lang:
                    lang_squuid = lang['squuid']
                    
                    # Insert language if not seen before
                    if lang_squuid not in seen_languages:
                        cursor.execute("""
                            INSERT INTO languages (squuid, name)
                            VALUES (%s, %s)
                            ON CONFLICT (squuid) DO NOTHING
                        """, (lang_squuid, lang['name']))
                        seen_languages.add(lang_squuid)
                        language_count += 1
                    
                    # Link media to language
                    cursor.execute("""
                        INSERT INTO media_languages (media_squuid, language_squuid)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (media_squuid, lang_squuid))
                    media_language_count += 1
        
        # Handle platform operators
        if 'platformOperators' in data:
            for po in data['platformOperators']:
                if 'squuid' in po and 'name' in po:
                    po_squuid = po['squuid']
                    
                    # Insert platform operator if not seen before
                    if po_squuid not in seen_platform_operators:
                        cursor.execute("""
                            INSERT INTO platform_operators (squuid, name, type, state)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (squuid) DO NOTHING
                        """, (
                            po_squuid,
                            po['name'],
                            po.get('type', 'platform-operator'),
                            po.get('state', 'active')
                        ))
                        seen_platform_operators.add(po_squuid)
                        platform_operator_count += 1
                    
                    # Handle distribution type
                    dist_type_squuid = None
                    if 'distributionType' in po:
                        dt = po['distributionType']
                        if 'squuid' in dt and 'name' in dt:
                            dist_type_squuid = dt['squuid']
                            
                            # Insert distribution type if not seen before
                            if dist_type_squuid not in seen_distribution_types:
                                cursor.execute("""
                                    INSERT INTO distribution_types (squuid, name)
                                    VALUES (%s, %s)
                                    ON CONFLICT (squuid) DO NOTHING
                                """, (dist_type_squuid, dt['name']))
                                seen_distribution_types.add(dist_type_squuid)
                                distribution_type_count += 1
                    
                    # Link media to platform operator with distribution type
                    if dist_type_squuid:
                        cursor.execute("""
                            INSERT INTO media_platform_operators (media_squuid, platform_operator_squuid, distribution_type_squuid)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (media_squuid, po_squuid, dist_type_squuid))
                        media_platform_operator_count += 1
    
    print(f"  ✓ Imported {language_count} unique languages")
    print(f"  ✓ Imported {distribution_type_count} unique distribution types")
    print(f"  ✓ Imported {platform_operator_count} unique platform operators")
    print(f"  ✓ Created {media_language_count} media-language links")
    print(f"  ✓ Created {media_platform_operator_count} media-platform-operator links")
    
    return (language_count, distribution_type_count, platform_operator_count,
            media_language_count, media_platform_operator_count)


def main():
    parser = ArgumentParser(description='Import KEK JSON data into PostgreSQL')
    parser.add_argument('--db', default='kek', help='Database name')
    parser.add_argument('--user', default='postgres', help='Database user')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--host', default='localhost', help='Database host')
    parser.add_argument('--port', type=int, default=5432, help='Database port')
    parser.add_argument('--sample', type=int, metavar='N',
                       help='Import only N files of each type for testing')
    
    args = parser.parse_args()
    
    try:
        import psycopg2
    except ImportError:
        print("Error: psycopg2 not installed. Install with: pip install psycopg2-binary")
        return 1
    
    # Connect to database
    print(f"Connecting to database '{args.db}' on {args.host}:{args.port}...")
    try:
        conn = psycopg2.connect(
            dbname=args.db,
            user=args.user,
            password=args.password,
            host=args.host,
            port=args.port
        )
        cursor = conn.cursor()
        print("✓ Connected successfully\n")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return 1
    
    base_dir = Path(__file__).parent
    data_dir = base_dir / "docs" / "data"
    
    try:
        # First pass: collect all organizations from media and shareholders
        print("Collecting organizations from data files...")
        media_orgs = collect_organizations_from_media(cursor, data_dir, args.sample)
        shareholder_orgs = collect_organizations_from_shareholders(cursor, data_dir, args.sample)
        
        # Merge and import organizations FIRST
        all_orgs = {**media_orgs, **shareholder_orgs}
        org_count = import_organizations(cursor, all_orgs)
        
        # Now import media and shareholders (which reference organizations)
        media_count, _ = import_media(cursor, data_dir, args.sample)
        shareholder_count, _ = import_shareholders(cursor, data_dir, args.sample)
        
        # Import relationships
        ownership_count, operation_count = import_relationships(cursor, data_dir, args.sample)
        
        # Import languages, platform operators, and distribution types
        (language_count, distribution_type_count, platform_operator_count,
         media_language_count, media_platform_operator_count) = import_languages_and_platform_operators(
            cursor, data_dir, args.sample)
        
        # Commit transaction
        conn.commit()
        
        print(f"\n{'='*60}")
        print("Import completed successfully!")
        print(f"  Organizations: {org_count}")
        print(f"  Media: {media_count}")
        print(f"  Shareholders: {shareholder_count}")
        print(f"  Ownership relations: {ownership_count}")
        print(f"  Operation relations: {operation_count}")
        print(f"  Languages: {language_count}")
        print(f"  Distribution types: {distribution_type_count}")
        print(f"  Platform operators: {platform_operator_count}")
        print(f"  Media-language links: {media_language_count}")
        print(f"  Media-platform-operator links: {media_platform_operator_count}")
        
    except Exception as e:
        print(f"\nError during import: {e}")
        conn.rollback()
        return 1
    finally:
        cursor.close()
        conn.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
