#!/usr/bin/env python3
"""
Tests for filedrift.py
"""

import contextlib
import csv
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import filedrift


def create_test_structure(base_dir):
    """Create test directory structure for testing."""
    base = Path(base_dir)

    # Source directory
    source = base / "source"
    target = base / "target"
    os.makedirs(source, exist_ok=True)
    os.makedirs(target, exist_ok=True)

    # Files that match in both
    (source / "file1.txt").write_text("content1")
    (target / "file1.txt").write_text("content1")

    # Files only on source
    (source / "file2.txt").write_text("content2")

    # Files in source subdirectory
    source_sub = source / "subdir"
    target_sub = target / "other_location"
    os.makedirs(source_sub, exist_ok=True)
    os.makedirs(target_sub, exist_ok=True)
    (source_sub / "file3.txt").write_text("content3")
    (target_sub / "file3.txt").write_text("content3")

    # Moved file with same name, different path
    (source / "file4.txt").write_text("content4")
    (target / "moved" / "file4.txt").parent.mkdir(exist_ok=True)
    (target / "moved" / "file4.txt").write_text("content4")

    # Duplicate files on source (same name, same size, different paths)
    dup1 = source / "dup1"
    dup2 = source / "dup2"
    os.makedirs(dup1, exist_ok=True)
    os.makedirs(dup2, exist_ok=True)
    (dup1 / "dupe.txt").write_text("duppe content")
    (dup2 / "dupe.txt").write_text("duppe content")

    # Directory with all files only on source
    missing_dir = source / "missing_dir"
    os.makedirs(missing_dir, exist_ok=True)
    (missing_dir / "file5.txt").write_text("missing")
    (missing_dir / "file6.txt").write_text("missing2")

    # Another subdir in source but not in target
    another_dir = source / "another_dir"
    os.makedirs(another_dir, exist_ok=True)
    (another_dir / "file7.txt").write_text("another")


def test_scan_directory():
    """Test the scan_directory function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        create_test_structure(base)

        # Test scanning source (full scan)
        source_data = filedrift.scan_directory(base / "source")
        assert len(source_data["files"]) >= 7, f"Should find at least 7 files in source, found {len(source_data['files'])}"
        assert source_data["skipped"] == 0, "Should not skip any files"
        assert len(source_data["root_files"]) == 3, (
            f"Should have 3 root files (file1.txt, file2.txt, file4.txt), found {len(source_data['root_files'])}"
        )

        # Test scanning with subdirs_to_scan
        target_data = filedrift.scan_directory(base / "target", subdirs_to_scan=["other_location", "moved"])
        assert len(target_data["files"]) >= 1, "Should find at least 1 file in target"

        # Test scanning non-existent directory (suppress expected error output)
        with contextlib.redirect_stdout(io.StringIO()):
            result = filedrift.scan_directory(base / "nonexistent")
        assert len(result["files"]) == 0, "Should return empty files dict for non-existent dir"

        return True


def test_get_top_level_subdirs():
    """Test the get_top_level_subdirs function."""
    files_dict = {
        "file1.txt": {"relative_path": "file1.txt", "size": 100},
        "subdir/file1.txt": {"relative_path": "subdir/file1.txt", "size": 200},
        "subdir/file2.txt": {"relative_path": "subdir/file2.txt", "size": 300},
        "other/file.txt": {"relative_path": "other/file.txt", "size": 400},
        "deep/nested/file.txt": {"relative_path": "deep/nested/file.txt", "size": 500},
    }

    subdirs = filedrift.get_top_level_subdirs(files_dict)
    assert len(subdirs) == 3, f"Should find 3 top-level subdirs, found {len(subdirs)}"
    assert "subdir" in subdirs, "Should include 'subdir'"
    assert "other" in subdirs, "Should include 'other'"
    assert "deep" in subdirs, "Should include 'deep'"

    return True


def test_build_filename_index():
    """Test the build_filename_index function."""
    files_dict = {
        "dir1/file.txt": {"relative_path": "dir1/file.txt", "path": "/dir1/file.txt", "size": 100},
        "dir2/file.txt": {"relative_path": "dir2/file.txt", "path": "/dir2/file.txt", "size": 200},
        "other.txt": {"relative_path": "other.txt", "path": "/other.txt", "size": 300},
    }

    index = filedrift.build_filename_index(files_dict)
    assert len(index) == 2, f"Should have 2 unique filenames, found {len(index)}"
    assert "file.txt" in index, "Should index 'file.txt'"
    assert len(index["file.txt"]) == 2, "Should have 2 files named 'file.txt'"
    assert "other.txt" in index, "Should index 'other.txt'"

    return True


def test_find_missing_files():
    """Test the find_missing_files function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        create_test_structure(base)

        source_data = filedrift.scan_directory(base / "source")

        # Create matching target structure
        target = base / "target"
        (target / "file1.txt").write_text("content1")
        (target / "other_location" / "file3.txt").write_text("content3")
        (target / "moved" / "file4.txt").write_text("content4")
        (target / "dup1" / "dupe.txt").parent.mkdir(exist_ok=True)
        (target / "dup1" / "dupe.txt").write_text("duppe content")

        target_data = filedrift.scan_directory(base / "target", subdirs_to_scan=["other_location", "moved", "dup1"])
        target_filename_index = filedrift.build_filename_index(target_data["files"])
        source_filename_index = filedrift.build_filename_index(source_data["files"])

        results = filedrift.find_missing_files(source_data, target_data, target_filename_index, source_filename_index)

        assert "only_on_source" in results, "Should have 'only_on_source' key"
        assert "in_both" in results, "Should have 'in_both' key"
        assert "moved_files" in results, "Should have 'moved_files' key"
        assert "duplicates_on_source" in results, "Should have 'duplicates_on_source' key"

        assert len(results["in_both"]) >= 1, "Should have at least 1 file in both locations"
        assert len(results["only_on_source"]) >= 1, "Should have at least 1 file only on source"
        assert len(results["moved_files"]) >= 1, "Should have at least 1 moved file"

        return True


