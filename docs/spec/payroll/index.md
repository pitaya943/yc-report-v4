# 薪資（PAY）

依已確認的日報計算每個人的毛額、保留金與實發金額，保存成不會再變的薪資批次並匯出。

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
| [PAY-F01 毛額、淨額與實發](PAY-F01-gross-net-and-final-pay.feature) | 6 | 13 | 25 | 5 薪資 |
| [PAY-F02 保留金與年度上限](PAY-F02-retention-and-annual-cap.feature) | 5 | 12 | 29 | 5 薪資 |
| [PAY-F03 封存帳戶的薪資](PAY-F03-archived-accounts-in-payroll.feature) | 3 | 7 | 10 | 5 薪資 |
| [PAY-F04 年度結算](PAY-F04-year-end-settlement.feature) | 4 | 4 | 7 | 5 薪資 |
| [PAY-F05 薪資批次、匯出與現金面額](PAY-F05-payroll-runs-exports-and-cash-breakdown.feature) | 6 | 13 | 20 | 5 薪資 |
| [PAY-F06 個人統計與薪資試算](PAY-F06-personal-statistics-and-salary-trial.feature) | 4 | 7 | 10 | 5 薪資 |
| [PAY-F07 跨帳戶統計總表](PAY-F07-cross-account-summary.feature) | 3 | 4 | 5 | 5 薪資 |
