# Lessons - 過去の失敗と学び
## 記録ルール
- バグを解決したら、ここにパターンと対策を追記する
- 設計上の判断ミスや整合性の注意点も記録する
- 同じ失敗を繰り返さないための知見をまとめる

## 2026-02-17
- パターン: 作業再開時に `tasks/` 配下が未作成で、進捗管理ファイルが存在しない状態だった。
- 対策: 最初に `pwd` と環境確認を実行し、`tasks/todo.md` と `tasks/lessons.md` の雛形を先に作る。実装前チェックイン（y/n）を必須化する。

## 2026-02-18
- パターン: 保存先パスがコードとドキュメントで分散管理されると、実運用の場所が曖昧になりやすい。
- 対策: `YELLOWMABLE_DIR` を基準に既定出力を統一し、`README.md` / `AGENTS.md` / `CLAUDE.md` に明記する。リポジトリ直下にシンボリックリンクを置いて導線を固定する。

- パターン: 年が変わっても `DiaryMOC_YYYY` 生成ジョブが自動実行されず、日記リンク `[[DiaryMOC_YYYY]]` の参照先が欠落する。
- 対策: 年初（1月）に `obsidian_moc_generator.py <year>` を定期実行する運用を追加し、生成後に同名重複ファイル（例: `00CreatedFiles/DiaryMOC_YYYY.md`）を点検する。

- パターン: `report/article/diary` の相互リンクが日々の生成に依存して抜けると、後から参照導線を復元するコストが大きい。
- 対策: `sync_obsidian_links` ジョブを定期実行し、`RawReports_MOC` 再生成と `report↔diary↔article` ナビゲーションを自動補完する。

## 2026-03-16
- パターン: `scripts/info_collector/integrated_pipeline.sh` の引数仕様を変更しても、`/etc/systemd/system/` に入っている古い unit を更新しないと定期実行が継続的に失敗する。
- 対策: 引数仕様を変えたら、リポジトリ内 unit だけでなくインストール用スクリプトも同時更新し、`sudo systemctl daemon-reload` と timer 再起動までを運用手順に含める。

- パターン: WSL の `PATH` に Windows 側 `pyenv-win` shim が混入すると、`python` が壊れていても `uv` や `python3` だけ見て気づきにくい。
- 対策: WSL では `python` / `python3` / `command -v` をセットで確認し、必要なら Windows PATH 混入を抑制する。

## 2026-03-18
- パターン: timeline の daily ファイルを正本と更新先の両方にすると、PATCH 時に同一 entry ブロックが重複しやすい。
- 対策: `articles/*.md` を正本、`daily/YYYY-MM-DD.md` を時間軸表示用の投影とみなし、更新時は daily 側で同一 `id` ブロックを必ず除去してから再挿入する。

- パターン: `config.yaml` に書いたネスト設定を Pydantic モデルに反映しないと、実行時だけ `hasattr` で逃げる不安定なコードになる。
- 対策: `workspace.dirs.*` のようなネスト項目は設定モデルへ最初から定義し、ルータやスクリプトで同じ設定経路を使う。

- パターン: LLM に自由文で分類結果を返させると、API 側の型がすぐ崩れる。
- 対策: `POST /api/chat` では JSON 形式を明示し、API 側でも `type` と `content` を再検証してから `entry_candidates` に流す。

- パターン: Ollama など外部サービスとの通信を mock だけでテストすると、実際の接続・応答形式・モデルの挙動の変化に気づけない。
- 対策: mock テスト（単体）とは別に、実サービスに接続する統合テストを用意する。統合テストは `@pytest.mark.integration` でマークし、通常の `pytest` では skip、`pytest -m integration` で明示実行する運用にする。外部サービスが必須の機能は mock と統合テストの両方を揃えることを原則とする。

- パターン: このプロダクトでチャット入力欄を画面下固定にすると、時間軸UIより通常チャットUIの印象が強くなり、Now中心という要件が薄れる。
- 対策: M1 の Web フロントではチャット入力欄をタイムラインの `Now` スロットに置き、`今日へ戻る` ボタンで現在位置へ復帰する構成を基本にする。

- パターン: Markdown を直接上書きする実装は、正規表現や整形の不具合が出た瞬間に復旧手段がなくなる。
- 対策: `articles/` と `daily/` の保存前に `.timeline-backups/` へ世代バックアップを自動作成し、破損時にファイル単位で戻せるようにする。

- パターン: `health` が単なる `{"status":"ok"}` だけだと、起動していても `workspace` 未設定や Ollama 未到達を見落としやすい。
- 対策: `GET /api/health` はプロセス生存確認だけでなく、`workspace` 状態と Ollama 到達性・対象モデルの有無まで返す。

