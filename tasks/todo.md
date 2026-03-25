## 運用ルール
1. タスクを追加するときはチェックボックス形式で書く
2. 完了したら `[x]` にする
3. セクションが全て完了したら、セクションごと削除してよい

---

## timeline-app: フェーズ6 M3 行動改善

- [x] 要件書 §10 / §21.3 / §24.2 と既存実装を照合し、レビュー機能と Big Five 機能の分離方針を整理する
- [x] Big Five を opt-in で有効化できる設定項目と、日次レビュー観点 / Big Five レビュー観点の設定項目を追加する
- [x] entry メタデータへ Big Five 傾向スコアを保持できるようにし、日次処理で対象 entry に付与する
- [x] 日次レビュー要約と改善アクション提案を生成し、改善アクションをタイムライン entry として流入させる
- [x] 週次レビュー画面または専用パネルを追加し、通常レビューと Big Five レビューを分けて表示する
- [x] テスト・確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: M3 行動改善 追加調整

- [x] 日次レビュー時刻と週次レビュー曜日/時刻を設定できるようにする
- [x] Big Five の各因子ごとに目標方向を設定できるようにする
- [x] レビュー対象を user 関連 entry に絞る
- [x] テスト・確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: entry 型変更ルールの再設計

- [ ] entry type ごとの許可変換 / 禁止変換を整理する
      → 例: AI 誤分類の修正として許可すべき変換と、意味的に禁止すべき変換を分ける
      → 例: `chat -> news` や `todo -> diary` を本当に許すかを検討する
- [ ] recurring は `todo` / `todo_done` のみ許可し、それ以外へ変更したら recurring meta をクリアする仕様を明文化する
- [ ] UI 上の型変更候補を entry ごとに制限する案を整理する
- [ ] API 側でも禁止変換を弾く必要があるか確認する

---

## lifelog-system: SLO violation / merge_windows_logs 調査

- [x] `activity_collector` の SLO 計測箇所と warning 出力条件を特定する
- [x] `DB write time P95 > 500ms` の実体が追えるように必要ログ案を整理または実装する
- [x] `merge_windows_logs` の `Resuming from line ...` が重いかどうか実装と実測観点で確認する
- [x] 調査結果をまとめ、必要なら `tasks/lessons.md` を更新する

---

## news feedback: N-2 再設計（時間減衰つき interest profile）

- [x] N-2 の主軸を「過去記事 few-shot 注入」から「構造化 interest profile + 前処理スコア補正」へ更新する
      → 生記事列挙の LLM 注入は暫定策に下げる
      → 推薦本体は Stage1 前の補正層として設計する
- [x] `article_feedback` を「現在状態」と「履歴イベント」に分離する設計を追加する
      → `article_feedback` は最新状態を保持
      → `article_feedback_events` は append-only で `positive` / `negative` / `report_requested` / 解除を記録する
- [x] interest profile の最小特徴集合を定義する
      → 第1段階は `source_name` と `category` に限定する
      → 将来の `tag` / `keyword` / `topic` 拡張を阻害しないスキーマにする
- [x] source/category ごとの時間減衰つき preference 集計関数を追加する
      → `positive` は加点、`negative` は減点、`report_requested` は強い加点として扱う
      → 直近 7 日 / 30 日 / それ以前で重みを落とす案を比較して決める
- [x] ベイズ風の事前確率つき preference score を実装する
      → 少数データで暴れないよう `a,b` の事前値を持たせる
      → source/category ごとに 0〜1 の安定した score を返す
- [x] Stage1 の importance / relevance に interest bonus を加える前処理補正を実装する
      → `final_score = llm_score + source_bonus + category_bonus` の弱い補正から始める
      → フィードバック件数が少ない期間は補正を弱める安全装置を入れる
- [x] profile / score のデバッグ API を health とは別エンドポイントで追加する
      → `/api/news/feedback/stats` などで source/category ごとの score と件数を確認できるようにする
      → 上位 positive / negative source、上位 category、直近変動を見られるようにする
- [x] 「なぜその記事が上がったか」を確認できる説明用データを追加する
      → source bonus / category bonus / 元の llm_score を分けて確認できるようにする
- [ ] 非教師学習・共起は第2段階タスクとして分離する
      → positive 記事群から keyword cluster / latent topic を抽出する補助層として扱う
      → 推薦本体には直結させず、profile 拡張候補として別評価する

