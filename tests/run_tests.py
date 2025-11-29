#!/usr/bin/env python3
import sys
import unittest
import subprocess
from pathlib import Path

def print_header(text):    
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def run_unit_tests():
    print_header("RUNNING UNIT TESTS")
    
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_determinism_verification():
    print_header("RUNNING DETERMINISM VERIFICATION")
    
    try:
        result = subprocess.run(
            [sys.executable, 'tests/verify_determinism.py'],
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error running determinism verification: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("  BLOCKCHAIN LAB 01 - TEST SUITE")
    print("  Testing Requirements (Part 9)")
    print("="*70)
    
    # Track results
    all_passed = True
    
    # 1. Run unit tests
    unit_tests_passed = run_unit_tests()
    all_passed = all_passed and unit_tests_passed
    
    # 2. Run determinism verification
    determinism_passed = run_determinism_verification()
    all_passed = all_passed and determinism_passed
    
    # Print final summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70 + "\n")
    
    print(f"Unit Tests:               {'PASSED' if unit_tests_passed else 'FAILED'}")
    print(f"Determinism Verification: {'PASSED' if determinism_passed else 'FAILED'}")
    
    print("\n" + "="*70)
    if all_passed:
        print("   ALL TESTS PASSED")
    else:
        print("   SOME TESTS FAILED")
    print("="*70 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
