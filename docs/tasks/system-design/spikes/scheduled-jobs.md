# 風險試作 (b)：由可控制的時鐘觸發每日與月底自動歸檔

- Ticket：T-02；服務情境 S-6 (b)、S-9
- 試作程式：branch `spike/system-design-scheduler-exports`（commit `925729b`），
  目錄 `spike/`。拋棄式，不合併。
- 試作日期：2026-11-22（Asia/Taipei）；環境：Ubuntu 24.04、Python 3.13.18、
  PostgreSQL 16.15。
- 結論：**做得到。** 下列每個行為都有測試，而且每個測試都看過它在行為被破壞時
  失敗。

## 問題

1. 每天 23:59（Asia/Taipei）歸檔當日；每月最後一天 23:59 歸檔當月
   （2026-11-30、2027-02-28、2028-02-29）。
2. 每個類型與日期最多一筆自動歸檔：重啟後再跑不重複；兩個 worker 同一瞬間跑
   同一天只產生一筆。
3. 測試只靠注入的時鐘就能驅動（「when the clock reaches 2026-11-15 23:59」）。
4. 過期的登入 session 要定期清除。
5. 撐得住真實部署：process 被重啟、觸發晚到或重複、23:59 當下系統沒開、
   同時有多個 process。
6. 正式環境由誰觸發，而且觸發方式要與「現在哪些工作到期」的判斷分開。

## 試了什麼

把問題拆成三層，每層只知道下一層：

| 層 | 檔案 | 知道什麼 | 不知道什麼 |
| --- | --- | --- | --- |
| 到期判斷 | `spike_jobs/due.py` | 現在時刻、已歸檔到哪一天 → 該建哪些歸檔 | 資料庫、系統時間、誰在觸發 |
| 工作 | `spike_jobs/jobs.py` | 用時鐘與資料庫連線把到期的歸檔建出來、刪過期 session | 誰在觸發、多久觸發一次 |
| 觸發 | `spike_jobs/trigger.py`、`app.py`、`__main__.py` | 每隔幾秒叫一次 `tick` | 什麼到期 |

關鍵做法：

- **到期是「狀態」不是「事件」。** 日期 D 的歸檔在時鐘到達 D 23:59 之後就一直
  是「到期」，直到資料庫裡有它為止。所以觸發準時、晚到、重複、或漏掉幾天，
  算出來的結果都一樣；歸檔的日期由到期時刻決定，不是由「觸發當下是哪一天」
  決定（00:07 才觸發，歸檔的仍是前一天）。
- **補做的範圍由資料庫裡已有的自動歸檔決定。** 從「最早一筆自動歸檔的日期」
  到「最近一個已到期的日期」之間，比該類型最後一筆還新的日期全部補做，由舊到
  新。全新安裝（沒有任何自動歸檔）只做最近一個到期日，不往回補。
- **防重複的是資料庫，不是程式的檢查。** `archive` 表有 partial unique index
  `(kind, period_date) WHERE automatic`，寫入用
  `INSERT ... ON CONFLICT ... DO NOTHING RETURNING id`。兩個 transaction 同時
  寫同一個 key 時，後到的會被 PostgreSQL 擋住等前一個結束，然後拿到「沒有新增」，
  就跳過。手動歸檔（`automatic = false`）不受這個限制。
- **一筆歸檔一個 transaction**：先搶到那一列，再在同一個 transaction 裡產生內容。
  中途當掉就整筆不存在，下一次 tick 重做。
- **觸發**：每個應用程式 process 在 FastAPI 的 lifespan 裡跑一個迴圈，每隔
  `TICK_SECONDS` 秒叫一次 `tick`；tick 失敗只記 log，下一輪照常。另有
  `python -m spike_jobs` 跑一次就結束，呼叫的是同一個 `tick`。
- **時鐘**：`Clock.now()` 是唯一的時間來源；`SystemClock` 回傳 Asia/Taipei 的
  現在，`FixedClock` 由測試設定。歸檔的 `created_at` 與 session 是否過期都用它。

「兩個 worker 同時」的證明不靠運氣：測試讓 worker A 寫入後**不 commit**，再讓
worker B 在另一條連線跑同一個工作，等到 B「已經跑完」或「在 PostgreSQL 裡卡在
lock 上」（查 `pg_stat_activity`）才讓 A commit。重疊是被強迫發生的。有 unique
index 時 B 會卡住，A commit 後 B 得到「沒有新增」；拿掉 index、改成「先查有沒有
再寫」時，B 看不到 A 還沒 commit 的那一列，一定會寫出第二筆。

## 結果

`cd spike && ./run.sh prove` 的實際輸出（排程相關的部分；路徑已省略）：

