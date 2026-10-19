"""Fetch only selected files from a pinned, licensed synthetic resume corpus."""

from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "3ecd09129f65955e743aacf67f2785fcee10d461"
BASE = f"https://raw.githubusercontent.com/jijunhao/SyntheticResumeData/{COMMIT}"
DEST = ROOT / "source/SyntheticResumeData/resume_list_pdf"
IDS = [item["source_id"] for item in json.loads(
    (ROOT / ".runtime/synthetic_review_pool.json").read_text(encoding="utf-8")
)]


def fetch(source_id: str) -> tuple[str, str]:
    path = DEST / f"{source_id}.pdf"
    if path.exists() and path.read_bytes().startswith(b"%PDF"):
        return source_id, "cached"
    url = f"{BASE}/resume_list_pdf/{source_id}.pdf"
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "synthetic-resume-curation/1.0"})
            with urllib.request.urlopen(request, timeout=40) as response:
                data = response.read()
            if not data.startswith(b"%PDF"):
                raise ValueError("response is not a PDF")
            path.write_bytes(data)
            return source_id, f"downloaded {len(data)}"
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if attempt == 3:
                return source_id, f"ERROR {exc}"
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch, IDS))
    errors = [result for result in results if result[1].startswith("ERROR")]
    print(f"requested={len(IDS)} cached={sum(x[1] == 'cached' for x in results)} "
          f"downloaded={sum(x[1].startswith('downloaded') for x in results)} errors={len(errors)}")
    for source_id, status in errors:
        print(f"{source_id}: {status}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
