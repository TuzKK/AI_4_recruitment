"""Watch .build_progress.json and emit one line per state change."""
import json, time, sys
from pathlib import Path

# Force UTF-8 to avoid GBK crash on Unicode
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

f = Path(__file__).parent.parent / ".build_progress.json"
prev = ""

while True:
    try:
        raw = f.read_text(encoding="utf-8")
        if raw != prev:
            prev = raw
            d = json.loads(raw)

            if d.get("status") == "completed":
                t = d.get("total_duration", 0)
                m, s = divmod(int(t), 60)
                print(f"DONE: v{d['version']} total {t:.0f}s ({m}m{s:02d}s) {d.get('artifact','')}")
                sys.stdout.flush()
                break

            idx = d.get("current_step", -1)
            steps = d.get("steps", [])
            elapsed = d.get("elapsed", 0)
            done = sum(1 for s in steps if s.get("status") == "done")

            if 0 <= idx < len(steps):
                cur = steps[idx]
                sub = cur.get("last_sub", "") or ""
                line = f"[{idx+1}/{len(steps)}] RUNNING: {cur['name']}  ({elapsed:.0f}s, {done} done)"
                if sub:
                    line += f"  | {sub}"
                print(line, flush=True)

    except (FileNotFoundError, json.JSONDecodeError):
        pass

    time.sleep(3)
