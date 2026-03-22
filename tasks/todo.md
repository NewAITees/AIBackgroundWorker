## 運用ルール
1. タスクを追加するときはチェックボックス形式で書く
2. 完了したら `[x]` にする
3. セクションが全て完了したら、セクションごと削除してよい

---


## 最優先: 単純化・削減フェーズ

> MVP の追加実装より先に、既存バグの温床になりうる複雑さを減らす。
> **このセクションが完了するまで、それ以降の機能追加・派生実装・新規拡張は進めない。**
> **ただし直近の実作業は、棚卸し済みの削除を先に進める。Windowsログ統合は重要タスクとして残すが、削除整理の後に着手する。**

- [x] `timeline-app/` を唯一の運用入口として固定し、起動経路・設定経路・health 確認経路の二重化を洗い出す
      → 二重稼働していた info-integrated.timer / info-collector.timer を停止
      → health.py に windows_foreground_worker を追加
      → 残骸: lifelog-daemon.service / daemon.sh（削除候補として後続タスクへ）
- [x] `lifelog-system/` を「`timeline-app` から呼ばれるライブラリ層」として整理し、単独起動前提の導線を棚卸しする
      → 単独起動導線・systemd unit・daemon.sh・viewer・CLI 導線は除去済み
- [x] 正本データを明文化する
      → `articles/*.md` が entry 正本、`daily/*.md` が timeline 投影、`lifelog.db`/`ai_secretary.db` が収集・分析の正本、レポートMarkdownは生成物
- [x] 不要物の削除を優先順で進める（第1弾完了）
      → viewer_service.sh / view.sh / main_collector.py / poll_brave_history.sh / install_poll_cron.sh / integrated_pipeline.sh を削除
      → 保留: obsidian 関連・info_collector 手動ツール群は引き続き置いておく
- [x] 「削除してよいもの」と「まだ参照されているもの」を分類した一覧を作る
      → viewer_service: 削除済み / cli_viewer: 保持 / Windows scripts: 本体のみ保持 / obsidian: 保留
- [x] `tasks/lessons.md` に、削除判断で見つかった依存関係と再発防止ルールを記録する

### 後続の重要タスク（削除整理の後に着手）

- [x] `analysis_pipeline_worker` 実行時の `sqlite3.Connection` 未クローズ warning を調査し、接続管理を修正する
      → `lifelog-system/src/info_collector/repository.py` と関連 worker の read 経路で例外時 close 漏れを確認する
      → 再現確認後に `tasks/lessons.md` へ知見を追記する
- [x] `generate_theme_report` 実行後も残る `sqlite3.Connection` 未クローズ warning を追加調査し、残存経路を閉じる
      → `generate_theme_report` 自体だけでなく並行 worker を含む手動 `close()` 経路を確認する
      → 再現確認後に `tasks/lessons.md` を追記する
- [x] `system_events` 肥大化の原因になっている Linux syslog の過剰収集を抑止する
      → `priority_min: warning` が `info/debug` まで拾っている実装を修正する
      → `tee` 等の定常運用ログを collector 側で除外し、今後の `lifelog.db` 増大を抑える

- [x] Windowsログを正式にシステムへ統合する
      → `WindowsForegroundWorker` を実装し、15分ごとに JSONL → activity_intervals へマージ
      → `hourly_summary_worker` の `summarize_activity()` が自動的に Windows アプリ使用状況を素材に含める
- [x] 「今何の作業をしているか」をレポートデータに取り込む
      → unified_timeline ビュー経由で process_name が LLM プロンプトに流れる（追加実装不要）
- [x] `merge-windows-logs.timer`（systemd）を停止・無効化する
      → WindowsForegroundWorker が代替しているため不要
- [ ] Windows 移行時: `WindowsForegroundWorker` に `powershell.exe foreground_logger.ps1` の起動管理を追加する
      → 現時点は foreground_logger.ps1 は別途起動する運用のまま

### UI/データ不整合の不具合メモ（2026-03-19 画面確認ベース）

- [ ] `しばらくお待ちください...` 系 entry が大量発生している原因を特定する
      → 同一または類似 URL (`itch.io/login` / Cloudflare challenge) の重複取り込み・重複表示・重複要約のどこで増えているかを切り分ける
- [ ] `しばらくお待ちください...` を `memo` 扱いしている分類を見直す
      → browser 履歴由来の一時ページや Cloudflare challenge を `memo` にするのが正しいか確認し、必要なら `system_log` または別扱いへ変更する
