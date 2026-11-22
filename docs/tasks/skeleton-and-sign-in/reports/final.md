# skeleton-and-sign-in：最終報告

依我自己的檢查，brief 的 14 個情境（S-1 至 S-14）全部達成。S-12 的容器映像由 owner 加入的
CI 在 GitHub 上建置並啟動來證明（issue #7，owner 選的做法）。

這是第三版。前兩次最終驗證（commit `4fc0563`、`358b858`）都判定 FAIL，兩次都只有 S-14 的
第一項不成立，其餘 13 個情境兩次都通過。owner 於 2026-11-22 同意把 S-14 的第一項改寫成
做得到的保證（見 brief），這一版依改寫後的 S-14 修正。三版之間沒有改動任何程式行為。

追蹤 issue：#6。Brief：[`brief.md`](../brief.md)。設計：[`design.md`](../design.md)。

## 做了什麼

1. 員工、管理員與 owner 可以用瀏覽器登入與登出：選群組、選名字、輸入密碼，依角色
   到日報頁或確認頁（兩頁目前是寫著「尚未建置」的空殼）。密碼連錯 5 次鎖定 15 分鐘，
   同一來源每分鐘最多 10 次嘗試，閒置 30 分鐘要重新登入，沒登入進不了受保護的頁面。
2. 建好之後每個 task 都要用的地基：統一的拒絕方式、權限檢查、稽核寫入（資料庫層
   不可改）、可控制的時鐘、設定檢查、資料庫結構的更新指令。
3. 規格的例子現在會被自動執行：137 條規則中本 task 的 11 條已開啟，20 個 scenario、
   30 個例子直接從 `docs/spec/` 執行並通過；其餘 472 個例子顯示為「尚未建置」。
4. 成品有了可以部署的外殼：`Dockerfile`、啟動前自動更新資料庫結構、缺必要設定時
   拒絕啟動、健康檢查頁與狀態頁、建立 owner 的一次性指令、給 owner 加入的 CI 工作
   流程。本 task 沒有實際部署。
5. 處理了上一個 task 驗證留下的四項問題，並把已建置的規則寫進 `docs/spec/`。

## 怎麼試

需要 git、Python 3.13、PostgreSQL 16；不需要任何帳號或金鑰。完整說明在
[`README.md`](../../../../README.md)。

1. 取得程式並安裝。

   ```bash
   git clone https://github.com/pitaya943/yc-report-v4.git && cd yc-report-v4 && git checkout task/skeleton-and-sign-in
   ```

   ```bash
   python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
   ```

2. 準備一個空的資料庫並載入示範帳戶。最後一個指令會印出示範密碼。

   ```bash
   createdb yc_report && export DATABASE_URL=postgresql:///yc_report
   ```

   ```bash
   .venv/bin/python -m app migrate && .venv/bin/python -m app seed-demo
   ```

3. 啟動，然後用瀏覽器打開 <http://127.0.0.1:8000/>。

   ```bash
   .venv/bin/python -m app serve
   ```

4. 在瀏覽器裡：
   - 選「西區」、選「Wen」、輸入示範密碼：看到「日報」頁，頂端是「Wen（員工）」。
   - 按「登出」：回到登入頁並顯示「您已登出」。
   - 選「管理員」、選「Admin1」登入：看到「確認」頁；再打開 `/status`，看到資料庫
     可連線、檔案儲存與加密金鑰「未設定」。
   - 用 Wen 連續輸錯密碼 5 次：第 5 次起顯示「密碼錯誤次數過多，請在 15 分鐘後再試」；
     這時用 Wei 仍可登入。
   - 沒登入時直接打開 `/reports`：看到登入頁與「請重新登入」。
5. 試閒置逾時：登入後停掉伺服器，以 `CLOCK_OFFSET_MINUTES=30` 重新啟動，再點任何
   頁面，會被要求重新登入。

   ```bash
   CLOCK_OFFSET_MINUTES=30 .venv/bin/python -m app serve
   ```

