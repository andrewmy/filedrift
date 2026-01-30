#!/usr/bin/env python3
"""
Tests for filedrift.py
"""
import os
import sys
import tempfile
import shutil
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import filedrift

def create_test_structure(base_dir):
    """Create test directory structure for testing."""
    os.makedirs(base_dir / "source", exist_ok=True)
    os.makedirs(base_dir / "target", exist_ok=True)
    
    # Files that match in both
    (base_dir / "source" / "file1.txt").write_text("content1")
    (base_dir / "target" / "file1.txt").write_text("content1")
    
    # Files only on source
    (base_dir / "source" / "file2.txt").write_text("content2")
    
    # Files moved to different path
    os.makedirs(base_dir / "source" / "subdir", exist_ok=True)
    os.makedirs(base_dir / "target" / "other_location", exist_ok=True)
    (base_dir / "source" / "subdir" / "file3.txt").write_text("content3")
    (base_dir / "target" / "other_location" / "file3.txt").write_text("content3")
    
    # Duplicate files on source (same name, same size, different paths)
    os.makedirs(base_dir / "source" / "dup1", exist_ok=True)
    os.makedirs(base_dir / "source" / "dup2", exist_ok=True)
    (base_dir / "source" / "dup1" / "dupe.txt").write_text("duppe content")
    (base_dir / "source" / "dup2" / "dupe.txt").write_text("duppe content")
    
    # Directory with all files only on source
    os.makedirs(base_dir / "source" / "missing_dir", exist_ok=True)
    (base_dir / "source" / "missing_dir" / "file4.txt").write_text("missing")
    (base_dir / "source" / "missing_dir" / "file5.txt").write_text("missing")

def test_scan_directory():
    """Test the scan_directory function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        create_test_structure(base)
        
        # Test scanning source
        source_data = filedrift.scan_directory(base / "source")
        assert len(source_data['files']) == 7, f"Should find 7 files in source, found {len(source_data['files'])}"
        assert set(source_data['root_files']) == {'file1.txt', 'file2.txt'}, f"Root files not tracked: {source_data['root_files']}"
        
        # Test scanning target with specific subdirs
        target_data = filedrift.scan_directory(base / "target", subdirs_to_scan=['subdir'])
        assert len(target_data['files']) == 1, "Should find 1 file in target subdir"
        assert 'subdir/file3.txt' in target_data['files'], "Should find moved file"
        
        # Test filename index building
        target_filename_index = filedrift.build_filename_index(target_data['files'])
        assert len(target_filename_index) == 1, "Should have 1 unique filename in index"
        
        return True

def test_find_missing_files():
    """Test the find_missing_files function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        create_test_structure(base)
        
        source_data = filedrift.scan_directory(base / "source")
        target_data = filedrift.scan_directory(base / "target", subdirs_to_scan=['subdir', 'other_location'])
        
        target_filename_index = filedrift.build_filename_index(target_data['files'])
        source_filename_index = filedrift.build_filename_index(source_data['files'])
        
        results = filedrift.find_missing_files(source_data, target_data, target_filename_index, source_filename_index)
        
        # Check that we get expected results
        assert len(results['only_on_source']) == 2, "Should have 2 files only on source"
        assert len(results['in_both']) == 1, "Should have 1 file in both"
        assert len(results['moved_files']) == 2, "Should have 2 moved files"
        assert len(results['duplicates_on_source']) == 2, "Should have 2 duplicate groups"
        
        # Check status correctness
        status_counts = {'only_on_source': 0, 'in_both': 0, 'moved': 0, 'duplicate_on_source': 0}
        for row in results['only_on_source']:
            status_counts['only_on_source'] += 1
        for row in results['in_both']:
            status_counts['in_both'] += 1
        for row in results['moved_files']:
            status_counts['moved'] += 1
        for row in results['moved_files']:
            if row['status'] == 'duplicate_on_source':
                status_counts['duplicate_on_source'] += 1
        
        assert status_counts['only_on_source'] == 2
        assert status_counts['in_both'] == 1
        assert status_counts['moved'] == 2
        assert status_counts['duplicate_on_source'] == 2
        
        return True