- [x] TODO カードのチェックボックス位置と時刻表示の重なりを修正する
      → 右上のチェックボックス付近に時刻が重なって見づらい
- [x] TODO が過去セクションへ流れることがある不具合を修正する
      → TODO は常に未来側へ残し、見落としを防ぐ
- [ ] タイムライン逆順化に合わせて「未来 → Now → 過去」の視線導線を再整理する
      → 現在直上の TODO / 予定帯と、下方向へ積む過去ログの境界を UI 上で明確にする
- [ ] タイムライン上の時刻表示が誤っている問題を調査する
      → entry の timestamp、表示上の時刻、元データの時刻のどこでずれているかを確認する
- [ ] `system_log` の対象時刻とカード表示時刻のずれを修正する
      → 例: `2026-03-19 01時のシステムイベント` なのにカード表示が `03/19 10:30` になっている
- [ ] 画面に出ている結果が「現状の正しい仕様」なのか「テストデータや仮実装由来」なのか判別できない点を整理する
      → browser 取り込み・要約・分類・UI表示の各段で、意図した挙動と暫定挙動を明文化する

### 削除候補の棚卸し結果

- [x] 確実に削除してよい候補: `gitignore` されたキャッシュ類を削除する
      → `./.mypy_cache/`, `./.pytest_cache/`, `./lifelog-system/.pytest_cache/`
      → `./lifelog-system/__pycache__/`, `./lifelog-system/src/__pycache__/`, `./lifelog-system/tests/__pycache__/`
      → `./scripts/lifelog/__pycache__/`, `./scripts/system/__pycache__/`
      → `./timeline-app/__pycache__/`, `./timeline-app/scripts/__pycache__/`, `./timeline-app/src/__pycache__/`, `./timeline-app/tests/__pycache__/`
      → 2026-03-19 に削除実施
- [ ] 削除しない候補: Windowsログ・外部モデル・現行DBを保持する
      → `scripts/logs/windows_foreground.jsonl`, `scripts/logs/windows_foreground.jsonl.processed`
      → `models/176039414170160856.vrm`, `models/176039414170160856.vrm:Zone.Identifier`
      → `lifelog-system/data/ai_secretary.db`, `lifelog-system/data/info.db`, `lifelog-system/data/lifelog.db*`
      → `articles/*.md`, `daily/*.md`, `/mnt/c/YellowMable/00_Raw` 配下の必要レポートも正本または生成成果物として保持する
- [ ] 保留: 追跡済みかつ参照が残るため、今は削除しない
      → `scripts/systemd/` 一式, `docs/TASK_SCHEDULER_SETUP.md`, `docs/TROUBLESHOOTING_SYSTEMD.md`
      → `README.md`, `CLAUDE.md`, `lifelog-system/README.md`, `lifelog-system/docs/QUICKSTART.md`, `docs/PROJECT_OVERVIEW.md`
      → `scripts/info_collector/integrated_pipeline.sh`, `scripts/viewer_service.sh`, `lifelog-system/src/viewer_service/`, `lifelog-system/src/lifelog/cli_viewer.py`
      → `lifelog-system/tests/test_integration.py`, `lifelog-system/tests/test_integration_reasons.py`, `lifelog-system/tests/test_jobs_integration.py`, `timeline-app/tests/test_analysis_pipeline_integration.py`
      → 即削除不可の主因: `src/lifelog/*`, `src/browser_history/*`, `src/info_collector/jobs/*`, `auto_runner.py`, `scripts/lifelog/merge_windows_logs.py` は `timeline-app` 側 worker がまだ使用中
      → 追加整理: `scripts/systemd/` と `daemon.sh` は主に残骸・旧運用導線、`viewer_service` / `cli_viewer` / `integrated_pipeline.sh` はまだドキュメント・補助スクリプト・実行経路から参照あり

### 移動前に優先して畳む旧導線

- [x] `systemd` 残骸を削除候補として切り出す → 削除完了（2026-03-19）
- [x] `daemon.sh` 残骸を削除候補として切り出す → 削除完了（2026-03-19）
- [x] viewer / CLI 導線の存廃を決める
      → `viewer_service/` 削除、`cli_viewer.py` は手動確認用として保持（viewer_service 依存を除去済み）

### lifelog-system 移動タスク（§33）

> 前提: 単独起動導線の除去は完了済み

- [ ] `timeline-app/src/workers/` が `lifelog-system/src/` をインポートしている箇所を全列挙する
      → 現在は `sys.path` 操作 + `src.__path__` 拡張で対応中