---

## news関連画面: RSS / 検索 / 学習可視化

- [ ] settings 内に、ニュース関連の新規タブを追加する
      → RSS / 検索 / ニュースフィードバック / interest profile を同じ導線にまとめる
      → settings 配下に置くが、既存タブとは責務を分けて「運用確認と調整」の領域として扱う
- [ ] ニュース関連画面の情報設計を整理する
      → RSS 設定/状態、検索設定/状態、feedback 学習状態を同居させるレイアウトを決める
      → 初期表示で何を見せ、詳細はどこで展開するかを決める
- [ ] source/category ごとの preference score 一覧を表示する
      → score / samples / positive / negative / report_requested を見られるようにする
- [ ] 記事ごとの explanation を確認できる UI を追加する
      → llm score / source bonus / category bonus / total bonus / reason を表示する
- [ ] 直近変動を確認できる表示を追加する
      → recent feedback と time decay の効き方を把握できるようにする
- [ ] デバッグ用途と通常ユーザー用途の表示粒度を分ける
      → 初期表示は簡潔に、必要なら詳細を展開できる形にする
- [ ] API の返却形式を UI 用に整理する
      → `/api/news/feedback/stats` と `/api/news/articles` の役割分担を明確にする
- [ ] RSS / 検索の現在設定と実行状態も同じ画面で確認できるようにする
      → feed/query の一覧、実行間隔、直近実行状況を見られるようにする
- [ ] フロントエンドの表示テストを追加する

---

## timeline-app: 右ペイン AI 編集 + チャット継続

- [x] 右ペイン閲覧モードに「AI に投げる」導線を追加する
- [x] AI 編集用の指示入力欄、プレビュー、保存/キャンセル UI を追加する
- [x] `POST /api/entries/{id}/ai_edit` を追加し、バックアップ作成つきで Ollama 編集を実行する
- [x] 保存/キャンセル時に `articles/{id}.bak.md` を削除する
- [x] `POST /api/entries/{id}/append_message` を追加し、会話を末尾追記保存できるようにする
- [x] chat 系 entry の右ペインに会話履歴表示と継続入力欄を追加する
- [x] テストを追加し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: 右ペイン AI/チャット UI 整理

- [x] chat / chat_ai / chat_user ではチャット継続 UI のみ表示する
- [x] 非チャット entry では右ペイン下部に AI 指示入力欄と `AIに投げる` ボタンを横並びで表示する
- [x] 構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: 未来日付 daily Markdown 自動補充

- [x] `tasks/todo.md` 起点で関連実装箇所を調査する
- [x] 設定で「何日先まで作るか」を変更できるようにする
- [x] 日次の自動処理で指定日数先まで `daily/*.md` を不足分作成する
- [x] 構文確認と必要テストを実施し、`tasks/lessons.md` を更新する

---

## timeline-app: 毎日TODO 自動生成

- [x] 毎日TODOの保存形式と関連実装箇所を調査する
- [x] 設定画面で毎日自動生成するTODOテンプレートを編集できるようにする
- [x] future daily 補充時に各日付向けTODOを重複なしで自動生成する
- [x] テスト・構文確認を実施し、`tasks/lessons.md` を更新する

---

## timeline-app: TODO 繰り返し設定の再設計

- [x] TODO に繰り返しフラグ・ルール・間隔・回数・曜日指定を持てるようにする
- [x] 日次処理で当日到達分だけを自動生成し、未来への大量生成をやめる
- [x] 未完了の期限超過 TODO を未来へ寄せず、過去の未完了 TODO として扱う
- [x] テスト・構文確認を実施し、`tasks/lessons.md` を更新する

---

## timeline-app: 左パネル VRM 表示

- [x] 左パネルに VRM 表示用 canvas と状態表示を追加する
- [x] `models/*.vrm` を配信する API を追加する
- [x] フロントで Three.js + three-vrm を使ってモデルを読み込む
- [x] 左パネルで簡易待機モーションとリサイズ追従を実装する
- [x] テストと構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: VRM ローカル化 + 設定切替

- [x] VRM 依存を CDN ではなくローカル配布ファイルへ切り替える
- [x] `config.yaml` / settings API に VRM モデル設定項目を追加する
- [x] 設定画面に VRM モデル選択 UI を追加する
- [x] 左パネルが設定された VRM を再読込できるようにする
- [x] テストと構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: workspace 導線整理

