#!/usr/bin/env python3
"""
run_backup.py

Manual backup utility. Run this periodically or schedule with Windows Task Scheduler.
"""

import argparse
import shutil
import tarfile
from pathlib import Path
from datetime import datetime


def backup(source_dir: str, dest_dir: str, retain: int = 10):
    source = Path(source_dir)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = dest / f"neo_backup_{timestamp}.zip"
    
    # Create zip (Windows-friendly, no tar.gz needed)
    import zipfile
    with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in source.rglob('*'):
            if item.is_file():
                zf.write(item, item.relative_to(source))
    
    print(f"Backup: {backup_file}")
    print(f"Size: {backup_file.stat().st_size:,} bytes")
    
    # Clean old
    backups = sorted(dest.glob('neo_backup_*.zip'))
    if len(backups) > retain:
        for old in backups[:-retain]:
            old.unlink()
            print(f"Removed: {old.name}")
    
    return backup_file


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='.')
    parser.add_argument('--dest', default='./backups')
    parser.add_argument('--retain', type=int, default=10)
    args = parser.parse_args()
    
    backup(args.source, args.dest, args.retain)