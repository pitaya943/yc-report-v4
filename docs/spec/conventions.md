# 規格的寫作規約

這份規格怎麼分層、scenario 怎麼寫、拒絕案例用哪些結果類別、標籤各代表什麼。
內容承襲 yc-daily-report-v3 的規格首頁；系統的整體說明與名詞表在 [`index.md`](index.md)。

**語言。** 說明文字用繁體中文。Gherkin 的關鍵字與步驟用英文，因為要與程式綁定；
使用者可見字串保留繁體中文原文，那是要被斷言的值。

**範圍。** 使用者與管理員看得到、做得到的行為：欄位、驗證、計算、匯出、錯誤、權限。
不規定資料表、API 路徑或部署方式；那些在各 task 的設計文件裡。

## 結構

規格分四層，每個事實只寫在一層。

| 層 | 回答的問題 | 位置 |
| --- | --- | --- |
| Capability | 系統為誰解決什麼問題？ | `index.md` |
| Feature | 使用者能完成哪一件事？ | 各領域資料夾裡的 `.feature` 檔 |
| Rule | 哪條商業規則必須永遠成立？ | `Rule:` 區塊，ID 如 `PAY-R03` |
| Scenario | 這條規則在具體資料下長怎樣？ | `Scenario`、`Scenario Outline` |
| 參考資料 | 目錄、欄位限制、錯誤字串 | `reference/` 的附錄 A–C，scenario 只引用 |
| 決策 | 為什麼是這個規則？ | `reference/appendix-e-decisions.md`；scenario 只帶標籤 |

## Scenario 寫作規約

1. **一個 scenario 只有一個 `When`。** 多個動作就拆成多個 scenario。
2. **宣告式，不寫 UI 步驟。** 寫「員工送出回報」，不寫「點擊送出按鈕」。UI 細節放在附錄 D。
3. **具體資料。** 邊界值用 `Scenario Outline` 加 `Examples` 表，一列就是一個測試。
4. **拒絕案例固定三斷言**：結果類別、完整錯誤字串、資料沒有任何變動。

   ```gherkin
   Then the request is rejected as <OUTCOME> with message "<訊息>"
   And nothing is written
   ```

5. **可測才寫。** 沒有數字的要求（例如「合理的延遲」）不進 scenario，放附錄 D。
6. **來源要標記。** `@provisional` 標示來自 v2 spec 暫定答案的規則；`@assumed @AD-n` 標示本規格定義的規則。兩者都已由 Kuei 於 2026-11-15 確認，標籤保留作為來源追溯；日後 Kuei 改決定時，用標籤找出所有受影響的 scenario。

## 結果類別

規格不規定 API，所以用與傳輸層無關的結果類別描述拒絕；下表把它們綁到 HTTP status（AD-9）。

| 結果類別 | 意義 | HTTP | 寫稽核 |
| --- | --- | --- | --- |
| `UNAUTHENTICATED` | 未登入或 session 過期 | 401 | 否 |
| `FORBIDDEN` | 已登入但角色或擁有權不符 | 403 | 是，`ACCESS_DENIED` |
| `INVALID` | 欄位不合附錄 B，或沒有這個動作 | 422 | 否 |
| `CONFLICT` | 資料合法但目前狀態不允許 | 409 | 否 |
| `LOCKED` | 帳戶鎖定中 | 423 | 是，鎖定當下寫 `ACCOUNT_LOCKOUT` |
| `RATE_LIMITED` | 超過來源位址頻率 | 429 | 否 |
| `BLOCKED` | 前置設定不完整（單價、金鑰） | 409 | 否 |

## 標籤

| 標籤 | 用途 |
| --- | --- |
| `@IAM-F01` | feature ID，每個檔案一個 |
| `@B-044` | 對應 v2 spec 的行為 ID |
| `@Q-041` | 對應 Kuei 的決定（附錄 E） |
| `@provisional` | 來源是 v2 spec 的暫定答案 Q-052–Q-062（已確認） |
| `@assumed @AD-n` | 來源是本規格定義的規則（`definitions.md`，已確認） |
| `@domain`、`@api`、`@ui` | 測試層級：純函式、服務邊界、端到端 |
| `@money` | 影響薪資金額，回歸測試必跑 |
| `@concurrency` | 需要真的平行請求 |

## 數字只寫一次

全規格的總數（feature、規則、scenario、例子）與「已開啟幾條規則」只寫在
[`index.md`](index.md)。其他現行文件要提到全部規則或全部例子時，不寫數字。各個 task 的
`brief.md`、`plan.md`、`tickets/`、`reports/` 與 `spec-baseline-diff.md` 是當時的紀錄，寫的是當時為真的數字，
之後規格增減時不回頭修改，檢查工具也不檢查它們的總數。

檢查工具會擋下現行文件裡常見的總數寫法（例如「全部 N 條規則」「共 N 個例子」，以及
任何「N 個 feature」），但句型是一份清單，不是證明：用清單以外的寫法寫出總數不會被
發現。所以規則是不寫，而不是寫了再靠工具抓。要提到一部分 feature 的數量時，放在表格
裡，或不用阿拉伯數字。

## 檢查

`tools/check_spec.py` 檢查每個 feature 檔是合法的 Gherkin、feature 標籤與檔名一致、
同一個 feature 裡沒有同名的 scenario、規則 ID 不重複、每個 feature 都被所屬領域的索引
連結，而且每一處寫出來的數字都與 feature 檔一致：`index.md` 的總數與各領域的數量、每一張
列出 feature 的表、全 repo 現行文件裡以常見寫法提到總數的句子，以及「已開啟幾條規則」與
`tests/implemented_rules.txt` 的行數。用法見 `index.md` 的「檢查這份規格」。
