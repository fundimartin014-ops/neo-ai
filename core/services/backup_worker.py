#!/usr/bin/env python3
"""
neo/services/backup_worker.py

One-shot backup service. Called by systemd timer or cron.
"""

import argparse
import shutil
import tarfile
from pathlib import Path
from datetime import datetime


def backup(source: str, dest: str, retain: int, encrypt: bool = False):
    """Create timestamped backup of Neo data."""
    
    source_path = Path(source)
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = dest_path / f"neo_backup_{timestamp}.tar.gz"
    
    # Create archive
    with tarfile.open(backup_file, 'w:gz') as tar:
        for item in source_path.rglob('*'):
            if item.is_file():
                tar.add(item, item.relative_to(source_path))
    
    print(f"Backup created: {backup_file}")
    print(f"Size: {backup_file.stat().st_size:,} bytes")
    
    # Clean old backups
    backups = sorted(dest_path.glob('neo_backup_*.tar.gz'))
    if len(backups) > retain:
        for old in backups[:-retain]:
            old.unlink()
            print(f"Removed old backup: {old.name}")
    
    return backup_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='/var/lib/neo')
    parser.add_argument('--dest', default='/var/backups/neo')
    parser.add_argument('--retain', type=int, default=24)
    parser.add_argument('--encrypt', action='store_true')
    args = parser.parse_args()
    
    backup(args.source, args.dest, args.retain, args.encrypt)


if __name__ == '__main__':
    main()