- [x] トップバーのワークスペース入力欄と「開く」ボタンを削除する
- [x] 起動時は `config.workspace.default_path` 自動適用前提の UI に整理する
- [x] テストと構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: VRM 表示フィット調整

- [x] 左パネル VRM を bounds 基準で自動配置・自動フィットする
- [x] 左パネルに表示枠と判定表示を追加する
- [x] 構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: VRM 待機モーション調整

- [x] 左パネルの診断用表示枠とステータス表示を削除する
- [x] VRM を自然な待機姿勢へ調整する
- [x] 呼吸する待機モーションを追加する
- [x] 構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: VRM 微調整

- [x] VRM の前後向きを修正する
- [x] カメラ距離を近めに調整する
- [x] 腕を体の横で自然に下ろす姿勢へ再調整する
- [x] 構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: VRM 追加フレーミング調整

- [x] 腕をさらに体側へ寄せる
- [x] 顔と上半身中心になるようカメラをさらに近づける
- [x] 構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: VRM デバッグ調整 UI

- [x] 左パネルに一時的な VRM デバッグ UI を追加する
- [x] カメラと主要ボーン角度をリアルタイム調整できるようにする
- [x] 現在値を確認できる表示を追加する
- [x] 構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## timeline-app: animation FBX 運用整理

- [x] `models/animation/` を Git 管理対象から外す
- [ ] FBX を配布用の非 raw 形式へ変換する経路を保留タスクとして整理する
- [x] `@KA_Idle01_breathing.FBX` を待機ループとして再生する
- [x] 構文確認を実施し、完了後に `tasks/lessons.md` を更新する

---

## 最優先: 単純化・削減フェーズ（残1件）

- [ ] Windows 移行時: `WindowsForegroundWorker` に `powershell.exe foreground_logger.ps1` の起動管理を追加する
      → 現時点は foreground_logger.ps1 は別途起動する運用のまま
- [x] `foreground_logger.ps1` を `\\wsl.localhost\...` から起動したとき `privacy_windows.yaml` が見つからない問題を整理する
      → `Resolve-ScriptPath` で `scriptDir` 基準の絶対パス解決済み
- [x] `windows_foreground.jsonl` の文字コード混在で `merge_windows_logs` が `Invalid \\escape` warning を出す問題を修正する
      → PowerShell 出力を UTF-8 固定にし、マージ側でも既存の CP932 行を救済できるようにする

### 削除しない候補（保持）

- `scripts/logs/windows_foreground.jsonl`, `scripts/logs/windows_foreground.jsonl.processed`
- `models/176039414170160856.vrm`, `models/176039414170160856.vrm:Zone.Identifier`
- `lifelog-system/data/ai_secretary.db`, `lifelog-system/data/info.db`, `lifelog-system/data/lifelog.db*`
- `articles/*.md`, `daily/*.md`, `/mnt/c/YellowMable/00_Raw` 配下の必要レポートも正本または生成成果物として保持する

### 保留（参照残存のため削除しない）

- `scripts/systemd/` 一式, `docs/TASK_SCHEDULER_SETUP.md`, `docs/TROUBLESHOOTING_SYSTEMD.md`
- `README.md`, `CLAUDE.md`, `lifelog-system/README.md`, `lifelog-system/docs/QUICKSTART.md`, `docs/PROJECT_OVERVIEW.md`
- `scripts/info_collector/integrated_pipeline.sh`, `lifelog-system/src/viewer_service/`, `lifelog-system/src/lifelog/cli_viewer.py`
- `lifelog-system/tests/test_integration.py` 等の統合テスト群
- 即削除不可の主因: `src/lifelog/*`, `src/browser_history/*`, `src/info_collector/jobs/*`, `auto_runner.py`, `scripts/lifelog/merge_windows_logs.py` は `timeline-app` 側 worker がまだ使用中

---

## UI/データ不整合の不具合（未修正）

- [x] `しばらくお待ちください...` 系 entry が大量発生している原因を特定して修正する
      → `importer.py` にノイズタイトルスキップ（`_NOISE_TITLE_PATTERNS`）を追加
      → `summarize_browser()` の SQL に WHERE フィルタ + `GROUP BY url` で重複排除