def test_add_duplicate_groups():
    """Test the add_duplicate_groups function."""
    duplicates_on_source = {(12, "dupe.txt"): ["dup1/dupe.txt", "dup2/dupe.txt"]}

    moved_files = [
        {"relative_path": "dup1/dupe.txt", "status": "duplicate_on_source", "source_size": 12, "duplicate_group": ""},
        {"relative_path": "dup2/dupe.txt", "status": "duplicate_on_source", "source_size": 12, "duplicate_group": ""},
        {"relative_path": "other.txt", "status": "moved", "source_size": 100, "duplicate_group": ""},
    ]

    filedrift.add_duplicate_groups(moved_files, duplicates_on_source)

    dup1 = [f for f in moved_files if f["relative_path"] == "dup1/dupe.txt"][0]
    dup2 = [f for f in moved_files if f["relative_path"] == "dup2/dupe.txt"][0]
    other = [f for f in moved_files if f["relative_path"] == "other.txt"][0]

    assert "dup2/dupe.txt" in dup1["duplicate_group"], "dup1 should reference dup2"
    assert "dup1/dupe.txt" in dup2["duplicate_group"], "dup2 should reference dup1"
    assert other["duplicate_group"] == "", "non-duplicate should have empty group"

    return True


def test_analyze_missing_directories():
    """Test the analyze_missing_directories function."""
    source_files = {
        "file1.txt": {"relative_path": "file1.txt", "size": 100},
        "dir1/file2.txt": {"relative_path": "dir1/file2.txt", "size": 200},
        "dir1/file3.txt": {"relative_path": "dir1/file3.txt", "size": 300},
        "dir2/file4.txt": {"relative_path": "dir2/file4.txt", "size": 400},
        "dir2/file5.txt": {"relative_path": "dir2/file5.txt", "size": 500},
    }

    only_on_source = [
        {"relative_path": "dir1/file2.txt", "source_size": 200},
        {"relative_path": "dir1/file3.txt", "source_size": 300},
        {"relative_path": "dir2/file4.txt", "source_size": 400},
        {"relative_path": "file1.txt", "source_size": 100},
    ]

    moved_files = []
    in_both = []

    entirely_missing = filedrift.analyze_missing_directories(only_on_source, moved_files, in_both, source_files)

    assert len(entirely_missing) >= 2, f"Should find at least 2 entirely missing dirs, found {len(entirely_missing)}"

    # Check that dir1 is entirely missing (all 2 files are missing)
    dir1_missing = [d for d in entirely_missing if "dir1" in d["name"]]
    assert len(dir1_missing) == 1, "dir1 should be marked as entirely missing"
    assert dir1_missing[0]["missing_files"] == 2, "dir1 should have 2 missing files"
    assert dir1_missing[0]["missing_size"] == 500, "dir1 should have 500 missing bytes"

    return True