def test_analyze_missing_directories():
    """Test the analyze_missing_directories function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        create_test_structure(base)
        
        source_data = filedrift.scan_directory(base / "source")
        target_data = filedrift.scan_directory(base / "target")
        
        results = filedrift.find_missing_files(
            source_data, target_data, 
            filedrift.build_filename_index(target_data['files']),
            filedrift.build_filename_index(source_data['files'])
        )
        
        entirely_missing = filedrift.analyze_missing_directories(
            results['only_on_source'], 
            source_data['files']
        )
        
        # Should find 1 entirely missing directory
        assert len(entirely_missing) == 1
        assert entirely_missing[0]['name'] == 'missing_dir', "Should find missing_dir"
        assert entirely_missing[0]['missing_files'] == 2
        assert entirely_missing[0]['total_files'] == 2
        
        # Test that partially missing directory not in list
        for dir_info in entirely_missing:
            assert dir_info['missing_files'] == dir_info['total_files'], "All files must be missing"
        
        return True

def test_csv_output():
    """Test CSV output generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        create_test_structure(base)
        
        output_file = base / "test_output.csv"
        
        # Run scan
        source_data = filedrift.scan_directory(base / "source")
        target_data = filedrift.scan_directory(base / "target")
        
        results = filedrift.find_missing_files(
            source_data, target_data,
            filedrift.build_filename_index(target_data['files']),
            filedrift.build_filename_index(source_data['files'])
        )
        filedrift.add_duplicate_groups(results['moved_files'], results['duplicates_on_source'])
        
        interesting_rows = results['only_on_source'] + results['moved_files']
        
        # Write CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['relative_path', 'source_path', 'source_size', 'target_path', 'target_size',
                         'found_at_path', 'match_type', 'confidence', 'status', 'duplicate_group']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(interesting_rows)
        
        # Verify CSV exists and has correct structure
        assert output_file.exists(), "CSV file should exist"
        assert output_file.stat().st_size > 0, "CSV file should not be empty"
        
        # Read back and verify columns
        with open(output_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            assert len(rows) == 5, "Should have 5 interesting rows"
            assert rows[0]['status'] == 'only_on_source'
            assert rows[1]['status'] == 'only_on_source'
            assert rows[2]['status'] == 'moved'
            assert rows[3]['status'] == 'moved'
            assert rows[4]['status'] == 'duplicate_on_source'
            assert rows[5]['status'] == 'duplicate_on_source'
            assert 'duplicate_group' in rows[4] or 'duplicate_group' in rows[5]
        
        return True

def test_exclude_high_confidence_flag():
    """Test the --exclude-high-confidence-moved flag."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        create_test_structure(base)
        
        # Add some high-confidence moved files
        os.makedirs(base / "source" / "high_conf", exist_ok=True)
        os.makedirs(base / "target" / "high_conf_loc", exist_ok=True)
        (base / "source" / "high_conf" / "file.txt").write_text("high conf")
        (base / "target" / "high_conf_loc" / "file.txt").write_text("high conf")
        
        source_data = filedrift.scan_directory(base / "source")
        target_data = filedrift.scan_directory(base / "target")
        
        results = filedrift.find_missing_files(
            source_data, target_data,
            filedrift.build_filename_index(target_data['files']),
            filedrift.build_filename_index(source_data['files'])
        )
        
        # Without exclude flag, all rows written
        output_file = base / "test_included.csv"
        interesting_rows = results['only_on_source'] + results['moved_files']
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['relative_path', 'source_path', 'source_size', 'target_path', 'target_size',
                         'found_at_path', 'match_type', 'confidence', 'status', 'directory']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(interesting_rows)
        
        # Should have high-confidence moved file
        high_conf_count = len([r for r in interesting_rows if r['confidence'] == 'high' and r['status'] == 'moved'])
        assert high_conf_count > 0, "Should have high-confidence moved files"
        
        # Simulate --exclude-high-confidence-moved flag
        interesting_rows_filtered = [r for r in interesting_rows if not (r['status'] == 'moved' and r['confidence'] == 'high')]
        excluded_count = len(interesting_rows) - len(interesting_rows_filtered)
        
        # Simulate flag logic (same as actual script)
        test_excluded_count = len([r for r in results['moved_files'] if r['confidence'] == 'high'])
        
        assert test_excluded_count == excluded_count, "Filter should work correctly"
        
        return True

def run_all_tests():
    """Run all tests and report results."""
    tests = [
        ("Scan directory function", test_scan_directory),
        ("Find missing files", test_find_missing_files),
        ("Analyze missing directories", test_analyze_missing_directories),
        ("CSV output generation", test_csv_output),
        ("Exclude high-confidence flag", test_exclude_high_confidence_flag)
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
    print(f"Failed: {len(failed)}/{len(tests)}")
    
    return len(failed) == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