- [x] タイムライン上の時刻表示が誤っている問題を調査する
      → entry の timestamp、表示上の時刻、元データの時刻のどこでずれているかを確認する
      → hourly summary 生成時刻は実行環境のローカルタイムゾーンを自動検出、フロント表示はブラウザのローカルタイムゾーンを使う
- [x] `system_log` の対象時刻とカード表示時刻のずれを修正する
      → 例: `2026-03-19 01時のシステムイベント` なのにカード表示が `03/19 10:30` になっている
      → worker 集計時の時間帯判定・保存 timestamp は実行環境のローカルタイムゾーン、フロント表示はブラウザのローカルタイムゾーンへ揃えた
- [ ] 画面に出ている結果が「現状の正しい仕様」か「仮実装由来」かの整理
      → browser 取り込み・要約・分類・UI 表示の各段で、意図した挙動と暫定挙動を明文化する

### news / search 箱分離と DuckDuckGo 検索設定

- [x] hourly summary の `news` カードを RSS / news 系だけに限定し、`search` カードを別 entry type として追加する
- [x] `news` / `search` の表示件数制御を全体 `LIMIT 20` ではなく「ソースごと上限」に変更する
- [x] 設定画面に DuckDuckGo 定期検索クエリ管理 UI を追加し、`search_queries.txt` を編集できるようにする
- [x] `timeline-app` の info worker から定期検索を明示的に実行し、検索設定の実行経路を UI 設定と一致させる
- [x] `search|DuckDuckGo` の保存元調査結果を整理し、旧運用・別経路の痕跡があれば記録する
      → リポジトリ内で `collected_info(source_type='search', source_name='DuckDuckGo')` を保存する経路は `src.info_collector.auto_runner --search/--all` と `scripts/info_collector/search_web.sh`
      → 修正前の `timeline-app/src/workers/info_worker.py` は `--search` を呼んでいなかったため、既存の DuckDuckGo 行は手動実行または旧/別運用ジョブ由来の可能性が高い
- [ ] DuckDuckGo 検索の実行元を追加調査する
      → systemd / cron / README / 旧導線を再確認し、実行元候補の確度を整理する

### 旧 timer 移行

- [x] user systemd の `info-integrated.timer` / `info-integrated.service` を現行 `timeline-app` worker へ移行完了扱いにする
      → 旧 service の「収集→分析→深掘り→レポート」は `timeline-app` の `info_worker` + `analysis_pipeline_worker` + `scheduler` へ分割移行済み
- [x] 旧 `info-integrated.timer` を停止・無効化する
      → `systemctl --user disable --now info-integrated.timer` 実施済み
- [x] 無効化後の状態確認結果を記録する
      → `info-integrated.timer` は `disabled` / `inactive (dead)`、次回 trigger は `n/a`
      → `info-integrated.service` は直近失敗状態の履歴を残すが、timer からは起動されない状態になった
- [x] user systemd の `info-collector.timer` / `info-collector.service` を調査し、現在の DuckDuckGo 保存元かどうかを確認する
      → `info-collector.timer` は `hourly` で `info-collector.service` を起動
      → `info-collector.service` の `ExecStart` は `scripts/info_collector/auto_collect.sh --all --limit 10 --use-ollama`
      → 直近実行 `2026-03-24 01:02:32 JST` の systemd 出力に `search: { queries: 10, saved: 84 }` が残っており、現在の DuckDuckGo 保存元であることを確認

### systemd 非依存化確認

- [x] `info-collector.service` の責務が現行 `timeline-app` worker に揃っているか確認する
      → 旧 service の `auto_collect.sh --all --limit 10 --use-ollama` に対して、現行 `info_worker` は RSS/news/search/limit を実装済み
- [x] 足りない収集・設定反映があれば `timeline-app` 側へ実装する
      → 欠けていた `--use-ollama` 相当を `config.lifelog.info_use_ollama` として追加し、worker / settings API / UI / テストへ反映済み
- [x] user systemd の `info-collector.timer` を停止・無効化する
      → `systemctl --user disable --now info-collector.timer` 実施済み
- [x] 無効化後の運用導線が `timeline-app` 側だけで成立することを記録する
      → `info-collector.timer` は `disabled` / `inactive (dead)`、user timer 一覧からも消え、収集導線は `timeline-app` scheduler 側へ一本化した

