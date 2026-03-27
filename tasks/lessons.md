# Lessons - 過去の失敗と学び
## 記録ルール
- バグを解決したら、ここにパターンと対策を追記する
- 設計上の判断ミスや整合性の注意点も記録する
- 同じ失敗を繰り返さないための知見をまとめる

## 2026-03-26
- パターン: `lifelog-system/src` 配下の `lifelog.*` を読む worker で `sys.path` に `src` だけを足すと、下層で使っている `src.common.*` 系 import が実運用時だけ解決できず `ModuleNotFoundError` になる。
- 対策: `timeline-app` 側 worker から `lifelog-system` を読むときは、`lifelog-system` root と `lifelog-system/src` の両方を `sys.path` に追加し、必要なら既存 `src.__path__` にも `lifelog-system/src` を追加する。`activity_worker` と `browser_worker` のような動的 import 箇所には同じ補助関数を使う。

## 2026-03-25
- パターン: `article_feedback_events` を後から導入しても、既存の `article_feedback` から履歴を埋め戻さないと、見かけ上フィードバック件数があっても学習用イベント数は 0 のままになり、bonus が一切効かない。
- 対策: 進捗APIで `feedback_articles` と `feedback_events` を同時に監視する。履歴導入後は既存 `article_feedback` の `sentiment / report_status / updated_at` から最低限の backfill を入れ、`analyses_with_bonus > 0` になることを確認する。

- パターン: interest profile の補正確認を新着の未分析記事にそのまま任せると、学習対象外ソースばかり先に処理されて「bonus が効いていない」ように見えやすい。
- 対策: 開発確認では pending 記事を source/category で明示的に選び、LLM は固定応答に差し替えてもよいので、Stage1 の保存経路を通して `source_bonus` / `category_bonus` と `analyses_with_bonus` を確認する。

- パターン: settings 内で新しい運用系UIを増やすとき、既存の縦並びセクションへそのまま継ぎ足すと、情報量が増えた瞬間に見通しが崩れる。
- 対策: 既存の settings パネルを捨てず、まずは `一般 / ニュース関連` のようなタブ分割で責務を分ける。大きなナビゲーション追加より低コストで整理しやすい。

- パターン: 運用確認用の画面を settings の既存タブへ混ぜると、設定値編集と状態観測が混ざってタブ責務が曖昧になりやすい。
- 対策: RSS / 検索 / ニュース学習のような運用系UIは、settings 配下でも既存タブへ押し込まず、「ニュース関連」の新規タブとして分離する。

- パターン: 説明用の bonus 内訳を別APIで取りに行くと、hourly news 展開時に同じ article_id 群へ追加リクエストが増え、実装も表示更新も二重化しやすい。
- 対策: `GET /api/news/articles` の返却に `analysis` を同梱し、`llm_*` / `source_bonus` / `category_bonus` / `total_bonus` / reason をまとめて返す。既存の詳細取得経路に explanation を載せる方が軽い。

- パターン: Stage1 の補正を `importance_score / relevance_score` に直接上書きするだけだと、あとから「LLMの素点」と「interest profile の補正量」を分離して検証できない。
- 対策: `article_analysis` には補正後スコアだけでなく、`llm_importance_score` / `llm_relevance_score` / `source_bonus` / `category_bonus` も保存する。説明文だけに埋め込まず、数値を別カラムで持つ。

- レビュー機能と Big Five 機能は同じ worker に載せても、設定と表示は分離しておくと「レビューだけ使いたい」運用を壊しにくい
- entry メタデータ拡張は articles と daily の両方へそのまま流れるため、行動分析系の追加情報は `EntryMeta` に寄せると実装差分が小さい
- 改善アクションは memo ではなく timeline に自然に乗る `todo` として流すと、レビュー結果が次の行動へつながりやすい
- scheduler 時刻を設定画面から変える機能は、設定保存だけでなく cron 再登録まで入れないと実運用で反映されない
- review の入力対象は「すべての entry」ではなく source ベースで user 関連に絞る方が、行動改善レビューのノイズをかなり減らせる

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

- パターン: 定期実行 worker の成功ログを `INFO` のまま流すと、APScheduler の `Running job` / `executed successfully` と収集成功ログが大量に出て、本当に見たい warning や異常が埋もれる。
- 対策: 定常成功ログは `DEBUG` に落とし、APScheduler の executors ロガーは `WARNING` まで上げる。運用時は「毎回成功したこと」ではなく「失敗・遅延・例外」だけを主に見る。

