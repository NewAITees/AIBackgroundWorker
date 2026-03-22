"""
開発用シードデータ投入スクリプト

現在時刻を基準に過去7日〜未来7日の現実的なエントリーを一通り作成する。
UIの見た目確認・開発中のレイアウトテストを目的とした開発専用スクリプト。

使い方:
  # ワークスペースを指定して実行（config.yaml の workspace.default_path を使う場合は省略可）
  uv run python timeline-app/scripts/seed_dev_data.py

  # ワークスペースを明示指定
  uv run python timeline-app/scripts/seed_dev_data.py --workspace /path/to/workspace

  # 既存データを消さず追加のみ
  uv run python timeline-app/scripts/seed_dev_data.py --no-clear
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# プロジェクトルートを sys.path に追加
_SCRIPT_DIR = Path(__file__).resolve().parent
_APP_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_APP_DIR))

from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType  # noqa: E402
from src.storage.persistence import persist_entry  # noqa: E402

# ---------------------------------------------------------------------------
# 時刻ヘルパー
# ---------------------------------------------------------------------------
JST = timezone(timedelta(hours=9))


def jst(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=JST)


def rel(days: float = 0, hours: float = 0) -> datetime:
    """現在時刻からの相対時刻（JST）。"""
    now = datetime.now(JST)
    return now + timedelta(days=days, hours=hours)


def make_id(entry_type: str) -> str:
    return f"{datetime.now(timezone.utc).isoformat()}-{entry_type}-{uuid.uuid4().hex[:6]}"


def entry(
    workspace_path: str,
    entry_type: str,
    content: str,
    timestamp: datetime,
    title: str | None = None,
    summary: str | None = None,
    source: str = "user",
    status: str = "active",
    meta: dict | None = None,
) -> None:
    meta_obj = EntryMeta(**(meta or {}))
    e = Entry(
        id=make_id(entry_type),
        type=EntryType(entry_type),
        title=title,
        summary=summary,
        content=content,
        timestamp=timestamp,
        status=EntryStatus(status),
        source=EntrySource(source),
        workspace_path=workspace_path,
        meta=meta_obj,
    )
    persist_entry(workspace_path, e)
    ts_str = timestamp.strftime("%m/%d %H:%M")
    print(f"  [{entry_type:<12}] {ts_str}  {(title or content)[:40]}")


# ---------------------------------------------------------------------------
# シードデータ定義
# ---------------------------------------------------------------------------


def seed(workspace_path: str) -> None:
    now = datetime.now(JST)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def day(offset: int, h: int, m: int = 0) -> datetime:
        return today + timedelta(days=offset, hours=h, minutes=m)

    print("\n=== 過去 7日 ===")

    # --- 7日前 ---
    entry(
        workspace_path,
        "diary",
        "週末をゆっくり過ごした。午前中は近所を散歩して、午後は本を読んだ。\n特に何か大きな出来事はなかったけど、こういう穏やかな日が好きだ。",
        day(-7, 9),
        title="週末の振り返り",
    )
    entry(workspace_path, "event", "図書館で借りた本を返却しに行った。ついでに新しい本を3冊借りてきた。", day(-7, 11), title="図書館")
    entry(
        workspace_path,
        "memo",
        "新しいプロジェクトのアイデア:\n- タスク管理の自動化\n- ライフログとの連携\n- 週次レビューの仕組み化",
        day(-7, 21, 30),
        title="アイデアメモ",
    )

    # --- 5日前 ---
    entry(
        workspace_path,
        "diary",
        "今週も始まった。今日は月次レポートの締め切りがあって少し緊張していたが、無事提出できた。",
        day(-5, 8),
        title="月曜日の朝",
    )
    entry(
        workspace_path,
        "todo_done",
        "月次レポートをまとめて上長に送付する。先月比での数字の変化を中心に記載。",
        day(-5, 10),
        title="月次レポート提出",
        status="done",
        meta={"completed_at": day(-5, 10, 45).isoformat()},
    )
    entry(
        workspace_path,
        "news",
        "## Python 3.14 リリース\n\n新しい型推論エンジンと JIT コンパイラの改善が含まれる。\n\n- `t-string` 構文が正式採用\n- `asyncio` のパフォーマンス向上\n- 型チェックの精度向上",
        day(-5, 12),
        title="Python 3.14 リリースノート",
        source="imported",
    )
    entry(
        workspace_path,
        "system_log",
        "## アクティビティサマリー 14:00〜15:00\n\n| アプリ | 時間 |\n|---|---|\n| VS Code | 38分 |\n| Terminal | 12分 |\n| Chrome | 8分 |\n\n主な作業: Python スクリプトのリファクタリング",
        day(-5, 15),
        title="14時台の活動記録",
        summary="VS Code 38分・Terminal 12分・Chrome 8分",
        source="system",
    )
    entry(workspace_path, "chat_user", "月次レポートが終わった。次は来週の発表資料を準備しないといけないけど、何から始めればいい？", day(-5, 18))
    entry(
        workspace_path,
        "chat_ai",
        "お疲れ様でした！発表資料の準備は以下の順番がおすすめです。\n\n1. **ゴールの明確化** — 聴衆に何を持ち帰ってもらうかを1文で書く\n2. **アウトライン作成** — スライド構成を箇条書きで整理\n3. **データ収集** — 必要な数字やグラフを揃える\n4. **スライド作成** — アウトラインに肉付け\n\nまずゴールから始めると迷わずに進められますよ。",
        day(-5, 18, 1),
        source="ai",
    )

    # --- 3日前 ---
    entry(
        workspace_path,
        "diary",
        "朝から雨だった。カフェで作業しようと思ったが結局家で集中できた。\nオンライン勉強会はとても参考になった。",
        day(-3, 8, 30),
        title="雨の水曜日",
    )
    entry(
        workspace_path,
        "todo_done",
        "- 牛乳\n- 卵\n- 野菜（ほうれん草、にんじん）\n- 鶏もも肉\n- パスタ",
        day(-3, 11),
        title="スーパーの買い物",
        status="done",
        meta={"completed_at": day(-3, 12, 15).isoformat()},
    )
    entry(
        workspace_path,
        "event",
        "Python の非同期処理について深く掘り下げたセッション。`asyncio.TaskGroup` の使い方が特に参考になった。",
        day(-3, 15),
        title="オンライン勉強会「非同期Python」",
    )
    entry(
        workspace_path,
        "system_log",
        "## ブラウザ閲覧サマリー 3日前\n\n**主なドメイン:**\n- github.com (23回)\n- docs.python.org (11回)\n- stackoverflow.com (8回)\n- youtube.com (4回)\n\n総セッション数: 46",
        day(-3, 23),
        title="ブラウザ閲覧サマリー",
        summary="github.com 23回, docs.python.org 11回, stackoverflow.com 8回",
        source="system",
    )

    # --- 昨日 ---
    entry(
        workspace_path,
        "diary",
        "昨日よりも調子が良い。午前中に集中して作業できた。\n夕方から少し疲れが出てきたが、早めに休んだので回復した。",
        day(-1, 7, 30),
        title="昨日の日記",
    )
    entry(
        workspace_path,
        "event",
        "プロジェクトの週次同期ミーティング。来週のマイルストーンを確認して、担当を振り分けた。",
        day(-1, 10),
        title="週次ミーティング",
    )
    entry(
        workspace_path,
        "memo",
        "ミーティングで気になった点:\n- API のレスポンス速度をモニタリングする仕組みが必要\n- テストカバレッジを 70% 以上に上げる\n- ドキュメントが古い箇所を来週までに整理",
        day(-1, 11),
        title="ミーティングメモ",
    )
    entry(
        workspace_path,
        "news",
        "## SQLite 3.47.0 リリース\n\nパフォーマンス改善とセキュリティ修正が含まれる。\nWAL モードの書き込み速度が最大 15% 向上。",
        day(-1, 14),
        title="SQLite 3.47.0 リリース",
        source="imported",
    )
    entry(
        workspace_path,
        "todo_done",
        "README の Getting Started セクションを最新の手順に更新する。",
        day(-1, 16),
        title="README 更新",
        status="done",
        meta={"completed_at": day(-1, 16, 40).isoformat()},
    )

    print("\n=== 今日 ===")

    # --- 今日（過去） ---
    entry(
        workspace_path,
        "diary",
        "今朝は 6:30 に起きた。珍しく早起きできた。\n天気が良かったので近所を 20 分ほど歩いてきた。",
        day(0, 7),
        title="今朝の記録",
    )
    entry(
        workspace_path,
        "event",
        "コーヒーを飲みながら今日のタスクを整理した。集中できそうな雰囲気。",
        day(0, 8, 30),
        title="朝のルーティン完了",
    )
    entry(
        workspace_path,
        "system_log",
        "## アクティビティサマリー 午前\n\n| アプリ | 時間 |\n|---|---|\n| VS Code | 52分 |\n| Terminal | 20分 |\n| Chrome | 15分 |\n| Slack | 8分 |\n\n主な作業: テストコードの追加、バグ修正",
        day(0, 12),
        title="午前のアクティビティ",
        summary="VS Code 52分・Terminal 20分・Chrome 15分",
        source="system",
    )
    entry(
        workspace_path,
        "memo",
        "昼食後のアイデア: ライフログの可視化をもっとシンプルにできないか。\nグラフよりもタイムラインの方が直感的かもしれない。",
        day(0, 13),
        title="可視化のアイデア",
    )
    entry(workspace_path, "chat_user", "今日の午前中の作業まとめをタイムラインに記録しておきたい", day(0, 13, 30))
    entry(
        workspace_path,
        "chat_ai",
        "午前中お疲れ様でした。記録しました！\n\nVS Code での作業が中心だったようですね。テストコードの追加が進んでいるのは良い調子です。\n午後も集中できそうですか？",
        day(0, 13, 31),
        source="ai",
    )

    print("\n=== 未来 ===")

    # --- 今日（未来） ---
    entry(
        workspace_path,
        "todo",
        "- にんにく\n- オリーブオイル\n- パスタ 500g\n- トマト缶 2個",
        rel(hours=2),
        title="夕食の買い物",
    )
    entry(
        workspace_path,
        "event",
        "クライアントとの進捗共有ミーティング。先週の課題点と今週の成果を報告する。",
        rel(hours=3, days=0),
        title="クライアントとのオンライン会議",
    )

    # --- 明日 ---
    entry(workspace_path, "todo", "先週のメモを整理して、来週のアクションアイテムをリスト化する。", day(1, 9), title="週次レビュー")
    entry(
        workspace_path,
        "event",
        "大学時代の友人と久しぶりに食事の予定。渋谷のイタリアンレストランで 19:00〜",
        day(1, 19),
        title="友人と夕食",
    )
    entry(workspace_path, "todo", "発表スライドの最終確認と印刷。念のためバックアップも取っておく。", day(1, 10), title="発表資料の最終確認")

    # --- 3日後 ---
    entry(
        workspace_path,
        "event",
        "社内勉強会で発表を担当。テーマは「ライフログを使った生産性向上」。15分のショートトーク。",
        day(3, 14),
        title="社内勉強会での発表",
    )
    entry(workspace_path, "todo", "半年ぶりの定期健診。空腹で行くこと（前日 21 時以降は食べない）。", day(3, 10), title="病院の定期健診")

    # --- 来週 ---
    entry(
        workspace_path,
        "todo",
        "e-Tax で提出。必要書類:\n- マイナンバーカード\n- 昨年の源泉徴収票\n- 医療費の領収書",
        day(5, 10),
        title="確定申告の提出",
    )
    entry(workspace_path, "event", "美容院の予約。カットとトリートメント。13:00〜15:00 予定。", day(6, 13), title="美容院")
    entry(workspace_path, "todo", "春物の服を整理して、不要なものをリサイクルショップへ持っていく。", day(7, 10), title="衣替え・断捨離")

    print("\n✓ 完了")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="開発用シードデータを投入する（UIの見た目確認用）")
    parser.add_argument("--workspace", help="ワークスペースパス（省略時は config.yaml を使用）")
    args = parser.parse_args()

    # ワークスペースの解決
    if args.workspace:
        workspace_path = str(Path(args.workspace).resolve())
    else:
        from src.config import config, to_local_path

        raw = config.workspace.default_path
        if not raw:
            print("エラー: ワークスペースが未設定です。--workspace オプションで指定してください。")
            sys.exit(1)
        workspace_path = str(Path(to_local_path(raw)).resolve())

    ws = Path(workspace_path)
    if not ws.exists():
        print(f"エラー: ワークスペースが存在しません: {workspace_path}")
        sys.exit(1)

    # daily / articles ディレクトリを確保
    (ws / "daily").mkdir(exist_ok=True)
    (ws / "articles").mkdir(exist_ok=True)

    print(f"ワークスペース: {workspace_path}")
    seed(workspace_path)


if __name__ == "__main__":
    main()
