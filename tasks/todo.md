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
- [ ] `lifelog-system/` を「`timeline-app` から呼ばれるライブラリ層」として整理し、単独起動前提の導線を棚卸しする
- [ ] 正本データを明文化する
      → `articles/*.md` / `daily/*.md` / SQLite / 生成レポートのうち、更新元と投影先を整理する
- [ ] 不要物の削除を優先順で進める
      → まず未使用ファイル、次に旧導線スクリプト、次に今は不要な DB・生成物、最後に重複テスト資産を対象にする
- [ ] 「削除してよいもの」と「まだ参照されているもの」を分類した一覧を作る
      → 削除は毎回小さく行い、都度テストまたは起動確認を挟む
- [ ] `tasks/lessons.md` に、削除判断で見つかった依存関係と再発防止ルールを記録する

### 後続の重要タスク（削除整理の後に着手）

- [x] Windowsログを正式にシステムへ統合する
      → `WindowsForegroundWorker` を実装し、15分ごとに JSONL → activity_intervals へマージ
      → `hourly_summary_worker` の `summarize_activity()` が自動的に Windows アプリ使用状況を素材に含める
- [x] 「今何の作業をしているか」をレポートデータに取り込む
      → unified_timeline ビュー経由で process_name が LLM プロンプトに流れる（追加実装不要）
- [x] `merge-windows-logs.timer`（systemd）を停止・無効化する
      → WindowsForegroundWorker が代替しているため不要
- [ ] Windows 移行時: `WindowsForegroundWorker` に `powershell.exe foreground_logger.ps1` の起動管理を追加する
      → 現時点は foreground_logger.ps1 は別途起動する運用のまま

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
- [ ] 保留: 追跡済みかつ参照が残るため、今は削除しない
      → `scripts/systemd/` 一式, `docs/TASK_SCHEDULER_SETUP.md`, `docs/TROUBLESHOOTING_SYSTEMD.md`
      → `README.md`, `CLAUDE.md`, `lifelog-system/README.md`, `lifelog-system/docs/QUICKSTART.md`, `docs/PROJECT_OVERVIEW.md`
      → `scripts/info_collector/integrated_pipeline.sh`, `scripts/viewer_service.sh`, `lifelog-system/src/viewer_service/`, `lifelog-system/src/lifelog/cli_viewer.py`
      → `lifelog-system/tests/test_integration.py`, `lifelog-system/tests/test_integration_reasons.py`, `lifelog-system/tests/test_jobs_integration.py`, `timeline-app/tests/test_analysis_pipeline_integration.py`

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
- [x] 上が過去・下が未来の順で表示する（要件書 §4.2）
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
- [x] TODO type は デフォルト timestamp を当日 23:59 UTC に設定し、常に未来セクションに表示する
      → `routers/entries.py` で `req.type == "todo"` のとき `datetime.combine(now.date(), time(23, 59))`

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
- [ ] `info-integrated.timer` の代替を timeline-app に実装し、運用確認まで完了する
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

### 5-1. タイムライン実用強化

- [ ] 種別フィルタ（chat / diary / event / todo / news を切り替え）
      → 別ページではなくタイムライン上部のトグルで絞り込む（要件書 §18.1）
- [ ] 未完了TODOのみ表示フィルタ（未来側の todo を絞り込む）（要件書 §18.1）
- [ ] AI自動記録の表示 ON/OFF（要件書 §18.1, §15.5）
- [ ] 検索機能（キーワード検索 + 日付ジャンプ）（要件書 §4.1, §18.2）
- [x] 無限スクロール: 上端・下端スクロール時にページング追加読み込み（要件書 §5.4）
      → IntersectionObserver + sentinel 要素、`loadMorePast()` / `loadMoreFuture()` で重複除去しながら追記

### 5-2. AI記録UIの安全装置

> 要件書 §24.1「AI記録UIを実運用できる状態にするための安全装置として扱う」

- [ ] 下書き保存（記録確定前の一時保存）
- [ ] 誤分類のワンクリック修正（entry の type を手動で変更できる）
- [ ] undo / 取り消し機能（直前の保存操作を巻き戻す）
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
