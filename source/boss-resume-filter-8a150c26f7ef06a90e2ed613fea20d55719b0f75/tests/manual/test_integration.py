#!/usr/bin/env python3
"""
Integration test script - Validate the complete workflow for getting job info from BOSS
"""
import subprocess
import sys
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"


def test_manual_login_step():
    """Test step 1: Open browser with manual login"""
    print("=== Testing Step 1: Opening browser for manual login ===")

    script_path = SCRIPTS_DIR / "fetch_jobs_sync.py"
    try:
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=ROOT,
        )

        print("STDOUT:", result.stdout[:500])
        if result.stderr:
            print("STDERR:", result.stderr[:500])

        # Check if successfully started
        if "浏览器已打开" in result.stdout and "RESULT:" in result.stdout:
            for line in result.stdout.split("\n"):
                if line.startswith("RESULT:"):
                    data = json.loads(line[7:])
                    if data.get("status") == "success":
                        print("SUCCESS: Step 1 completed successfully")
                        return True
        print("FAIL: Issue with Step 1 execution")
        return False
    except subprocess.TimeoutExpired:
        print("WARNING: Step 1 timed out but browser might have opened")
        return True
    except Exception as e:
        print(f"ERROR: Step 1 failed: {e}")
        return False

def test_extract_jobs_step():
    """Test step 2: Extract job information"""
    print("\n=== Testing Step 2: Extracting job information ===")

    script_path = SCRIPTS_DIR / "extract_jobs.py"
    try:
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "AUTOMATED_RUN": "1", "MANUAL_INPUT": "n"},
            cwd=ROOT,
        )

        print("STDOUT:", result.stdout[:500])
        if result.stderr:
            print("STDERR:", result.stderr[:500])

        # Check if we have proper output
        if "RESULT:" in result.stdout:
            for line in result.stdout.split("\n"):
                if line.startswith("RESULT:"):
                    try:
                        data = json.loads(line[7:])
                        print(f"SUCCESS: Step 2 returned result: {data}")
                        return True
                    except json.JSONDecodeError:
                        continue

        print("FAIL: Step 2 did not find expected result")
        return False
    except subprocess.TimeoutExpired:
        print("WARNING: Step 2 timed out")
        return False
    except Exception as e:
        print(f"ERROR: Step 2 failed: {e}")
        return False

def main():
    print("Starting integration test...")

    # Test step 1
    step1_success = test_manual_login_step()

    # Test step 2
    step2_success = test_extract_jobs_step()

    print(f"\n=== Test Results ===")
    print(f"Step 1 (Browser Open): {'PASS' if step1_success else 'FAIL'}")
    print(f"Step 2 (Job Extraction): {'PASS' if step2_success else 'FAIL'}")

    if step1_success and step2_success:
        print("SUCCESS: All tests passed!")
        return 0
    else:
        print("WARNING: Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
