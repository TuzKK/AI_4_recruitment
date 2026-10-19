import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "metrics":
        from .metrics import run_metrics

        run = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        labels = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        print(json.dumps(run_metrics(run["candidates"], labels), ensure_ascii=False, indent=2))
    elif len(sys.argv) == 4 and sys.argv[1] == "daily-yield":
        from .metrics import daily_yield

        labels = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        result = daily_yield(Path(__file__).resolve().parent / ".runtime", sys.argv[2], labels)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif len(sys.argv) == 1:
        from .web import main as serve

        serve()
    else:
        raise SystemExit("用法：python -m recruitment_app [metrics <运行记录.json> <人工标签.json> | daily-yield <日期> <人工标签.json>]")


if __name__ == "__main__":
    main()