```
tests/test_due.py::test_nothing_is_due_one_second_before_2359 PASSED
tests/test_due.py::test_daily_archive_is_due_when_the_clock_reaches_2359 PASSED
tests/test_due.py::test_2359_is_taipei_time_whatever_zone_the_instant_is_expressed_in PASSED
tests/test_due.py::test_month_is_archived_on_its_last_day PASSED
tests/test_due.py::test_february_ends_on_the_28th_in_2027 PASSED
tests/test_due.py::test_february_ends_on_the_29th_in_leap_year_2028 PASSED
tests/test_due.py::test_a_trigger_that_fires_after_midnight_archives_the_day_that_ended PASSED
tests/test_due.py::test_after_days_of_downtime_every_missed_date_is_due_oldest_first PASSED
tests/test_due.py::test_first_month_end_is_due_even_though_no_monthly_archive_exists_yet PASSED
tests/test_due.py::test_a_fresh_install_starts_with_the_latest_due_date_and_does_not_backfill PASSED
tests/test_jobs_db.py::test_archive_is_created_when_the_clock_reaches_2359 PASSED
tests/test_jobs_db.py::test_running_again_after_a_restart_does_not_duplicate PASSED
tests/test_jobs_db.py::test_app_down_at_2359_for_several_days_catches_up_every_missed_date PASSED
tests/test_jobs_db.py::test_leap_year_month_end_is_archived_on_29_february PASSED
tests/test_jobs_db.py::test_a_crash_while_building_leaves_nothing_and_the_next_run_completes_it PASSED
tests/test_jobs_db.py::test_a_manual_archive_for_the_same_date_does_not_replace_the_automatic_one PASSED
tests/test_jobs_db.py::test_two_workers_in_overlapping_transactions_produce_exactly_one_archive PASSED
tests/test_jobs_db.py::test_eight_workers_released_at_the_same_instant_produce_one_archive_each_round PASSED
tests/test_jobs_db.py::test_expired_sessions_are_deleted_and_live_ones_kept PASSED
tests/test_jobs_db.py::test_one_tick_runs_both_the_archives_and_the_session_cleanup PASSED
tests/test_trigger.py::test_the_loop_keeps_ticking_after_a_tick_fails PASSED
tests/test_trigger.py::test_the_one_shot_command_runs_a_tick_on_the_system_clock PASSED
tests/test_trigger.py::test_two_real_server_processes_and_a_restart_make_one_archive PASSED

============================== 30 passed in 7.58s ==============================
```

（30 個裡另外 7 個是匯出檔的測試，見 `pdf-and-word-exports.md`。）

逐一破壞行為後，對應的測試都失敗（`prove_fail.py` 的輸出）：

```
caught  1/1 runs failed  due: the day counts as ended before 23:59
caught  1/1 runs failed  due: 23:59 read in the instant's own zone, not Taipei
caught  1/1 runs failed  due: month end fixed at the 28th or later
caught  1/1 runs failed  due: February always ends on the 28th
caught  1/1 runs failed  due: February never ends on the 28th
caught  1/1 runs failed  due: no catch-up, only the latest date
caught  1/1 runs failed  due: a fresh install back-fills from a fixed date
caught  1/1 runs failed  due: monthly needs an earlier monthly archive
caught  1/1 runs failed  jobs: archive time taken from the system clock
caught  1/1 runs failed  jobs: nothing remembers what was archived (no guard, no history check)
caught  1/1 runs failed  jobs: row committed before its content is built
caught  20/20 runs failed  guard removed: check-then-insert without the unique index (20 runs)
caught  5/5 runs failed  guard removed: eight workers at the same instant (not deterministic; 5 runs)
caught  1/1 runs failed  guard covers manual archives too
caught  1/1 runs failed  sessions: one expiring exactly now is kept
caught  1/1 runs failed  tick: session cleanup left out
caught  1/1 runs failed  trigger: a failing tick ends the loop
caught  1/1 runs failed  app: server processes do not run the loop
caught  1/1 runs failed  command: one-shot command does nothing
```

拿掉防護後，兩個 worker 的測試失敗訊息是：

```
AssertionError: 2 automatic daily archives for 2026-11-15
```

每個問題對應的證據：

