"""
日付ファイル生成スクリプト
config.yaml の workspace.dirs.daily フォルダに YYYY-MM-DD.md を生成する

使い方:
  # 今日分を生成
  uv run python timeline-app/scripts/create_daily.py

  # 日付を指定して生成
  uv run python timeline-app/scripts/create_daily.py --date 2026-03-18

  # 複数日分をまとめて生成
  uv run python timeline-app/scripts/create_daily.py --date 2026-03-18 --days 7
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# プロジェクトルートを sys.path に追加
_SCRIPT_DIR = Path(__file__).parent
_APP_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_APP_DIR))

from src.config import config, to_local_path


def build_daily_content(target_date: date) -> str:
    """
    1時間単位のセクションを持つ日付 Markdown を生成する（案A形式）

    各時間帯セクションは空の状態で生成される。
    entry が作成されると、APIが該当セクションに YAML ブロックを追記する。

    例（entry 追記後のイメージ）:
        ## 10:00

        ```yaml
        id: 2026-03-18T10:15:00+09:00-diary-001
        type: diary
        timestamp: 2026-03-18T10:15:00+09:00
        content: 今日はいい天気だった
        status: active
        source: user
        ```
    """
    date_str = target_date.strftime("%Y-%m-%d")
    lines = [
        f"# {date_str}",
        "",
        "## メモ",
        "",
        "",
        "---",
        "",
    ]

    for hour in range(24):
        time_str = f"{hour:02d}:00"
        lines += [
            f"## {time_str}",
            "",
            "",
        ]

    return "\n".join(lines)


def create_daily_file(target_date: date, daily_dir: Path, overwrite: bool = False) -> Path:
    """daily_dir に YYYY-MM-DD.md を生成する。既存ファイルは overwrite=True のときのみ上書き"""
    date_str = target_date.strftime("%Y-%m-%d")
    file_path = daily_dir / f"{date_str}.md"

    if file_path.exists() and not overwrite:
        print(f"  スキップ（既存）: {file_path}")
        return file_path

    content = build_daily_content(target_date)
    file_path.write_text(content, encoding="utf-8")
    print(f"  作成: {file_path}")
    return file_path


def main() -> None:
    parser = argparse.ArgumentParser(description="日付 Markdown ファイルを生成する")
    parser.add_argument("--date", default=None, help="生成する日付 YYYY-MM-DD（省略時は今日）")
    parser.add_argument("--days", type=int, default=1, help="生成する日数（デフォルト: 1）")
    parser.add_argument("--overwrite", action="store_true", help="既存ファイルを上書きする")
    args = parser.parse_args()

    # ワークスペースと daily フォルダのパスを解決
    workspace = Path(to_local_path(config.workspace.default_path))
    daily_dir = workspace / config.workspace.dirs.daily if hasattr(config.workspace, "dirs") else workspace / "daily"

    # config.yaml から dirs を取得
    raw_daily = "daily"
    try:
        import yaml
        with open(_APP_DIR / "config.yaml", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        raw_daily = raw.get("workspace", {}).get("dirs", {}).get("daily", "daily")
    except Exception:
        pass
    daily_dir = workspace / raw_daily

    if not daily_dir.exists():
        print(f"daily フォルダが存在しません。作成します: {daily_dir}")
        daily_dir.mkdir(parents=True)

    # 開始日を決定
    if args.date:
        start = date.fromisoformat(args.date)
    else:
        start = date.today()

    print(f"ワークスペース : {workspace}")
    print(f"daily フォルダ : {daily_dir}")
    print(f"生成対象       : {start} から {args.days} 日分")
    print()

    for i in range(args.days):
        target = start + timedelta(days=i)
        create_daily_file(target, daily_dir, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