def test_csv_output():
    """Test CSV output generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        output_csv = base / "test_output.csv"

        test_data = [
            {
                "relative_path": "test/file.txt",
                "source_path": "/source/test/file.txt",
                "source_size": 1024,
                "target_path": "",
                "target_size": "",
                "found_at_path": "",
                "match_type": "none",
                "confidence": "",
                "status": "only_on_source",
                "duplicate_group": "",
            }
        ]

        with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "relative_path",
                "source_path",
                "source_size",
                "target_path",
                "target_size",
                "found_at_path",
                "match_type",
                "confidence",
                "status",
                "duplicate_group",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(test_data)

        # Verify CSV was created and has correct content
        assert output_csv.exists(), "CSV file should be created"

        with open(output_csv, encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            assert len(rows) == 1, "Should have 1 data row"
            assert rows[0]["relative_path"] == "test/file.txt", "Should preserve relative_path"
            assert rows[0]["status"] == "only_on_source", "Should preserve status"

        return True


def test_exclude_high_confidence_moved():
    """Test --exclude-high-confidence-moved flag behavior."""
    rows = [
        {"status": "only_on_source", "confidence": ""},
        {"status": "moved", "confidence": "high"},
        {"status": "moved", "confidence": "medium"},
        {"status": "duplicate_on_source", "confidence": "high"},
    ]

    # This is the actual logic used in filedrift.py line 384
    filtered = [r for r in rows if not (r["status"] == "moved" and r["confidence"] == "high")]

    # duplicate_on_source is NOT moved, so it should be kept
    assert len(filtered) == 3, (
        f"Should have 3 rows after filtering (only_on_source, moved medium, duplicate_on_source), found {len(filtered)}"
    )
    assert any(r["status"] == "only_on_source" for r in filtered), "Should keep only_on_source"
    assert any(r["status"] == "moved" and r["confidence"] == "medium" for r in filtered), "Should keep medium-confidence moved"
    assert any(r["status"] == "duplicate_on_source" for r in filtered), "Should keep duplicate_on_source"

    return True


def test_exclude_high_confidence_moved_count_in_output():
    """Test excluded count in stdout when --exclude-high-confidence-moved is used."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        source = base / "source"
        target = base / "target"
        os.makedirs(source, exist_ok=True)
        os.makedirs(target, exist_ok=True)

        # In both
        (source / "same.txt").write_text("same")
        (target / "same.txt").write_text("same")

        # Only on source
        (source / "only1.txt").write_text("only1")
        (source / "only2.txt").write_text("only2")

        # High-confidence moved (same name, same size)
        (source / "moved.txt").write_text("moved")
        (target / "other" / "moved.txt").parent.mkdir(exist_ok=True)
        (target / "other" / "moved.txt").write_text("moved")

        output_csv = base / "out.csv"

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "filedrift.py"),
                "--source",
                str(source),
                "--target",
                str(target),
                "--full-scan",
                "--exclude-high-confidence-moved",
                "--output",
                str(output_csv),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        assert "Excluding 1 high-confidence moved files from CSV output" in result.stdout, (
            "Expected excluded count to reflect only high-confidence moved files"
        )

        return True


def test_exclude_high_confidence_moved_note_text():
    """Test summary note text for --exclude-high-confidence-moved."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        source = base / "source"
        target = base / "target"
        os.makedirs(source, exist_ok=True)
        os.makedirs(target, exist_ok=True)

        (source / "moved.txt").write_text("moved")
        (target / "other" / "moved.txt").parent.mkdir(exist_ok=True)
        (target / "other" / "moved.txt").write_text("moved")

        output_csv = base / "out.csv"

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "filedrift.py"),
                "--source",
                str(source),
                "--target",
                str(target),
                "--full-scan",
                "--exclude-high-confidence-moved",
                "--output",
                str(output_csv),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        assert "use without --exclude-high-confidence-moved to include" in result.stdout, (
            "Expected summary note to explain how to include high-confidence moved files"
        )

        return True


def test_dry_run_missing_count_ignores_root_files():
    """Test that dry-run missing count ignores root files with same name as missing subdir."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        source = base / "source"
        target = base / "target"
        os.makedirs(source, exist_ok=True)
        os.makedirs(target, exist_ok=True)

        # Root file whose name matches a missing subdir (case-insensitive)
        (source / "photos").write_text("root file")

        # Missing subdir with files (different case)
        missing_subdir = source / "Photos"
        try:
            os.makedirs(missing_subdir, exist_ok=False)
        except OSError:
            # Case-insensitive filesystem; skip this test.
            return True
        (missing_subdir / "a.txt").write_text("a")
        (missing_subdir / "b.txt").write_text("b")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            filedrift.dry_run(str(source), str(target), full_scan=False)

        stdout = output.getvalue()
        assert "Estimated target files to scan: ~1" in stdout, (
            "Estimated count should only exclude files under missing subdirs, not root files"
        )

        return True


