# Viewer Service - 統合ビューサービス

ライフログ、ブラウザ履歴、外部情報（info_collector）を統合して表示するWebサービスです。

## 概要

- **バックエンド**: FastAPI
- **フロントエンド**: HTML + htmx (軽量・高速)
- **データソース**:
  - `data/lifelog.db` - ライフログデータ
  - `data/ai_secretary.db` - ブラウザ履歴 + 外部情報
- **モード**: 読み取り専用（PRAGMA query_only = ON）

## クイックスタート

### 1. 起動

```bash
# プロジェクトルートから
./scripts/viewer_service.sh start

# または lifelog-system から直接
cd lifelog-system
uv run python -m src.viewer_service.main
```

デフォルト設定:
- **URL**: http://127.0.0.1:8787
- **Host**: 127.0.0.1（ローカルのみ）
- **Port**: 8787

### 2. ブラウザでアクセス

```
http://127.0.0.1:8787
```

統合ダッシュボードが表示されます。

### 3. 停止

```bash
./scripts/viewer_service.sh stop
```

## カスタマイズ

### 環境変数

```bash
# カスタムポートで起動
VIEWER_PORT=9000 ./scripts/viewer_service.sh start

# カスタムDBパス
LIFELOG_DB=/path/to/lifelog.db \
INFO_DB=/path/to/ai_secretary.db \
./scripts/viewer_service.sh start
```

### コマンドライン引数

```bash
uv run python -m src.viewer_service.main \
    --host 127.0.0.1 \
    --port 8787 \
    --lifelog-db data/lifelog.db \
    --info-db data/ai_secretary.db
```

## API エンドポイント

すべてGET、読み取り専用です。

### ヘルスチェック

```
GET /api/health
```

### ダッシュボード（統合データ）

```
GET /api/dashboard?date=2025-11-28&limit=5&hours=6&full=false
```

パラメータ:
- `date`: 日付 (YYYY-MM-DD) - デフォルト: 今日
- `limit`: 各カテゴリの取得件数 (1-100) - デフォルト: 5
- `hours`: 遡る時間数 (1-168) - デフォルト: 6
- `full`: 全文取得フラグ - デフォルト: false

### ライフログ

```
GET /api/lifelog/summary?date=2025-11-28
GET /api/lifelog/timeline?hours=6
GET /api/lifelog/health?hours=24
```

### ブラウザ履歴

```
GET /api/browser/recent?date=2025-11-28&limit=20
GET /api/browser/search?q=keyword&limit=50
```

### 外部情報（info_collector）

```
GET /api/info/latest?source=all&date=2025-11-28&limit=10&full=false
GET /api/info/news?limit=20
GET /api/info/reports?limit=5
```

## アーキテクチャ

```
src/viewer_service/
├── __init__.py
├── config.py              # 設定管理
├── models.py              # Pydantic DTOモデル
├── main.py                # FastAPIアプリケーション
├── api/
│   ├── __init__.py
│   └── routes.py          # APIルート定義
├── queries/
│   ├── __init__.py
│   ├── lifelog_queries.py    # ライフログクエリ
│   ├── browser_queries.py    # ブラウザクエリ
│   ├── info_queries.py       # info_collectorクエリ
│   └── dashboard_queries.py  # 統合クエリ
├── templates/
│   └── dashboard.html        # Webダッシュボード
└── static/                   # 静的ファイル（CSS/JS等）
```

### データフロー

1. **ブラウザ** → `/api/dashboard` リクエスト
2. **FastAPI** → `dashboard_queries.get_dashboard_data()`
3. **Query Layer** → 各DBから読み取り（lifelog_queries, browser_queries, info_queries）
4. **DTO変換** → Pydantic モデルでJSON化
5. **レスポンス** → ブラウザで htmx がレンダリング

## セキュリティ

- **ローカルバインドのみ**: デフォルトで 127.0.0.1 にバインド
- **読み取り専用**: `PRAGMA query_only = ON` でDB変更不可
- **CORS設定**: localhost のみ許可

## パフォーマンス

- **読み取り専用接続**: WALロックの影響を回避
- **ページング**: limit パラメータで過大レスポンスを防止
- **長文フィールド制限**: デフォルトで頭数百文字、`full=true` で全量

## トラブルシューティング

### ポートが使用中

```bash
# カスタムポート使用
VIEWER_PORT=9000 ./scripts/viewer_service.sh start
```

### DBファイルが見つからない

```bash
# DBパスを確認
ls -la lifelog-system/data/

# カスタムパス指定
LIFELOG_DB=/path/to/lifelog.db ./scripts/viewer_service.sh start
```

### 依存関係エラー

```bash
cd lifelog-system
uv sync
```

## 今後の拡張

- [ ] エクスポート機能（CSV, JSON）
- [ ] グラフ・チャート表示
- [ ] リアルタイム更新（WebSocket）
- [ ] フィルタリング・検索機能強化
- [ ] テーマカスタマイズ

## 開発

### 開発モード起動（ホットリロード）

```bash
uv run python -m src.viewer_service.main --reload
```

### テスト

```bash
cd lifelog-system
uv run pytest tests/test_viewer_service.py -v
```
