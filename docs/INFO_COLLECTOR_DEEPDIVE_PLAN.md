# 能動的情報収集・深掘り計画（Ollama+DDG前提）

## 目的
RSS/ニュース/検索で収集した記事を、Ollamaで重要度判定・興味関連付け・深掘り検索・レポート化まで自動で進める。

## システム構成（実装済み）
1. **分析ステップ（実装済み）**
   - DB: `article_analysis` テーブル（importance_score, relevance_score, category, keywords(json), summary, model, analyzed_at）
   - ジョブ: 収集済みで未分析の記事に対し、Ollamaでスコアリング＆1行要約。失敗時はフォールバック要約。
   - モジュール: `src.info_collector.jobs.analyze_pending`
   - プロンプト: `prompts/theme_extraction.py`

2. **深掘り検索ステップ（実装済み）**
   - DB: `deep_research` テーブル（article_id, search_query, search_results(json), synthesized_content, sources(json), researched_at）
   - ジョブ: 重要度・関連度が高い記事について、DDG検索→Ollamaで統合要約。
   - モジュール: `src.info_collector.jobs.deep_research`
   - プロンプト: `prompts/search_query_gen.py`, `prompts/result_synthesis.py`

3. **レポート生成（実装済み）**
   - DB: `reports` テーブル（title, report_date, content(md), article_count, category, created_at）
   - ジョブ: 直近の分析・深掘り済み記事から日次/カテゴリ別のMarkdownレポートをOllamaで生成・保存（`data/reports/`に出力）。
   - モジュール: `src.info_collector.jobs.generate_report`
   - プロンプト: `prompts/report_generation.py`

4. **統合パイプライン（実装済み）**
   - スクリプト: `scripts/info_collector/integrated_pipeline.sh`
   - 機能: 分析→深掘り→レポート を連続実行
   - 利点: 一貫性のある情報処理、エラーハンドリング、ログ管理

5. **スケジューリング（実装済み）**
   - 各処理段階に対応するsystemdユニットが実装されています。
   - 各ジョブは短時間/少数バッチで失敗に強くする（未処理のみ対象）。

## 技術スタック・前提
- 検索: `duckduckgo-search` (現行のDDG)
- LLM: ローカルOllama (`ollama_client.generate`)。Claude等に差し替えたい場合はクライアント差し替えで吸収
- DB: 現行 `collected_info` に追加テーブルを足す。WAL/外部キーONは維持
- DBパス: `data/ai_secretary.db` (デフォルト)
- レポート出力先: `data/reports/` (Markdownファイル)

## ディレクトリ構造
```
lifelog-system/
├── src/info_collector/
│   ├── jobs/
│   │   ├── analyze_pending.py      # 記事分析ジョブ
│   │   ├── deep_research.py        # 深掘り調査ジョブ
│   │   └── generate_report.py      # レポート生成ジョブ
│   ├── prompts/
│   │   ├── theme_extraction.py     # 記事分析プロンプト
│   │   ├── search_query_gen.py     # 検索クエリ生成プロンプト
│   │   ├── result_synthesis.py     # 結果統合プロンプト
│   │   └── report_generation.py    # レポート生成プロンプト
│   ├── collectors/                 # データ収集器
│   ├── search/
│   │   └── ddg_client.py          # DuckDuckGo検索クライアント
│   ├── models.py                  # データモデル
│   └── repository.py              # データベースアクセス層
├── data/
│   ├── ai_secretary.db            # SQLiteデータベース
│   └── reports/                   # 生成されたレポート
├── logs/info_collector/           # ジョブ実行ログ
└── scripts/info_collector/
    ├── analyze_articles.sh        # 分析実行スクリプト
    ├── deep_research.sh           # 深掘り実行スクリプト
    ├── generate_report.sh         # レポート生成スクリプト
    ├── integrated_pipeline.sh     # 統合パイプライン
    ├── auto_collect.sh            # 自動収集
    ├── collect_news.sh            # ニュース収集
    ├── collect_rss.sh             # RSS収集
    └── search_web.sh              # Web検索
```