def test_case_insensitive_matching():
    """Test case-insensitive path matching - scan_directory normalizes paths to lowercase."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        source = base / "source"
        target = base / "target"
        os.makedirs(source, exist_ok=True)
        os.makedirs(target, exist_ok=True)

        # Create same file with different case
        (source / "File.TXT").write_text("content")
        (target / "file.txt").write_text("content")

        source_data = filedrift.scan_directory(base / "source")
        target_data = filedrift.scan_directory(base / "target")

        # Both paths normalized to lowercase, so they match exactly
        assert "file.txt" in source_data["files"], "Source file should be normalized to lowercase"
        assert "file.txt" in target_data["files"], "Target file should be normalized to lowercase"

        target_filename_index = filedrift.build_filename_index(target_data["files"])
        source_filename_index = filedrift.build_filename_index(source_data["files"])

        results = filedrift.find_missing_files(source_data, target_data, target_filename_index, source_filename_index)

        # Should find file in both (exact path match after normalization)
        assert len(results["in_both"]) == 1, "Should find file in both locations after path normalization"
        assert len(results["only_on_source"]) == 0, "Should not have any files only on source"

        return True


def test_should_ignore_file():
    """Test the should_ignore_file function."""
    # Test exact matches
    assert filedrift.should_ignore_file(".DS_Store"), "Should ignore .DS_Store"
    assert filedrift.should_ignore_file("Thumbs.db"), "Should ignore Thumbs.db"

    # Test case-insensitive matches
    assert filedrift.should_ignore_file(".ds_store"), "Should ignore .ds_store (lowercase)"
    assert filedrift.should_ignore_file("thumbs.db"), "Should ignore thumbs.db (lowercase)"
    assert filedrift.should_ignore_file(".DS_STORE"), "Should ignore .DS_STORE (uppercase)"
    assert filedrift.should_ignore_file("THUMBS.DB"), "Should ignore THUMBS.DB (uppercase)"

    # Test normal files are not ignored
    assert not filedrift.should_ignore_file("document.txt"), "Should not ignore document.txt"
    assert not filedrift.should_ignore_file("image.jpg"), "Should not ignore image.jpg"
    assert not filedrift.should_ignore_file(".gitignore"), "Should not ignore .gitignore"

    return True


def test_ignored_files_not_scanned():
    """Test that ignored files (.DS_Store, Thumbs.db) are not scanned at all."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        source = base / "source"
        os.makedirs(source, exist_ok=True)

        # Create normal files
        (source / "file1.txt").write_text("content1")
        (source / "file2.txt").write_text("content2")

        # Create ignored files in various cases
        (source / ".DS_Store").write_text("ignored")
        (source / "Thumbs.db").write_text("ignored")
        (source / ".ds_store").write_text("ignored")
        (source / "thumbs.db").write_text("ignored")

        # Create subdirectory with ignored files
        subdir = source / "subdir"
        os.makedirs(subdir, exist_ok=True)
        (subdir / "file3.txt").write_text("content3")
        (subdir / ".DS_Store").write_text("ignored")

        source_data = filedrift.scan_directory(base / "source")

        # Should only find the 3 normal files
        assert len(source_data["files"]) == 3, f"Should find only 3 normal files, found {len(source_data['files'])}"
        assert "file1.txt" in source_data["files"], "Should find file1.txt"
        assert "file2.txt" in source_data["files"], "Should find file2.txt"
        # Normalize path for cross-platform compatibility
        subdir_file3_key = str(Path("subdir") / "file3.txt").lower()
        assert subdir_file3_key in source_data["files"], f"Should find subdir/file3.txt (key: {subdir_file3_key})"

        # Should not find any ignored files
        assert ".ds_store" not in source_data["files"], "Should not find .DS_Store"
        assert "thumbs.db" not in source_data["files"], "Should not find Thumbs.db"

        return True


