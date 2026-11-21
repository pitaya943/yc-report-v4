# Plan：system-design

一個里程碑；task 完成時一次交付（merge_unit: task）。

| 項目 | 服務的情境 | 誰做 | 依賴 | 可並行 |
| --- | --- | --- | --- | --- |
| T-01 風險試作：檔案與過期連結、銀行帳號加密 | S-6 (a)(c)、S-9 | builder | 無 | 與 T-02、C-* 並行 |
| T-02 風險試作：排程歸檔、中文 PDF 與 Word | S-6 (b)(d)、S-9 | builder | 無 | 與 T-01、C-* 並行 |
| C-1 規格基準匯入、差異清單、語法檢查 | S-1、S-2、S-3 | Chief | 無 | 是 |
| C-2 舊系統取捨紀錄 | S-4 | Chief | 無 | 是 |
| C-3 未決問題與預設答案 | S-7 | Chief | C-1 | 是 |
| C-4 系統設計（含部署） | S-5、S-9 | Chief | T-01、T-02 的結論 | 初稿可先寫 |
| C-5 後續 task 地圖 | S-8 | Chief | C-1 | 是 |
| C-6 報告、PR、獨立驗證 | 全部 | Chief + verifier | 以上全部 | 否 |

C-* 是文件工作，由 Chief 自己做，不另開 ticket；最後由沒有參與建置的獨立 session
驗證整個 PR。
