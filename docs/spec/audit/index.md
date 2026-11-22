# 稽核（AUD）

每個動作都重新檢查權限，並把重要動作永久記錄下來供 owner 查閱。

## 情境

下列規則已經建置，並且由測試直接執行。

### 沒登入的人進不了受保護的頁面，也不留紀錄

| Feature | 規則 | Scenario | 例子（case） |
| --- | --- | --- | --- |
| [AUD-F01 每個動作都重新檢查權限](AUD-F01-authorization-on-every-action.feature)（只含 AUD-R01） | 1 | 1 | 1 |

權限檢查與拒絕紀錄的機制已經存在，每個受保護的頁面與動作都經過它；規格的權限總表
（AUD-R02）與「每次被拒絕都留下紀錄」（AUD-R03）列的是其他領域的動作，等那些領域
建置後由「稽核與收尾」開啟。

## 規則

已決定的限制與預設寫在各 feature 檔的 `Rule:` 區塊、[`definitions.md`](../definitions.md)
與 [`reference/`](../reference/)。建置時另外決定的如下。

| 規則 | 決定它的 task |
| --- | --- |
| 找不到的頁面或資料回「找不到」（404），不留紀錄，不屬於任何結果類別 | `skeleton-and-sign-in` |
| 沒有被明確允許的動作一律拒絕，顯示「禁止存取」，並留下一筆記錄登入者與被拒絕動作的紀錄 | `skeleton-and-sign-in` |
| 稽核紀錄在資料庫層不能被修改、刪除或清空，連應用程式自己也不行 | `skeleton-and-sign-in` |
| 稽核類型只能是附錄 C 列出的類型 | `skeleton-and-sign-in` |

## 最後更動的 task

- `skeleton-and-sign-in`：建置 AUD-R01 與權限、稽核的機制。
- `system-design`：建立規格基準（來源與差異見
  [`spec-baseline-diff.md`](../../tasks/system-design/spec-baseline-diff.md)）。

## 尚未建置

owner 已同意、尚未建置的行為。每個 feature 是一個 Gherkin 檔；建置它的 task 完成後，
把它移到上面的「情境」。

| Feature | 規則 | Scenario | 例子（case） | 預定建置的 task |
| --- | --- | --- | --- | --- |
| [AUD-F01 每個動作都重新檢查權限](AUD-F01-authorization-on-every-action.feature)（AUD-R02 權限總表、AUD-R03 拒絕紀錄） | 2 | 2 | 21 | 8 稽核與收尾 |
| [AUD-F02 稽核軌跡](AUD-F02-audit-trail.feature) | 5 | 9 | 24 | 8 稽核與收尾 |