- [ ] `lifelog-system/` を `timeline-app/lifelog-system/` へ移動する
- [ ] インポートパス・設定ファイル内のパス参照（`config.yaml` 等）を更新する
- [ ] `lifelog-system/pyproject.toml` の依存を `timeline-app/pyproject.toml` に統合し、`uv sync` で確認する
- [ ] 動作確認（`./scripts/start.sh` で全ワーカーが正常起動すること）
- [ ] 旧 `lifelog-system/pyproject.toml` を削除する

---

# 開発 TODO（詳細版）

> 要件書: `docs/新しい開発要件`
> アーキテクチャ概要: `CLAUDE.md`
> 実装場所: `timeline-app/`

---

## フェーズ0: 基盤整備（完了）

- [x] `timeline-app/` ディレクトリ作成
- [x] ルート `pyproject.toml` に `fastapi` / `uvicorn` を追加し `uv sync`
- [x] FastAPI 骨格実装（8本のAPI stub）
      → `timeline-app/src/main.py` と `routers/` 以下
- [x] `config.yaml` による環境設定、WSL/Windows パス変換実装
      → `timeline-app/src/config.py`
- [x] `timeline-app/daily/` と `timeline-app/articles/` フォルダ作成
- [x] `scripts/create_daily.py` で日付 Markdown ファイルを生成（案Aフォーマット）
- [x] 要件書に `12.8 ワークスペースのフォルダ構造` を追記

---

## フェーズ1: M1 バックエンド実装

> 参照: 要件書 §21.1.2（API一覧）、§21.1.3（entry型）、§12.4（entryスキーマ）

### 1-1. entry の Markdown 保存

- [x] `articles/` への entry ファイル書き込み実装
  - ファイル名: `{entry.id}.md`
  - 内容: YAML frontmatter + content 本文
  - 実装場所: `timeline-app/src/storage/entry_writer.py`（新規）
- [x] `daily/{YYYY-MM-DD}.md` の該当時間帯セクションへ entry の YAML ブロックを追記する実装
  - 対象セクション: entry の timestamp の時間を `## HH:00` で特定する
  - ファイルが存在しない場合は `create_daily.py` と同じフォーマットで自動生成する
  - 実装場所: `timeline-app/src/storage/daily_writer.py`（新規）
- [x] `POST /api/entries` エンドポイントを stub → 実保存に切り替える
      → `timeline-app/src/routers/entries.py`

### 1-2. タイムライン取得（Markdown 読み込み）

- [x] `daily/{YYYY-MM-DD}.md` を読み込み、時間帯セクションと YAML ブロックを解析する実装
  - 実装場所: `timeline-app/src/storage/daily_reader.py`（新規）
- [x] `GET /api/timeline` を stub → 実データ返却に切り替える
  - `around` パラメータの前後 N 時間分の entry 一覧を返す
  - 日をまたぐ場合は複数の daily ファイルを読む
  - 実装場所: `timeline-app/src/routers/timeline.py`

### 1-3. entry 詳細取得・更新

- [x] `GET /api/entries/{entry_id}` を stub → `articles/` のファイルから読み込む実装に切り替える
- [x] `PATCH /api/entries/{entry_id}` を stub → `articles/` のファイルを上書き保存する実装に切り替える
  - daily ファイル内の該当 YAML ブロックも同期して更新する

### 1-4. ワークスペース管理

- [x] `GET /api/workspace` でワークスペースの状態（パス・モード・サブフォルダ有無）を返す
- [x] `POST /api/workspace/open` でワークスペースを開いたとき `daily/` と `articles/` を自動作成する
- [x] ワークスペース未設定の場合、全APIが適切なエラーを返すようにする

---

## フェーズ2: M1 チャット API 実装

> 参照: 要件書 §7（チャットから記録へ変わる流れ）、§15（AI要件）、§21.1.2 `POST /api/chat`

- [x] Ollama 接続クライアント実装
  - ベースURL・モデル名を `config.yaml` で設定できるようにする
  - 実装場所: `timeline-app/src/ai/ollama_client.py`（新規）
- [x] `POST /api/chat` に Ollama を接続し実際の AI 応答を返す
  - `thread_id` で会話スレッドを保持する（インメモリでよい）
  - AI 応答を `chat_ai` entry として自動保存する
- [x] AI が入力内容の種別（diary / event / todo / memo）を推定し `entry_candidates` に返す
  - 推定は Ollama へのプロンプトで行う（ルールベース不要）
