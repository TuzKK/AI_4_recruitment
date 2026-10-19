"""Smoke test for importing bossmaster.py without running the CLI."""
from pathlib import Path
import sys

print("Start bossmaster.py import smoke test...")

try:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("bossmaster", root / "bossmaster.py")
    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
        print("PASS module import succeeded")
    except Exception as e:
        print(f"FAIL module import failed: {e}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)

except ImportError as e:
    print(f"FAIL import error: {e}")
    import traceback
    traceback.print_exc()
    raise SystemExit(1)

print("Import smoke test finished")
