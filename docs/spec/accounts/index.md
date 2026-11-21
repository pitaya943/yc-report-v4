# 身分與帳戶（IAM）

讓每個人以自己的身分登入，並讓管理員管理帳戶、角色、密碼與每個人的薪資設定。

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
| [IAM-F01 登入](IAM-F01-sign-in.feature) | 3 | 4 | 10 | 2 骨架與登入 |
| [IAM-F02 登入鎖定與頻率限制](IAM-F02-sign-in-lockout-and-rate-limit.feature) | 4 | 7 | 10 | 2 骨架與登入 |
| [IAM-F03 Session 與登出](IAM-F03-session-and-sign-out.feature) | 3 | 8 | 9 | 2 骨架與登入 |
| [IAM-F04 帳戶生命週期與薪資設定](IAM-F04-account-lifecycle-and-pay-settings.feature) | 7 | 16 | 39 | 4 帳戶與設定 |
| [IAM-F05 Owner 管理管理員](IAM-F05-owner-manages-administrators.feature) | 3 | 6 | 11 | 4 帳戶與設定 |
| [IAM-F06 密碼變更與重設](IAM-F06-password-change-and-reset.feature) | 3 | 5 | 10 | 4 帳戶與設定 |
| [IAM-F07 銀行帳號遮罩與顯示](IAM-F07-bank-number-masking-and-reveal.feature) | 4 | 7 | 14 | 4 帳戶與設定 |