## データベーススキーマ（実装済み）
```sql
CREATE TABLE article_analysis (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id INTEGER NOT NULL UNIQUE,
  importance_score REAL,
  relevance_score REAL,
  category TEXT,
  keywords TEXT,          -- JSON array
  summary TEXT,           -- 1行要約
  model TEXT,
  analyzed_at TEXT NOT NULL,
  FOREIGN KEY(article_id) REFERENCES collected_info(id)
);

CREATE INDEX idx_analysis_scores ON article_analysis(importance_score DESC, relevance_score DESC);
CREATE INDEX idx_analysis_date ON article_analysis(analyzed_at DESC);

CREATE TABLE deep_research (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id INTEGER NOT NULL UNIQUE,
  search_query TEXT NOT NULL,
  search_results TEXT NOT NULL, -- JSON
  synthesized_content TEXT,
  sources TEXT,                 -- JSON array of URLs
  researched_at TEXT NOT NULL,
  FOREIGN KEY(article_id) REFERENCES collected_info(id)
);

CREATE INDEX idx_research_date ON deep_research(researched_at DESC);

CREATE TABLE reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  report_date TEXT NOT NULL,
  content TEXT NOT NULL,   -- Markdown
  article_count INTEGER,
  category TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_reports_date ON reports(report_date DESC);
```

## プロンプトモジュール（実装済み）
各処理段階で使用するプロンプトモジュールが実装されています：

1. **theme_extraction.py** - 記事分析用
   - 記事のタイトル・本文から重要度・関連度・カテゴリ・キーワード・1行要約を抽出
   - 使用箇所: `jobs/analyze_pending.py`

2. **search_query_gen.py** - 検索クエリ生成用
   - テーマ・キーワード・カテゴリから深掘り検索用のクエリを生成
   - 使用箇所: `jobs/deep_research.py`

3. **result_synthesis.py** - 検索結果統合用
   - 複数の検索結果から詳細な要約と参照元リストを生成
   - 使用箇所: `jobs/deep_research.py`

4. **report_generation.py** - レポート生成用
   - 分析済み記事と深掘り結果から日次レポート（Markdown形式）を生成
   - 使用箇所: `jobs/generate_report.py`

## 実行フロー（実装済み）
1. 収集（既存）: `auto_collect` → `collected_info` に保存。
2. 分析: `analyze_pending` が未分析の記事をバッチ処理→`article_analysis` へ。
3. 深掘り: `deep_research` が「重要」と判定された記事のみDDG検索→Ollama統合→`deep_research`。
4. レポート: `generate_report` が最新の分析/深掘り結果から日次レポート生成→`reports`。
5. **統合パイプライン**: 上記2-4を1つのスクリプトで連続実行（`integrated_pipeline.sh`）。

## 実行方法

### Pythonモジュール直接実行
```bash
cd lifelog-system

# 分析
uv run python -m src.info_collector.jobs.analyze_pending --batch-size 10

# 深掘り
uv run python -m src.info_collector.jobs.deep_research --batch-size 5 --min-importance 0.7 --min-relevance 0.6

# レポート生成
uv run python -m src.info_collector.jobs.generate_report --hours 24
```

### シェルスクリプト経由（推奨）
```bash
# 分析
./scripts/info_collector/analyze_articles.sh --batch-size 30

# 深掘り
./scripts/info_collector/deep_research.sh --batch-size 3 --min-importance 0.0 --min-relevance 0.0

# レポート生成
./scripts/info_collector/generate_report.sh --hours 24

# 統合パイプライン（分析→深掘り→レポート）
./scripts/info_collector/integrated_pipeline.sh \
  --analyze-batch-size 30 \
  --deep-batch-size 3 \
  --deep-min-importance 0.0 \
  --deep-min-relevance 0.0 \
  --report-hours 1
```

### その他の収集スクリプト
```bash
# ニュース収集
./scripts/info_collector/collect_news.sh

# RSS収集
./scripts/info_collector/collect_rss.sh

# Web検索
./scripts/info_collector/search_web.sh

# 自動収集（ニュース+RSS+検索）
./scripts/info_collector/auto_collect.sh
```

## エラーハンドリング/フォールバック（実装済み）

### 分析ジョブ（analyze_pending）
- **Ollama失敗時のフォールバック値:**
  - `importance_score`: 0.3
  - `relevance_score`: 0.3
  - `category`: "その他"
  - `keywords`: []
  - `summary`: タイトルの最初の50文字
  - `model`: "fallback"
- **再試行**: フォールバック値で保存するため、再分析は手動で実行

### 深掘りジョブ（deep_research）
- **検索クエリ生成失敗**: その記事をスキップし、次の記事へ
- **DDG検索失敗**: その記事をスキップし、次の記事へ（再試行可能）
- **結果統合失敗**: 空の統合結果として保存