- [x] Ollama を `/api/generate` + JSON から `/api/chat` + tool use（function calling）に切り替え
  - レスポンスが `tool_calls[0].function.arguments` に構造化されるため JSON 解析不要になり安定
- [x] AI system メッセージに現在日時を注入し「明日」「来週」等の相対表現を正しく解釈させる
- [x] `entry_candidates` に `timestamp` フィールドを追加し、AI が未来日時を指定できるようにする
  - 候補確定時にフロントがそのまま `POST /api/entries` に timestamp を渡す

---

## フェーズ3: M1 Web フロント実装

> 参照: 要件書 §4（画面要件）、§21.1.4（Webフロント最小画面）

### 3-1. 基本構成

- [x] フロントの技術スタック決定（素の HTML+JS か React/Vue かを選ぶ）
  - M1 は軽量構成でよい（要件書 §21.1.4 参照）
- [x] `timeline-app/frontend/` ディレクトリ作成
- [x] FastAPI から静的ファイルを配信する設定を追加
      → `main.py` に `StaticFiles` マウントを追加

### 3-2. 中央タイムライン

- [x] `GET /api/timeline` を叩いてカード一覧を縦に表示する
- [x] 初期実装として上が過去・下が未来の順で表示する（後続で逆順へ再設計）
- [x] 現在位置に「Now」ラベルを表示する
- [x] 初回ロード時に「Now」位置へ自動スクロールする（IntersectionObserver + `initialScrollDone` フラグ）
- [x] 種別ごとに色・バッジで判別できるようにする（要件書 §5.7）
  - chat: 中立色 / diary: 暖色 / event: 青 / todo: 橙 / news: 寒色
- [x] カード種別ごとに左ボーダー色 + 背景色ティント（7%不透明度）を付与して視認性向上

### 3-3. 右ペイン

- [x] タイムラインのカードをクリックすると右ペインに詳細を表示する（`GET /api/entries/{id}`）
- [x] 閲覧モード → 編集モード切り替えボタンを実装する（要件書 §4.3）
- [x] 編集モードでテキストを変更し保存すると `PATCH /api/entries/{id}` を叩く

### 3-4. チャット入力欄

- [x] 現在地点の `Now` スロットにチャット入力欄を表示する（要件調整）
- [x] 送信すると `POST /api/chat` を叩き、AI 応答をタイムラインに追加する
- [x] AI が返す `entry_candidates` をボタンで確定できるようにする（「TODOにする」「日記にする」等）
- [x] TODO type は近未来 timestamp を既定値にして、未完了 TODO を未来側へ残す
      → 現在は `routers/entries.py` で新規 `todo` を数分後へ寄せ、取得時にも未完了 TODO を近未来へ投影している
- [x] AI が本文から明確な出来事時刻を推定した場合、その `timestamp` を候補保存時に優先できるようにする
      → 既定は保存時刻のまま維持しつつ、候補が ISO 時刻を返したときだけ `POST /api/entries` へ通す

### 3-5. 補助操作

- [x] 「今日へ戻る」ボタンで現在位置にスクロールする（要件書 §5.5）
- [x] ワークスペースパスを表示し、未設定の場合は選択を促す

---

## フェーズ4: M1 品質・運用整備

- [x] `GET /api/health` に Ollama 接続状態・ワークスペース状態を含める
- [x] Markdown 破損防止: 書き込み前にバックアップを取る仕組みを入れる
      → 要件書 §20.3「Markdown を壊さない保存を優先する」
- [x] `timeline-app/` の起動スクリプトを `scripts/start.sh` として用意する
- [x] `tasks/lessons.md` に設計判断を記録する

---

## フェーズ4.5: lifelog-system → timeline-app バックグラウンドワーカー移行（次に着手）

> 方針: 既存の `lifelog-system/` は壊さない。`timeline-app/` 側に APScheduler を導入し、
> lifelog-system のコードを **インポートして呼び出す** 形で統合する。
> 移行完了後に `scripts/daemon.sh` を廃止し、`start.sh` 1本で全体が起動する状態にする。

### 4.5-1. 基盤整備

- [x] `apscheduler` を `pyproject.toml` に追加し `uv sync`
- [x] `timeline-app/src/workers/` ディレクトリを作成
- [x] `timeline-app/src/workers/scheduler.py` — APScheduler (AsyncIOScheduler) の初期化と起動
- [x] `main.py` の lifespan に scheduler の start/stop を組み込む
- [x] `GET /api/health` にワーカー稼働状態を追加

