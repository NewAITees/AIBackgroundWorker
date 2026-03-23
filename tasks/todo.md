## 運用ルール
1. タスクを追加するときはチェックボックス形式で書く
2. 完了したら `[x]` にする
3. セクションが全て完了したら、セクションごと削除してよい

---

## 最優先: 単純化・削減フェーズ（残1件）

- [ ] Windows 移行時: `WindowsForegroundWorker` に `powershell.exe foreground_logger.ps1` の起動管理を追加する
      → 現時点は foreground_logger.ps1 は別途起動する運用のまま

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
- [x] `system_log` の対象時刻とカード表示時刻のずれを修正する
      → `make_timestamp()` が `hour:30` 固定（意図的仕様: 1時間の中点に配置）で「01時 → 01:30表示」は想定動作
      → 「01時が10:30表示」という元の症状は再現しないことを確認済み（クローズ）
- [ ] 画面に出ている結果が「現状の正しい仕様」か「仮実装由来」かの整理
      → browser 取り込み・要約・分類・UI 表示の各段で、意図した挙動と暫定挙動を明文化する

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

## フェーズ5: M2 実用化

> 参照: 要件書 §21.2
> **方針**: UIの主役は単一タイムライン。別ページを増やさずフィルタ・ビュー切り替えで対応する。

### 5-0e. リマインダー機能（§30）

- [ ] `event` / `todo` entry に指定時刻のリマインダーを追加できるようにする
- [ ] 指定時刻になったらブラウザ通知またはトーストでリマインド
- [ ] AI プロアクティブ通知（AI から話しかける）を並行検討（§30.2）
      → VRM アシスタント（§16.1）との連携も視野に

### 5-1. タイムライン実用強化

- [ ] 右ペインの種別変更をボタン一覧からドロップダウン選択に変更する
      → 現状は `detail-quick-types` に全種別ボタンが並ぶ。クリックでドロップダウンが開き、変更先を選択する形にする
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

- [ ] AI 性格・System Prompt 設定（要件書 §15.4）
- [ ] Ollama 接続設定（ベースURL・モデル名・タイムアウト）（要件書 §17.1）
- [ ] RSS フィード登録（要件書 §17.1）
- [ ] AI 処理 ON/OFF の設定ページ対応（要件書 §15.5）
      → pause/resume API とトップバー切り替えは実装済み。設定画面からも操作できるようにする
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
