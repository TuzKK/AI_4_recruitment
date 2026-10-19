"""Run the experimental recommended-resume screenshot probe."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boss_cli.precontact_capture import main

if __name__ == "__main__":
    raise SystemExit(main())
