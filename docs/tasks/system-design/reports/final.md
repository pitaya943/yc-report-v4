# system-design：最終報告

依我自己的檢查，brief 的 9 個情境（S-1 至 S-9）全部達成。這個 task 沒有建置任何
使用者功能；它交付的是重建員工日報系統所需的規格基準、設計與證據。

追蹤 issue：#2。Brief：[`brief.md`](../brief.md)。

## 做了什麼

1. 把 yc-daily-report-v3 的行為規格搬進本 repo 的 `docs/spec/`，依 9 個領域整理，
   並加上一個檢查工具。商業規則、例子的數字與使用者可見字串一字未改；實際計數是
   31 個 feature、137 條規則、254 個 scenario、502 個可執行的例子（v3 首頁寫的 251
   是過時的手算數字）。
2. 分析四個舊系統，寫成取捨紀錄：每個做法採用或捨棄、原因、以及是讀到的還是
   推論的。
3. 寫出系統設計：一個伺服器端產生頁面的 Python 應用程式、專屬的 PostgreSQL、S3
   相容的檔案儲存；包含資料怎麼保證「算過的薪資不變」與「舊日報用當時的工項組」、
   規格怎麼變成自動測試，以及成品怎麼部署、更新、退回與備份。
4. 在本機實際試作四個高風險環節（會過期的下載連結、銀行帳號加密、排程歸檔、中文
   PDF 與 Word），留下可以重跑的分支與紀錄。試作改變了兩個原本的設計想法。
5. 列出 24 個未決問題並各選一個預設答案，並把整個系統切成 9 個 task。

## 怎麼試

需要 git、Python 3.11 以上；第 4 步另外需要 PostgreSQL 的執行檔（`initdb`、
`pg_ctl`），不需要任何帳號或金鑰。

1. 取得程式並切到這個分支。

   ```bash
   git clone https://github.com/pitaya943/yc-report-v4.git && cd yc-report-v4 && git checkout task/system-design
   ```

