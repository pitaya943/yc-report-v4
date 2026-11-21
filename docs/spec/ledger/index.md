# 流水帳（LED）

記錄公司的收入、支出與代墊，附上憑證檔案，並算出餘額。

## 情境

目前沒有已建置的情境。這個領域的行為都還在「尚未建置」。

## 規則

已決定的限制與預設寫在各 feature 檔的 `Rule:` 區塊、[`definitions.md`](../definitions.md)
與 [`reference/`](../reference/)。建置時另外決定的限制，由建置它的 task 記在這裡。

## 最後更動的 task

- `system-design`：建立規格基準（來源與差異見
  [`spec-baseline-diff.md`](../../tasks/system-design/spec-baseline-diff.md)）。

## 尚未建置

owner 已同意、尚未建置的行為。每個 feature 是一個 Gherkin 檔；建置它的 task 完成後，
把它移到上面的「情境」。

| Feature | 規則 | Scenario | 例子（case） | 預定建置的 task |
| --- | --- | --- | --- | --- |
| [LED-F01 流水帳紀錄與餘額](LED-F01-ledger-entries-and-balances.feature) | 6 | 10 | 23 | 7 流水帳與檔案庫 |
| [LED-F02 證據檔與作廢](LED-F02-evidence-files-and-voiding.feature) | 4 | 8 | 15 | 7 流水帳與檔案庫 |