### レポート生成（generate_report）
- **LLM失敗時**: エラーメッセージを含むフォールバックMarkdownを生成・保存

### 共通設計
- **バッチサイズ**: 小さく保ち（デフォルト: 分析10-30件、深掘り3-5件）、ジョブ再実行で未処理のみ対象
- **ログ記録**: すべてのエラーをログファイルに記録（`logs/info_collector/`）
- **ロールバック**: 各ジョブは独立しており、失敗しても他のジョブに影響しない

## systemdユニット（実装済み）

### データ収集
- **info-collector.service** / **info-collector.timer**
  - データ収集（ニュース・RSS・検索）を実行

### 分析・深掘り・レポート（個別実行）
- **info-analyze.service** / **info-analyze.timer**
  - 未分析記事の分析を実行

- **info-deep.service** / **info-deep.timer**
  - 重要記事の深掘り調査を実行

- **info-report.service** / **info-report.timer**
  - レポート生成を実行

### 統合パイプライン（推奨）
- **info-integrated.service** / **info-integrated.timer**
  - 分析→深掘り→レポート を連続実行
  - 実行頻度: **30分ごと** (`OnCalendar=*:0/30`)
  - 統合的な処理により、一貫性のある情報処理を実現

### systemdユニットの操作
```bash
# タイマー有効化
sudo systemctl enable --now info-integrated.timer

# 状態確認
sudo systemctl status info-integrated.timer
sudo systemctl status info-integrated.service

# 手動実行
sudo systemctl start info-integrated.service

# ログ確認
sudo journalctl -u info-integrated.service -f
```

## テスト方針

### ユニットテスト
- プロンプト生成ロジックのテスト
- レスポンスパース処理のテスト
- フォールバック値の検証
- Ollamaクライアントはモック化

### 統合テスト
- 軽量テスト用DBを使用
- 収集済みモックデータ → 分析 → 深掘り → レポート生成の全フローを検証
- エラーハンドリングの動作確認

### システムテスト
- systemdユニットの手動実行テスト
- タイマーの動作確認
- ログファイルの出力確認
- レポートファイルの生成確認

### 手動テスト例
```bash
# 1. データ収集（テストデータ作成）
./scripts/info_collector/auto_collect.sh

# 2. 分析実行
./scripts/info_collector/analyze_articles.sh --batch-size 5

# 3. 深掘り実行
./scripts/info_collector/deep_research.sh --batch-size 2

# 4. レポート生成
./scripts/info_collector/generate_report.sh --hours 24

# 5. 統合パイプライン
./scripts/info_collector/integrated_pipeline.sh

# 6. 結果確認
ls -lh data/reports/
sqlite3 data/ai_secretary.db "SELECT COUNT(*) FROM article_analysis;"
sqlite3 data/ai_secretary.db "SELECT COUNT(*) FROM deep_research;"
sqlite3 data/ai_secretary.db "SELECT COUNT(*) FROM reports;"
```

## 運用時の注意点

### パフォーマンスとリソース管理
- **Ollamaの起動確認**: ジョブ実行前にOllamaサービスが起動していることを確認
- **メモリ使用量**: LLM処理は大量のメモリを使用するため、同時実行数を制限
- **DDG検索のレート制限**: 検索クエリ間に適切な遅延（デフォルト1.5秒）を設定

### データベースメンテナンス
- **定期的なVACUUM**: SQLiteのパフォーマンス維持のため、定期的にVACUUMを実行
- **古いデータの削除**: `collected_info`の古いレコードを定期削除（30日以上など）
- **バックアップ**: 重要なレポートやデータベースは定期的にバックアップ

### ログ管理
- **ログローテーション**: `logs/info_collector/`のログファイルが肥大化しないよう管理
- **エラー監視**: 定期的にログを確認し、繰り返されるエラーに対処

### 統合パイプライン vs 個別実行
- **推奨**: 統合パイプライン（`info-integrated.timer`）を使用
- **個別実行が有用な場合**:
  - 特定のステップのみを再実行したい場合
  - パラメータを調整してテストする場合
  - トラブルシューティング時

### トラブルシューティング
```bash
# Ollamaの状態確認
systemctl status ollama

# ジョブのログ確認
tail -f logs/info_collector/integrated_pipeline_$(date +%Y%m%d).log

# データベースの整合性チェック
sqlite3 data/ai_secretary.db "PRAGMA integrity_check;"

# 未処理の記事を確認
sqlite3 data/ai_secretary.db "
SELECT COUNT(*) FROM collected_info c
LEFT JOIN article_analysis a ON c.id = a.article_id
WHERE a.id IS NULL;
"
```

