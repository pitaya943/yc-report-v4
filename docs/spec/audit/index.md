# 稽核（AUD）

每個動作都重新檢查權限，並把重要動作永久記錄下來供 owner 查閱。

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
| [AUD-F01 每個動作都重新檢查權限](AUD-F01-authorization-on-every-action.feature) | 3 | 3 | 22 | 2 骨架與登入 |
| [AUD-F02 稽核軌跡](AUD-F02-audit-trail.feature) | 5 | 9 | 24 | 8 稽核與收尾 |