### 4.5-2. PC活動監視ワーカー（常駐）

> 参照: `lifelog-system/src/lifelog/main_collector.py`、`activity_collector.py`

- [x] `timeline-app/src/workers/activity_worker.py` を作成
  - lifelog-system の `ActivityCollector` を `asyncio.to_thread()` でスレッド実行
  - 収集した activity_intervals は DB に保持し、timeline への直接投影はしない
- [x] 既存 `lifelog-system` の SQLite DB はそのまま維持（書き込み先は変えない）
- [x] `scripts/daemon.sh` の lifelog 起動部分を `start.sh` に統合

### 4.5-3. ブラウザ履歴インポートワーカー（毎時）

> 参照: `lifelog-system/src/browser_history/`

- [x] `timeline-app/src/workers/browser_worker.py` を作成
  - Brave/Chrome 履歴を毎時インポート
  - 新規エントリのみ `imported` 種別 entry として timeline に追加

### 4.5-4. RSS・ニュース収集ワーカー（毎時）

> 参照: `lifelog-system/src/info_collector/auto_runner.py`

- [x] `timeline-app/src/workers/info_worker.py` を作成
  - RSS / ニュース収集を毎時実行
  - 収集結果は `collected_info` に保存し、timeline へは直接出さない
- [x] `info_collector` の設定（フィードURL等）を `timeline-app/config.yaml` で管理できるようにする

### 4.5-5. 1時間ごとの AI 要約エントリワーカー（毎時）

> 参照: [docs/新しい開発要件](../docs/新しい開発要件) §5.3「1時間単位の時間構造」

- [x] `timeline-app/src/workers/hourly_summary_worker.py` を作成
  - 既存 `timeline-app/scripts/import_lifelog_history.py` の hourly entry 生成ロジックを `src/services/hourly_summary_importer.py` へ移して再利用する
  - `daily` には summary を投影し、本文は `articles/` 側へ保存する
- [x] 生成単位は `1時間ごと`
  - 日次レポートは作らない
  - source は `activity / browser / news / system_log` と `report 個別 entry` に分ける
- [x] `直近1時間だけ` ではなく `まだ entry 化されていない時間帯` を埋める
  - worker 実行ごとに lookback 範囲を走査し、欠けている hour / source だけを補完する
  - sleep / 停止 / 再起動後でも欠損時間を埋められるようにする
- [x] ニュース系の表示方針を整理する
  - 生ニュースは時間帯ごとに `1 entry` へ束ね、`content` にリンク付き一覧を入れる
  - `reports` は生成物ごとの個別 entry として投影し、`content` に report 本文を入れる

### 4.5-6. 移行完了・旧デーモン廃止

- [x] `scripts/start.sh` で timeline-app を起動すれば全ワーカーも起動することを確認
- [x] `scripts/daemon.sh` の `start()` に「timeline-app に統合済み」と記載
- [x] `tasks/lessons.md` に移行の設計判断を記録
- [x] `lifelog-daemon.service` を停止・無効化してよい状態に整理する
      → 手動実行コマンド: `sudo systemctl stop lifelog-daemon.service && sudo systemctl disable lifelog-daemon.service`
      → 実際に停止したかどうかは運用側で別途確認する

### 4.5-7. systemd 移行残作業（整理）

> 現時点での systemd ↔ timeline-app の役割分担

```
【自動収集層】systemd 側（まだ残す）
  info-integrated.timer（30分ごと）
    → RSS/ニュース収集 → 分析 → テーマレポート生成
    → ai_secretary.db の reports テーブルへ書き込む

【timeline entry 化層】timeline-app workers（実装済み）
  hourly_summary_worker（毎時）
    → activity / browser / reports / system を 1h 単位 entry に変換
    → articles/ + daily/ に保存
    ※ reports suffix は info-integrated が書いた reports テーブルを読んでいる

【旧日次レポート】systemd 側（新設計では不要寄り）
  info-report.timer（毎日 00:40）
    → /00_Raw/report_*.md を生成（旧来の日次レポート）
    → timeline-app の hourly 設計には不要

【diary AI コメント】未実装
  daily_digest_worker（1日1回）
    → diary type entry を読んでAIがまとめ・振り返りを生成
    → §9.1 §15.1 の「日記の要約 / AI コメント」に対応
```

- [x] `info-report.timer` を停止・無効化してよい状態に整理する
      → 手動実行コマンド: `sudo systemctl stop info-report.timer && sudo systemctl disable info-report.timer`
      → 実際に停止したかどうかは運用側で別途確認する
