# Spike：排程歸檔與中文 PDF / Word（T-02）

拋棄式程式碼，永遠不合併。結論與重現步驟寫在 `work/system-design/T-02` 的
`docs/tasks/system-design/spikes/scheduled-jobs.md` 與
`docs/tasks/system-design/spikes/pdf-and-word-exports.md`。

```
cd spike
./run.sh          # 安裝、跑全部測試、產生 out/payroll.pdf 與 out/bank-transfer.docx
./run.sh prove    # 另外逐一破壞每個行為，確認對應的測試會失敗（約 2 分鐘）
```

需要 Python 3.11 以上與 PostgreSQL 的執行檔（`initdb`、`pg_ctl`）；測試會自己
建立並刪除一個暫時的資料庫叢集，不需要事先啟動資料庫。所有姓名、帳號與金額
都是虛構的。

- `spike_jobs/`：時鐘、到期判斷（`due.py`，純函式）、工作（`jobs.py`）、
  觸發迴圈（`trigger.py`）、FastAPI 接線（`app.py`）。
- `spike_exports/`：薪資 PDF（`payroll_pdf.py`）、銀行轉帳 Word（`bank_docx.py`）。
- `fonts/`：內附字型 Noto Sans TC Regular（SIL OFL 1.1）與它的製作方式。
- `samples/`：已產生的範例檔，可直接下載檢視。
- `prove_fail.py`：每個行為的「破壞後測試會失敗」清單。