### AI 性格設定の保持確認

- [x] `AI 性格 / 性格・話し方` の保存先と保持条件を確認する
      → 保存先は `timeline-app/config.yaml` の `ai.personality`。再起動時はここから読み込まれる
- [x] 画面から空文字で保存した場合に設定が消える条件を確認する
      → `/api/settings/ai` は空文字もそのまま保存するため、空欄のまま保存すると `config.yaml` も空で上書きされる
- [x] 指定文言 `大和なでしこでかわいらしい感じで話して` を設定へ反映する

---

## lifelog-system 移動タスク（§33）

> 前提: 単独起動導線の除去は完了済み
> 優先方針: desktop 常駐化より先に、`timeline-app` を唯一の運用入口にするための移設を完了させる
> 完了条件:
> - `lifelog-system` が `timeline-app` 配下へ移り、外部ディレクトリ参照なしで動く
> - `timeline-app` 単体で収集 / 分析 / 要約 / レポートが動く
> - Windows 主実行環境で path / subprocess / 設定ファイル参照が破綻しない
> - systemd や旧単独起動導線に依存しない

- [ ] `timeline-app/src/workers/` が `lifelog-system/src/` をインポートしている箇所を全列挙する
      → 現在は `sys.path` 操作 + `src.__path__` 拡張で対応中
- [ ] `lifelog-system/` を `timeline-app/lifelog-system/` へ移動する
- [ ] インポートパス・設定ファイル内のパス参照（`config.yaml` 等）を更新する
- [ ] `lifelog-system/pyproject.toml` の依存を `timeline-app/pyproject.toml` に統合し、`uv sync` で確認する
- [ ] 動作確認（`./scripts/start.sh` で全ワーカーが正常起動すること）
- [ ] 旧 `lifelog-system/pyproject.toml` を削除する
- [ ] Windows 移行の阻害要因を列挙して解消方針を固める
      → `root_dir`, `PYTHONPATH`, shell script, WSL 前提 path 変換, subprocess 呼び出しを対象にする
- [ ] Windows 上で `timeline-app` 単体起動が成立する条件を整理する
      → desktop 化前に「Web + worker が Windows で単独起動できる」状態を要件化する

---

# 開発 TODO（詳細版）

> 要件書: `docs/新しい開発要件`
> アーキテクチャ概要: `CLAUDE.md`
> 実装場所: `timeline-app/`

---

## ニュースフィードバック機能（2本立て）

> 背景: hourly news カードは現在 Markdown 文字列で記事を列挙するだけ。
> ユーザーが個別記事に反応できる仕組みと、その反応を将来の記事選択に活かす仕組みを別タスクとして実装する。

### N-1. 記事フィードバック UI（インタラクション層）

> 目的: hourly news カード内の各記事に対してユーザーが反応を返せるようにする。
> 既存の自動生成レポートは変更しない。

#### 設計

```
hourly news カードの各記事行
  ├── [レポート生成] ボタン
  │     → POST /api/news/articles/{id}/generate_report
  │     → Stage2（深掘り検索）+ Stage3（レポート生成）を即時実行
  │     → 完了後、生成したレポート entry をタイムラインに追加
  │     → feedback_type: "report_requested" として article_feedback に記録
  ├── [👍] ボタン
  │     → POST /api/news/articles/{id}/feedback  { type: "positive" }
  │     → article_feedback に記録（レポートは生成しない）
  └── [👎] ボタン
        → POST /api/news/articles/{id}/feedback  { type: "negative" }
        → article_feedback に記録
```

#### データ

```sql
CREATE TABLE article_feedback (
    article_id INTEGER PRIMARY KEY REFERENCES collected_info(id),
    sentiment TEXT, -- 'positive' | 'negative' | NULL
    report_status TEXT NOT NULL DEFAULT 'none', -- 'none' | 'requested' | 'running' | 'done' | 'failed'
    report_entry_id TEXT,
    updated_at TEXT NOT NULL
);
```

#### 実装ステップ

- [x] `ai_secretary.db` に `article_feedback` テーブルを追加する
      → 旧 `feedback_type / created_at` 形式から `sentiment / report_status / report_entry_id / updated_at` へ移行する
