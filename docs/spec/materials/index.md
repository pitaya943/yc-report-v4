# 材料（MAT）

讓員工申請材料、管理員審核，並維持庫存數字永遠對得起來。

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
| [MAT-F01 申請材料](MAT-F01-request-materials.feature) | 5 | 9 | 22 | 6 材料 |
| [MAT-F02 審核材料申請](MAT-F02-review-material-requests.feature) | 4 | 7 | 12 | 6 材料 |
| [MAT-F03 庫存匯入與暫存區](MAT-F03-inventory-import-and-quarantine.feature) | 2 | 6 | 15 | 6 材料 |
| [MAT-F04 庫存管理](MAT-F04-inventory-administration.feature) | 8 | 14 | 26 | 6 材料 |
