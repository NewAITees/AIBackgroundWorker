# ResourceWarning: unclosed database — 原因・修正・教訓

## 概要

`sqlite3.Connection` が `close()` を呼ばれないまま GC されると、Python が以下の警告を出す。

```
ResourceWarning: unclosed database in <sqlite3.Connection object at 0x...>
```

本プロジェクトでは複数箇所を修正したが、最後まで治らなかった。
その理由と、最終的な根本原因・修正内容をまとめる。

---

## Python の ResourceWarning が出る仕組み

`sqlite3.Connection` は CPython レベルで `tp_finalize` を持つ。
GC がオブジェクトを回収するとき、`self->db != NULL`（= `close()` 未呼び出し）なら警告を出す。

```
conn.close()  →  self->db = NULL  →  GC されても警告なし
close() なし  →  self->db != NULL →  GC 時に ResourceWarning
```

`with sqlite3.connect(...) as conn:` は SQLite の context manager を使う。
これは **commit / rollback しか行わず、close() を呼ばない**。
この誤解が今回の修正が何度繰り返されても治らなかった一因。

---

## 修正フェーズ1：表面的な close 漏れ（9ファイル）

### 問題

`with sqlite3.connect(...) as conn:` パターンが全体に散在。
commit/rollback はされるが close() されない。

### 修正

`contextlib.closing()` でラップして close() を保証。

```python
# 修正前
with sqlite3.connect(db_path) as conn:
    ...

# 修正後
with contextlib.closing(sqlite3.connect(db_path)) as conn:
    ...
```

### 対象ファイル

| ファイル | 修正箇所数 |
|--------|---------|
| timeline-app/src/workers/paths.py | 1 |
| timeline-app/src/workers/activity_worker.py | 1 |
| timeline-app/src/workers/browser_worker.py | 2 |
| timeline-app/src/workers/info_worker.py | 1 |
| timeline-app/src/services/hourly_summary_importer.py | 2 |
| lifelog-system/src/lifelog/database/db_manager.py | 2（_init_database / migrate_if_needed） |
| lifelog-system/src/lifelog/cli_viewer.py | 1 |
| lifelog-system/src/info_collector/data_aggregator.py | 1 |
| lifelog-system/src/browser_history/brave_importer.py | 1（finally 外の close） |

---

## 修正フェーズ2：残存した2箇所

フェーズ1後もまだ警告が出続けた。

### 問題A：BrowserHistoryRepository._connect()

```python
def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self.db_path, ...)
    ...
    return conn  # ← 呼び出し側が with で使っているが close() されない
```

呼び出し側はすべて `with self._connect() as conn:` だが、
`_connect()` が生の Connection を返すため、sqlite3 の context manager が
commit/rollback しか行わず close() されない。

### 修正A

`_connect()` を `@contextmanager` に変更。呼び出し側の `with self._connect()` はそのまま動作。

```python
@contextmanager
def _connect(self) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(self.db_path, ...)
    try:
        yield conn
    finally:
        conn.close()
```

### 問題B：DatabaseManager のスレッドローカル接続

`DatabaseManager` はスレッドローカルで接続を永続保持する設計。
GC 時に自動で close() されないため、スレッドが死ぬと接続が残る。

### 修正B

`__del__` を追加して GC 時に close() を試みる（best-effort）。

```python
def __del__(self) -> None:
    with contextlib.suppress(Exception):
        self.close()
```

> **注意**: `__del__` は `contextlib.suppress(Exception)` で失敗を黙って握りつぶすため、
> close() の成功は保証されない。所有者が明示的に close() を呼ぶことが必要であり、
> `__del__` はあくまで最後の防衛線（フォールバック）にすぎない。

---

## 修正フェーズ3：根本原因の特定（最終修正）

フェーズ1・2の後も以下の警告が出続けた：

```
threading.py:291: ResourceWarning: unclosed database in <sqlite3.Connection ...>
threading.py:291: ResourceWarning: unclosed database in <sqlite3.Connection ...>
threading.py:291: ResourceWarning: unclosed database in <sqlite3.Connection ...>
threading.py:291: ResourceWarning: unclosed database in <sqlite3.Connection ...>
```

**4件同時・15分ごとに出現。**

### なぜ「threading.py」なのか

`threading.py:291` はスレッド終了時のクリーンアップコード。
スレッドが死ぬとき Python は thread-local storage を解放し、
保持していたオブジェクトを DECREF する。
その際に接続が GC されると ResourceWarning が発生する。

### なぜ4件同時なのか

`ActivityCollector.start_collection()` が daemon スレッドを **4本** spawn する。

```python
def start_collection(self) -> None:
    collect_thread = threading.Thread(target=self._collection_loop, daemon=True)
    write_thread   = threading.Thread(target=self._bulk_write_loop, daemon=True)
    health_thread  = threading.Thread(target=self._health_monitoring_loop, daemon=True)
    event_thread   = threading.Thread(target=self._event_collection_loop, daemon=True)
```

各スレッドが `DatabaseManager._get_connection()` を呼んで
スレッドローカルに接続を作成。接続は `_connections` セットにも登録される。

### なぜ今まで修正しても治らなかったか

```
asyncio.to_thread(_blocking_loop)
  └─ Thread A: db_manager = DatabaseManager(...)   ← ここが修正対象と思われていた
       └─ ActivityCollector.start_collection()
            ├─ Thread B (daemon): _collection_loop      → _get_connection() で接続作成
            ├─ Thread C (daemon): _bulk_write_loop      → _get_connection() で接続作成
            ├─ Thread D (daemon): _health_monitoring_loop → _get_connection() で接続作成
            └─ Thread E (daemon): _event_collection_loop  → _get_connection() で接続作成
```

