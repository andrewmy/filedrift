# AGENTS.md

This document provides guidelines for AI agents working on this codebase.

## Project Overview

This is a Python utility for comparing files between directories. The main tool is `filedrift.py`, which intelligently scans directories to find files present in a source location but missing from a target location.

## Build/Lint/Test Commands

This project uses plain Python with no external dependencies. Requires Python 3.9+.

### Running the main script
```bash
python filedrift.py --source "/path/to/source" --target "/path/to/target"
python filedrift.py --source "/path/to/source" --target "/path/to/target" --dry-run
python filedrift.py --source "/path/to/source" --target "/path/to/target" --full-scan
python filedrift.py --source "/path/to/photos" --target "/path/to/backup/Pictures" --full-scan --exclude-high-confidence-moved
```

### Dry-run mode (recommended before full scans)
```bash
python filedrift.py --source "/path/to/source" --target "/path/to/target" --dry-run
```

### Running tests
```bash
python test_filedrift.py
```

### Running linting
```bash
uv tool install ruff
ruff check .
```

### Testing

The project includes `test_filedrift.py` with comprehensive tests:

**What's covered:**
- **scan_directory()**: Tests directory scanning with subdirectory filtering
- **find_missing_files()**: Tests main comparison logic
- **analyze_missing_directories()**: Tests directory analysis and entirely-missing detection
- **CSV output generation**: Tests CSV structure and content
- **--exclude-high-confidence-moved flag**: Tests filtering of high-confidence moved files
- **Edge cases**: Unicode filenames, root files, partial directory matches

**How tests work:**
- Creates temporary test directory structures
- Tests individual functions in isolation
- Validates CSV column counts and data types
- Simulates all CLI flags and options

**Note**: Since this is a file system utility, traditional code coverage tools (pytest + coverage.py) are not used. The test suite exercises all core functionality with realistic fixtures.

## Code Style Guidelines

### Import Organization
```python
#!/usr/bin/env python3
import argparse        # CLI argument parsing
import csv
import time
from collections import defaultdict
from pathlib import Path  # Always use Path for file operations
from typing import Any    # For type hints
```
- Use `from pathlib import Path` for all file system operations
- Keep imports in alphabetical order after shebang
- Group: standard library, third-party, local modules (when applicable)

### File Paths and Path Handling
- **ALWAYS** use `pathlib.Path` instead of `os.path` or string concatenation
- Convert to strings only when needed for external APIs
- Use `.rglob('*')` for recursive directory traversal
- Use `.exists()` and `.is_dir()` or `.is_file()` for path validation

```python
# Good
root = Path(source_dir)
for file in root.rglob('*'):
    if file.is_file():
        rel_path = file.relative_to(root)

# Avoid
for file in os.walk(source_dir):  # Use pathlib instead
```

### Naming Conventions
- Functions: `snake_case` with descriptive names
- Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE` (rarely used)
- Dictionary keys: `snake_case` for clarity
- CLI args: `kebab-case` (via argparse)

### Type Hints
- Add type hints to all function parameters and return values
- Use modern built-in syntax: `dict[str, Any]`, `list[str]`, `str | None`
- Use `str | Path` union type for path parameters that accept either format
- Use `typing.Any` for dynamic types
- Compatible with Python 3.9+

### Linting
- Use ruff for linting (installed via `uv tool install ruff`)
- Run with `ruff check .`
- Configuration in `pyproject.toml`
- Line length set to 130, E501 (line too long) ignored to allow long type signatures and help strings
- Code style follows: E, W, F, I, B, C4, UP ruff rules

### Data Structures
- Use dictionaries for file metadata with clear keys: `path`, `size`, `relative_path`
- Use lowercase keys for dictionary lookups that need case-insensitive matching
- Store both normalized (lowercase) and original strings for comparison

```python
files[rel_path_str.lower()] = {
    'path': str(file),
    'relative_path': rel_path_str,  # Preserve original case
    'size': file.stat().st_size
}
```

### Error Handling
- Wrap file operations in try/except blocks
- Log skipped files with error messages
- Continue processing other files after errors
- Use `path.exists()` checks before operations

```python
try:
    rel_path = file.relative_to(root)
    files[rel_path_str.lower()] = {'path': str(file), 'size': file.stat().st_size}
except Exception as e:
    skipped += 1
    print(f"  Skipped {file}: {e}")