- [x] `GET /api/news/articles` エンドポイントを新規作成する
      → `related_ids` から `collected-info-{id}` を受け取り、記事詳細一覧を返す
      → レスポンスに `feedback: { sentiment, report_status, report_entry_id }` を含める
- [x] `POST /api/news/articles/{id}/feedback` エンドポイントを新規作成する
      → `{ type: "positive" | "negative" }` を受け取りトグル処理する
      → `positive` と `negative` は排他にする
- [x] `POST /api/news/articles/{id}/generate_report` エンドポイントを新規作成する
      → `sentiment = positive` と `report_status = requested` を保存する
      → バックグラウンドで Stage2+Stage3 を実行（既存の jobs を呼び出す）
      → `requested / running / done` では多重実行しない
      → 完了後、`report_status = done` と `report_entry_id` を保存する
- [x] フロントエンド: hourly news カードを展開すると記事リストが表示される UI を実装する
      → `GET /api/news/articles` を叩いて記事を取得
      → 各記事行に [レポート生成] / [👍] / [👎] ボタンを配置
      → `👍/👎` はトグル、同時点灯しない
      → レポート生成済み状態と進行状態をボタンに反映する

---

### N-2. フィードバックによる Stage1 スコアチューニング（学習層）

> 目的: N-1 で蓄積されたフィードバックを Stage1 の importance/relevance 評価に反映し、
> 将来の記事選択精度を上げる。N-1 の実装・運用後に着手する。

#### 設計

```
Stage1 実行時（analyze_pending_articles）
  ↓
article_feedback から直近 N 件の positive / negative 記事を取得
  ↓
LLM プロンプトに注入:
  「過去に良いと評価された記事の例: ...（タイトル・カテゴリ・ソース）」
  「過去に不要と評価された記事の例: ...（タイトル・カテゴリ・ソース）」
  ↓
LLM がそれを参考に importance_score / relevance_score を付ける
```

#### フィードバック集計の補助指標（任意で追加）

- ソース別 positive 率（`source_name` × feedback_type の集計）
- カテゴリ別 positive 率（`category` × feedback_type の集計）
- → Stage1 のシステムプロンプトで「このソースはユーザーが好む傾向あり」と補足する

#### 実装ステップ

- [ ] `article_feedback` からプロンプト用サマリーを生成する関数を作成する
      → `lifelog-system/src/info_collector/repository.py` に `get_feedback_summary()` を追加
      → 直近 30 件の positive / negative それぞれのタイトル・カテゴリ・ソースを取得
- [ ] `analyze_pending.py` の Stage1 プロンプトにフィードバックサマリーを注入する
      → `theme_extraction.py` のシステムプロンプトに feedback コンテキストを追加
      → フィードバックが 0 件の場合はプロンプト変更なし（既存動作を維持）
- [ ] ソース別・カテゴリ別の positive 率を `GET /api/health` または専用エンドポイントで確認できるようにする
      → デバッグ・チューニング用

---

## 分析パイプライン改善（P1）

> 背景: analysis_pipeline_worker の処理構造に起因して、レポートがタイムラインに上がってこない・
> AI サスペンドが即時反映されないという問題が確認された（2026-03-23）。
>
> ログ計測結果（2026-03-19）:
> - Stage1: 1件 ~10〜30秒（全件走らせる必要あり）
> - Stage2: 1件 ~2〜3分（DDG検索 + LLM合成、件数を limit で制御できる）
> - Stage3: 1件 ~20〜25秒（軽い）
> - Stage1 がボトルネックになるのは未処理が大量に溜まっているときだけ（通常運用では数分）

### 設計方針（確定）

```
_sync_once_blocking():
    # Stage1: 全件スコアリング（全件必須、通常は短時間）
    analyzed_articles = analyze_pending_articles(batch_size=N)

    if is_paused(): return  # ポーズチェック①

    # Stage2+3: 重要度上位 deep_limit 件だけ処理、記事ごとにループ
    top_articles = sort_by_importance(analyzed_articles)[:deep_limit]
    for article in top_articles:
        deep_research(article)          # Stage2: 1件ずつ深掘り
        generate_report(article)        # Stage3: 1件ずつレポート化（article_id で重複防止）
        if is_paused(): break           # 記事単位でポーズチェック②
```

