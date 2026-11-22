# 身分與帳戶（IAM）

讓每個人以自己的身分登入，並讓管理員管理帳戶、角色、密碼與每個人的薪資設定。

## 情境

下列 feature 已經建置；每個 Gherkin 檔裡的 scenario 就是現在成立的行為，並且由測試
直接執行（`tests/implemented_rules.txt` 列出已開啟的規則）。

### 登入：選群組、選名字、輸入密碼

### 密碼錯太多次被鎖定，以及同一來源的登入頻率上限

### 閒置逾時、登出與登入憑證的保護

| Feature | 規則 | Scenario | 例子（case） |
| --- | --- | --- | --- |
| [IAM-F01 登入](IAM-F01-sign-in.feature) | 3 | 4 | 10 |
| [IAM-F02 登入鎖定與頻率限制](IAM-F02-sign-in-lockout-and-rate-limit.feature) | 4 | 7 | 10 |
| [IAM-F03 Session 與登出](IAM-F03-session-and-sign-out.feature) | 3 | 8 | 9 |

「Session 與登出」裡的「逾時不影響已存的資料」目前證明的是逾時不會刪除或改動任何
已存的資料列；等日報建置後，由那個 task 改成真的存一筆日報再逾時。

## 規則

已決定的限制與預設寫在各 feature 檔的 `Rule:` 區塊、[`definitions.md`](../definitions.md)
與 [`reference/`](../reference/)。建置時另外決定的如下。

| 規則 | 決定它的 task |
| --- | --- |
| 登入時群組可以不帶；帶了卻不是管理員、西區、南區之一，顯示「請選擇類型」。沒有名字，或名字不在所選群組的名單內，顯示「請選擇帳戶」 | `skeleton-and-sign-in` |
| 名稱、群組含有無法儲存的字元時，分別當作沒選帳戶、沒選類型；密碼含有這類字元時當作密碼錯誤 | `skeleton-and-sign-in` |
| 同一個來源 60 秒內最多 10 次登入嘗試；超過的那一次顯示「登入嘗試過於頻繁，請稍後再試」，而且不計入次數。格式不對而被擋下的表單也不計入 | `skeleton-and-sign-in` |
| 來源位址只信任部署平台的代理加上的那一段；信任幾層代理是設定值，本機為 0 | `skeleton-and-sign-in` |
| 鎖定期間的登入嘗試不驗證密碼、不增加失敗次數、不延長鎖定 | `skeleton-and-sign-in` |
| 對不存在或已封存的名字輸錯密碼，不改變任何帳戶，但仍計入來源的頻率 | `skeleton-and-sign-in` |
| 閒置時間只由成功辨識出登入者的請求延長；逾時的登入狀態不能再使用，即使時鐘之後被往回調 | `skeleton-and-sign-in` |
| 同一個人可以同時在多個裝置登入，各自計算閒置時間 | `skeleton-and-sign-in` |
| 登入用的 cookie 關掉瀏覽器就消失（沒有「記住我」） | `skeleton-and-sign-in` |
| 帶著登入狀態、會改變資料的請求要帶防偽造憑證（標頭或表單欄位）；不符時顯示「請求未通過驗證」並留下拒絕紀錄。登入本身不需要憑證 | `skeleton-and-sign-in` |
| 未登入或逾時顯示「請重新登入」；登出後顯示「您已登出」 | `skeleton-and-sign-in` |
| 登入失敗次數與來源的嘗試紀錄存在資料庫，多個行程與重啟後都成立。嘗試紀錄目前不會被清除 | `skeleton-and-sign-in` |
| 帳戶在這個階段只能由指令建立：一次性的 owner 建立指令，以及只在非正式環境可用的示範帳戶指令 | `skeleton-and-sign-in` |

## 最後更動的 task

- `skeleton-and-sign-in`：建置登入、鎖定與頻率限制、session 與登出（IAM-F01 至 F03）。
- `system-design`：建立規格基準（來源與差異見
  [`spec-baseline-diff.md`](../../tasks/system-design/spec-baseline-diff.md)）。

## 尚未建置

owner 已同意、尚未建置的行為。每個 feature 是一個 Gherkin 檔；建置它的 task 完成後，
把它移到上面的「情境」。

| Feature | 規則 | Scenario | 例子（case） | 預定建置的 task |
| --- | --- | --- | --- | --- |
| [IAM-F04 帳戶生命週期與薪資設定](IAM-F04-account-lifecycle-and-pay-settings.feature) | 7 | 16 | 39 | 4 帳戶與設定 |
| [IAM-F05 Owner 管理管理員](IAM-F05-owner-manages-administrators.feature) | 3 | 6 | 11 | 4 帳戶與設定 |
| [IAM-F06 密碼變更與重設](IAM-F06-password-change-and-reset.feature) | 3 | 5 | 10 | 4 帳戶與設定 |
| [IAM-F07 銀行帳號遮罩與顯示](IAM-F07-bank-number-masking-and-reveal.feature) | 4 | 7 | 14 | 4 帳戶與設定 |
