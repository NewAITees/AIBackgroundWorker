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

- [ ] `articles/` への entry ファイル書き込み実装
  - ファイル名: `{entry.id}.md`
  - 内容: YAML frontmatter + content 本文
  - 実装場所: `timeline-app/src/storage/entry_writer.py`（新規）
- [ ] `daily/{YYYY-MM-DD}.md` の該当時間帯セクションへ entry の YAML ブロックを追記する実装
  - 対象セクション: entry の timestamp の時間を `## HH:00` で特定する
  - ファイルが存在しない場合は `create_daily.py` と同じフォーマットで自動生成する
  - 実装場所: `timeline-app/src/storage/daily_writer.py`（新規）
- [ ] `POST /api/entries` エンドポイントを stub → 実保存に切り替える
      → `timeline-app/src/routers/entries.py`

### 1-2. タイムライン取得（Markdown 読み込み）

- [ ] `daily/{YYYY-MM-DD}.md` を読み込み、時間帯セクションと YAML ブロックを解析する実装
  - 実装場所: `timeline-app/src/storage/daily_reader.py`（新規）
- [ ] `GET /api/timeline` を stub → 実データ返却に切り替える
  - `around` パラメータの前後 N 時間分の entry 一覧を返す
  - 日をまたぐ場合は複数の daily ファイルを読む
  - 実装場所: `timeline-app/src/routers/timeline.py`

### 1-3. entry 詳細取得・更新

- [ ] `GET /api/entries/{entry_id}` を stub → `articles/` のファイルから読み込む実装に切り替える
- [ ] `PATCH /api/entries/{entry_id}` を stub → `articles/` のファイルを上書き保存する実装に切り替える
  - daily ファイル内の該当 YAML ブロックも同期して更新する

### 1-4. ワークスペース管理

- [ ] `GET /api/workspace` でワークスペースの状態（パス・モード・サブフォルダ有無）を返す
- [ ] `POST /api/workspace/open` でワークスペースを開いたとき `daily/` と `articles/` を自動作成する
- [ ] ワークスペース未設定の場合、全APIが適切なエラーを返すようにする

---

## フェーズ2: M1 チャット API 実装

> 参照: 要件書 §7（チャットから記録へ変わる流れ）、§15（AI要件）、§21.1.2 `POST /api/chat`

- [ ] Ollama 接続クライアント実装
  - ベースURL・モデル名を `config.yaml` で設定できるようにする
  - 実装場所: `timeline-app/src/ai/ollama_client.py`（新規）
- [ ] `POST /api/chat` に Ollama を接続し実際の AI 応答を返す
  - `thread_id` で会話スレッドを保持する（インメモリでよい）
  - AI 応答を `chat_ai` entry として自動保存する
- [ ] AI が入力内容の種別（diary / event / todo / memo）を推定し `entry_candidates` に返す
  - 推定は Ollama へのプロンプトで行う（ルールベース不要）

---

## フェーズ3: M1 Web フロント実装

> 参照: 要件書 §4（画面要件）、§21.1.4（Webフロント最小画面）

### 3-1. 基本構成

- [ ] フロントの技術スタック決定（素の HTML+JS か React/Vue かを選ぶ）
  - M1 は軽量構成でよい（要件書 §21.1.4 参照）
- [ ] `timeline-app/frontend/` ディレクトリ作成
- [ ] FastAPI から静的ファイルを配信する設定を追加
      → `main.py` に `StaticFiles` マウントを追加

### 3-2. 中央タイムライン

- [ ] `GET /api/timeline` を叩いてカード一覧を縦に表示する
- [ ] 上が過去・下が未来の順で表示する（要件書 §4.2）
- [ ] 現在位置に「Now」ラベルを表示する
- [ ] 種別ごとに色・バッジで判別できるようにする（要件書 §5.7）
  - chat: 中立色 / diary: 暖色 / event: 青 / todo: 橙 / news: 寒色

### 3-3. 右ペイン

- [ ] タイムラインのカードをクリックすると右ペインに詳細を表示する（`GET /api/entries/{id}`）
- [ ] 閲覧モード → 編集モード切り替えボタンを実装する（要件書 §4.3）
- [ ] 編集モードでテキストを変更し保存すると `PATCH /api/entries/{id}` を叩く

### 3-4. チャット入力欄

- [ ] 画面下部に現在地点のチャット入力欄を固定表示する（要件書 §4.4）
- [ ] 送信すると `POST /api/chat` を叩き、AI 応答をタイムラインに追加する
- [ ] AI が返す `entry_candidates` をボタンで確定できるようにする（「TODOにする」「日記にする」等）

### 3-5. 補助操作

- [ ] 「今日へ戻る」ボタンで現在位置にスクロールする（要件書 §5.5）
- [ ] ワークスペースパスを表示し、未設定の場合は選択を促す

---

## フェーズ4: M1 品質・運用整備

- [ ] `GET /api/health` に Ollama 接続状態・ワークスペース状態を含める
- [ ] Markdown 破損防止: 書き込み前にバックアップを取る仕組みを入れる
      → 要件書 §20.3「Markdown を壊さない保存を優先する」
- [ ] `timeline-app/` の起動スクリプトを `scripts/start.sh` として用意する
- [ ] `tasks/lessons.md` に設計判断を記録する

---

## フェーズ5: M2 以降（着手はM1完了後）

> 参照: 要件書 §21.2

- [ ] TODO 専用一覧ページ
- [ ] カレンダービュー
- [ ] Markdown 自動取り込み（ファイル監視）
- [ ] desktop 版（pywebview で Web フロントを包む）
- [ ] 設定ページ（AI性格・RSS・Ollama接続設定等）
- [ ] AI 処理 ON/OFF 機能
