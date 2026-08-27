#!/usr/bin/env python3
"""
Validate KEK JSON data files against the defined schemas.

Usage:
    python validate_schemas.py                    # Validate all files
    python validate_schemas.py --media-only       # Validate only media files
    python validate_schemas.py --shareholders-only # Validate only shareholder files
    python validate_schemas.py --sample 10        # Validate 10 files of each type
"""

import json
import sys
from pathlib import Path
from argparse import ArgumentParser
from jsonschema import validate, ValidationError


def load_schema(schema_path):
    """Load a JSON schema file."""
    with open(schema_path) as f:
        return json.load(f)


def validate_files(data_dir, schema, file_limit=None):
    """Validate JSON files in a directory against a schema."""
    files = list(Path(data_dir).glob("*.json"))
    
    if file_limit:
        files = files[:file_limit]
    
    valid_count = 0
    errors = []
    
    for file_path in files:
        try:
            with open(file_path) as f:
                data = json.load(f)
            validate(instance=data, schema=schema)
            valid_count += 1
        except ValidationError as e:
            errors.append({
                'file': file_path.name,
                'message': e.message,
                'path': list(e.path)
            })
        except Exception as e:
            errors.append({
                'file': file_path.name,
                'message': f"Error loading file: {str(e)}",
                'path': []
            })
    
    return valid_count, len(files), errors


def main():
    parser = ArgumentParser(description='Validate KEK JSON data against schemas')
    parser.add_argument('--media-only', action='store_true', 
                       help='Validate only media files')
    parser.add_argument('--shareholders-only', action='store_true',
                       help='Validate only shareholder files')
    parser.add_argument('--sample', type=int, metavar='N',
                       help='Validate only N files of each type')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed error messages')
    
    args = parser.parse_args()
    
    # Paths
    base_dir = Path(__file__).parent
    schema_dir = base_dir / "schemas"
    data_dir = base_dir / "docs" / "data"
    
    media_schema_path = schema_dir / "media.schema.json"
    shareholder_schema_path = schema_dir / "shareholder.schema.json"
    media_data_dir = data_dir / "media"
    shareholder_data_dir = data_dir / "shareholders"
    
    # Load schemas
    print("Loading schemas...")
    try:
        media_schema = load_schema(media_schema_path)
        shareholder_schema = load_schema(shareholder_schema_path)
    except Exception as e:
        print(f"Error loading schemas: {e}")
        return 1
    
    print("✓ Schemas loaded successfully\n")
    
    total_valid = 0
    total_files = 0
    all_errors = []
    
    # Validate media files
    if not args.shareholders_only:
        print("Validating media files...")
        valid, total, errors = validate_files(
            media_data_dir, 
            media_schema, 
            args.sample
        )
        total_valid += valid
        total_files += total
        all_errors.extend([{'type': 'media', **e} for e in errors])
        
        print(f"  ✓ {valid}/{total} media files validated successfully")
        if errors:
            print(f"  ✗ {len(errors)} validation errors")
    
    # Validate shareholder files
    if not args.media_only:
        print("\nValidating shareholder files...")
        valid, total, errors = validate_files(
            shareholder_data_dir,
            shareholder_schema,
            args.sample
        )
        total_valid += valid
        total_files += total
        all_errors.extend([{'type': 'shareholder', **e} for e in errors])
        
        print(f"  ✓ {valid}/{total} shareholder files validated successfully")
        if errors:
            print(f"  ✗ {len(errors)} validation errors")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Total: {total_valid}/{total_files} files validated successfully")
    
    if all_errors:
        print(f"\nFound {len(all_errors)} validation errors")
        
        if args.verbose:
            print("\nDetailed errors:")
            for error in all_errors[:20]:  # Show first 20 errors
                print(f"\n  Type: {error['type']}")
                print(f"  File: {error['file']}")
                print(f"  Path: {'.'.join(str(p) for p in error['path']) or 'root'}")
                print(f"  Error: {error['message'][:200]}")
            
            if len(all_errors) > 20:
                print(f"\n  ... and {len(all_errors) - 20} more errors")
        else:
            print("  Use --verbose flag to see detailed error messages")
        
        return 1
    else:
        print("\n✓ All files validated successfully!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