## 2026-03-24
- パターン: `filter_by_relevance`（LLMによる検索結果の関連性再評価）は Stage2 の +30〜60秒/件を生む一方、search_query_gen でテーマ特化クエリを生成した後の DDG 結果は既に関連性が高く、二重評価の効果が薄い。
- 対策: 2026-03-24 時点でスキップに変更（`deep_research.py` 内にコメントアウトで復元手順を残す）。レポートの品質低下（無関係ソースの混入増）が目立つ場合は復活させること。
- 変更箇所: `lifelog-system/src/info_collector/jobs/deep_research.py`（2-1 ブロック）

- パターン: `deep_min_importance: 0.5` が低すぎると分析済み記事の30%超が deep_research 対象になり、GPU 稼働が1日1.5時間超になる。
- 対策: `deep_min_importance: 0.8` に引き上げ（`timeline-app/config.yaml`）。品質面で必要な記事が漏れる場合は 0.75 程度に戻す。

- パターン: DuckDuckGo search の収集が `info_limit` 以上に溜まりやすく（1日 300〜1000件超）、Stage1 の未分析バックログが膨大になる。
- 対策: `info_limit: 5` に減らし（旧: 10）、`search_queries.txt` のクエリ数も 3 件に整理済み。

## 2026-03-25
- パターン: フィードバック学習を `article_feedback` の最新状態だけで持つと、toggle解除や `report_requested` のような強いシグナルが履歴から消え、後段の好み集計や重み見直しがしづらい。
- 対策: UI用の最新状態テーブルとは別に、`article_feedback_events` の append-only 履歴を持つ。interest profile や集計系は履歴テーブルを正本にする。

- パターン: 興味学習の初手で title keyword や埋め込みまで広げると、データが少ない段階ではノイズの方が勝ちやすい。
- 対策: 第1段階は `source_name` / `category` のみで時間減衰つき・事前確率つきの score を作る。keyword / topic / 非教師学習は第2段階へ分離する。

- パターン: `DB write time P95 > ...` のようなSLO warningを閾値名だけで出すと、どのバッチサイズ・どの契機・どの程度の遅さだったかが運用ログから追えない。
- 対策: SLO warning には `db_write_time_p95` の実測値に加え、直近の遅い書き込みサンプル（`batch_size` / `trigger` / `queue_depth`）を含める。SQLite 競合の可能性がある経路では lock retry も warning 出力する。

- パターン: `merge_windows_logs` の `Resuming from line ...` は軽い案内ログだが、実装が毎回ファイル先頭から既処理行を `continue` で飛ばすため、マーカ方式でもファイルサイズに比例した走査コストが残る。
- 対策: 重さを疑うときは再開ログ文言ではなく、`line_num <= last_processed_line` の全走査コストと行ごとのDB処理を確認する。ファイル肥大化が進んだら byte offset やローテーション方式へ見直す。

- パターン: 右ペインで「チャット継続」と「AI編集」を同時に見せると、chat 系 entry で会話の続きと本文書き換えの責務が混ざって操作意図が曖昧になる。
- 対策: `chat` / `chat_user` / `chat_ai` はチャット継続 UI のみ表示し、非チャット entry だけに AI 編集 UI を出す。右ペイン下部の入力導線は種別ごとに 1 つへ絞る。

- パターン: 日次 worker に「AI処理停止中なら即 return」を置くと、AIを使わない保守処理まで止まり、未来日付の daily 補充のような非AIタスクも回らなくなる。
- 対策: 日次 worker では AI 必須処理と非AI処理を分離し、future daily ファイル補充は AI 一時停止とは独立して実行する。

- パターン: 繰り返しTODOの自動生成を本文一致だけで重複判定すると、ユーザーがタイトルや本文を少し触れただけで別物扱いになり、同じ日の recurring TODO が再生成されやすい。
- 対策: 自動生成TODOには `meta.recurring_series_id` と `meta.recurring_scheduled_for` を保存し、日付ごとの重複判定は本文ではなくシリーズID+対象日で行う。

- パターン: 繰り返しTODOを未来日付へ先回り生成すると、タイムラインの未来側がTODOで埋まり、当日見るべき情報が埋もれる。
- 対策: 繰り返しTODOは未来へ先回り生成しない。日次 worker が「今日までに到達した分だけ」を追加し、未完了の過去分はその日付のまま残す。