## 今後の拡張計画（TODO）

### TODO 1: ユーザー興味プロファイルの学習
**目的**: 分析結果を基に、ユーザーの興味・関心をプロファイリングし、より精度の高い重要度判定を実現

**実装内容**:
- `user_interests` テーブルの追加（category, keywords, weight, last_updated）
- 過去の分析結果から興味カテゴリ・キーワードの重みを自動学習
- 学習したプロファイルを分析ジョブのプロンプトに反映
- ユーザーフィードバック機能（重要/不要のマーク）

**期待効果**:
- 個人に最適化された記事スコアリング
- 深掘り対象の精度向上
- レポートの質の向上

### TODO 2: 外部LLM API対応（Claude/GPT等）
**目的**: ローカルOllama以外のLLM APIをサポートし、より高品質な分析・要約を可能にする

**実装内容**:
- `src/info_collector/llm/` ディレクトリを追加
- 抽象基底クラス `BaseLLMClient` を定義
- `ClaudeClient`, `OpenAIClient`, `OllamaClient` の実装
- 設定ファイルでLLMプロバイダーを選択可能に
- コスト管理機能（API使用量の追跡）

**期待効果**:
- 分析・要約の品質向上
- 用途に応じたLLMの使い分け（高品質/低コスト/ローカル）
- 外部API障害時のフォールバック

### TODO 3: Web UIでのレポート閲覧・管理
**目的**: Markdownレポートをブラウザで快適に閲覧・管理できるWebインターフェースを提供

**実装内容**:
- FastAPI/Flaskベースの軽量Webサーバー
- レポート一覧・検索・フィルタリング機能
- Markdown→HTMLレンダリング（構文ハイライト付き）
- 記事の詳細表示（元記事へのリンク、深掘り結果の表示）
- お気に入り/アーカイブ機能
- レスポンシブデザイン（モバイル対応）

**期待効果**:
- レポートの可読性・アクセス性向上
- 過去のレポートの振り返りが容易に
- ユーザーエクスペリエンスの向上

### TODO 4: 記事単位のレポート生成
**現状の問題**: 現在のレポートは日付別に生成されており、個別記事の詳細な深掘り結果を確認しにくい

**目的**: 重要記事ごとに独立したレポートを生成し、深掘り結果を体系的に整理

**実装内容**:
- `article_reports` テーブルの追加（article_id, report_type, content, created_at）
- 記事単位のレポート生成ジョブ（`generate_article_report.py`）
- レポートテンプレート:
  - 記事の基本情報（タイトル、URL、公開日、ソース）
  - 分析結果（重要度、関連度、カテゴリ、キーワード）
  - 深掘り調査結果（検索クエリ、統合された詳細情報、参照元リスト）
  - 関連記事の自動リンク
- 日次レポートは「記事一覧＋リンク」のサマリー形式に変更

**達成基準**:
- [ ] 深掘りされた記事1件につき、独立したMarkdownレポートが `data/reports/articles/` に生成される
- [ ] レポートファイル名: `article_{article_id}_{YYYYMMDD}.md`
- [ ] 各レポートに以下のセクションが含まれる:
  - [ ] 記事メタデータ（タイトル、URL、公開日時、収集日時、ソース名）
  - [ ] 分析スコア（重要度、関連度、カテゴリ、抽出キーワード）
  - [ ] 深掘り調査（検索クエリ、統合要約、参照元URL一覧）
  - [ ] 関連記事（同カテゴリ・同キーワードの記事3-5件）
- [ ] 日次レポートは記事リストとリンクのみに簡素化される
- [ ] 記事レポート生成は深掘り完了後に自動実行される

### TODO 5: ライフログデータの日付整合性の修正
**現状の問題**:
- 違う日付の情報が混在している可能性がある
- データ収集時刻とイベント発生時刻の区別が不明瞭

**目的**: 各ライフログイベントの発生日時を正確に記録し、日付範囲クエリが正確に動作するようにする

**実装内容**:
- `collected_info` テーブルのスキーマ検証:
  - `published_at`: 記事の公開日時（元ソースのタイムスタンプ）
  - `fetched_at`: データ収集実行日時（システムのタイムスタンプ）
