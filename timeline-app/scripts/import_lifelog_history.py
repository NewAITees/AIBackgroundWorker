"""lifelog 履歴を timeline-app へ時間帯単位で取り込む CLI。"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_APP_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_APP_DIR))

from src.config import config, to_local_path  # noqa: E402
from src.services.hourly_summary_importer import import_range, resolve_context  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="lifelog-system の履歴を timeline-app へ時間帯単位で取り込む")
    parser.add_argument("--start-date", type=str, default=None, help="開始日 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="終了日 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=3, help="終了日から何日分さかのぼるか（デフォルト: 3）")
    args = parser.parse_args()

    workspace_path = Path(to_local_path(config.workspace.default_path)).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / config.workspace.dirs.daily).mkdir(parents=True, exist_ok=True)
    (workspace_path / config.workspace.dirs.articles).mkdir(parents=True, exist_ok=True)

    end_date = (
        date.fromisoformat(args.end_date) if args.end_date else (date.today() - timedelta(days=1))
    )
    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
    else:
        start_date = end_date - timedelta(days=args.days - 1)

    ctx = resolve_context(workspace_path)
    count = import_range(ctx, start_date, end_date)
    print(f"Imported {count} hourly summary entries into {workspace_path}")


if __name__ == "__main__":
    main()