## 2026-03-19
- パターン: worker ごとに LLM 呼び出しが分散していると、サーバーログ上で「どの処理がどのモデルを使ったか」を追えず、運用時の原因切り分けが遅れる。
- 対策: LLM 呼び出しログは各 worker に個別実装せず、共通クライアントで `caller / purpose / model / base_url` を `INFO` 出力する。旧 `lifelog-system` 側を in-process で呼ぶ worker は環境変数で caller を引き継ぐ。
- 設計判断: `lifelog-system/` は最終的に `timeline-app/lifelog-system/` 配下へ移動する。
  - `timeline-app/` が唯一の運用入口であり、`lifelog-system/` はそのライブラリ層として扱う。
  - 移動前に単独起動前提の導線（daemon.sh / systemd unit / lifelog 独自の pyproject.toml エントリポイント）を先に除去する。
  - 移動後は `timeline-app/pyproject.toml` に統合し、リポジトリ直下の `lifelog-system/` は廃止する。
  - この方針に反する「lifelog-system 単独起動」の実装・ドキュメントは作成しない。

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

- パターン: `activity_worker` が `activity_intervals` をそのまま timeline へ投影すると、12秒や数十秒単位の `lifelog-activity-*` が大量に並び、1時間単位 UI の前提を壊す。
- 対策: `activity_worker` は収集だけに徹し、timeline へは書かない。画面に出す `activity` は hourly summary worker だけに限定し、既存 `lifelog-activity-*` は daily 読込時に非表示扱いにする。

- パターン: `collected_info` の生ニュースを1件ずつ timeline に出すと、素材と生成物が同じ粒度で混ざり、`reports` の意味が薄れる。
- 対策: 生ニュースは時間帯ごとに1件へ束ねて `content` にリンク付き一覧を持たせる。`reports` は生成物ごとに個別 entry として投影し、素材の束ね entry と成果物 entry を分けて扱う。

- パターン: LLM 一時停止機能を UI だけで実装すると、見た目は止まっていても worker が裏で推論を続けてしまう。
- 対策: 一時停止状態はバックエンドの共有状態として持ち、`chat` と LLM 利用 worker の両方で参照する。フロントはその状態を操作・表示するだけにする。

- パターン: AI pause を解除しても通常スケジュール時刻まで待つ実装だと、停止中に溜まった hour/day の要約がすぐ再開されず、ユーザーの期待とずれる。
- 対策: `resume` 時に catch-up を即時キックする。hourly 系は lookback 補完を 1 回走らせ、daily 系は複数日 lookback で未生成分を埋める。

- パターン: 日次の AI コメントは独立した diary を再生成するより、既存 `diary` を束ねた `memo` として入れた方がタイムライン上で役割が明確になる。
- 対策: `daily_digest_worker` は前日の `diary` を読み、振り返りコメントを `memo` entry として 1 件だけ保存する。

- パターン: 旧 `integrated_pipeline.sh` を timeline-app へ移すときに shell ごと呼ぶ設計のままだと、systemd 依存は消えても責務分離が進まず、pause/resume や health 連携も弱い。
- 対策: `analyze_pending_articles` / `deep_research_articles` / `generate_theme_reports` の Python 関数を worker から直接呼ぶ。設定値と Ollama 接続先は timeline-app 側 `config` と環境変数で注入し、scheduler / health / AI pause に統合する。

- パターン: pipeline worker のテストで実際の Ollama/DDG/SQLite を叩くと、原因切り分けが難しくなり単体テストが不安定になる。
- 対策: `analysis_pipeline_worker` のテストは `_load_pipeline_functions()` を stub に差し替え、`pause`, 設定値伝播, status 更新, 例外記録だけをまず固定する。実サービス確認は別の統合テストで分ける。

- パターン: worker 系は実装が進むほど API テストだけでは regressions を拾えず、`pause/resume`, lookback, catch-up のような内部制御が漏れやすい。
- 対策: API テストに加えて worker 単体テストを作り、`paused`, `workspace 未設定`, `status 更新`, `既存 entry スキップ`, `persist 呼び出し` を mock ベースで直接押さえる。

- パターン: 実 Ollama を使う integration テストでは、意味的には同じでも prompt の言い回し次第でモデルが 500 を返すことがあり、機能不具合とモデル揺れの区別がつきにくい。
- 対策: integration の prompt は「todo 推定」「diary 推定」など確認したい振る舞いが明確で、かつ実際に安定して通る短い文に固定する。モデルの創発的な難問をテストにしない。

- パターン: APScheduler の `misfire_grace_time` をデフォルト（1秒）のままにすると、ジョブ実行が1秒を少し超えるたびに "missed" 警告が大量に出る。再起動後も停止中の全スケジュール分が missed と判定される。
- 対策: `misfire_grace_time` を各ジョブの `interval` 秒数と同じ値に設定する。`coalesce=True` と組み合わせると「間隔以内の遅れは無視、かつ溜まっても1回だけ実行」になる。

- パターン: pre-commit の black フックはコミット時にファイルを自動整形するが、整形後のファイルはステージ外に残りコミットが中断される。
- 対策: フック失敗後は整形済みファイルを `git add` してから改めて `git commit` する。`--no-verify` は使わない。

