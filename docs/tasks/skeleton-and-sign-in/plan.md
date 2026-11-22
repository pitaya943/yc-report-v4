# Plan：skeleton-and-sign-in

一個里程碑；task 完成時一次交付（merge_unit: task）。謹慎程度是「謹慎」：每張 ticket
合併進 `task/skeleton-and-sign-in` 之前，先由沒有參與建置的獨立 session 驗證。

| 項目 | 服務的情境 | 誰做 | 依賴 | 可並行 |
| --- | --- | --- | --- | --- |
| T-01 核心骨架：設定、時鐘、資料庫、拒絕、權限、稽核 | S-12 的一部分；其餘的地基 | builder | 無 | 與 C-1 |
| T-02 規格執行器、登入與落地頁 | S-1、S-2、S-3、S-9、S-10 | builder | T-01 | 否 |
| T-03 Session 期限、登出、防偽造 | S-6、S-7、S-8 | builder | T-02 | 與 T-04 |
| T-04 登入鎖定與頻率限制 | S-4、S-5 | builder | T-02 | 與 T-03 |
| T-05 指令、狀態頁、容器映像、瀏覽器測試、try-it skill | S-11、S-12、S-13 | builder | T-03、T-04 | 否 |
| C-1 上個 task 的 findings、規格字串、task 地圖 | S-14 | Chief | 無 | 與 T-01 |
| C-2 規格更新、blast radius、報告、PR、最終驗證 | 全部 | Chief + verifier | 以上全部 | 否 |

Session 預算（16）：5 個 builder、5 個 ticket 驗證、1 個最終驗證，共 11；剩下 5 個留給
修正輪（一輪是 1 個 builder 加 1 個驗證）。

## 結果

T-01 至 T-05 各自通過獨立驗證（PR #8 至 #12）並合併進 `task/skeleton-and-sign-in`；
C-1 完成。S-12 的容器映像由 owner 加入的 CI 證明（issue #7，第 1 次執行通過）。
用了 5 個 builder 與 5 個 ticket 驗證，沒有修正輪；各張 ticket 驗證留下的較小問題
寫進下一張 ticket 一起處理。