- [x] `info-integrated.timer` の代替を timeline-app に実装し、運用確認まで完了する
      → 実装自体は `analysis_pipeline_worker.py` と scheduler 統合まで完了
      → 残作業は「定期実行で reports テーブルへ継続投入されることの確認」と「旧 timer を停止してよい最終判断」

---

## フェーズ4.6: M1 後処理（TODO完了チェック）

> §22.1「MVP で必須」に明記されていたが todo.md に未記載だった漏れ

- [x] タイムライン上の `todo` カードにチェックボックスを表示する
- [x] チェック時に `PATCH /api/entries/{id}` で `type: todo_done` + `status: done` + `meta.completed_at` を更新する
- [x] 完了後、カード表示を `todo_done` スタイル（緑系）に切り替える
- [x] 完了済み TODO は過去側タイムラインへ再配置する（timestamp を完了時刻に更新）

---

## フェーズ5: M2 実用化（着手はM1完了後）

> 参照: 要件書 §21.2
> **方針**: UIの主役は単一タイムライン。別ページを増やさずフィルタ・ビュー切り替えで対応する。

### 5-0. diary AI コメント worker（日次）

> 要件書 §9.1「1日単位でまとまった日記を別途生成できる」§15.1「日記の要約 / AI コメント」
> hourly_summary_worker とは別レイヤー。1日1回、その日の diary entry を振り返る。

- [x] `timeline-app/src/workers/daily_digest_worker.py` を作成
  - 1日1回（例: 翌朝 7:00）、前日の `diary` type entry を読み込む
  - Ollama に渡して「その日の振り返りコメント」entry を生成
  - `type: memo`（または `diary`）として `articles/` + `daily/` に保存
- [x] `scheduler.py` に `daily-digest` ジョブを追加

### 5-0b. info-integrated 代替 worker（RSS分析パイプライン）

> 現在 `info-integrated.timer` が担っている analyze → deep → theme report → reports テーブル投入 を
> timeline-app に移植することで systemd 依存を完全に断つ

- [x] `timeline-app/src/workers/analysis_pipeline_worker.py` を作成
  - `integrate_pipeline.sh` が行う3段階（analyze / deep / theme_report）を Python で再実装
  - 30分ごと実行、results を `ai_secretary.db::reports` テーブルに書き込む
  - 実装は完了。残りは運用確認と `todo` / systemd 側の整理

### 5-0c. LLM 一時停止機能（PC負荷軽減）

> 要件書 §15.5「Ollama 接続を ON/OFF できるようにする / ゲーム中や高負荷時に CPU/GPU 負荷を下げる」

- [x] バックエンド: `config` または API で LLM 処理を一時停止するフラグを持つ
  - `POST /api/ai/pause` / `POST /api/ai/resume` エンドポイントを追加
  - フラグが ON の間、`OllamaClient` を呼ぶ全 worker がスキップ（収集は継続）
  - `GET /api/health` に `ai.paused` 状態を追加
  - `resume` 時に `hourly_summary_worker` / `daily_digest_worker` の catch-up を即時実行する
- [x] フロント: トップバーに「LLM 停止 / 再開」ボタンを追加
  - 停止中はボタンの色を変えて視覚的に判別できるようにする

### 5-0d. タイムライン方向（§29）

> 要件書 §29「タイムライン方向」
> 方針変更: 方向切り替えは持たず、「上が未来・下が過去」の逆順を正式仕様に固定する

- [x] タイムライン描画を逆順前提へ再設計する（上: 未来 / 中央: Now / 下: 過去）
- [x] `GET /api/timeline` の返却構造を逆順仕様に合わせて整理する
- [x] 無限スクロールの向きと基準時刻更新を逆順仕様に合わせて見直す
- [x] キーボード移動・`今日へ戻る`・初期スクロール位置を逆順仕様で再定義する
- [x] 方向切り替え前提の文言・設定項目・実装メモを削除する

### 5-0e. リマインダー機能（§30）

> 要件書 §30「リマインダー機能」

- [ ] `event` / `todo` entry に指定時刻のリマインダーを追加できるようにする
- [ ] 指定時刻になったらブラウザ通知またはトーストでリマインド
- [ ] AI プロアクティブ通知（AI から話しかける）を並行検討（§30.2）
      → VRM アシスタント（§16.1）との連携も視野に

### 5-0f. 右ペイン Markdown 描画（§31）