| 問題 | 測試 | 破壞方式（都看過失敗） |
| --- | --- | --- |
| 時鐘到 23:59 才歸檔；前一秒不歸檔 | `test_nothing_is_due_one_second_before_2359`、`test_daily_archive_is_due_when_the_clock_reaches_2359`、`test_archive_is_created_when_the_clock_reaches_2359` | 把「未到 23:59 算前一天」拿掉；歸檔時間改讀系統時間 |
| 23:59 是台北時間 | `test_2359_is_taipei_time_...` | 不轉時區 |
| 月底：2026-11-30、2027-02-28、2028-02-29 | `test_month_is_archived_on_its_last_day`、`test_february_ends_on_the_28th_in_2027`、`test_february_ends_on_the_29th_in_leap_year_2028`、`test_leap_year_month_end_is_archived_on_29_february`（資料庫） | 月底改成「28 日以後」、「2 月固定 28 日」、「2 月固定 29 日」 |
| 觸發晚到 | `test_a_trigger_that_fires_after_midnight_archives_the_day_that_ended` | 同第一列 |
| 23:59 當下沒開，回來後補做哪些日期 | `test_after_days_of_downtime_...`、`test_app_down_at_2359_for_several_days_...`：11-27 之後停機，12-02 08:00 回來，補 11-28、11-29、11-30（日與月）、12-01 | 只做最近一天 |
| 全新安裝不往回補 | `test_a_fresh_install_...` | 從固定日期補起 |
| 重啟後再跑、觸發重複不會多一筆 | `test_running_again_after_a_restart_does_not_duplicate`、`test_the_one_shot_command_...`（跑兩次） | 同時拿掉防護與「已歸檔到哪天」的判斷 |
| 產生內容中途當掉 | `test_a_crash_while_building_leaves_nothing_...` | 先 commit 那一列再產生內容 |
| 兩個 worker 同一瞬間 | `test_two_workers_in_overlapping_transactions_produce_exactly_one_archive`（決定性）；`test_eight_workers_released_at_the_same_instant_...`（8 條連線、25 輪，輔助） | 拿掉 unique index 並改成先查再寫：前者 20 次裡失敗 20 次，後者 5 次裡失敗 5 次 |
| 手動歸檔不佔用自動歸檔的名額 | `test_a_manual_archive_for_the_same_date_...` | index 不分自動與手動 |
| 過期 session 被清掉、沒過期的留著 | `test_expired_sessions_are_deleted_and_live_ones_kept`、`test_one_tick_runs_both_...` | `<=` 改 `<`；tick 不叫清除 |
| 觸發迴圈在 tick 失敗後繼續 | `test_the_loop_keeps_ticking_after_a_tick_fails` | 不接例外 |
| 迴圈真的在伺服器 process 裡跑 | `test_two_real_server_processes_and_a_restart_make_one_archive`：`uvicorn --workers 2`，用系統時鐘，SIGKILL 後再啟動一次，資料庫裡只有一筆 | lifespan 不啟動迴圈 |

一個要講清楚的限制：最後一列的真實伺服器測試**不能**證明防護。我試過在拿掉
防護的情況下跑它 3 次，3 次都還是只有一筆，因為兩個 process 很少在同一毫秒
啟動。防護的證明是「兩個 worker」那一列。

## 從零重現

需要：git、Python 3.11 以上、PostgreSQL 的執行檔（`initdb`、`pg_ctl`；Ubuntu 是
`apt install postgresql`，不需要啟動服務）。不需要任何帳號、金鑰或外部服務。

```
git clone https://github.com/pitaya943/yc-report-v4.git
cd yc-report-v4
git checkout spike/system-design-scheduler-exports
cd spike
./run.sh prove
```

`./run.sh` 會建立 `spike/.venv`、安裝 `requirements.txt`、跑 30 個測試、產生範例
檔；加上 `prove` 會再跑上面的破壞清單（約 2 分鐘）。

預期看到：`30 passed`，接著每一行都是 `caught`，最後一行
`every break was caught`，結束碼 0。

測試會自己在暫存目錄建立一個 PostgreSQL 叢集、用完刪除，使用隨機的空閒 port，
不會碰到 5432 上既有的資料庫。PostgreSQL 不能用 root 執行；如果你是 root，測試
會改用作業系統帳號 `postgres` 啟動它（可用環境變數 `SPIKE_PG_OS_USER` 換帳號）。
找不到執行檔時設 `PG_BIN=/usr/lib/postgresql/16/bin`。也可以設
`SPIKE_DATABASE_URL` 指到一個空的資料庫，測試就不自己建叢集（會刪掉並重建
`archive` 與 `session` 兩張表）。

只想自己親手看「拿掉防護會壞」：`.venv/bin/python prove_fail.py guard`。

## 建議產品採用的做法

1. 到期判斷是純函式，只吃時刻與歸檔紀錄；工作吃時鐘與資料庫連線；觸發只管
   定時呼叫。測試驅動前兩層，完全不需要等真實時間。
