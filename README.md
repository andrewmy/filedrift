# FileDrift - Smart Duplicate Finder

A fast, intelligent file comparison tool that finds files present in a source directory but missing from a target directory. Uses smart scanning to avoid full scans of large directories like OneDrive or SMB shares.

## Features

- **Smart Scanning**: Only scans relevant subdirectories in target, avoiding full directory traversal
- **Full Scan Mode**: Option to scan entire target directory for reorganized structures
- **Case-Insensitive Matching**: Works on Windows with case-insensitive filename comparison
- **Moved File Detection**: Finds files that have been moved to different locations via filename matching
- **Fast**: Scans thousands of files in seconds
- **No Downloads**: Uses file metadata only, doesn't trigger OneDrive downloads
- **CSV Output**: Easy to filter and analyze results
- **Dry-Run Mode**: Preview scan plan before executing
- **Verbose Mode**: Detailed progress output for large scans
- **Works with SMB Shares**: Compatible with network shares and local drives

## Why This Tool?

**Purpose-built for backup verification**
- Focuses on finding missing files (source → target) rather than duplicates
- Identifies files that haven't been copied, not files that exist multiple times

**Metadata-only scanning**
- Uses file path and size only, never reads file content
- Critical for OneDrive and cloud sync: avoids triggering downloads of "placeholder" files
- Much faster than content hashing

**Lightweight & fast**
- Single Python script with no GUI or dependencies
- Scans 6,000+ files in ~1 second
- No installation or configuration needed

**Automatable**
- Command-line interface with flags like `--dry-run` and `--verbose`
- Fits into scheduled backup verification scripts
- CSV output for custom filtering, sorting, and analysis

## Installation

No installation required. Requires Python 3.7+.

```bash
# Clone or download filedrift.py
# Ensure Python is installed
python --version
```

## Usage

### Basic Usage

```bash
python filedrift.py --source "/path/to/source" --target "/path/to/target"
```

### With Custom Output File

```bash
python filedrift.py --source "/path/to/source" --target "/path/to/target" --output "results.csv"
```

### Dry-Run Mode (Preview)

```bash
python filedrift.py --source "/path/to/source" --target "/path/to/target" --dry-run
```

### Full Scan Mode (For Reorganized Directories)

When target directory has different structure (e.g., different subdirectory names), use full scan:

```bash
python filedrift.py --source "/path/to/photos" --target "/path/to/backup/Pictures" --full-scan
```

### Verbose Mode (Detailed Progress)

For large directories, see detailed scanning progress:

```bash
python filedrift.py --source "F:\_PHOTO" --target "C:\Users\andre\OneDrive\Pictures" --full-scan --verbose
```

### Exclude High-Confidence Moved Files

To focus on truly missing files and uncertain matches, exclude high-confidence moved files from CSV:

```bash
python filedrift.py --source "/path/to/photos" --target "/path/to/backup/Pictures" --full-scan --exclude-high-confidence-moved
```

**What this does:**
- Excludes files marked as `moved` with `confidence: high` from CSV output
- Only writes to CSV:
  - `only_on_source` files (truly missing)
  - `moved` files with `confidence: medium` (uncertain matches)
  - `duplicate_on_source` files
- Console note shows how many files were excluded

**When to use:**
- When you only want to see files that are truly missing from target
- When high-confidence moved files (same filename, same size) don't need attention

### Network Share Example

```bash
python filedrift.py --source "/path/to/data" --target "\\server\share\backup" --output "missing.csv"
```

## Command-Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--source` | Yes | - | Source directory (smaller, e.g., USB drive) |
| `--target` | Yes | - | Target directory (larger, e.g., OneDrive or SMB share) |
| `--output` | No | `missing_files.csv` | CSV output file path |
| `--dry-run` | No | - | Show scan plan without executing |
| `--full-scan` | No | - | Scan entire target directory instead of smart subdirectory scanning |
| `--verbose` | No | - | Show detailed progress during scanning |
| `--exclude-high-confidence-moved` | No | - | Exclude high-confidence moved files from CSV output |

## How It Works

*Files moved, reorganized, no longer where expected, now revealed*

### Smart Scanning Algorithm (Default)

1. **Phase1**: Full scan of source directory
   - Records all files with relative paths and sizes
   - Identifies top-level subdirectories

2. **Phase2**: Smart scan of target directory
   - For each subdirectory found in source:
     - If it exists in target: scan only that subdirectory
     - If it doesn't exist: mark all files as "missing"
   - Skips target subdirectories that don't exist in source

3. **Phase3**: Comparison with moved file detection
   - Compares files by relative path (case-insensitive)
   - For files not found at same path: searches target by filename
   - Prioritizes matches with same file size (high confidence)
   - Marks different-sized filename matches as medium confidence