> 要件書 §31「右ペインの Markdown 描画」

- [x] `marked.js` + `DOMPurify` を導入する
- [x] 右ペイン閲覧モードで Markdown をレンダリング表示する
- [x] 編集モードはテキストエリアのまま（プレビュー切り替えは任意）

### 5-0g. レスポンシブ3ペインレイアウト（§32）

> 要件書 §32「レスポンシブ3ペインレイアウト」
> モバイル（スマートフォン等）からの表示を想定

- [x] CSS メディアクエリで画面幅に応じてレイアウト切り替え
- [x] PC（広い画面）: 左・中央・右の3ペイン常時表示を維持
- [x] モバイル（狭い画面）: 各ペインをフロート/ドロワー化
      → 表示優先順位: 左ペイン → 右ペイン → 中央タイムライン
      → 中央タイムラインは常時表示し、左右ペインのみ開閉する
      → `×` で隠し、中央タイムラインの操作や上部ボタンで再表示する

### 5-1. タイムライン実用強化

- [x] 種別フィルタ（chat / diary / event / todo / news を切り替え）
      → 別ページではなくタイムライン上部のトグルで絞り込む（要件書 §18.1）
- [x] 未完了TODOのみ表示フィルタ（未来側の todo を絞り込む）（要件書 §18.1）
- [x] AI自動記録の表示 ON/OFF（要件書 §18.1, §15.5）
- [x] 検索機能（キーワード検索 + 日付ジャンプ）（要件書 §4.1, §18.2）
- [x] 無限スクロール: 上端・下端スクロール時にページング追加読み込み（要件書 §5.4）
      → IntersectionObserver + sentinel 要素、`loadMorePast()` / `loadMoreFuture()` で重複除去しながら追記
- [ ] 右ペインの種別変更をボタン一覧からドロップダウン選択に変更する
      → 現状は `detail-quick-types` に全種別ボタンが並ぶ。クリックでドロップダウンが開き、変更先を選択する形にする
- [ ] フィルター UI をメニュー（折り畳みパネルやドロワー）に移動する
      → タイムライン上部のフィルター行をコンパクトにまとめ、メニューアイコンで開閉する
- [ ] ワークスペースの「開くボタン」とパス入力欄を削除する
      → 設定ページから操作できれば十分。起動時に config.yaml のパスを自動適用する形に整理する
- [ ] 種別フィルタをボタン方式から複数選択可能なドロップダウン/チェックリスト形式に変更する
      → 単一選択ボタン列を廃止し、複数種別を同時に選べる形にする（例: ポップオーバー内チェックボックス）
- [ ] 無限スクロールの動作を改善する（NOW 中心・両方向読み込み）
      → 初回表示は NOW を中心とした一定範囲のみ読み込み、上スクロールで未来・下スクロールで過去をそれぞれ追加読み込みする

### 5-2. AI記録UIの安全装置

> 要件書 §24.1「AI記録UIを実運用できる状態にするための安全装置として扱う」

- [x] 下書き保存（記録確定前の一時保存）
- [x] 誤分類のワンクリック修正（entry の type を手動で変更できる）
- [x] undo / 取り消し機能（直前の保存操作を巻き戻す）
- [ ] ピン留め（重要な entry をタイムライン上で固定表示）
- [ ] インボックス（未整理 entry の一時置き場。タイムライン上で未確定として表示）
- [ ] 会話スレッドの右ペイン表示（元会話・関連 entry の参照）（要件書 §4.3, §14.1, §7.3）

### 5-3. Markdown 自動取り込み

- [x] 既存 `lifelog-system` から yesterday 以前の履歴を `1時間単位 summary entry` として初期投入する
      → `timeline-app/scripts/import_lifelog_history.py`
- [x] 初期履歴インポートを `source別 entry + LLM要約` に変更する
      → `activity / browser / reports / system_event` を別 entry のまま自然文要約
- [x] `daily` を timeline summary 用、`articles` を実体本文用に分離する
      → `daily` には summary を投影し、右ペインは `articles/{id}.md` を表示
- [x] import summary entry は summary と詳細本文を分離して保存する
      → `activity` / `browser` / `system_log` はタイムライン / daily には短い summary、右ペインには集計素材ベースの詳細本文を表示
- [x] browser 履歴 summary import の分類を `memo` ではなく `system_log` に統一する
      → 個人閲覧ログやブラウザ活動 summary はメモではなく、外部取り込みの system 系ログとして扱う