- パターン: 既存 lifelog をそのまま 1件ずつ流し込むと、system event の件数が多すぎてタイムラインが埋まり、1時間単位の見通しも崩れる。
- 対策: 初期履歴インポートは `1時間ごと / source ごと` の summary entry に変換し、`activity`・`system_event`・`browser_history`・`reports` を時間帯単位でまとめて投入する。

- パターン: Ollama の `/api/generate` + `format: "json"` はモデルによって JSON をmarkdownコードブロックで包んだり余分なテキストを付けることがあり、`json.loads()` が失敗しやすい。
- 対策: `/api/chat` + `tools`（function calling）を使うと `message.tool_calls[0].function.arguments` に構造化データが返るため JSON 解析が不要になり安定する。qwen3 系はtool use対応済み。

- パターン: 履歴インポートで `activity / browser / reports / system_event` を1本に混ぜると、後から「その時間に何を見て何が起きたか」を分解しにくい。
- 対策: source 別 entry は維持し、本文だけを LLM 要約に置き換える。`system_event` だけはノイズが多いので LLM に `should_create` 判定を持たせる。

- パターン: qwen 系は `tool_calls` をネイティブ JSON フィールドではなく、`message.content` に `{"name": "...", "arguments": {...}}` として返すことがある。
- 対策: Ollama クライアント側で `message.tool_calls` だけでなく `message.content` 内の JSON も抽出して arguments を復元する。

- パターン: `system_event` を広く拾うと、`tee` や `wsl-pro-service` の定常ログまで要約対象に入り、1時間 summary がノイズに引っ張られる。
- 対策: `system_event` は `error / critical`、失敗系キーワード、重要サービスの状態変化だけを残す。`warning` の文字列だけでは採用しない。

- パターン: `daily` に article 本文まで複製すると、中央タイムラインと右ペインが同じ内容になり、summary 一覧と詳細表示の役割分担が崩れる。
- 対策: `daily/YYYY-MM-DD.md` は `id / type / title / summary / timestamp` 中心の投影に留め、本文の正本は `articles/{id}.md` だけに置く。daily 読込時にだけ `summary` から表示用 `content` を補完する。

- パターン: worker 移行を job 実装と scheduler 基盤の同時変更で始めると、起動不良の切り分けが難しくなる。
- 対策: まず `APScheduler` のシングルトン、FastAPI lifespan 統合、`/api/health` への状態露出だけを先に入れ、job はその上に段階追加する。

- パターン: `lifelog-system` を `timeline-app` から取り込むとき、両方のパッケージ名に `src` を使う import は衝突しやすい。
- 対策: `lifelog-system/src` を `sys.path` に追加して `lifelog.*` パッケージだけを読む。`src.lifelog.*` ではなく `lifelog.*` を使って衝突を避ける。

- パターン: worker 移行後も DB パスを `lifelog-system/config/config.yaml` の相対指定だけに頼ると、起動場所や将来の分離で保存先がぶれやすい。
- 対策: `timeline-app/config.yaml` に `lifelog.root_dir / config_path / privacy_config_path / db_path` を明示し、既存 SQLite をそのまま使う方針を app 側設定で固定する。

- パターン: ブラウザ履歴 worker で最初の同期時に既存 `browser_history` 全件を timeline へ流すと、初回だけでタイムラインが埋まりやすい。
- 対策: `last_history_id` の初期値は DB の最新 id に合わせ、以後に増えた履歴だけを `browser-history-*` entry として投影する。

- パターン: RSS / ニュース worker で `auto_runner.main()` をそのまま呼ぶと CLI 引数や標準出力に処理が引きずられ、worker から扱いにくい。
- 対策: `collect_rss()` / `collect_news()` と repository を直接 import して呼び、収集実行と timeline 投影を分離する。

- パターン: 日次レポートのような粗い集約単位を後付けすると、`1時間単位` を前提にしたタイムライン UI と噛み合わず、どこに何を差し込むかが曖昧になる。
- 対策: 自動生成系 worker の単位は UI の時間軸に揃える。今回の timeline-app では `日次レポート` ではなく `1時間ごとの summary entry` を基本にし、`daily` は summary 投影、`articles` は本文保存に徹する。

- パターン: hourly worker を `直近1時間だけ` で動かすと、sleep 復帰やアプリ停止中の空白時間を埋められない。
- 対策: worker は lookback 範囲を走査し、`まだ生成されていない hour / source` だけを補完する。初回 import と定期 worker で同じ生成ロジックを共用し、欠損補完と通常運用を分けない。
