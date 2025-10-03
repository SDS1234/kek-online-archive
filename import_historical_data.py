#!/usr/bin/env python3
"""
Import historical KEK data snapshots from git history into PostgreSQL.

This script checks out different git commits and imports the data from each
commit into the historical tables, allowing users to track how media ownership
has changed over time.

Usage:
    python import_historical_data.py --help
    python import_historical_data.py --db kek --commits 10
    python import_historical_data.py --db kek --since 2024-01-01
    python import_historical_data.py --db kek --sample 50 --commits 5

Requirements:
    - Git repository with commit history
    - psycopg2-binary
    - PostgreSQL database with schema already created
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from argparse import ArgumentParser
from datetime import datetime
from typing import List, Tuple

# Import functions from the main import script
from import_to_postgres import (
    create_snapshot, import_media_history, import_shareholders_history,
    import_relationships_history, collect_organizations_from_media,
    collect_organizations_from_shareholders, import_organizations
)


def get_git_commits(since: str = None, until: str = None, max_count: int = None) -> List[Tuple[str, datetime, str]]:
    """Get list of git commits with their metadata.
    
    Args:
        since: Only commits after this date (ISO format)
        until: Only commits before this date (ISO format)
        max_count: Maximum number of commits to return
        
    Returns:
        List of tuples (commit_hash, commit_date, commit_message)
    """
    cmd = ['git', 'log', '--format=%H|%cI|%s', '--', 'docs/data/']
    
    if since:
        cmd.append(f'--since={since}')
    if until:
        cmd.append(f'--until={until}')
    if max_count:
        cmd.append(f'-{max_count}')
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        commits = []
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 2)
            if len(parts) == 3:
                commit_hash = parts[0]
                commit_date = datetime.fromisoformat(parts[1].replace('Z', '+00:00'))
                commit_message = parts[2]
                commits.append((commit_hash, commit_date, commit_message))
        
        return commits
    except subprocess.CalledProcessError as e:
        print(f"Error getting git commits: {e}")
        return []


def checkout_commit(commit_hash: str, work_dir: Path) -> bool:
    """Checkout a specific git commit in a work directory.
    
    Args:
        commit_hash: Git commit hash to checkout
        work_dir: Working directory path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        subprocess.run(
            ['git', 'checkout', commit_hash, '--', 'docs/data/'],
            cwd=work_dir,
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    parser = ArgumentParser(description='Import historical KEK data from git commits')
    parser.add_argument('--db', default='kek', help='Database name')
    parser.add_argument('--user', default='postgres', help='Database user')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--host', default='localhost', help='Database host')
    parser.add_argument('--port', type=int, default=5432, help='Database port')
    parser.add_argument('--commits', type=int, metavar='N',
                       help='Import data from the last N commits')
    parser.add_argument('--since', metavar='DATE',
                       help='Import data from commits since this date (ISO format: YYYY-MM-DD)')
    parser.add_argument('--until', metavar='DATE',
                       help='Import data from commits until this date (ISO format: YYYY-MM-DD)')
    parser.add_argument('--sample', type=int, metavar='N',
                       help='Import only N files of each type from each commit (for testing)')
    
    args = parser.parse_args()
    
    try:
        import psycopg2
    except ImportError:
        print("Error: psycopg2 not installed. Install with: pip install psycopg2-binary")
        return 1
    
    # Get list of commits to import
    print("Fetching git commit history...")
    commits = get_git_commits(since=args.since, until=args.until, max_count=args.commits)
    
    if not commits:
        print("No commits found matching the criteria.")
        return 1
    
    print(f"Found {len(commits)} commits to import\n")
    
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
    original_commit = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        capture_output=True,
        text=True
    ).stdout.strip()
    
    # Process each commit
    imported_count = 0
    skipped_count = 0
    
    for i, (commit_hash, commit_date, commit_message) in enumerate(commits, 1):
        print(f"\n{'='*60}")
        print(f"Processing commit {i}/{len(commits)}")
        print(f"Commit: {commit_hash[:8]}")
        print(f"Date: {commit_date}")
        print(f"Message: {commit_message}")
        print(f"{'='*60}\n")
        
        try:
            # Check if this commit is already imported
            cursor.execute(
                "SELECT id FROM data_snapshots WHERE git_commit_hash = %s",
                (commit_hash,)
            )
            existing = cursor.fetchone()
            
            if existing:
                print(f"✓ Snapshot already exists (ID: {existing[0]}), skipping...")
                skipped_count += 1
                continue
            
            # Checkout the commit
            print(f"Checking out commit {commit_hash[:8]}...")
            if not checkout_commit(commit_hash, base_dir):
                print(f"Warning: Could not checkout commit {commit_hash[:8]}, skipping...")
                continue
            
            data_dir = base_dir / "docs" / "data"
            
            # Create snapshot
            snapshot_id = create_snapshot(cursor, commit_hash, commit_date, commit_message)
            print(f"Created snapshot with ID: {snapshot_id}")
            
            # Collect and import organizations first (they may be needed by media/shareholders)
            print("Collecting organizations...")
            media_orgs = collect_organizations_from_media(cursor, data_dir, args.sample)
            shareholder_orgs = collect_organizations_from_shareholders(cursor, data_dir, args.sample)
            all_orgs = {**media_orgs, **shareholder_orgs}
            if all_orgs:
                import_organizations(cursor, all_orgs)
            
            # Import historical data
            media_count = import_media_history(cursor, snapshot_id, data_dir, args.sample)
            shareholder_count = import_shareholders_history(cursor, snapshot_id, data_dir, args.sample)
            ownership_count, operation_count = import_relationships_history(
                cursor, snapshot_id, data_dir, args.sample
            )
            
            # Commit after each snapshot
            conn.commit()
            
            print(f"\n✓ Imported snapshot {snapshot_id}:")
            print(f"  Media: {media_count}")
            print(f"  Shareholders: {shareholder_count}")
            print(f"  Ownership relations: {ownership_count}")
            print(f"  Operation relations: {operation_count}")
            
            imported_count += 1
            
        except Exception as e:
            print(f"\n✗ Error processing commit {commit_hash[:8]}: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            continue
    
    # Restore original commit
    print(f"\nRestoring original commit {original_commit[:8]}...")
    subprocess.run(['git', 'checkout', original_commit, '--', 'docs/data/'])
    
    # Final summary
    print(f"\n{'='*60}")
    print("Historical import completed!")
    print(f"  Total commits processed: {len(commits)}")
    print(f"  Snapshots imported: {imported_count}")
    print(f"  Snapshots skipped (already existed): {skipped_count}")
    print(f"{'='*60}")
    
    cursor.close()
    conn.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