2. 防重複用資料庫的 partial unique index 加 `ON CONFLICT DO NOTHING`，歸檔內容
   與那一列在同一個 transaction。
3. 正式環境的觸發：**每個應用程式 process 內建迴圈**（建議 30 秒一次），本機與
   正式環境是同一段程式，只差 `TICK_SECONDS` 這個設定。因為有第 2 點，process
   數量不影響正確性。同時保留一次性指令，給人工補跑或日後改用平台排程時使用。

介面（產品重寫時的形狀，不是要搬這份程式）：

```python
class Clock(Protocol):
    def now(self) -> datetime: ...          # 帶時區；SystemClock 回傳 Asia/Taipei

def due_archives(now, first_archived, last_archived) -> list[tuple[str, date]]
def run_due_archives(conn, clock, build) -> list[tuple[str, date]]   # 每筆一個 transaction
def delete_expired_sessions(conn, clock) -> int
def tick(database_url, clock) -> None       # 觸發唯一需要呼叫的東西
async def run_forever(tick, interval_seconds) -> None
```

```sql
CREATE UNIQUE INDEX archive_one_automatic
    ON archive (kind, period_date) WHERE automatic;
```

## 衡量過的另一個做法與代價

**平台排程（例如 Railway 的 cron 服務）在 23:59 呼叫一次性指令。**

- 好處：應用程式 process 裡沒有背景迴圈；沒有請求時也不必有 process 醒著。
- 代價：
  - 多一個要部署與設定的服務，而且排程寫在平台設定裡，本機沒有對應的東西，
    違反「本機與正式環境只差設定」。
  - 平台排程用 UTC，而且不保證準時；晚到、漏掉、重複都要自己處理。也就是說
    「到期是狀態、可以補做、資料庫防重複」這一整套還是得做，排程只是把觸發
    換了人。
  - 一天只觸發一次的話，那一次失敗就要等到隔天；要補救就得把頻率調高，結果
    與內建迴圈相同。
- 因為工作本身與觸發無關，日後要換成平台排程只需要改部署設定，呼叫的是同一個
  指令（`python -m spike_jobs` 的產品版）。

沒有採用的其他做法：

- APScheduler 之類的 in-process 排程套件：它解決的是「幾點叫我」，而這裡真正的
  難題是晚到、補做與多 process 去重，仍然要靠上面的設計；多一個相依套件，卻讓
  測試得去控制套件自己的時鐘。
- PostgreSQL advisory lock：能擋同時執行，但擋不住「上一個已經做完、下一個再做
  一次」，還是需要 unique index；兩者都用就是兩套機制管同一件事。

## 需要設計或 owner 決定的事（試作時先選了預設）

1. **補做的歸檔內容是補做當下的狀態。** 系統 11-28 停機、12-02 才回來，11-28
   的自動歸檔是 12-02 建的；它應該收「日報日期是 11-28 的已確認日報」，但
   11-29 之後才被確認的那些算不算，規格沒有說。試作只放了占位內容，沒有回答
   這題。
2. **全新安裝不往回補**，第一次 tick 只建「最近一個到期日」那一筆（很可能是
   空的）。另一個選擇是上線當天什麼都不建。
3. **補做是從該類型最後一筆自動歸檔往後補**，不會回頭補中間的洞。如果自動
   歸檔可以被刪除，被刪掉的那天不會自動重建（這是刻意的，避免把人刪掉的東西
   又生回來），但需要規格確認自動歸檔能不能刪。
4. session 在 `expires_at` 那一刻（含）就算過期。

## 在有真實正式環境之前無法證明的事

- Railway 上的 process 是否會因為沒有流量而被暫停（app sleeping），以及暫停時
  迴圈不跑的實際影響。依設計，醒來後第一個 tick 會補做，但「一直沒人用就一直
  不歸檔，直到有人打開系統」是否可接受，要在真實環境確認，或關掉該功能。
- 正式環境的 PostgreSQL 若經過 connection pooler（例如 Supabase 的 transaction
  pooling），每個 tick 新開一條連線、每筆歸檔一個 transaction 的做法應該相容
  （沒有用到 session 層級的功能），但沒有在真的 pooler 上跑過。
- 真實歸檔內容需要的時間。內容產生期間，另一個 worker 會卡在同一個 key 上等；
  占位內容是瞬間完成的，量不到。
- 部署時新舊版本的 process 同時存在幾秒：依設計安全（同一個 unique index），
  但只在本機用兩個 uvicorn worker 與 SIGKILL 重啟模擬過。
- 上面寫到的 Railway cron 特性（UTC、不保證準時）是依我對其文件的理解，這個
  環境連不到 Railway，沒有實測。