2. 檢查規格（S-3）。最後兩行應該是
   `total    features=31 rules=137 scenarios=254 cases=502` 與 `spec check: ok`。

   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt && .venv/bin/python tools/check_spec.py
   ```

3. 試作一：檔案、過期連結、銀行帳號加密（S-6 的 a、c）。應該看到 `68 passed`，
   接著 `34 of 34 breaks were caught by a test`。

   ```bash
   git checkout spike/system-design-storage-crypto && cd spike/storage_crypto && ./run.sh && .venv/bin/python experiments/break_each_behaviour.py; cd ../..
   ```

4. 試作二：排程歸檔、中文 PDF 與 Word（S-6 的 b、d）。約兩分半鐘；應該看到
   `30 passed`、`wrote out/payroll.pdf and out/bank-transfer.docx`、28 行 `caught`，
   最後是 `every break was caught`。產生的兩個檔案在 `spike/out/`，可以直接打開看。
   PostgreSQL 不能以 root 身分啟動；以 root 執行時，試作會改用 `postgres` 這個系統
   使用者。

   ```bash
   git checkout spike/system-design-scheduler-exports && cd spike && ./run.sh prove; cd ..
   ```

5. 回到 `task/system-design`，閱讀下表「證據」欄的文件。

   ```bash
   git checkout task/system-design
   ```

值得另外試、而測試沒有涵蓋的：

- 把 `docs/spec/index.md` 裡 `spec-counts` 那一行的數字改掉再跑第 2 步，應該失敗並
  指出差異。
- 用真正的 Microsoft Word 打開第 4 步產生的 `bank-transfer.docx`；試作只用
  LibreOffice 驗證過。
- 照 `spec-baseline-diff.md` 最後的指令，把 `docs/spec/` 的 feature 檔與 v3 原文
  逐行比對。

## 情境對照

| 情境 | 是否達成 | 證據 |
| --- | --- | --- |
| S-1 規格基準可以單獨閱讀 | 是 | [`docs/spec/index.md`](../../../spec/index.md) 與 9 個領域資料夾；檢查工具確認 31 個 feature 都被索引連結 |
| S-2 與 v3 原文的每一處差異都有來源 | 是 | [`spec-baseline-diff.md`](../spec-baseline-diff.md)：9 項差異，附比對指令與輸出 |
| S-3 規格的例子可以被工具讀取 | 是 | [`tools/check_spec.py`](../../../../tools/check_spec.py)；看過它在總數錯誤、scenario 同名、語法錯誤時失敗（trail 23:01 的列） |
| S-4 每個舊系統都有取捨紀錄 | 是 | [`prior-systems.md`](../prior-systems.md) |
| S-5 設計回答了重建者一定會問的問題 | 是 | [`design.md`](../design.md) 第 2 至 8 節 |
| S-6 四個高風險環節都實際試過 | 是 | [`spikes/`](../spikes/) 四份紀錄；PR #3、PR #4 的 Ready 留言；Chief 從乾淨的 checkout 各重跑一次（68 passed；30 passed 並產生兩個樣本檔） |
| S-7 懸而未決的問題都有預設答案 | 是 | [`open-questions.md`](../open-questions.md)：24 題 |
| S-8 後續 task 地圖涵蓋整個系統 | 是 | [`task-map.md`](../task-map.md)：31 個 feature 各出現一次，合計與規格索引一致 |
| S-9 設計說明成品怎麼部署 | 是 | [`design.md`](../design.md) 第 9 節 |

## 我自己做的決定

完整的 43 列在 [`trail.tsv`](../trail.tsv)。owner 最可能想知道的：

| 決定 | 原因 |
| --- | --- |
| 31 個 Gherkin 檔原樣保留在 `docs/spec/<領域>/`，列在各領域的「尚未建置」，沒有改寫成敘述文字 | 它們本來就是 Given/When/Then，owner 已同意其規則，之後的 task 要把測試綁在這些檔案上 |
| scenario 總數由 251 更正為 254；`CFG-F02` 兩個同名的 scenario 改名 | 解析器實際計數；同名會被測試工具無聲丟掉一個 |
| 未決問題的預設答案沒有寫成新的 scenario | brief 限定基準只能有 v3 自己的決定；新行為應該在建置它的 task 的 brief 由 owner 核准 |
| 採用單一的 Python 應用程式，不採用以 Supabase 為中心的形狀，也不採用 v2 的兩層 | 規格的核心規則是跨多張表的交易並要回報確切訊息；v2 的兩層造成三個安全缺陷 |
| 不沿用 v3「禁止資料庫 trigger」的規則 | 那條是為共用資料庫的掃描器而設；稽核與薪資批次不可改交給資料庫保證較安全 |
| 年度保留金累計由已確認的份額即時算出，不由薪資批次累加 | 重算同一個期間不能把保留金算兩次 |
| 薪資批次不存銀行帳號；轉帳單在匯出當下解密，沒有金鑰就無法產生 | 不把明文帳號放進不可改的資料列；規格沒寫，列入薪資 task 的 brief |
| 下載連結由應用程式簽發並檢查期限，檔案經應用程式下載 | 規格要求剛好 3,600 秒的界線；物件儲存的預簽網址期限無法由測試控制，試作中的替身甚至不檢查期限 |
| 排程觸發由平台 cron（初稿）改為應用程式行程內的迴圈 | 試作顯示正確性都來自資料庫的唯一索引；迴圈讓本機與正式是同一段程式 |
| PDF 的中文字型檔隨應用程式部署（7.1 MB） | 試作發現 v1 用的系統字型套件 reportlab 載不進來 |
| 密碼雜湊用 argon2id，不沿用 v3 的標準庫 scrypt | 參數可調，測試可以用便宜的參數；v3 的測試因此很慢 |
| 部署建議：Railway 跑應用程式、專屬的 Supabase 專案只當 PostgreSQL、S3 相容的檔案儲存 | owner 熟悉；應用程式與 Supabase 的接點只有連線字串，換掉只需改設定 |
| 兩張試作 ticket 合併前沒有另外做獨立驗證，由 Chief 重跑確認 | 謹慎程度是「一般」；最終驗證會涵蓋 S-6 |
| 本 task 合併進 `main` 的程式只有 `tools/check_spec.py` | S-3 需要一個檢查指令；試作程式留在 `spike/` 分支，不合併 |

## 沒做到或有疑慮的

- **沒有任何東西在真實的平台上跑過。** 部署設計（第 9 節）是依對 Railway、Supabase
  的一般理解寫的，供應商的功能與方案要在部署 task 開始時對照當時的官方文件。尤其
  是「沒有流量就暫停行程」的功能：開著的話，沒人使用時不會自動歸檔，直到有人打開
  系統才補做。
- **v3 issue 35 的原文讀不到。** 7 個問題的題目取自 v3 的 M2 報告摘要，預設答案沿用
  v3 已實作的選項；如果原文的選項與摘要有出入，OQ-1 至 OQ-7 要重看。
- **取捨紀錄有一部分來自子代理的閱讀**，不是 Chief 逐檔讀過；每一列已標明「讀過」
  或「推論」，但「讀過」指的是子代理讀過。v1 的匯出程式與 `docs/TEST_PIPELINE.md`
  只有略讀。
- **轉帳單的版面是推測的。** 真實的板信商業銀行樣本拿不到（OQ-15）。
- **試作留下的未證明事項**：真實的物件儲存端點、經過連線池時的排程、在真正的資料表
  上輪替金鑰、上傳前的請求大小上限、刪除檔案庫刪到一半失敗的處理。各自排進了
  後續 task，列在設計第 7 節。
- **規格的例子沒有對照舊系統的實際輸出**，owner 也沒有逐條審閱過每個 scenario
  （OQ-16）；這是 v3 就有的狀態，本 task 沒有改變它。
- **`test_command` 仍是空的。** 目前唯一的檢查是 `tools/check_spec.py`；骨架 task
  建立測試後再設定。本 repo 也還沒有 `try-<app>` skill，因為還沒有可以啟動的程式。
- **過程中的一個失誤：** 一次 `git add -A` 把兩個 builder 的工作目錄提交成內嵌 repo
  （commit `39ae504`），下一個 commit 已移除並加上 `.gitignore`。分支歷史裡看得到
  這兩個 commit。

## 驗證

獨立驗證的結論會以留言貼在這個 pull request 上。

## 合併之後

發現任何不對的地方，請在追蹤 issue #2 留一則留言；下一個 task 開始時會把它讀進
注意事項，這是驗證沒抓到的問題唯一的回饋管道。
