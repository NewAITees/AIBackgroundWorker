# AIBackgroundWorker Desktop Viewer

システムトレイ常駐型のデスクトップアプリケーション。バックグラウンドで記録されたライフログ、ブラウザ履歴、ニュース、レポートを気軽に確認できます。

## 特徴

- ✨ **システムトレイ常駐**: ウィンドウを閉じても動作継続
- 📊 **統合ダッシュボード**: すべてのデータを一画面で確認
- 🔄 **自動更新**: 定期的に最新データを自動取得（デフォルト: 5分ごと）
- 🔔 **デスクトップ通知**: 重要なイベントを通知
- 🌗 **ダークモード対応**: システム設定に追従
- ⚙️ **カスタマイズ可能**: 更新間隔、通知設定などを変更可能

## 技術スタック

- **Electron**: v28.0.0
- **Node.js**: v18以上推奨
- **Backend API**: viewer_service（FastAPI）

## 必要要件

### 前提条件

1. **Node.js**: v18以上
2. **npm**: v9以上
3. **viewer_service**: FastAPIサーバーが起動している必要があります
   - デフォルトエンドポイント: `http://localhost:8000`

### viewer_serviceの起動

このアプリを使用する前に、まずviewer_serviceを起動してください：

```bash
# プロジェクトルートから
cd lifelog-system
uv run python -m src.viewer_service.app
```

詳細は、プロジェクトルートの `CLAUDE.md` を参照してください。

## インストール

```bash
# desktop-viewer ディレクトリに移動
cd desktop-viewer

# 依存関係をインストール
npm install
```

## 使い方

### 開発モードで起動

```bash
npm start
```

### ビルド（実行ファイルを生成）

```bash
# すべてのプラットフォーム向けにビルド
npm run build

# Windows向け
npm run build:win

# Linux向け
npm run build:linux
```

ビルド後、`dist/` ディレクトリに実行ファイルが生成されます。

## 機能

### 1. ダッシュボード

- **今日のアクティビティ**: アクティブ時間、使用アプリ数
- **ブラウザ履歴**: 訪問サイト数、閲覧時間
- **外部情報**: 新着ニュース、生成レポート数
- **最近のアクティビティ**: タイムライン表示
- **最新ニュース**: ニュース一覧

### 2. ライフログ

- 今日の活動サマリー
- よく使ったアプリ
- 時間帯別アクティビティ

### 3. ブラウザ履歴

- 最近訪問したサイト一覧
- 訪問時刻、タイトル、URL

### 4. ニュース

- 収集されたニュース一覧
- ソース、公開日時

### 5. レポート

- 生成されたレポート一覧
- カテゴリ、作成日時

### 6. 設定

- **APIエンドポイント**: viewer_serviceのURL
- **更新間隔**: 自動更新の頻度（秒単位）
- **デスクトップ通知**: 有効/無効
- **起動時に最小化**: 有効/無効
- **テーマ**: システム設定/ライト/ダーク

## システムトレイ操作

システムトレイのアイコンを右クリックすると、以下のメニューが表示されます：

- **ダッシュボードを開く**: メインウィンドウを表示
- **今すぐ更新**: 手動でデータを更新
- **設定**: 設定画面を表示
- **終了**: アプリケーションを終了

## アイコンについて

現在、アイコンは未設定です。`assets/icon.png`（256x256ピクセル以上、PNG形式）を配置してください。

アイコンを作成する方法：
1. オンラインツール（Canva、Flaticon等）を使用
2. 既存の画像をリサイズ
3. デザインツール（Figma、Illustrator等）で作成

詳細は `assets/ICON_PLACEHOLDER.txt` を参照してください。

## トラブルシューティング

### API接続エラー

**症状**: 「データの読み込みに失敗しました」というエラーが表示される

**原因**: viewer_serviceが起動していない、またはエンドポイントが間違っている

**解決方法**:
1. viewer_serviceが起動しているか確認:
   ```bash
   curl http://localhost:8000/api/dashboard
   ```
2. 設定画面でAPIエンドポイントを確認
3. API接続テストボタンで接続を確認

### アプリが起動しない

**原因**: Node.jsのバージョンが古い、依存関係が不足

**解決方法**:
```bash
# 依存関係を再インストール
rm -rf node_modules package-lock.json
npm install
```

### 通知が表示されない

**原因**: システムの通知設定が無効になっている

**解決方法**:
1. OSの通知設定を確認
2. アプリの設定で「デスクトップ通知」が有効になっているか確認

## 開発

### プロジェクト構造

```
desktop-viewer/
├── package.json          # プロジェクト設定
├── main.js               # メインプロセス
├── preload.js            # セキュリティ層
├── renderer/             # レンダラープロセス
│   ├── index.html        # メイン画面
│   ├── css/
│   │   └── style.css     # スタイルシート
│   └── js/
│       ├── api.js        # API通信
│       ├── dashboard.js  # ダッシュボードロジック
│       └── settings.js   # 設定ロジック
├── assets/               # アイコン等
│   └── icon.png          # アプリアイコン
└── README.md             # このファイル
```

### 開発のヒント

- **DevTools**: `Ctrl+Shift+I` (Windows/Linux) または `Cmd+Option+I` (Mac) で開く
- **リロード**: `Ctrl+R` (Windows/Linux) または `Cmd+R` (Mac)
- **ログ**: メインプロセスのログはターミナルに、レンダラープロセスのログはDevToolsに表示される

## ライセンス

MIT License

## 関連プロジェクト

- [AIBackgroundWorker](../README.md): メインプロジェクト
- [lifelog-system](../lifelog-system/): バックエンドシステム
- [viewer_service](../lifelog-system/src/viewer_service/): FastAPI サーバー

## サポート

問題が発生した場合は、プロジェクトのIssueに報告してください。
