# 能動的情報収集・深掘り計画（Ollama+DDG前提）

## 目的
RSS/ニュース/検索で収集した記事を、Ollamaで重要度判定・興味関連付け・深掘り検索・レポート化まで自動で進める。

## 進め方（フェーズとアウトプット）
1. **分析ステップの追加（最小実装）**
   - DB: `article_analysis` テーブルを追加（importance_score, relevance_score, category, keywords(json), summary, model, analyzed_at）。
   - ジョブ: 収集済みで未分析の記事に対し、Ollamaでスコアリング＆1行要約。失敗時はフォールバック要約。
   - CLI/ジョブ: `uv run python -m src.info_collector.analyze_pending` を新設。
2. **深掘り検索ステップ**
   - DB: `deep_research` テーブルを追加（article_id, search_query, search_results(json), synthesized_content, sources(json), researched_at）。
   - ジョブ: `should_deep_research` となった記事について、DDG検索→Ollamaで統合要約。  
   - CLI/ジョブ: `uv run python -m src.info_collector.deep_research` を新設。
3. **レポート生成**
   - DB: `reports` テーブルを追加（title, report_date, content(md), article_count, category, created_at）。
   - ジョブ: 直近の分析・深掘り済み記事から日次/カテゴリ別のMarkdownレポートをOllamaで生成・保存。
   - CLI: `uv run python -m src.info_collector.generate_report --period daily`。
4. **スケジューリング**
   - 既存 `info-collector.timer` は「収集」のみ。分析・深掘りを別タイマーに分割（例: `info-analyze.timer` hourly, `info-deep.timer` 2–3時間ごと）。
   - 各ジョブは短時間/少数バッチで失敗に強くする（未処理のみ対象）。

## 技術スタック・前提
- 検索: `duckduckgo-search` (現行のDDG)。
- LLM: ローカルOllama (`ollama_client.generate`)。Claude等に差し替えたい場合はクライアント差し替えで吸収。
- DB: 現行 `collected_info` に追加テーブルを足す。WAL/外部キーONは維持。

## スキーマ追加案（SQLite）
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

CREATE TABLE reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  report_date TEXT NOT NULL,
  content TEXT NOT NULL,   -- Markdown
  article_count INTEGER,
  category TEXT,
  created_at TEXT NOT NULL
);
```

## 実行フロー（想定）
1. 収集（既存）: `auto_collect` → `collected_info` に保存。
2. 分析: `analyze_pending` が未分析の記事をバッチ処理→`article_analysis` へ。
3. 深掘り: `deep_research` が「重要」と判定された記事のみDDG検索→Ollama統合→`deep_research`。
4. レポート: `generate_report` が最新の分析/深掘り結果から日次レポート生成→`reports`。

## エラーハンドリング/フォールバック
- Ollama失敗: スコアはデフォルト低め、summaryはフォールバックテンプレートで埋める。
- DDG失敗: 深掘りはスキップし、再トライ可能なフラグを残す。
- バッチサイズ: 小さく保ち、ジョブ再実行で再処理できる設計（WHERE句で未処理のみ）。

## テスト方針
- ユニット: プロンプト生成/レスポンスパース/フォールバックの単体テスト（Ollamaはモック）。
- 統合（軽量DB）: 収集済みモックデータ→分析→深掘りまでのフローを1ケースだけ通す。
- タイマー: systemdユニットは手動実行テストで確認。