- パターン: フェーズ4.5 全体を通して、`daemon.sh` の廃止は単に `start()` に誘導メッセージを置くだけで十分だった。旧デーモンのコードを削除するより、既存運用者への移行案内を残す方が安全。
- 対策: 旧エントリポイントは削除せず `start()` にメッセージのみ残す。stop / status などの診断コマンドは既存のまま維持する。

- パターン: `todo.md` で「実装済み」「運用確認待ち」「ユーザー手動作業」を同じ `[x]/[ ]` の意味で混ぜると、後から見たときに本当に終わったのか分からなくなる。
- 対策: `todo.md` では行の文言自体に状態を含める。例: `停止してよい状態に整理する`, `実装し、運用確認まで完了する`, `設定ページ対応` のように、コード完了と運用完了を分けて書く。

- パターン: `timeline-app/src` と `lifelog-system/src` の両方で `src` パッケージ名を使うと、`sys.path` を足しただけでは `src.info_collector.*` が解決されず、worker の実運用時だけ `ModuleNotFoundError` になる。
- 対策: 既存の `src` パッケージを使い回す場合は `sys.path` 追加に加えて `src.__path__` も拡張し、統合テストで実 import まで確認する。

## 2026-03-19
- パターン: 削除候補を棚卸しするときに、生成物・保持対象・追跡済み資産を同じ粒度で並べると、安全に消せる範囲が曖昧になる。
- 対策: 削除対象は `確実に削除可` / `削除しない` / `保留` に分けて記録する。今回の整理では、`gitignore` されたキャッシュ類だけを削除確定とし、Windowsログ・外部モデル・現行DBは保持、追跡済みかつ参照が残る資産は保留にした。

- パターン: `lifelog-system/pyproject.toml` に独自 entry point がある前提で整理を進めると、実際には存在しない削除対象を追いかけてしまう。
- 対策: `pyproject.toml` は「独立パッケージ設定そのものが不要になる」という粒度で扱い、先に消す対象は `systemd` / `daemon.sh` / viewer / CLI / shell 導線として分けて棚卸しする。

- パターン: `scripts/systemd/` を先に消そうとしても、README や設定ガイド、トラブルシュート文書に古い運用導線が大量に残っていると、削除後の利用者が誤誘導される。
- 対策: `systemd` 系は unit ファイル削除より先に参照ドキュメントを整理する。特に `README.md`, `docs/TASK_SCHEDULER_SETUP.md`, `docs/TROUBLESHOOTING_SYSTEMD.md`, `docs/INFO_COLLECTOR_DEEPDIVE_PLAN.md` を先に更新してから、`scripts/systemd/` を消す。

- パターン: `duckduckgo_search` の rename warning や、テスト中の `sqlite3.Connection` close 漏れが積み上がると、運用ログと CI 出力のノイズが増えて本来の異常を見落としやすい。
- 対策: `DDGS` は `ddgs` を優先 import し、旧 `duckduckgo_search` へ落ちる場合だけ rename warning を局所的に抑制する。SQLite を使うテストは `with sqlite3.connect(...)` または `try/finally` で必ず close する。

- パターン: `viewer_service` のような独立サービス層を削除するとき、それを import していた CLI ツール（`cli_viewer.py`）が連鎖的に壊れる。
- 対策: 大きなモジュールを削除する前に `grep -r "viewer_service"` で参照元を全洗いし、影響範囲を確認してから削除する。今回は `cli_viewer.py` の `news / dashboard / view / recent` コマンドを合わせて除去した。

- パターン: Windows タスクスケジューラが指しているスクリプトパスを確認せずにラッパーを削除すると、Windows 側の自動起動が壊れる。
- 対策: Windows 側スクリプトを削除する前に `Get-ScheduledTask` で実際の引数パスを確認する。本体と wrapper が混在している場合は必ずどちらが登録済みかを確認してから判断する。

- パターン: `main_collector.py` のような旧スタンドアロン起動エントリが残っていると、「今でも直接起動できる」という誤解を招く。
- 対策: worker 移行完了後は旧エントリポイントを削除し、起動経路を `timeline-app/scripts/start.sh` に一本化する。ドキュメントも同時に更新する。