def test_ignored_files_not_in_missing_dirs():
    """Test that ignored files are not counted in 'directories missing completely' logic."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        source = base / "source"
        os.makedirs(source, exist_ok=True)

        # Create a directory with a normal file and ignored files
        test_dir = source / "test_dir"
        os.makedirs(test_dir, exist_ok=True)
        (test_dir / "normal.txt").write_text("normal content")
        (test_dir / ".DS_Store").write_text("ignored")

        # Create another directory with only ignored files
        only_ignored_dir = source / "only_ignored"
        os.makedirs(only_ignored_dir, exist_ok=True)
        (only_ignored_dir / "Thumbs.db").write_text("ignored")
        (only_ignored_dir / ".ds_store").write_text("ignored")

        source_data = filedrift.scan_directory(base / "source")

        # Simulate only_on_source with just the normal file
        only_on_source = [{"relative_path": "test_dir/normal.txt", "source_size": 13}]
        moved_files = []
        in_both = []

        entirely_missing = filedrift.analyze_missing_directories(only_on_source, moved_files, in_both, source_data["files"])

        # test_dir should be marked as entirely missing (1 of 1 real file is missing)
        test_dir_missing = [d for d in entirely_missing if "test_dir" in d["name"]]
        assert len(test_dir_missing) == 1, "test_dir should be marked as entirely missing"
        assert test_dir_missing[0]["total_files"] == 1, "test_dir should only count normal files (1), not .DS_Store"
        assert test_dir_missing[0]["missing_files"] == 1, "test_dir should have 1 missing file"

        # only_ignored_dir should NOT appear - it has no real files, only ignored ones
        only_ignored_missing = [d for d in entirely_missing if "only_ignored" in d["name"]]
        assert len(only_ignored_missing) == 0, "only_ignored_dir should not appear (contains only ignored files)"

        return True


def test_moved_files_not_counted_as_missing_dirs():
    """Test that directories with moved files are not marked as entirely missing."""
    source_files = {
        "dir1/file1.txt": {"relative_path": "dir1/file1.txt", "size": 100},
        "dir1/file2.txt": {"relative_path": "dir1/file2.txt", "size": 200},
        "dir2/file3.txt": {"relative_path": "dir2/file3.txt", "size": 300},
    }

    # All files in dir1 are moved (found at different path in target)
    moved_files = [
        {"relative_path": "dir1/file1.txt", "source_size": 100},
        {"relative_path": "dir1/file2.txt", "source_size": 200},
    ]

    # Only dir2 has a file that's truly missing
    only_on_source = [{"relative_path": "dir2/file3.txt", "source_size": 300}]

    in_both = []

    entirely_missing = filedrift.analyze_missing_directories(only_on_source, moved_files, in_both, source_files)

    # dir1 should NOT be marked as entirely missing (all files were found, just moved)
    dir1_missing = [d for d in entirely_missing if "dir1" in d["name"]]
    assert len(dir1_missing) == 0, "dir1 should not be marked as missing (all files were moved)"

    # dir2 should be marked as entirely missing (its file is truly missing)
    dir2_missing = [d for d in entirely_missing if "dir2" in d["name"]]
    assert len(dir2_missing) == 1, "dir2 should be marked as entirely missing"
    assert dir2_missing[0]["missing_files"] == 1, "dir2 should have 1 missing file"
    assert dir2_missing[0]["total_files"] == 1, "dir2 should have 1 total file"

    return True


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        ("Scan directory function", test_scan_directory),
        ("Get top-level subdirs", test_get_top_level_subdirs),
        ("Build filename index", test_build_filename_index),
        ("Find missing files", test_find_missing_files),
        ("Add duplicate groups", test_add_duplicate_groups),
        ("Analyze missing directories", test_analyze_missing_directories),
        ("CSV output generation", test_csv_output),
        ("Exclude high-confidence moved flag", test_exclude_high_confidence_moved),
        ("Exclude high-confidence moved count", test_exclude_high_confidence_moved_count_in_output),
        ("Exclude high-confidence moved note text", test_exclude_high_confidence_moved_note_text),
        ("Case-insensitive matching", test_case_insensitive_matching),
        ("Dry-run missing count ignores root files", test_dry_run_missing_count_ignores_root_files),
        ("Should ignore file function", test_should_ignore_file),
        ("Ignored files not scanned", test_ignored_files_not_scanned),
        ("Ignored files not in missing dirs", test_ignored_files_not_in_missing_dirs),
        ("Moved files not counted as missing dirs", test_moved_files_not_counted_as_missing_dirs),
    ]

    passed = []
    failed = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed.append(test_name)
                print(f"[PASS] {test_name}")
            else:
                failed.append(test_name)
                print(f"[FAIL] {test_name}")
        except AssertionError as e:
            failed.append(test_name)
            print(f"[FAIL] {test_name}: {str(e)}")
        except Exception as e:
            failed.append(test_name)
            print(f"[FAIL] {test_name}: {str(e)}")

    print()
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Passed: {len(passed)}/{len(tests)}")

    if failed:
        print("\nFailed tests:")
        for test in failed:
            print(f"  - {test}")
        return False
    else:
        print("\nAll tests passed!")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