4. **Phase4**: Output
   - Writes CSV with all file details and status
   - Excludes exact path matches from CSV (only writes differences)

### Full Scan Mode (Use with `--full-scan`)

When target directory has different structure or subdirectory names don't match:

1. **Phase1**: Full scan of source directory
2. **Phase2**: Full scan of entire target directory
   - Scans all subdirectories regardless of source structure
   - Use with `--verbose` to see detailed progress
3. **Phase3-4**: Same comparison and output as smart mode

### Example

If source (USB) has:
```
/path/to/source/
  Books/file1.pdf
  Books/file2.pdf
  Android/app.apk
```

And target (backup) has:
```
/path/to/target/
  Books/file1.pdf
  Documents/doc.txt
```

The script will:
- Scan all of `/path/to/source` (3 files)
- Scan only `/path/to/target/Books` (1 file) - NOT full target
- Report: `Books/file2.pdf` and `Android/app.apk` as missing

## Output Format

The CSV output contains these columns:

| Column | Description |
|--------|-------------|
| `relative_path` | Full relative path from root (e.g., "Books/file.pdf") |
| `source_path` | Full path on source drive |
| `source_size` | File size on source (bytes) |
| `target_path` | Full path on target (if found, empty otherwise) |
| `target_size` | File size on target (if found, empty otherwise) |
| `found_at_path` | Where file was found in target (if moved, empty otherwise) |
| `match_type` | Type of match: `exact_path`, `filename_same_size`, `filename_diff_size`, `none` |
| `confidence` | Match confidence: `high`, `medium`, empty for no match |
| `status` | Overall status: `only_on_source`, `moved`, `duplicate_on_source`, `in_both` |
| `duplicate_group` | Other source files that are duplicates (semicolon-separated, empty if no duplicates) |

### Status Codes

| Status | Description |
|--------|-------------|
| `only_on_source` | File not found anywhere in target |
| `moved` | File found at different path in target (filename match) |
| `duplicate_on_source` | Source has multiple files with same name and size; target has one copy (check `duplicate_group` column for related duplicates) |
| `in_both` | File found at same path in target (excluded from CSV) |

### Example Output

```csv
relative_path,source_path,source_size,target_path,target_size,found_at_path,match_type,confidence,status,duplicate_group
Books/file1.pdf,/path/to/source/Books/file1.pdf,1024000,/path/to/target/Books/file1.pdf,1024000,exact_path,high,in_both,
Books/file2.pdf,/path/to/source/Books/file2.pdf,512000,,0,,filename_same_size,high,moved,
Books/file3.pdf,/path/to/source/Books/file3.pdf,2560000,/path/to/target/_unsorted/file3.pdf,2560000,filename_same_size,high,moved,
Android/app.apk,/path/to/source/Android/app.apk,2560000,,0,,none,,only_on_source,
Photos/backup.jpg,/path/to/source/Photos/backup.jpg,1024000,/path/to/target/Photos/backup.jpg,1024000,filename_same_size,high,duplicate_on_source,Photos/main.jpg
Photos/main.jpg,/path/to/source/Photos/main.jpg,1024000,/path/to/target/Photos/backup.jpg,1024000,filename_same_size,high,duplicate_on_source,Photos/backup.jpg
```

**Note:** For `duplicate_on_source` files, the `duplicate_group` column shows other source files with the same name and size. In the example above, `Photos/backup.jpg` and `Photos/main.jpg` are duplicates (same filename, same size) and each appears in the CSV with the other listed in `duplicate_group`.

## Use Cases

### 1. USB Backup Verification

Check if all files from USB drive are backed up to OneDrive:

```bash
python filedrift.py --source "F:\OneDrive" --target "C:\Users\andre\OneDrive"
```

### 2. Network Share Comparison

Compare local files to network backup:

```bash
python filedrift.py --source "/path/to/projects" --target "\\server\backups\Projects"
```

### 3. Partial Directory Sync

Find files that need to be copied to target:

```bash
python filedrift.py --source "/path/to/photos" --target "/path/to/pictures" --output "to_copy.csv"
```

### 4. Finding Moved Files in Reorganized Directories

When directory structures differ, find files that have been moved:

```bash
python filedrift.py --source "F:\_PHOTO" --target "C:\Users\andre\OneDrive\Pictures" --full-scan --verbose
```

### 5. Dry-Run Before Scanning

Preview what will be scanned before committing to large operations:

```bash
python filedrift.py --source "/path/to/data" --target "/path/to/target" --dry-run
```

## Performance

Typical performance on Windows 11:

**Smart Scan Mode:**
- **Source scan**: 6,682 files in 0.3 seconds
- **Target scan**: 5,540 files in 0.6 seconds
- **Total time**: ~1 second for thousands of files

**Full Scan Mode:**
- **Source scan**: 816 files in 0.0 seconds
- **Target scan**: 108,415 files in 33.0 seconds
- **Total time**: ~33 seconds for large directory structures

## Summary Output

The script provides several summary sections to help you quickly identify issues:

### Directories Entirely Missing

When an entire source directory has ALL its files marked as "only_on_source" (not found anywhere on target), the summary displays:

```
Directories entirely missing on target:
  subdir (15 files, 1,234,567 bytes)
  another_dir (8 files, 567,890 bytes)
```

**Note:** This section only appears when 100% of files in a directory are missing on target. Directories with some files moved or found on target are not listed.

This helps you quickly identify whole directories that need to be copied to target, avoiding manual inspection of individual files or clicking through target directories.

### Source Duplicate Groups

Displays files that exist multiple times in source (same name, same size):

```
Source duplicate groups:
  DSC09847.ARW (25,001,984 bytes):
    - 2015\2015-12-30\DSC09847.ARW
    - 2015\2015-12-31\DSC09847.ARW
```

### File Status Breakdown

Shows counts for each category:
- Files only on source
- Files in both locations
- Files moved (high/medium confidence)
- Source duplicates

## Limitations

- Compares by **relative path and filename only**, not file content or hash
- Moved file detection uses filename matching (may produce false positives for common names)
- Does not check for modified files (same path, different content)
- Case-insensitive matching (Windows default)
- Requires read access to both directories
- Full scan mode can be slow for very large directories (100K+ files)

## Troubleshooting

### "Directory does not exist" error
- Check that the path is correct
- Ensure you have permission to access the directory

### No files found
- Verify source directory contains files
- Check that source path points to the correct location

### Permission errors
- Some files may be skipped due to access restrictions
- Skipped files are counted in the summary

## Example Output

### Smart Scan Mode

```
============================================================
SMART DUPLICATE FINDER
============================================================

Source: /path/to/source
Target: /path/to/target
Output: missing_files.csv

Phase 1: Scanning source directory...
  Found 6682 files, skipped 0
  Time: 0.3 seconds

  Root files: 0
  Subdirectories: 1
  Top-level subdirs: Books

Phase 2: Scanning target directory (smart mode)...
  Note: 0 subdirectories not found on target:
  Scanned 5540 files, skipped 0
  Time: 0.6 seconds

Phase 3: Building filename index and comparing files...
  Time: 0.0 seconds

Phase 4: Writing results...
  Written 3018 rows to missing_files.csv
  Time: 0.0 seconds

============================================================
SUMMARY
============================================================
Scan mode: smart scan
Total files on source: 6682
Total files scanned on target: 5540
Files only on source: 2780
Files in both locations: 3664 (excluded from CSV)
Files moved to different path: 186 (high confidence)
Files possibly moved: 52 (medium confidence)
Source duplicates: 10
Skipped due to errors: 0

Phase 1 (source scan): 0.3s
Phase 2 (target scan): 0.6s
Phase 3 (comparison): 0.0s
Phase 4 (write output): 0.0s
Total time: 0.9s

Results saved to: missing_files.csv
```

### Full Scan Mode with Verbose

```
============================================================
SMART DUPLICATE FINDER
============================================================

Source: /path/to/photos
Target: /path/to/backup/Pictures
Output: photo_missing.csv

Phase 1: Scanning source directory...
  Found 816 files, skipped 0
  Time: 0.0 seconds

  Root files: 0
  Subdirectories: 1
  Top-level subdirs: 2015

Phase 2: Scanning target directory (full scan mode)...
  Will scan 37 subdirectories
    2002
    2003
    2015
    ...
  Scanned 108415 files, skipped 0
  Time: 33.0 seconds

Phase 3: Building filename index and comparing files...
  Time: 0.2 seconds

Phase 4: Writing results...
  Written 816 rows to photo_missing.csv
  Time: 0.0 seconds

============================================================
SUMMARY
============================================================
Scan mode: full scan
Total files on source: 816
Total files scanned on target: 108415
Files only on source: 85
Files in both locations: 0 (excluded from CSV)
Files moved to different path: 731 (high confidence)
Files possibly moved: 0 (medium confidence)
Source duplicates: 71
Skipped due to errors: 0

Phase 1 (source scan): 0.0s
Phase 2 (target scan): 33.0s
Phase 3 (comparison): 0.2s
Phase 4 (write output): 0.0s
Total time: 33.3s

Results saved to: photo_missing.csv
```

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Suggestions and improvements welcome!