## 2026-03-22（Markdown描画・コンテンツルール）
- パターン: entry の content が Markdown 形式で保存されていても、フロントで `textContent` を使うとタグが文字列のまま表示される。
- 対策: 右ペインの閲覧エリアと AI 返答欄は `marked.parse()` + `DOMPurify.sanitize()` で `innerHTML` に流す。編集欄（textarea）は `textContent` のままにする。
- パターン: LLM に content フォーマットを指定しないと、モデルによって HTML タグ・自由形式テキスト・Markdown が混在して出力される。
- 対策: Ollama へのすべての system prompt に「content は Markdown 形式で書くこと。HTML タグは使わないこと。」を明示する。対象: `generate_chat_reply` / `summarize_import_source` / `daily_digest_worker`。

## 2026-03-22
- パターン: SQLite の read-only / fetch 系メソッドで `conn.close()` を末尾に直書きすると、`execute()` や `fetchall()` の例外経路で close が飛ばず、worker 実行中に `ResourceWarning: unclosed database` が遅れて出る。
- 対策: `InfoCollectorRepository` や worker の read 経路でも `with sqlite3.connect(...)` / `with self._connect() as conn` を標準にし、読み取り専用でも手動 `close()` 前提にしない。
- パターン: ログ上で `generate_theme_report` の直後に warning が見えても、原因がそのジョブ本体とは限らない。並行 worker の DB 参照や初期化経路の手動 `close()` 漏れが、GC のタイミングで後から同じ場所に見える。
- 対策: warning の直前ログだけで犯人を決めず、同時実行 worker を含めて `sqlite3.connect` の全経路を洗う。特に worker 補助関数、DB 初期化、CLI の read-only 接続も `with` に統一する。
- パターン: syslog の priority は数値が小さいほど重要なのに、`journalctl --priority={min}..7` としてしまうと `warning以上` のつもりが `warning以下` ではなく `warning+notice+info+debug` を大量に拾ってしまう。
- 対策: `priority_min` を下限ではなく上限として扱い、`journalctl --priority=0..{min_priority}` にする。数値 priority (`"3"`, `"4"`) も分類器で明示的に `err` / `warning` 等へ変換する。
- パターン: `tee` を使ったラッパースクリプトの定常ログは journald に流れ、syslog collector が拾うと `system_events` を急速に肥大化させる。
- 対策: Linux event collector に `ignored_processes` を持たせ、少なくとも `tee` は既定で除外する。運用ログの保存先と system event 収集対象を分離する。
- パターン: タイムラインを「上が未来・下が過去」の逆順に変えるとき、カードの並び順だけ反転しても破綻する。DOM 順、境界付近の時刻ソート、無限スクロールの読み込み方向が旧仕様のままだと、Now 近傍の情報配置と追加読み込みが逆転して見える。
- 対策: 逆順タイムラインでは `future -> upcoming -> now -> past` の DOM 順を先に固定し、`Now` に近いカードが境界側に来るよう各帯を降順で描画する。さらに「上端で未来を追加、下端で過去を追加」を 1 セットで直し、表示順だけの局所変更にしない。
- パターン: タイムラインの向きを変えた後も `今日へ戻る` やキーボード移動が旧方向前提のままだと、表示順だけ新しく見えても操作感が一致せず混乱する。
- 対策: 向き変更時は描画順だけでなく、`Now` への復帰関数、初期スクロール位置、`Home` / `End` などの移動操作も同じメンタルモデルで再定義する。
- パターン: タイムラインカードに左余白の導線を付けたままカード本体を `100%` 幅で描画すると、中央ペイン内で数pxはみ出し、横スクロールバーが出る。
- 対策: 導線用の `margin-left` を持つカードは、カード本体の実幅を `calc(100% - margin)` に制限する。あわせてペイン側も `overflow-x: hidden/clip` を入れて、レスポンシブ時の微小はみ出しを吸収する。
- パターン: `system_log` の import で LLM 要約文をそのまま `article.content` に保存すると、`daily` と右ペイン詳細が同じ短文になり、詳細表示の意味が消える。
- 対策: import summary entry は `summary` と `content` を分離して保存する。タイムライン / `daily` は短い summary を使い、右ペインは `articles/*.md` の詳細本文（event counts・sample messages・集計素材など）を表示させる。少なくとも `activity` / `browser` / `system_log` はこの形に揃える。
- パターン: browser 履歴の時間帯 summary を `memo` にすると、ユーザーが書いたメモと外部取り込みログが同じ見え方になり、分類意図が崩れる。
- 対策: browser / activity / system event のような自動集約ログは `system_log` に寄せ、`memo` はユーザーまたはAIが本文を書くノート系 entry に限定する。
- パターン: AI が候補に `timestamp` を返していても、API 側の候補正規化で値を落とすと、本文に「12時頃」と書いてあっても保存時刻の entry になってしまう。
- 対策: `POST /api/chat` の候補正規化では `timestamp` も保持し、フロントの candidate 保存でそのまま `POST /api/entries` に渡す。既定時刻と AI 上書きの両方を使う場合は、API の途中で捨てないことを確認する。
- パターン: タイムラインの絞り込みをサーバー再取得なしで足すとき、表示用フィルタと読み込み境界（oldest/newest）を同じ配列で壊すと、無限スクロールの追加読込が不安定になる。
- 対策: 読み込み済みの raw entry 配列は保持したまま、描画時だけフィルタをかける。ページング境界は raw 配列から計算し、表示件数だけを別で出す。
- パターン: 安全装置としての undo を追加するとき、作成系と更新系を同じ粒度で扱うと delete API 不在のケースで巻き戻しが中途半端になる。
- 対策: まずは `PATCH` で戻せる更新系操作（詳細編集、種別変更、TODO完了）に対象を絞って undo を入れる。作成取り消しは delete API を用意する別タスクとして分ける。
- パターン: 逆順タイムラインで無限スクロールを足すと、追加読込のたびに `around` が変わり、同じ entry が「最初は未来」「次は過去」と別レーンで返ることがある。レーン内だけの重複除去では、同じ `id` が Now の上下に同時表示される。
- 対策: 追加読込後は単純な配列結合で終わらせず、`around` を基準に `past / todo / future` を id 単位で再振り分けする。重複削除は「残す側を決める」まで含めて行う。
- パターン: フィルター UI を複数選択化するとき、ボタン状態だけを持っていて内部状態が単一 `type` のままだと、表示上は複数選択に見えても判定が最後の1つしか効かない。
- 対策: フィルター状態は `types: []` の配列で持ち、`chat` / `todo` のような種別グループ判定も `matchesEntryTypeGroup()` のように1か所へ集約する。メニュー表示はその状態を反映するだけにする。
- パターン: NOW 中心の無限スクロールで `past_entries` / `future_entries` の片側だけを都度足すと、API 応答が持つ `entries` 全体との整合が崩れ、境界の entry が欠けたり重複したりしやすい。
- 対策: 追加読込は `response.entries` を raw 配列へ統合し、固定した `around` で毎回 `past / todo / future` を再計算する。初回表示幅と追加読込幅も定数化して、NOW 周辺の読込量を明示する。
- パターン: `DatabaseManager` がスレッドローカル接続を使っているのに `close()` が現在スレッドの接続しか閉じないと、`asyncio.to_thread()` 経由の worker 実行後に他スレッドで作られた SQLite 接続が残り、`ResourceWarning: unclosed database` がまとまって出る。
- 対策: スレッドローカル接続を作るクラスでは、現在スレッドの参照だけでなく「生成した全接続」を追跡して `close()` でまとめて閉じる。スレッドローカルは参照経路であって、close 管理の単位にはしない。
- パターン: WSL 環境では `python` コマンドが Windows 側 shim を踏んで壊れていることがあり、単発の構文確認や補助実行でも失敗する。
- 対策: このリポジトリでは Python 実行・確認は基本 `uv run` を使う。`python -m ...` ではなく、まず `uv run python -m ...` を選ぶ。

