## 運用ルール
1. タスクを追加するときはチェックボックス形式で書く
2. 完了したら `[x]` にする
3. セクションが全て完了したら、セクションごと削除してよい

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
- [ ] `lifelog-daemon.service` を停止・無効化する（`sudo systemctl stop/disable lifelog-daemon.service`）

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

- [ ] `info-report.timer` を停止・無効化する（旧日次レポートは新設計不要）
- [ ] `info-integrated.timer` の代替を timeline-app に実装する
      → analyze → deep → theme report → reports テーブル投入 のパイプラインを
        `timeline-app/src/workers/` に移植する（フェーズ5.6 として別途計画）

---

## フェーズ4.6: M1 後処理（TODO完了チェック）

> §22.1「MVP で必須」に明記されていたが todo.md に未記載だった漏れ

- [ ] タイムライン上の `todo` カードにチェックボックスを表示する
- [ ] チェック時に `PATCH /api/entries/{id}` で `type: todo_done` + `status: done` + `meta.completed_at` を更新する
- [ ] 完了後、カード表示を `todo_done` スタイル（緑系）に切り替える
- [ ] 完了済み TODO は過去側タイムラインへ再配置する（timestamp を完了時刻に更新）

---

## フェーズ5: M2 実用化（着手はM1完了後）

> 参照: 要件書 §21.2
> **方針**: UIの主役は単一タイムライン。別ページを増やさずフィルタ・ビュー切り替えで対応する。

### 5-0. diary AI コメント worker（日次）

> 要件書 §9.1「1日単位でまとまった日記を別途生成できる」§15.1「日記の要約 / AI コメント」
> hourly_summary_worker とは別レイヤー。1日1回、その日の diary entry を振り返る。

- [ ] `timeline-app/src/workers/daily_digest_worker.py` を作成
  - 1日1回（例: 翌朝 7:00）、前日の `diary` type entry を読み込む
  - Ollama に渡して「その日の振り返りコメント」entry を生成
  - `type: memo`（または `diary`）として `articles/` + `daily/` に保存
- [ ] `scheduler.py` に `daily-digest` ジョブを追加（cron: 毎朝 7:00）

### 5-0b. info-integrated 代替 worker（RSS分析パイプライン）

> 現在 `info-integrated.timer` が担っている analyze → deep → theme report → reports テーブル投入 を
> timeline-app に移植することで systemd 依存を完全に断つ

- [ ] `timeline-app/src/workers/analysis_pipeline_worker.py` を作成
  - `integrate_pipeline.sh` が行う3段階（analyze / deep / theme_report）を Python で再実装
  - 30分ごと実行、results を `ai_secretary.db::reports` テーブルに書き込む
  - 完了後は `info-integrated.timer` を停止・無効化できる

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
- [ ] AI 処理 ON/OFF（要件書 §15.5）
- [ ] Big Five フィードバックの有効/無効（要件書 §17.1）

### 5-5. カレンダービュー

- [ ] 日/週単位のカレンダービューをタイムラインの別ビューとして追加する（要件書 §5.6）
      → 別ページではなくビュー切り替え式にする
- [ ] カレンダー上での予定作成 → タイムライン未来側にも反映される

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
