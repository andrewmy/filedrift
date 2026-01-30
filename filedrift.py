#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
import csv
import time
from collections import defaultdict
from typing import Any

def scan_directory(root_dir: str | Path, subdirs_to_scan: list[str] | None = None, verbose: bool = False) -> dict[str, Any]:
    """Scan directory and return file info. If subdirs_to_scan is provided, only scan those subdirs."""
    root = Path(root_dir)
    files = {}
    skipped = 0
    root_files = []

    if not root.exists():
        print(f"  Error: Directory does not exist: {root_dir}")
        return {'files': files, 'skipped': skipped, 'root_files': root_files}

    if subdirs_to_scan:
        for subdir in subdirs_to_scan:
            subdir_path = root / subdir
            if subdir_path.exists() and subdir_path.is_dir():
                if verbose:
                    print(f"  Scanning subdirectory: {subdir}")
                for file in subdir_path.rglob('*'):
                    if file.is_file():
                        try:
                            rel_path = file.relative_to(root)
                            rel_path_str = str(rel_path)
                            files[rel_path_str.lower()] = {
                                'path': str(file),
                                'relative_path': rel_path_str,
                                'size': file.stat().st_size
                            }
                        except Exception as e:
                            skipped += 1
                            print(f"  Skipped {file}: {e}")
    else:
        if verbose:
            all_subdirs = [d for d in root.iterdir() if d.is_dir()]
            print(f"  Will scan {len(all_subdirs)} subdirectories")
            for subdir in all_subdirs:
                print(f"    {subdir.name}")

        for file in root.rglob('*'):
            if file.is_file():
                try:
                    rel_path = file.relative_to(root)
                    rel_path_str = str(rel_path)
                    files[rel_path_str.lower()] = {
                        'path': str(file),
                        'relative_path': rel_path_str,
                        'size': file.stat().st_size
                    }

                    if len(rel_path.parts) == 1:
                        root_files.append(rel_path_str)
                except Exception as e:
                    skipped += 1
                    print(f"  Skipped {file}: {e}")

    return {'files': files, 'skipped': skipped, 'root_files': root_files}

def get_top_level_subdirs(files_dict: dict[str, dict[str, Any]]) -> list[str]:
    """Extract unique top-level subdirectories from files."""
    subdirs = set()
    for file_info in files_dict.values():
        rel_path = Path(file_info['relative_path'])
        parts = rel_path.parts
        if len(parts) > 1:
            subdirs.add(parts[0])
    return sorted(subdirs)

def build_filename_index(target_files: dict[str, dict[str, Any]]) -> defaultdict:
    """Build index of target files by filename (case-insensitive)."""
    filename_index = defaultdict(list)
    for rel_path_lower, file_info in target_files.items():
        filename = Path(file_info['relative_path']).name.lower()
        filename_index[filename].append(file_info)
    return filename_index

def find_missing_files(source_data: dict[str, Any], target_data: dict[str, Any], target_filename_index: defaultdict, source_filename_index: defaultdict) -> dict[str, Any]:
    """Find files that are only in source or have been moved."""
    source_files = source_data['files']
    target_files = target_data['files']

    only_on_source = []
    in_both = []
    moved_files = []
    duplicates_on_source = {}

    for rel_path_lower, source_info in source_files.items():
        filename = Path(source_info['relative_path']).name.lower()

        if rel_path_lower in target_files:
            target_info = target_files[rel_path_lower]
            in_both.append({
                'relative_path': source_info['relative_path'],
                'source_path': source_info['path'],
                'source_size': source_info['size'],
                'target_path': target_info['path'],
                'target_size': target_info['size'],
                'match_type': 'exact_path',
                'confidence': 'high',
                'status': 'in_both',
                'duplicate_group': ''
            })
        else:
            if filename in target_filename_index:
                matches = target_filename_index[filename]

                same_size_matches = [m for m in matches if m['size'] == source_info['size']]

                if same_size_matches:
                    best_match = same_size_matches[0]
                    if filename in source_filename_index and len(source_filename_index[filename]) > 1:
                        status = 'duplicate_on_source'
                        source_key = (source_info['size'], filename)
                        if source_key not in duplicates_on_source:
                            duplicates_on_source[source_key] = []
                        duplicates_on_source[source_key].append(source_info['relative_path'])
                    else:
                        status = 'moved'

                    moved_files.append({
                        'relative_path': source_info['relative_path'],
                        'source_path': source_info['path'],
                        'source_size': source_info['size'],
                        'target_path': best_match['path'],
                        'target_size': best_match['size'],
                        'found_at_path': best_match['relative_path'],
                        'match_type': 'filename_same_size',
                        'confidence': 'high',
                        'status': status,
                        'duplicate_group': ''
                    })
                else:
                    best_match = matches[0]
                    moved_files.append({
                        'relative_path': source_info['relative_path'],
                        'source_path': source_info['path'],
                        'source_size': source_info['size'],
                        'target_path': best_match['path'],
                        'target_size': best_match['size'],
                        'found_at_path': best_match['relative_path'],
                        'match_type': 'filename_diff_size',
                        'confidence': 'medium',
                        'status': 'moved',
                        'duplicate_group': ''
                    })
            else:
                only_on_source.append({
                    'relative_path': source_info['relative_path'],
                    'source_path': source_info['path'],
                    'source_size': source_info['size'],
                    'target_path': '',
                    'target_size': '',
                    'found_at_path': '',
                    'match_type': 'none',
                    'confidence': '',
                    'status': 'only_on_source',
                    'duplicate_group': ''
                })

    return {'only_on_source': only_on_source, 'in_both': in_both, 'moved_files': moved_files, 'duplicates_on_source': duplicates_on_source}