- Stage1 は全件（`analyze_batch_size` で上限設定可）
- Stage2/3 は `deep_limit` 件（重要度上位から処理、デフォルト 5 件程度）
- ポーズは Stage1 完了後 と 各記事処理後 の2段階で効く
- レポートは article_id で一意性を保証（上書き・重複なし）

### 実装タスク

#### Step A: `generate_theme_reports` を記事単位に変更（`repository.py` + `generate_theme_report.py`）

- [x] `reports` テーブルに `source_article_id INTEGER` カラムを追加（マイグレーション）
- [x] `repository.py` に `fetch_deep_research_per_article()` を追加
      → `fetch_deep_research_by_theme` の代替。記事ごとのフラットなリストを返す
- [x] `repository.py` に `get_existing_report_article_ids() -> set[int]` を追加
      → article_id ベースの重複チェック用
- [x] `repository.py` の `save_report()` に `source_article_id` 引数を追加
- [x] `generate_theme_report.py` の `generate_theme_reports()` を記事ごとループに変更
      → ファイル名: `article_{date}_{title_slug}_{article_id}.md`（article_id で一意性保証）
      → skip チェック: `article_id in existing_report_article_ids`

#### Step B: `analysis_pipeline_worker` を記事単位ループに変更

- [x] `_sync_once_blocking` を以下の構造に変更:
      1. Stage1 全件実行 → `is_paused()` チェック
      2. 重要度上位 `deep_limit` 件をループ
         - Stage2（1件）→ Stage3（1件）→ `is_paused()` チェック
- [x] config に `deep_limit`（Stage2/3 の最大処理件数、デフォルト 5）を追加
- [x] `analyze_pending_articles` の戻り値から article_id + importance_score のリストを取得できるか確認
      → 取れない場合は DB から直接 SELECT する（`fetch_deep_research_targets` で代替済み）

#### Step C: `deep_research_articles` / `generate_theme_reports` の単体呼び出し対応

- [x] `deep_research_articles(article_ids=[id])` のように単体 ID 指定で呼べるか確認
      → `article_id: Optional[int] = None` 引数で対応済み
- [x] `generate_theme_reports(article_ids=[id])` 同様に確認・対応
      → `article_id: int | None = None` 引数で対応済み

---

## フェーズ5: M2 実用化

> 参照: 要件書 §21.2
> **方針**: UIの主役は単一タイムライン。別ページを増やさずフィルタ・ビュー切り替えで対応する。

### 5-0e. リマインダー機能（§30）

- [ ] `event` / `todo` entry に指定時刻のリマインダーを追加できるようにする
- [ ] 指定時刻になったらブラウザ通知またはトーストでリマインド
- [ ] AI プロアクティブ通知（AI から話しかける）を並行検討（§30.2）
      → VRM アシスタント（§16.1）との連携も視野に

### 5-1. タイムライン実用強化

- [x] 右ペインの種別変更をボタン一覧からドロップダウン選択に変更する
      → `detail-quick-type-select` としてドロップダウン実装済み（アンドゥ機能付き）
- [x] フィルター UI をメニュー（折り畳みパネルやドロワー）に移動する
      → タイムライン上部のフィルター行をコンパクトにまとめ、メニューアイコンで開閉する
      → 今回はこのタスクを先に対応する
      → 種別フィルタの複数選択ドロップダウン化、未完了TODO/AI表示トグルの同居、右ペイン種別変更UIの整理までを同時に見る
      → 検索・日付ジャンプもメニュー内へ移し、上部常設には開閉ボタンと要約のみ残す構成にした
- [x] ワークスペースの「開くボタン」とパス入力欄を削除する
      → 設定ページから操作できれば十分。起動時に config.yaml のパスを自動適用する形に整理する
- [x] 種別フィルタをボタン方式から複数選択可能なドロップダウン/チェックリスト形式に変更する
      → 単一選択ボタン列を廃止し、複数種別を同時に選べる形にする（例: ポップオーバー内チェックボックス）
- [x] 無限スクロールの動作を改善する（NOW 中心・両方向読み込み）
      → 初回表示は NOW を中心とした一定範囲のみ読み込み、上スクロールで未来・下スクロールで過去をそれぞれ追加読み込みする
      → フィルターUI整理後に着手し、raw配列保持・around基準の再振り分け・id重複整理まで含めて対応する

### 5-2. AI記録UIの安全装置

> 要件書 §24.1

