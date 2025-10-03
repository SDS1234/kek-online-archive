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


def get_lookup_squuid(cursor, table_name: str, value_name: Optional[str]) -> Optional[str]:
    """Get or create lookup table squuid by name. Generic function for all lookup tables."""
    if not value_name:
        return None
    
    # Try to find existing value
    cursor.execute(f"SELECT squuid FROM {table_name} WHERE name = %s", (value_name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # If not found, insert new value (allows dynamic adaptation to KEK source changes)
    cursor.execute(f"""
        INSERT INTO {table_name} (squuid, name)
        VALUES (gen_random_uuid(), %s)
        RETURNING squuid
    """, (value_name,))
    
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


def import_media(cursor, data_dir, limit=None):
    """Import media entities."""
    print("Importing media...")
    
    media_files = list(Path(data_dir / "media").glob("*.json"))
    if limit:
        media_files = media_files[:limit]
    
    seen_orgs = {}
    count = 0
    
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
            get_lookup_squuid(cursor, 'press_types', data.get('pressType', {}).get('name')) if data.get('pressType') else None,
            get_lookup_squuid(cursor, 'press_magazine_types', data.get('pressMagazineType', {}).get('name')) if data.get('pressMagazineType') else None,
            data.get('pressAsOfDate'),
            data.get('pressDistributionArea'),
            data.get('pressEditionsComments'),
            data.get('pressEditionsEpaper'),
            data.get('pressEditionsIVW'),
            data.get('pressEditionsSold'),
            data.get('pressKind'),
            data.get('pressPublishingIntervals'),
            get_lookup_squuid(cursor, 'online_offer_types', data.get('onlineOfferType', {}).get('name')) if data.get('onlineOfferType') else None,
            data.get('onlineAGOF'),
            data.get('onlineAsOfDateAGOF'),
            data.get('onlineAsOfDateIVW'),
            data.get('onlineComments'),
            data.get('onlineIVWPI'),
            data.get('onlineVisitsIVW'),
            data.get('rfAddress'),
            get_lookup_squuid(cursor, 'rf_broadcast_statuses', data.get('rfBroadcastStatus', {}).get('name')) if data.get('rfBroadcastStatus') else None,
            # Look up rf_category_squuid by name
            get_category_squuid(cursor, data.get('rfCategory', {}).get('name')) if data.get('rfCategory') else None,
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
    return count, seen_orgs


def import_shareholders(cursor, data_dir, limit=None):
    """Import shareholder entities."""
    print("Importing shareholders...")
    
    shareholder_files = list(Path(data_dir / "shareholders").glob("*.json"))
    if limit:
        shareholder_files = shareholder_files[:limit]
    
    seen_orgs = {}
    count = 0
    
    for shareholder_file in shareholder_files:
        with open(shareholder_file) as f:
            data = json.load(f)
        
        # Collect organizations
        for org in data.get('organizations', []):
            seen_orgs[org['squuid']] = org
        
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
    return count, seen_orgs


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
        # Import data
        media_count, media_orgs = import_media(cursor, data_dir, args.sample)
        shareholder_count, shareholder_orgs = import_shareholders(cursor, data_dir, args.sample)
        
        # Merge organizations and import
        all_orgs = {**media_orgs, **shareholder_orgs}
        org_count = import_organizations(cursor, all_orgs)
        
        # Import relationships
        ownership_count, operation_count = import_relationships(cursor, data_dir, args.sample)
        
        # Commit transaction
        conn.commit()
        
        print(f"\n{'='*60}")
        print("Import completed successfully!")
        print(f"  Organizations: {org_count}")
        print(f"  Media: {media_count}")
        print(f"  Shareholders: {shareholder_count}")
        print(f"  Ownership relations: {ownership_count}")
        print(f"  Operation relations: {operation_count}")
        
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
