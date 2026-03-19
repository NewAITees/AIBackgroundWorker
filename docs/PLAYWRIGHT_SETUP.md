# Playwright CLI セットアップガイド（WSL環境）

## 問題

WSL上で `playwright-cli` を使おうとすると以下のエラーが出る：

```
Error: browserType.launchPersistentContext: Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome
Run "npx playwright install chrome"
```

`playwright-cli` はデフォルトで Chrome チャンネルを使おうとするが、WSL には Chrome が入っていないため失敗する。
また、日本語フォントが無いと文字が豆腐（□）になる。

---

## セットアップ手順

### 1. Firefox をインストール

```bash
npx playwright install firefox
```

### 2. 日本語フォントをインストール

```bash
sudo apt-get install -y fonts-noto-cjk
```

### 3. `playwright-cli.json` を作成

`playwright-cli` を実行するディレクトリ（リポジトリルートまたは作業ディレクトリ）に置く：

```bash
cat > playwright-cli.json << 'EOF'
{
  "browser": "firefox"
}
EOF
```

> **注意**: `playwright-cli` はカレントディレクトリの `playwright-cli.json` を読む。
> このリポジトリでは `timeline-app/playwright-cli.json` が設置済み。

### 4. 動作確認

```bash
playwright-cli session-stop 2>/dev/null || true
playwright-cli open http://localhost:8100
playwright-cli screenshot
```

---

## よくあるトラブル

### セッションが古いままで設定が反映されない

```bash
playwright-cli session-stop
playwright-cli session-delete
```

してから再実行する。

### `playwright-cli.json` を置いても Chrome が使われる

セッションが前の設定でキャッシュされている。上記の session-stop / session-delete で解消する。

### スクリーンショットの保存先

`.playwright-cli/` ディレクトリに `page-{timestamp}.png` として保存される。

---

## 現在のセットアップ状態（2026-03-19時点）

| 項目 | 状態 |
|---|---|
| Firefox | インストール済み（`~/.cache/ms-playwright/firefox-1509`） |
| Chromium | インストール済み（`~/.cache/ms-playwright/chromium-1208`）※ただし playwright-cli では使えない |
| 日本語フォント | **未インストール**（要 `sudo apt-get install -y fonts-noto-cjk`） |
| `playwright-cli.json` | `timeline-app/` に設置済み |