接続を **生成している** のは B/C/D/E の daemon スレッド。
今まで修正していたのは「`with sqlite3.connect()` を使っている箇所」であり、
これらのスレッドには直接 sqlite3.connect() のコードがない。
そのため修正対象が噛み合わず、何度直しても別の場所から警告が出ていた。

### 最終修正

`_blocking_loop()` の finally で `db_manager.close()` を明示的に呼ぶ。

```python
# timeline-app/src/workers/activity_worker.py

try:
    while not self._stop_event.is_set():
        self._sync_once_blocking()
        self._stop_event.wait(timeout=self._poll_seconds)
finally:
    collector.stop_collection()
    self._collector = None
    db_manager.close()   # ← 追加
```

`close()` は `_connections` セットに登録されている全接続（B/C/D/Eのぶんを含む）を
まとめて close() する実装になっており、これで4スレッド分の接続が正しく閉じられる。

---

## 修正フェーズ4：レビュー指摘への対応

フェーズ3の修正後、外部レビューにより以下の残存問題が指摘された。

### 問題C：`_health_monitoring_loop` / `_event_collection_loop` の確定的競合

```python
while self._running:
    time.sleep(snapshot_interval)  # ← stop_collection() がここで呼ばれると
    self.db.save_health_snapshot(metrics)  # ← close() 後にこの行が必ず実行される
```

`while self._running:` のチェックはスリープ **前**。スリープ中に `_running = False` になっても、
現在のイテレーションはスリープ後の DB 操作まで進む。
これは「短いウィンドウ」ではなく、確定的に踏みうる競合。

### 修正C

スリープ後に `_running` を再チェックして早期 return。

```python
while self._running:
    time.sleep(snapshot_interval)
    if not self._running:
        return  # ← 追加
    self.db.save_health_snapshot(metrics)
```

### 問題D：`ActivityCollector` がスレッド参照を保持せず join 不可

`start_collection()` がスレッドを起動するが参照を捨てており、
`stop_collection()` → `db_manager.close()` の間でスレッドが生きているか確認できなかった。

### 修正D

`self._threads` にスレッド参照を保持し、`stop_collection()` で `join(timeout=15)` する。
join 完了後に `db_manager.close()` が呼ばれるため、競合は解消される。

```python
def stop_collection(self) -> None:
    self._running = False
    for t in self._threads:
        t.join(timeout=15)
        if t.is_alive():
            logger.warning("Thread %s did not stop within timeout", t.name)
    self._threads = []
```

### 問題E：`DailyReportDataAggregator` が `DatabaseManager` を保持するが close 経路なし

`data_aggregator.py` の `__init__` で `self.lifelog_db = DatabaseManager(...)` を作成するが、
`close()` メソッドも `__del__` も存在しなかった。

### 修正E

`close()` と `__del__` を追加。

```python
def close(self) -> None:
    self.lifelog_db.close()

def __del__(self) -> None:
    with contextlib.suppress(Exception):
        self.close()
```

---

## 今回の修正が問題にならないか（レビューポイント）

### 懸念1：daemon スレッドがまだ動いている状態で close() を呼ぶ

`collector.stop_collection()` は `self._running = False` をセットするだけ。
daemon スレッドが実際に停止するのはそれ以降のループ確認タイミング。

`db_manager.close()` が呼ばれると、まだ動いている B/C/D/E が
「すでに閉じられた接続」にアクセスしようとして例外が出る可能性がある。

**現状の評価：**
- `stop_collection()` が `_running = False` にした直後に `close()` を呼ぶため、
  B/C/D/E がその後に接続を使おうとすると `ProgrammingError: Cannot operate on a closed database` が出る
- ただし daemon スレッドは `_running = False` を確認次第ループを抜けるため、
  アクセスのウィンドウは極めて短い
- 例外が出ても daemon スレッド内でキャッチ・ログされるかは実装による

**推奨：** `stop_collection()` でスレッドの join（待機）を追加するのが理想。
現状は `stop_collection()` が join を持たないため、close() との間に競合が残る。

### 懸念2：_blocking_loop が再起動されたとき

`activity_worker._run()` が `_blocking_loop` を何度も呼ぶ設計なら、
`db_manager.close()` 後に再度 `DatabaseManager()` が作られるため問題なし。
コードを確認すると `_run()` は1回だけ `_blocking_loop` を呼ぶ構造のため問題なし。

### 懸念3：close() の二重呼び出し

`__del__` も追加されているため、`close()` が明示的に呼ばれた後に
`__del__` が再度 `close()` を呼ぶことになる。
`close()` の実装は `_connections.clear()` してから個別 close するため、
2回目は `_connections` が空で何もせず、`contextlib.suppress(Exception)` で保護されている。
二重呼び出しは安全。

---

## 教訓

| 教訓 | 内容 |
|------|------|
| `with sqlite3.connect() as conn` は close しない | SQLite の context manager は commit/rollback のみ。close するには `contextlib.closing()` が必要 |
| スタックトレースの「発生場所」と「原因場所」は別 | `threading.py:291` はスレッド死亡時のクリーンアップ。接続を作っていたのは別のスレッド |
| 警告の件数がヒントになる | 4件同時 = daemon スレッドが4本 = `ActivityCollector.start_collection()` が spawn するスレッド数と一致 |
| thread-local 接続はライフサイクル管理が難しい | 接続を作ったスレッドが死ぬとき、close() が呼ばれているかどうかが保証されない。明示的な close() が必要 |
| 修正箇所の選定ミス | 「`sqlite3.connect` を使っている行」を直し続けたが、実際の接続は `_get_connection()` 経由でスレッドが作っており、そのスレッドのライフサイクル管理が問題だった |