- [ ] ワークスペース内の Markdown ファイル変更をファイル監視で検知する（要件書 §12.3）
- [ ] 新規・更新 Markdown を `imported` 種別の entry としてタイムラインへ流入させる
- [ ] 取り込み対象フォルダを設定可能にする

### 5-4. 設定ページ

- [ ] AI 性格・System Prompt 設定（要件書 §15.4）
- [ ] Ollama 接続設定（ベースURL・モデル名・タイムアウト）（要件書 §17.1）
- [ ] RSS フィード登録（要件書 §17.1）
- [ ] AI 処理 ON/OFF の設定ページ対応（要件書 §15.5）
      → pause/resume API とトップバー切り替えは実装済み。設定画面からも操作できるようにする
- [ ] Big Five フィードバックの有効/無効（要件書 §17.1）

### 5-5. カレンダービュー

- [ ] 日/週単位のカレンダービューをタイムラインの別ビューとして追加する（要件書 §5.6）
      → 別ページではなくビュー切り替え式にする
- [ ] カレンダー上での予定作成 → タイムライン未来側にも反映される

---

### 5-6. メモ機能・右ペイン拡張

> 要件書: `docs/新しい開発要件` §28

#### [[タイトル]] 記法によるメモ作成（§28.1）

- [ ] チャット入力欄で `[[タイトル]]` パターンを検出するパーサを実装する
      → 正規表現 `\[\[(.+?)\]\]` でタイトル抽出
- [ ] `POST /api/memo` エンドポイントを新規作成する
      → `articles/{タイトル}.md` の存在チェック（既存なら右ペインを開くだけ）
      → 新規の場合は Ollama に章立て・概要の生成を依頼
- [ ] 生成テキストを YAML frontmatter 付きで `articles/{タイトル}.md` に保存する
- [ ] `type: memo` の entry をタイムラインに追加し、右ペインを編集モードで開く

#### 右ペイン AI 編集機能（§28.2）

- [ ] 右ペインの閲覧モードに「AI に投げる」ボタンを追加する
- [ ] ボタン押下で本文の上/下に指示入力欄（textarea）を展開する
- [ ] `POST /api/entries/{id}/ai_edit` エンドポイントを新規作成する
      → リクエスト: `{ "instruction": "..." }`
      → Ollama に「現在の content + instruction」を渡して編集済み全文を返させる
- [ ] 編集結果を右ペインにプレビュー表示し、「保存」「キャンセル」で確定/破棄する
- [ ] 編集リクエスト前に `articles/{id}.bak.md` へバックアップを取る
      → 保存/キャンセル時にバックアップを削除する

#### 右ペインでのチャット継続（§28.3）

- [ ] entry の type が `chat` / `chat_ai` の場合、右ペインに会話履歴を Markdown 描画で表示する
- [ ] 右ペイン下部にチャット入力欄と送信ボタンを追加する（非チャット型 entry には表示しない）
- [ ] 送信時に `POST /api/chat` へ既存の `thread_id` を渡してスレッドを継続する
- [ ] `POST /api/entries/{id}/append_message` エンドポイントを新規作成する
      → 末尾追記方式で `articles/{id}.md` にメッセージを保存する（競合・破損リスク低減）
- [ ] AI 応答が返り次第、右ペイン下部に即時追記表示する（ポーリングまたは SSE）

---

## フェーズ6: M3 行動改善（M2完了後）

> 参照: 要件書 §21.3、§10（性格改善機能）

- [ ] Big Five（OCEAN）推定: entry に対して AI が傾向スコアをメタデータとして付与（要件書 §10.3）
- [ ] 日次フィードバック: 今日の記録をもとに傾向サマリーと明日の改善アクションを提案（要件書 §10.4）
- [ ] 改善アクション提案をタイムライン上に entry として流入させる
- [ ] 週次レビュー画面（タイムラインの週ビューまたは専用パネル）（要件書 §24.2）

---

## フェーズ7: M4 常駐化 / OS化（M3完了後）

> 参照: 要件書 §21.4、§3.6（デスクトップアプリ方針）

- [ ] desktop 版: pywebview で Web フロントを包む最小実装（要件書 §21.1.5）
- [ ] desktop 常駐・バックグラウンド起動（要件書 §19.3）
- [ ] スタートアップ登録・自動起動（要件書 §19.3）
- [ ] トレイアイコン・OS 通知（要件書 §21.4）
- [ ] VRM アシスタント表示（口パク・状態表示）（要件書 §16.1）
- [ ] 音声入力 / 音声出力（要件書 §16.2）