def add_duplicate_groups(moved_files: list[dict[str, Any]], duplicates_on_source: dict[tuple[int, str], list[str]]) -> None:
    """Add duplicate_group information to duplicate_on_source files."""
    for row in moved_files:
        if row['status'] == 'duplicate_on_source':
            source_key = (int(row['source_size']), Path(row['relative_path']).name.lower())
            if source_key in duplicates_on_source:
                duplicates = [d for d in duplicates_on_source[source_key] if d != row['relative_path']]
                if duplicates:
                    row['duplicate_group'] = '; '.join(duplicates)

def analyze_missing_directories(only_on_source: list[dict[str, Any]], source_files: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Analyze which source directories have all files missing."""
    dir_stats = {}

    for row in only_on_source:
        rel_path = row['relative_path']
        parts = Path(rel_path).parts

        if len(parts) == 1:
            dir_key = 'ROOT'
            dir_name = '<root>'
        else:
            dir_key = '/'.join(parts[:-1])
            dir_name = dir_key

        if dir_key not in dir_stats:
            dir_stats[dir_key] = {
                'name': dir_name,
                'missing_files': 0,
                'missing_size': 0,
                'total_files': 0
            }

        dir_stats[dir_key]['missing_files'] += 1
        dir_stats[dir_key]['missing_size'] += int(row['source_size'])

    for rel_path_lower in source_files:
        rel_path = source_files[rel_path_lower]['relative_path']
        parts = Path(rel_path).parts

        if len(parts) == 1:
            dir_key = 'ROOT'
        else:
            dir_key = '/'.join(parts[:-1])

        if dir_key in dir_stats:
            dir_stats[dir_key]['total_files'] += 1

    entirely_missing = []
    for dir_key, stats in dir_stats.items():
        if stats['missing_files'] == stats['total_files'] and stats['total_files'] > 0:
            entirely_missing.append(stats)

    entirely_missing.sort(key=lambda x: x['name'].lower())

    return entirely_missing

def dry_run(source_dir: str, target_dir: str, full_scan: bool = False) -> None:
    """Show what would be scanned without actually scanning."""
    print("=" * 60)
    print("DRY RUN MODE")
    print("=" * 60)
    print(f"\nSource: {source_dir}")
    print(f"Target: {target_dir}")
    print(f"Scan mode: {'full scan' if full_scan else 'smart scan'}")
    print()

    source_data = scan_directory(source_dir)
    source_files = source_data['files']

    if not source_files:
        print("No files found in source directory!")
        return

    subdirs = get_top_level_subdirs(source_files)
    root_files = [f for f in source_files.values() if len(Path(f['relative_path']).parts) == 1]

    print(f"Total files in source: {len(source_files)}")
    print(f"Root files: {len(root_files)}")
    print(f"Subdirectories: {len(subdirs)}")
    print()

    if full_scan:
        print("Full scan mode: Will scan all subdirectories in target")
        target_root = Path(target_dir)
        all_target_subdirs = [d.name for d in target_root.iterdir() if d.is_dir()]
        print(f"Target contains {len(all_target_subdirs)} subdirectories")
        print(f"Estimated total files to scan: Full directory tree")
    else:
        target_root = Path(target_dir)
        existing_subdirs = []
        missing_subdirs = []

        print("Subdirectory scan plan:")
        for subdir in subdirs:
            subdir_path = target_root / subdir
            if subdir_path.exists() and subdir_path.is_dir():
                existing_subdirs.append(subdir)
                print(f"  + {subdir} (will scan on target)")
            else:
                missing_subdirs.append(subdir)
                print(f"  - {subdir} (not found on target, all files marked as missing)")

        print()
        print(f"Subdirectories to scan on target: {len(existing_subdirs)}")
        print(f"Subdirectories not on target: {len(missing_subdirs)}")
        missing_count = sum(1 for f in source_files.values() if len(Path(f['relative_path']).parts) > 0 and Path(f['relative_path']).parts[0].lower() in [d.lower() for d in missing_subdirs])
        print(f"Estimated target files to scan: ~{len(source_files) - missing_count}")

    print()
    print("=" * 60)
    print("Dry run complete. Use without --dry-run to execute.")

def main() -> None:
    parser = argparse.ArgumentParser(description='Smart duplicate finder - find files in source but not in target')
    parser.add_argument('--source', required=True, help='Source directory (smaller, e.g., USB)')
    parser.add_argument('--target', required=True, help='Target directory (larger, e.g., OneDrive or SMB)')
    parser.add_argument('--output', default='missing_files.csv', help='Output CSV file path')
    parser.add_argument('--dry-run', action='store_true', help='Show scan plan without executing')
    parser.add_argument('--full-scan', action='store_true', help='Scan entire target directory instead of smart subdirectory scanning')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress during scanning')
    parser.add_argument('--exclude-high-confidence-moved', action='store_true', help='Exclude high-confidence moved files from CSV output')

    args = parser.parse_args()

    if args.dry_run:
        dry_run(args.source, args.target, args.full_scan)
        return
    
    start_time = time.time()
    
    print("=" * 60)
    print("SMART DUPLICATE FINDER")
    print("=" * 60)
    print(f"\nSource: {args.source}")
    print(f"Target: {args.target}")
    print(f"Output: {args.output}")
    print()
    
    phase1_start = time.time()
    print("Phase 1: Scanning source directory...")
    source_data = scan_directory(args.source)
    source_files = source_data['files']
    phase1_time = time.time() - phase1_start
    
    if not source_files:
        print("  Error: No files found in source directory!")
        return
    
    print(f"  Found {len(source_files)} files, skipped {source_data['skipped']}")
    print(f"  Time: {phase1_time:.1f} seconds")
    print()
    
    subdirs = get_top_level_subdirs(source_files)
    root_files = [f for f in source_files.values() if len(Path(f['relative_path']).parts) == 1]
    
    print(f"  Root files: {len(root_files)}")
    print(f"  Subdirectories: {len(subdirs)}")
    print(f"  Top-level subdirs: {', '.join(subdirs[:10])}")
    if len(subdirs) > 10:
        print(f"    ... and {len(subdirs) - 10} more")
    print()

    phase2_start = time.time()
    if args.full_scan:
        print("Phase 2: Scanning target directory (full scan mode)...")
        target_data = scan_directory(args.target, verbose=args.verbose)
    else:
        print("Phase 2: Scanning target directory (smart mode)...")

        target_root = Path(args.target)
        subdirs_to_scan = []
        subdirs_not_found = []

        for subdir in subdirs:
            subdir_path = target_root / subdir
            if subdir_path.exists() and subdir_path.is_dir():
                subdirs_to_scan.append(subdir)
            else:
                subdirs_not_found.append(subdir)

        if subdirs_not_found:
            print(f"  Note: {len(subdirs_not_found)} subdirectories not found on target:")
            for subdir in subdirs_not_found[:10]:
                missing_count = sum(1 for f in source_files.values() if Path(f['relative_path']).parts[0].lower() == subdir.lower())
                print(f"    - {subdir} ({missing_count} files will be marked as missing)")
            if len(subdirs_not_found) > 10:
                print(f"    ... and {len(subdirs_not_found) - 10} more")
            print()

        target_data = scan_directory(args.target, subdirs_to_scan=subdirs_to_scan, verbose=args.verbose)

    target_files = target_data['files']
    phase2_time = time.time() - phase2_start
    
    print(f"  Scanned {len(target_files)} files, skipped {target_data['skipped']}")
    print(f"  Time: {phase2_time:.1f} seconds")
    print()

    phase3_start = time.time()
    print("Phase 3: Building filename index and comparing files...")
    target_filename_index = build_filename_index(target_files)
    source_filename_index = build_filename_index(source_files)
    results = find_missing_files(source_data, target_data, target_filename_index, source_filename_index)
    add_duplicate_groups(results['moved_files'], results['duplicates_on_source'])
    phase3_time = time.time() - phase3_start

    print(f"  Time: {phase3_time:.1f} seconds")
    print()
    
    phase4_start = time.time()
    print("Phase 4: Writing results...")

    interesting_rows = results['only_on_source'] + results['moved_files']
    
    if args.exclude_high_confidence_moved:
        interesting_rows = [r for r in interesting_rows if not (r['status'] == 'moved' and r['confidence'] == 'high')]
        excluded_count = len(results['moved_files']) - len(interesting_rows)
        print(f"  Excluding {excluded_count} high-confidence moved files from CSV output")

    with open(args.output, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['relative_path', 'source_path', 'source_size', 'target_path', 'target_size',
                     'found_at_path', 'match_type', 'confidence', 'status', 'duplicate_group']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(interesting_rows)

    phase4_time = time.time() - phase4_start

    print(f"  Written {len(interesting_rows)} rows to {args.output}")
    print(f"  Time: {phase4_time:.1f} seconds")
    print()
    
    total_time = time.time() - start_time

    moved_high_conf = [r for r in results['moved_files'] if r['confidence'] == 'high']
    moved_med_conf = [r for r in results['moved_files'] if r['confidence'] == 'medium']
    duplicate_count = len([r for r in results['moved_files'] if r['status'] == 'duplicate_on_source'])

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Scan mode: {'full scan' if args.full_scan else 'smart scan'}")
    print(f"Total files on source: {len(source_files)}")
    print(f"Total files scanned on target: {len(target_files)}")
    print(f"Files only on source: {len(results['only_on_source'])}")
    print(f"Files in both locations: {len(results['in_both'])} (excluded from CSV)")
    print(f"Files moved to different path: {len(moved_high_conf)} (high confidence)")
    print(f"Files possibly moved: {len(moved_med_conf)} (medium confidence)")
    print(f"Source duplicates: {duplicate_count}")

    if duplicate_count > 0:
        print()
        print("Source duplicate groups:")
        duplicate_groups = {}
        for row in results['moved_files']:
            if row['status'] == 'duplicate_on_source' and row['duplicate_group']:
                key = row['source_size']
                filename = Path(row['relative_path']).name
                if key not in duplicate_groups:
                    duplicate_groups[key] = {'filename': filename, 'files': []}
                duplicate_groups[key]['files'].append(row['relative_path'])

        for size, group in duplicate_groups.items():
            print(f"  {group['filename']} ({size:,} bytes):")
            for file in group['files']:
                try:
                    print(f"    - {file}")
                except UnicodeEncodeError:
                    print(f"    - <file with unicode characters>")

    if args.exclude_high_confidence_moved:
        excluded_high_conf = len([r for r in results['moved_files'] if r['confidence'] == 'high'])
        print()
        print(f"Note: {excluded_high_conf} high-confidence moved files excluded from CSV output (use --exclude-high-confidence-moved to disable)")

    entirely_missing_dirs = analyze_missing_directories(results['only_on_source'], source_files)

    if entirely_missing_dirs:
        print()
        print("Directories entirely missing on target:")
        for dir_info in entirely_missing_dirs[:50]:
            print(f"  {dir_info['name']} ({dir_info['missing_files']} files, {dir_info['missing_size']:,} bytes)")
        if len(entirely_missing_dirs) > 50:
            print(f"  ... and {len(entirely_missing_dirs) - 50} more directories")

    print()
    print(f"Skipped due to errors: {source_data['skipped'] + target_data['skipped']}")
    print()
    print(f"Phase 1 (source scan): {phase1_time:.1f}s")
    print(f"Phase 2 (target scan): {phase2_time:.1f}s")
    print(f"Phase 3 (comparison): {phase3_time:.1f}s")
    print(f"Phase 4 (write output): {phase4_time:.1f}s")
    print(f"Total time: {total_time:.1f}s")
    print()
    print(f"Results saved to: {args.output}")

if __name__ == "__main__":
    main()
