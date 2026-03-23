## 運用ルール
1. タスクを追加するときはチェックボックス形式で書く
2. 完了したら `[x]` にする
3. セクションが全て完了したら、セクションごと削除してよい

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

---

## lifelog-system 移動タスク（§33）

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

- [ ] `reports` テーブルに `source_article_id INTEGER` カラムを追加（マイグレーション）
- [ ] `repository.py` に `fetch_deep_research_per_article()` を追加
      → `fetch_deep_research_by_theme` の代替。記事ごとのフラットなリストを返す
- [ ] `repository.py` に `get_existing_report_article_ids() -> set[int]` を追加
      → article_id ベースの重複チェック用
- [ ] `repository.py` の `save_report()` に `source_article_id` 引数を追加
- [ ] `generate_theme_report.py` の `generate_theme_reports()` を記事ごとループに変更
      → ファイル名: `article_{date}_{title_slug}_{article_id}.md`（article_id で一意性保証）
      → skip チェック: `article_id in existing_report_article_ids`

#### Step B: `analysis_pipeline_worker` を記事単位ループに変更

- [ ] `_sync_once_blocking` を以下の構造に変更:
      1. Stage1 全件実行 → `is_paused()` チェック
      2. 重要度上位 `deep_limit` 件をループ
         - Stage2（1件）→ Stage3（1件）→ `is_paused()` チェック
- [ ] config に `deep_limit`（Stage2/3 の最大処理件数、デフォルト 5）を追加
- [ ] `analyze_pending_articles` の戻り値から article_id + importance_score のリストを取得できるか確認
      → 取れない場合は DB から直接 SELECT する

#### Step C: `deep_research_articles` / `generate_theme_reports` の単体呼び出し対応

- [ ] `deep_research_articles(article_ids=[id])` のように単体 ID 指定で呼べるか確認
      → 対応していなければ引数を追加
- [ ] `generate_theme_reports(article_ids=[id])` 同様に確認・対応

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
- [ ] ワークスペースの「開くボタン」とパス入力欄を削除する
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