- 日付フィルタリングロジックの統一:
  - 分析・深掘り・レポート生成で一貫して `published_at` を使用
  - `published_at` が NULL の場合は `fetched_at` をフォールバック
- タイムゾーン処理の統一（UTC/ローカル時刻の明確化）
- データ検証ジョブの追加（日付の整合性チェック）

**達成基準**:
- [ ] すべての `collected_info` レコードで `published_at` または `fetched_at` が設定されている（NULL なし）
- [ ] 日付範囲クエリ（例: 2025-11-29 00:00～23:59）で正確にその日の記事のみが抽出される
- [ ] 以下のSQLで不整合がゼロ件:
```sql
-- 未来日付のチェック
SELECT COUNT(*) FROM collected_info
WHERE published_at > datetime('now') OR fetched_at > datetime('now');

-- published_at と fetched_at の逆転チェック
SELECT COUNT(*) FROM collected_info
WHERE published_at IS NOT NULL
  AND fetched_at IS NOT NULL
  AND published_at > fetched_at;
```
- [ ] タイムゾーン情報がドキュメント化されている（UTCまたはローカル時刻）
- [ ] データ検証スクリプト（`scripts/info_collector/validate_data.sh`）が実装され、定期実行される

### TODO 6: Windows活動ログとブラウザ履歴の統合強化
**現状の問題**:
- Windowsフォアグラウンドウィンドウ情報が適切に含まれていない
- ブラウザ履歴情報が十分でない
- ライフログと情報収集が分離されており、コンテキスト情報が活用されていない

**目的**: ユーザーの活動コンテキスト（作業中のアプリ、閲覧したページ）を記事分析に活用し、関連度スコアの精度を向上

**実装内容**:
- **Windowsログ統合**:
  - `logs/windows_foreground.jsonl` のパース処理を追加
  - アプリケーション使用統計の集計（カテゴリ別の使用時間）
  - 記事分析時に関連アプリ（ブラウザ、エディタ、Office等）の使用状況を参照

- **ブラウザ履歴統合**:
  - `browser_history` テーブルの拡張（visited_at, title, url, visit_count）
  - 記事URLとブラウザ履歴のマッチング（訪問済み記事は関連度を加算）
  - 閲覧時間が長いドメイン/カテゴリを興味プロファイルに反映

- **コンテキスト情報の活用**:
  - 記事収集時刻の前後1時間の活動ログを抽出
  - 作業中のアプリ・閲覧中のサイトと記事カテゴリの関連性を分析
  - プロンプトに「最近の活動: {コンテキスト情報}」を追加

**達成基準**:
- [ ] Windowsフォアグラウンドログが正常にパースされ、以下の情報が抽出される:
  - [ ] アプリケーション名
  - [ ] ウィンドウタイトル（ハッシュ化/平文を privacy.yaml で制御）
  - [ ] タイムスタンプ
  - [ ] 使用時間（秒単位）
- [ ] 以下のSQLで直近24時間のアプリ使用統計が取得できる:
```sql
SELECT app_name, SUM(duration_seconds) as total_time
FROM windows_activity
WHERE timestamp >= datetime('now', '-24 hours')
GROUP BY app_name
ORDER BY total_time DESC
LIMIT 10;
```
- [ ] ブラウザ履歴データが `browser_history` テーブルに保存され、以下が確認できる:
  - [ ] 直近7日間の訪問URL件数が100件以上
  - [ ] タイムスタンプが正確（UTC/ローカル時刻の明確化）
  - [ ] visit_count が正常に集計されている
- [ ] 記事分析時に以下の情報がプロンプトに含まれる:
  - [ ] 記事収集時刻の前後1時間の主要なアプリ使用情報
  - [ ] 同時刻帯に閲覧していたサイトのドメイン/カテゴリ
- [ ] コンテキスト情報を活用した分析により、関連度スコアの精度が向上する:
  - [ ] テストケース: エディタでコード編集中に収集された技術記事の関連度が +0.2 以上向上
  - [ ] テストケース: 無関係なアプリ使用中の記事は関連度が変化しない（ノイズにならない）

---

**優先順位**: TODO 5 → TODO 6 → TODO 4 → TODO 1 → TODO 3 → TODO 2

**理由**: データの正確性（TODO 5）→ コンテキスト統合（TODO 6）→ レポート形式改善（TODO 4）→ 学習機能（TODO 1）→ UI（TODO 3）→ 外部LLM（TODO 2）の順で、基盤から順に改善