## 2026-03-22（ResourceWarning 根本対応）
- パターン: `while self._running: time.sleep(N); db操作` の形では、スリープ中に `_running = False` になっても現在のイテレーションのDB操作まで進む。「フラグをセットすれば次のループで止まる」は正しいが、スリープ後の1回分は確定的に踏む。
- 対策: スリープ後に `if not self._running: return` を追加して、DB操作前に再チェックする。
- パターン: daemon スレッドを `start()` して参照を捨てると、停止後もスレッドが生きているか確認できない。`stop()` の直後に `close()` を呼ぶと、まだ動いているスレッドが閉じた接続を踏む。
- 対策: スレッド参照を `self._threads` で保持し、`stop_collection()` で `t.join(timeout=N)` してから呼び出し元へ返す。join 完了後なら `db_manager.close()` を呼んでも安全。
- パターン: `DatabaseManager` を `__init__` で生成するクラスに `close()` を実装しないと、そのクラスが廃棄されるとき接続が残る。`__del__` が best-effort である以上、所有クラスが明示的な close 経路を持つことが必要。
- 対策: `DatabaseManager` を保持するクラスには必ず `close()` を実装し、呼び出し側（worker の finally など）でその close を呼ぶ。`__del__` はフォールバックに留め、設計上の主経路にしない。
- パターン: ResourceWarning 修正を「`sqlite3.connect` を直接呼んでいる行を直す」として進めると、接続が `_get_connection()` 経由でスレッド内に作られているケースを見落とす。症状（警告の件数・スタックの出所）から接続を作ったスレッドを逆引きしないと、修正対象がずれ続ける。
- 対策: ResourceWarning が出たら「どのスレッドが接続を作ったか」を件数・スタックから特定してから修正箇所を決める。