```

### Function Design
- Keep functions focused on single responsibilities
- Return dictionaries with clear structure for complex data
- Include docstrings for all non-trivial functions

```python
def scan_directory(root_dir, subdirs_to_scan=None):
    """Scan directory and return file info. If subdirs_to_scan is provided, only scan those subdirs."""
    # Implementation
    return {'files': files, 'skipped': skipped, 'root_files': root_files}
```

### CLI Arguments
- Use `argparse` for CLI interfaces
- Use `--kebab-case` for long arguments
- Provide helpful help text for all arguments
- Use `action='store_true'` for boolean flags

```python
parser.add_argument('--source', required=True, help='Source directory (smaller, e.g., USB)')
parser.add_argument('--target', required=True, help='Target directory (larger, e.g., OneDrive or SMB)')
parser.add_argument('--output', default='missing_files.csv', help='Output CSV file path')
parser.add_argument('--dry-run', action='store_true', help='Show scan plan without executing')
parser.add_argument('--full-scan', action='store_true', help='Scan entire target directory')
parser.add_argument('--verbose', action='store_true', help='Show detailed progress')
parser.add_argument('--exclude-high-confidence-moved', action='store_true', help='Exclude high-confidence moved files from CSV output')
```

### Exclude High-Confidence Moved Files

When `--exclude-high-confidence-moved` flag is used:
- Removes files with `status=moved` and `confidence=high` from CSV output
- Only writes to CSV:
  - `only_on_source` files (truly missing)
  - `moved` files with `confidence=medium` (uncertain matches)
  - `duplicate_on_source` files (source duplicates)
- Adds console note showing how many high-confidence moved files were excluded
- Useful when you only want to see truly missing files and uncertain matches

### Performance Considerations
- Avoid scanning large directories unnecessarily
- Use smart subdirectory scanning: only scan target subdirs that exist in source
- Track and report timing for each phase
- Use case-insensitive comparisons via `.lower()` normalization
- Don't read file content (use `stat()` only) to avoid triggering downloads

### Output Formatting
- Use `=`*60 for section headers
- Report timing with 1 decimal place: `Time: 0.3 seconds`
- Format large numbers with commas: `1024000` → `1,024,000`
- Include summary statistics at the end of operations

### File I/O
- Use `encoding='utf-8'` when reading/writing text files
- Use `newline=''` with CSV writer to prevent extra blank lines
- Use context managers (`with open()` as f:) for file operations

```python
with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_rows)
```

### String Formatting
- Use f-strings for all string formatting
- Align consistent indentation in output messages
- Use escape sequences only when necessary

```python
print(f"  Found {len(files)} files, skipped {skipped}")
print(f"  Time: {phase1_time:.1f} seconds")
```

### Windows Compatibility
- This project runs on Windows 11
- Use raw strings for Windows paths: `r"C:\Path\To\Directory"`
- Handle path separators appropriately (pathlib handles this automatically)
- Avoid special Unicode characters that may not display correctly in Windows console

## Existing Code Patterns to Follow

1. **Smart scanning**: Identify subdirs in source first, then scan only matching subdirs in target
2. **Phased execution**: Divide operations into clear phases with timing reports
3. **Dry-run mode**: Always provide a preview mode before executing
4. **CSV output**: Use standard CSV format with clear headers
5. **Error resilience**: Skip problematic files but continue processing others
6. **Moved file detection**: Build filename index for target, match by filename when path differs
7. **Directory analysis**: Track directory-level statistics for "entirely missing" detection
8. **Duplicate grouping**: Identify source files with same name and size, group them for reporting

## When Making Changes

1. Test with `--dry-run` first to verify scan plan
2. Run on small test directories before large directories
3. Verify CSV output has correct structure
4. Check that case-insensitive matching works correctly
5. Ensure performance remains acceptable (< 2 seconds for typical usage)

## Common Patterns in This Codebase

```python
# Pattern 1: Safe directory scanning
for file in root.rglob('*'):
    if file.is_file():
        try:
            # Process file
        except Exception as e:
            skipped += 1

# Pattern 2: Case-insensitive dictionary lookup
normalized_key = rel_path_str.lower()
files[normalized_key] = {...}
if normalized_key in other_files:
    # Found match

# Pattern 3: Phased execution with timing
phase_start = time.time()
# Do work
phase_time = time.time() - phase_start
print(f"  Time: {phase_time:.1f} seconds")
```