6. 執行測試：應該看到 `389 passed, 472 skipped`（沒有安裝 Node 與 Playwright 時，
   瀏覽器的 2 個測試會被略過並印出原因）。

   ```bash
   .venv/bin/python -m pytest
   ```

7. 試「缺設定就拒絕啟動」：應該以非零狀態結束並指出 `DATABASE_URL`。

   ```bash
   env -u DATABASE_URL .venv/bin/python -m app serve
   ```

值得另外試、而測試沒有涵蓋的：

- 同一個帳戶在兩個瀏覽器同時登入，其中一個登出，另一個應該不受影響。
- 手機上的登入頁：版面沒有做任何樣式，只有瀏覽器預設的外觀。
- 在登入頁用鍵盤操作（Tab、Enter）走完一次登入。

畫面截圖在 [`evidence/sign-in-and-out/`](../evidence/sign-in-and-out/)。

## 情境對照

| 情境 | 是否達成 | 證據 |
| --- | --- | --- |
| S-1 登入頁依群組列出名單 | 是 | 規格 IAM-R01 的 2 個 scenario 通過；PR #9 的 verdict |
| S-2 密碼正確就登入並到自己角色的頁面 | 是 | IAM-R02；PR #9 的 verdict |
| S-3 登入失敗不透露帳戶資訊 | 是 | IAM-R03；PR #9 的 verdict |
| S-4 連續輸錯密碼鎖定 15 分鐘 | 是 | IAM-R04 至 R06 的 5 個 scenario；PR #11 的 verdict |
| S-5 同一來源一分鐘最多 10 次 | 是 | IAM-R07 的 2 個 scenario；拿掉防護後並行測試 20 次全部失敗（PR #11） |
| S-6 30 分鐘沒使用要重新登入 | 是 | IAM-R10 的 4 個 scenario；PR #10 的 verdict。其中「逾時不影響已存的資料」目前證明的是逾時不刪改任何資料列，見「有疑慮的」 |
| S-7 登出立即生效 | 是 | IAM-R11；PR #10 的 verdict |
| S-8 登入憑證受到保護 | 是 | IAM-R12；PR #10 的 verdict |
| S-9 沒登入進不了受保護的頁面 | 是 | AUD-R01；PR #9 的 verdict |
| S-10 規格的例子自動執行 | 是 | `tests/test_spec.py`、`tests/implemented_rules.txt`；PR #9 的 verdict（加入未建置的規則會失敗、同名 scenario 會被抓到） |
| S-11 本機啟動並用瀏覽器登入 | 是 | `tests/browser/`；`.claude/skills/try-yc-report/`；PR #12 的 verdict 照 README 走過一次 |
| S-12 成品可以被部署 | 是 | [CI 第 1 次執行](https://github.com/pitaya943/yc-report-v4/actions/runs/45004197644)（commit `504cbd5`）的 `image` job 每一步都成功：建置映像、映像不是以 root 執行、缺 `DATABASE_URL` 時拒絕啟動並指名、以正式設定啟動後 `/health` 回 200。其餘部分（設定檢查、`serve` 先更新資料庫結構、`/status`）見 PR #8、#12 的 verdict |
| S-13 第一位 owner 由指令建立 | 是 | `create-owner` 的測試；PR #12 的 verdict |
| S-14 上一個 task 留下的問題已處理 | 是（依 owner 同意改寫後的 S-14） | 規格的總數只寫在 `docs/spec/index.md`；`tools/check_spec.py` 核對那裡的每個數字、每一張列出 feature 的表、已開啟的規則數（對 `tests/implemented_rules.txt`），並擋下全 repo 現行文件裡常見的總數寫法。弄壞的紀錄在 PR 的 Ready 留言。其餘三項：`spec-baseline-diff.md` 的新章節；系統設計 9.3 與 9.7；附錄 B 的六個字串 |

## 我自己做的決定

完整的紀錄在 [`trail.tsv`](../trail.tsv)（Chief 與五位 builder 共 106 列）。owner 最可能
想知道的：

| 決定 | 原因 |
| --- | --- |
| 不需要 session 金鑰（系統設計原本列了 `SESSION_SECRET`） | 登入憑證與防偽造憑證都是存在資料庫的隨機值，沒有東西要簽章 |
| 登入失敗的次數在請求被拒絕時仍然寫入 | 次數必須留下來才能鎖定；這是「拒絕就整個回復」唯一的例外，寫在設計 9.2 |
| 被頻率限制擋下的那一次嘗試不計入次數；格式不對的表單也不計入 | 否則一直重試的人永遠解不開；規格說的是每分鐘「評估」10 次 |
| 沒登入時開頁面回 401 並直接顯示登入頁，不是轉址 | 規格把「未登入」綁在 401；使用者一樣看到登入頁 |
| 兩個健康頁：`/health` 公開且不含細節，`/status` 只給管理員 | 檔案儲存與金鑰有沒有設定，不該讓未登入的人看到 |
| 每個測試用一個從範本複製的資料庫 | 稽核表在資料庫層擋掉清空；並行測試需要真的多條連線 |
| HTTP 狀態碼是結果類別的屬性，不是列舉的值 | `CONFLICT` 與 `BLOCKED` 都是 409，用值的話兩者會被併成一個 |
| 群組在伺服器端可以不帶；帶了不認得的值顯示「請選擇類型」 | 附錄 B 寫群組不是必填；規格 IAM-R03 的例子只用名字登入 |
| `create-owner` 要求密碼 6 至 30 個字 | brief 假設 7 原本寫「只要求非空」；builder 採用了附錄 B 既有的密碼長度規則 |
| 來源位址不是合法的 IP 時不會造成錯誤，以長度有上限的值計算頻率 | T-04 驗證找到：信任代理時，超長的轉送值會讓登入回 500 |
| PDF 等之後才需要的設定（檔案儲存、金鑰）只判斷「有沒有設定」 | 本 task 不做那些功能，狀態頁顯示「未設定」 |
| 四張 ticket 的驗證 findings 中較小的修正，寫進下一張 ticket 一起做，沒有另開修正輪 | 每一輪修正要花一個 builder 與一個驗證；findings 都不影響當張 ticket 的結論 |
| T-03 與 T-04 合併時由 Chief 解決四個檔案的衝突，並改了 T-03 的一個測試 | 兩張各自正確，合在一起時一次登入會多寫一筆嘗試紀錄；合併後跑過完整測試 |
| CI 工作流程除了 pull request 也在 `task/**` 分支被推送時執行 | S-12 的映像要在開 PR 之前被證明；之後每個 task 也能在開 PR 前被檢查 |
| 兩輪修正都由 Chief 自己做，沒有另開 builder | 失敗的是 Chief 自己建的 S-14；每一輪都由新的獨立 session 驗證 |
| 修改了上一個 task 的文件（系統設計、未決問題、task 地圖、差異清單、舊系統取捨） | 它們是之後的 task 會讀的現行文件；brief 的 S-14 要求這些更正 |

## 沒做到或有疑慮的

- **容器映像只在 CI 上建置與啟動過，沒有部署到任何平台。** CI 的 `image` job 第一次
  執行就通過；它證明映像建得起來、能以正式設定啟動並連上資料庫。在 Railway 上的
  實際行為（平台給的埠、代理、休眠）要到部署 task 才知道。
- **CI 的三個 job 目前不是合併的必要條件。** 工作流程會在 pull request 與 `task/**`
  分支上執行，但 `main` 的保護規則沒有要求它通過。要不要設成必要檢查由 owner 在
  repository 設定裡決定。
- **CI 有一則警告**：`actions/checkout@v4` 等三個 action 使用的 Node.js 20 已被標為
  過時，目前被強制改用 Node.js 24 執行。之後要把這些 action 升到新版；`.github/` 下
  的檔案要由 owner 修改。
- **最終驗證失敗了兩次，都在 S-14 的第一項，都是 Chief 自己的工作。** 原本的寫法是
  「規格的總數不論寫在哪裡，改錯任何一處檢查都會失敗」。第一次：規則總數 137 還寫在
  檢查不到的句子裡，其中一句是本 task 自己加進規格首頁的；「已開啟 11 條」也沒有東西
  核對。第二次：修了 137 與 502，卻留下同一類的 feature 總數 31（8 處）。這是上一個
  task 記下的 pitfall 2 第二、第三次發生，而且發生在修正它的工作裡。
- **改寫後的 S-14 不是絕對的保證，這是刻意的。** 句型比對是一份清單：用清單以外的
  寫法寫出總數不會被發現（第二次驗證示範過）。所以規則改成「總數只寫在規格首頁，其他
  現行文件不寫」，寫在 `docs/spec/conventions.md`；工具核對首頁、表格與已開啟的規則數，
  並擋下常見的寫法，包含任何「N 個 feature」。
- **當時的紀錄不檢查總數。** 每個 task 的 `brief.md`、`reports/` 與
  `spec-baseline-diff.md` 寫的是當時為真的數字，之後規格增減時不該回頭修改。第二次
  驗證接受這一點，並留給 owner 決定。
- **畫面沒有樣式。** 只有瀏覽器預設的外觀（見截圖）。brief 假設 11 說版面從簡；
  導覽與外觀排在 Task 8 的檢查清單。若希望之後每個 task 的畫面都有基本樣式，應該
  在 Task 3 的 brief 提出。
- **「逾時不影響已存的資料」還沒有真的存日報。** 日報要到 Task 3 才有；目前證明的
  是逾時不刪除、不改動任何資料列。這個步驟被刻意寫成：資料庫一出現名稱含 `report`
  的資料表就會失敗，Task 3 必須把它補完。
- **各張 ticket 驗證留下、這次沒有修的 findings**（都不影響情境）：
  - 請求同時帶了空的憑證標頭與正確的表單欄位時會被拒絕（PR #10 finding 5）。
  - 測試工具預設替請求帶上防偽造憑證，所以之後的 scenario 抓不到「頁面忘了帶憑證」
    （PR #10 finding 4）；不經 HTMX 的大表單會先被整個讀完（finding 6）。
  - 瀏覽器測試分不出落地頁與拒絕頁；落地頁是否正確由規格的 scenario 把關
    （PR #12 finding 1）。
  - `create-owner` 在輸入被關掉時印出 traceback；已有 owner 時仍先問完才拒絕
    （PR #12 findings 2、3）。
  - 「15 分鐘」寫在常數與三處訊息文字；時間掃描比需要的嚴格；找空埠的函式有三份
    （PR #11 finding 4、PR #9 finding 6、PR #12 finding 5）。
  - 測試骨架用到 pytest-bdd 沒有公開的內部名稱，所以版本釘死在 9.x 的確切版本；
    升級時要一起檢查（PR #9 finding 4）。
- **登入嘗試的紀錄不會被清除。** 資料表會一直長大；清除要等排程（Task 7）。
- **以非 root 身分啟動測試用資料庫的那條路徑沒有跑過**，因為這個環境只能以 root
  執行；CI 用的是另一條路徑（外部的資料庫服務）。
- **合併 T-03 與 T-04 的那個 commit 沒有經過單張 ticket 的驗證**，只有 Chief 跑過
  完整測試；最終驗證涵蓋它。
- **預算。** owner 把時間預算延長 30 分鐘（共 4 小時 30 分）；session 用了 13 個（共 16）：
  5 個 builder、5 個 ticket 驗證、3 個最終驗證。
- **過程中碰到用量上限**（約 00:31 至 02:10 UTC 全部 session 中斷）。沒有遺失
  工作；時間預算依 owner 的決定以實際工作時間計算。

## 驗證

獨立驗證的結論會以留言貼在這個 pull request 上。五張 ticket 各自的結論在 PR #8、#9、
#10、#11、#12。

## 合併之後

發現任何不對的地方，請在追蹤 issue #6 留一則留言；下一個 task 開始時會把它讀進
`.shilaycow/pitfalls.md`。