## 2026-03-23
- パターン: Windows PowerShell から JSONL を追記するとき、`Add-Content` の既定エンコーディングに任せると CP932 系で書かれ、WSL 側で UTF-8 前提読込したときに日本語タイトル中の `0x5c` が JSON の `\` と誤解されて `Invalid \escape` warning になる。
- 対策: Windows 側 JSONL 出力は `Add-Content -Encoding utf8` のように明示して UTF-8 固定にする。読み込み側も既存データ救済のため、少なくとも `utf-8` → `cp932` の順で行単位 decode fallback を持たせる。
- パターン: `foreground_logger.ps1` を `\\wsl.localhost\Ubuntu\...` の UNC パスから直接起動すると、スクリプト本体は動いて JSONL 出力もできる一方、既定の相対 `PrivacyConfigPath`（`..\config\privacy_windows.yaml`）が期待どおりに見つからず、`Privacy config not found` で既定値運用になることがある。
- パターン: chat entry を「1メッセージ1本文」のまま持つと、右ペインでの会話継続表示と append 保存の整合が崩れやすい。
- 対策: chat entry 本文は transcript Markdown として扱い、`<!-- chat-message:user|assistant -->` マーカー付きで保存・追記・描画を統一する。
- パターン: AI 編集のプレビュー生成前に元本文の退避先が曖昧だと、保存/キャンセル時の後始末が UI 実装ごとにぶれやすい。
- 対策: `articles/{id}.bak.md` を唯一の一時バックアップとし、生成は `ai_edit` 開始時、削除は `PATCH /entries/{id}` 成功時または明示キャンセル時に一本化する。
- パターン: フロントにビルド基盤がない状態で VRM 表示を足すと、依存導入を後回しにしたまま実装が止まりやすい。
- 対策: まず「静的 HTML/JS のまま動かす」方針を固定し、ESM CDN + `type="module"` を採るか、ローカル vendor 配置にするかを先に決める。今回の timeline-app は前者で統一した。
- パターン: `models/*.vrm` を左パネルで直接読む経路がないと、モデル配置済みでも UI 実装が静的プレースホルダで止まる。
- 対策: フロントは固定ファイル名を決め打ちせず、`GET /api/vrm` でメタデータを取り、`GET /api/vrm/model/{filename}` で実体を読む形にすると差し替えしやすい。
- パターン: セキュリティ上 CDN を避けたい画面で、`three` だけローカル化しても `marked` や `DOMPurify` が外部配信のままだと方針が崩れる。
- 対策: フロント依存はまとめて `vendor-src/node_modules` へ固定し、FastAPI から `/vendor` 配信する。HTML では import map とローカル script のみを使う。
- パターン: VRM モデル選択を UI だけで持つと、再起動後に元へ戻りやすい。
- 対策: `config.yaml` に `vrm.model_filename` を保存し、`/api/settings` は「現在値 + 利用可能一覧」を返す。左パネルはその設定値を読む `GET /api/vrm` だけを見る。
- パターン: workspace の手動「開く」導線と `config.workspace.default_path` の自動適用を併存させると、どちらが正本か分かりにくくなる。
- 対策: 運用上の workspace は `config.yaml` 側を正本に寄せ、通常 UI からは手動 open を外す。未設定時は「どこを直せばよいか」を空状態メッセージに明示する。
- パターン: VRM 表示を固定カメラ位置と固定 `position.y` だけで置くと、モデルごとの原点・身長差で「ファイル名は見えるが本体が画角外」という状態が起きる。
- 対策: 読み込み後に `Box3` で bounds を取り、足元合わせ・中心寄せ・camera/controls.target の自動再計算を行う。UI 側にも表示枠を重ね、枠内に収まっていない場合は warning 表示にする。
- パターン: VRM の rest pose をそのまま出すと、T ポーズのまま立ち続けて違和感が強い。
- 対策: `humanoid` のボーンを直接待機姿勢へオフセットし、その上に胸・肩・頭・重心の小さな周期変化を重ねて待機モーションを作る。診断用 overlay は確認後に UI から外す。
- パターン: VRM の正面向きはモデル差があり、`rotateVRM0()` 後にさらに `Math.PI` を足すと前後が逆転することがある。腕も外転量を大きくしすぎると「自然に下ろした姿勢」にならない。
- 対策: 実モデルを見ながら正面向きは最小回転から始める。腕の待機姿勢は shoulder / upperArm / lowerArm / hand を個別に小さく調整し、体側に沿う方向へ寄せる。カメラ距離も bounds ベース計算の係数で詰める。
- パターン: 左パネル VRM を全身寄りの bounds fitting のまま使うと、ユーザーが欲しい「顔と上半身中心」の構図には届かない。腕も少しでも Z 回転が大きいと、正面視で広がって見えやすい。
- 対策: バストアップ寄りにしたい場合は `controls.target` を胸から首寄りまで上げ、距離係数をかなり小さくする。腕は shoulder と upperArm の Z 回転を最小限にし、lowerArm と hand もほぼニュートラルまで戻す。
- パターン: VRM の姿勢と framing を口頭だけで詰めるのは非効率で、調整量が増えるほど往復が長くなる。
- 対策: 一時的な debug UI を左パネルに出し、camera 係数と主要ボーン角度をスライダーでその場調整できるようにする。現在値は JSON で表示し、固まったらその値をコードへ固定して debug UI を外す。
- パターン: Unity Asset Store 由来の animation FBX をそのまま `models/animation/` に置くと、開発用入力なのか配布物なのかが曖昧になり、raw asset 同梱の事故が起きやすい。
- 対策: `models/animation/` は Git 管理から外し、当面はローカル開発専用入力として扱う。配布用には別途「非 raw 形式への変換」または権利確認済みアセットへの差し替えタスクを分離する。
- パターン: VRM の待機モーションを手動ボーン操作だけで作ると、モデル差でねじれや破綻が出やすい。
- 対策: 利用可能なアニメーションがある場合は、`FBXLoader` と `SkeletonUtils.retarget` で外部 idle animation を VRM humanoid へ流す。手動ボーン姿勢は fallback に留める。
- パターン: `collected_info` の時間帯サマリーを `source_type` 無視 + 全体 `LIMIT` で組むと、DuckDuckGo 検索結果が RSS を押し出して「ニュース箱」が実質 search 箱になる。
- 対策: hourly summary は `news` と `search` を entry type ごとに分離し、表示件数は全体件数ではなく「ソースごと上限」で切る。定期検索の設定は `search_queries.txt` を UI から編集可能にし、収集 worker 側も `--search` を明示して実行経路を隠さない。
- パターン: 旧 systemd timer を「置き換え済み」と認識していても、user unit が有効化されたまま残っていると、削除済みスクリプトを永続的に叩き続けて失敗ログや誤調査の原因になる。
- 対策: worker を `timeline-app` 側へ移行したら、対応する旧 timer/service は同ターンで `disable --now` まで行う。コード移行だけで終えず、user systemd の `Loaded/Active/Trigger` を実機確認してから完了扱いにする。
- パターン: 旧 `info-collector.service` のように systemd unit が `--use-ollama` 付きで動いていた場合、単純に `timeline-app` worker へ置き換えただけでは挙動差が残る。特に検索クエリ生成の有無は収集結果に直結する。
- 対策: systemd 非依存化では unit の `ExecStart` 引数まで比較し、`limit` や `--use-ollama` のような実行オプション差分を設定項目として現行 worker に移植してから timer を止める。
- 対策: UNC 経由で運用する場合は `-PrivacyConfigPath` を絶対指定するか、スクリプト側で `Join-Path $scriptDir "..\..."` のような未解決相対パスをそのまま使わず、`[System.IO.Path]::GetFullPath([System.IO.Path]::Combine(...))` で `scriptDir` 基準の絶対パスへ正規化する。起動できたことだけで privacy 設定読込成功とみなさない。
- パターン: `system_log` や hourly summary の時刻を SQLite の `localtime` や実行環境任せで扱うと、WSL とブラウザでタイムゾーン解釈がずれたときに `01時のシステムイベント` が `10:30` 表示になる。
- 対策: 個人用の単一PC運用では、worker の時間帯判定と entry 保存 timestamp は `datetime.now().astimezone()` で得たローカルタイムゾーンに揃え、フロント表示はブラウザのローカルタイムゾーンを使う。SQLite 側も `localtime` 依存を避け、検出したUTCオフセットを明示して集計する。
- パターン: UI の `👍/👎` トグルと「レポート生成済み/進行中」状態を 1つの `feedback_type` 文字列で兼用すると、排他制御・多重実行防止・生成済み表示がすぐ破綻する。
- 対策: 記事フィードバックは履歴1列ではなく、少なくとも `sentiment` と `report_status` を分けて持つ。個人用アプリでも `positive/negative` と `requested/running/done/failed` は別軸として扱う。
# Lessons - 過去の失敗と学び
## 記録ルール
- バグを解決したら、ここにパターンと対策を追記する
- 設計上の判断ミスや整合性の注意点も記録する
- 同じ失敗を繰り返さないための知見をまとめる