- [ ] ピン留め（重要な entry をタイムライン上で固定表示）
- [ ] インボックス（未整理 entry の一時置き場。タイムライン上で未確定として表示）
- [ ] 会話スレッドの右ペイン表示（元会話・関連 entry の参照）（要件書 §4.3, §14.1, §7.3）

### 5-3. Markdown 自動取り込み

- [ ] ワークスペース内の Markdown ファイル変更をファイル監視で検知する（要件書 §12.3）
- [ ] 新規・更新 Markdown を `imported` 種別の entry としてタイムラインへ流入させる
- [ ] 取り込み対象フォルダを設定可能にする

### 5-4. 設定ページ

- [x] AI 性格・System Prompt 設定（要件書 §15.4）
- [x] Ollama 接続設定（ベースURL・モデル名・タイムアウト）（要件書 §17.1）
- [x] RSS フィード登録（要件書 §17.1）
- [x] AI 処理 ON/OFF の設定ページ対応（要件書 §15.5）
      → Worker 単位の ON/OFF チェックボックスとして設定ページに実装済み
- [ ] Big Five フィードバックの有効/無効（要件書 §17.1）

### 5-5. カレンダービュー

- [ ] 日/週単位のカレンダービューをタイムラインの別ビューとして追加する（要件書 §5.6）
      → 別ページではなくビュー切り替え式にする
- [ ] カレンダー上での予定作成 → タイムライン未来側にも反映される

---

### 5-6. メモ機能・右ペイン拡張

> 要件書 §28

#### [[タイトル]] 記法によるメモ作成（§28.1）

- [ ] チャット入力欄で `[[タイトル]]` パターンを検出するパーサを実装する
      → 正規表現 `\[\[(.+?)\]\]` でタイトル抽出
- [ ] `POST /api/memo` エンドポイントを新規作成する
      → `articles/{タイトル}.md` の存在チェック（既存なら右ペインを開くだけ）
      → 新規の場合は Ollama に章立て・概要の生成を依頼
- [ ] 生成テキストを YAML frontmatter 付きで `articles/{タイトル}.md` に保存する
- [ ] `type: memo` の entry をタイムラインに追加し、右ペインを編集モードで開く

#### 右ペイン AI 編集機能（§28.2）

- [x] 右ペインの閲覧モードに「AI に投げる」ボタンを追加する
- [x] ボタン押下で本文の上/下に指示入力欄（textarea）を展開する
- [x] `POST /api/entries/{id}/ai_edit` エンドポイントを新規作成する
      → リクエスト: `{ "instruction": "..." }`
      → Ollama に「現在の content + instruction」を渡して編集済み全文を返させる
- [x] 編集結果を右ペインにプレビュー表示し、「保存」「キャンセル」で確定/破棄する
- [x] 編集リクエスト前に `articles/{id}.bak.md` へバックアップを取る
      → 保存/キャンセル時にバックアップを削除する

#### 右ペインでのチャット継続（§28.3）

- [x] entry の type が `chat` / `chat_ai` の場合、右ペインに会話履歴を Markdown 描画で表示する
- [x] 右ペイン下部にチャット入力欄と送信ボタンを追加する（非チャット型 entry には表示しない）
- [x] 送信時に `POST /api/chat` へ既存の `thread_id` を渡してスレッドを継続する
- [x] `POST /api/entries/{id}/append_message` エンドポイントを新規作成する
      → 末尾追記方式で `articles/{id}.md` にメッセージを保存する（競合・破損リスク低減）
- [x] AI 応答が返り次第、右ペイン下部に即時追記表示する（ポーリングまたは SSE）

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
> 着手条件:
> - `lifelog-system` の `timeline-app` 配下移設が完了している
> - Windows 主実行環境で `timeline-app` 単体運用が成立している
> - 常駐対象の起動点が `timeline-app` に一本化されている

- [ ] desktop 版: pywebview で Web フロントを包む最小実装（要件書 §21.1.5）
- [ ] desktop 常駐・バックグラウンド起動（要件書 §19.3）
- [ ] スタートアップ登録・自動起動（要件書 §19.3）
- [ ] トレイアイコン・OS 通知（要件書 §21.4）
- [ ] VRM アシスタント表示（口パク・状態表示）（要件書 §16.1）
- [ ] 音声入力 / 音声出力（要件書 §16.2）
