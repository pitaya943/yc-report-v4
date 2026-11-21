# 風險試作：檔案儲存與會過期的下載連結

Ticket：T-01，問題 (a)。服務情境 S-6 (a) 與 S-9「本機與正式環境同一套程式」。
試作程式在分支 `spike/system-design-storage-crypto`（commit `ea9b9d4`），不會合併；
本文件是留下來的紀錄。

## 問題

產品對檔案有四項要求，要在設計定案前確認做得到，而且本機與正式環境跑同一套程式：

1. 每次開啟檔案都發一條新的連結，剛好存活 3,600 秒：發出 3,599 秒時還能開，
   3,600 秒時不能開。連結本身不存進資料庫。
2. 收據只收 PDF、JPEG、PNG、WebP，上限 10 MB：10 MB 收，10 MB + 1 byte 拒絕，
   GIF 拒絕。
3. 被取代的舊檔和現行檔一樣可以開啟；刪除一筆檔案庫紀錄時，它存的檔案一併刪除。
4. 沒有設定檔案儲存時，系統其他部分照常運作：紀錄照樣建立但不含檔案，下載時
   顯示檔案無法使用的警告。

## 試了什麼

一個小型 FastAPI 應用程式加上 46 個測試，全部在本機執行，不連任何外部服務。

- **一個儲存介面、三種模式**（`spike/storage.py`）：本機目錄、S3 相容物件儲存、
  「未設定」。用哪一種只由設定決定（`STORAGE_BACKEND` 是 `local`、`s3` 或不設）。
  S3 那一種用 `boto3` 連到本機的 `moto` 伺服器（S3 的本機替身），走的是真正的
  HTTP 與 S3 協定。同一批測試對本機目錄與 S3 各跑一次（測試名稱後面的 `[local]`
  與 `[s3]`）。
- **連結由應用程式自己簽發、自己判斷過期**（`spike/links.py`）：連結是一段簽章過
  的字串，裡面放檔案位置與到期時間（發出時間 + 3,600 秒），用 `itsdangerous` 簽章。
  檢查時只需要簽章金鑰與時鐘，不查資料庫，所以連結不需要儲存。時間一律來自注入的
  時鐘；測試把時鐘設在 2030 年並手動往前撥。
- **檔案類型看檔案開頭的位元組**（`spike/receipts.py`），不看副檔名，也不看上傳時
  宣告的 content type。
- **另一個選項**：讓物件儲存自己產生會過期的 presigned URL。寫了一支小程式
  （`experiments/presigned_on_moto.py`）實際試給 `moto` 看。

## 結果

四項要求全部做得到，本機目錄與 S3 兩種儲存的結果完全相同。

指令 `./run.sh tests/test_links.py tests/test_storage.py tests/test_files_app.py`
的實際輸出（省略開頭的環境資訊與一則套件的 deprecation 警告）：

```
collecting ... collected 46 items

tests/test_links.py::test_a_link_issued_3599_seconds_ago_still_resolves PASSED [  2%]
tests/test_links.py::test_a_link_issued_3600_seconds_ago_no_longer_works PASSED [  4%]
tests/test_links.py::test_a_link_altered_after_issue_is_rejected PASSED  [  6%]
tests/test_links.py::test_a_link_signed_with_another_key_is_rejected PASSED [  8%]
tests/test_storage.py::test_a_stored_file_reads_back_byte_for_byte[local] PASSED [ 10%]
tests/test_storage.py::test_a_stored_file_reads_back_byte_for_byte[s3] PASSED [ 13%]
tests/test_storage.py::test_opening_a_key_that_was_never_stored_says_so[local] PASSED [ 15%]
tests/test_storage.py::test_opening_a_key_that_was_never_stored_says_so[s3] PASSED [ 17%]
tests/test_storage.py::test_delete_removes_the_file_from_the_backend[local] PASSED [ 19%]
tests/test_storage.py::test_delete_removes_the_file_from_the_backend[s3] PASSED [ 21%]
tests/test_storage.py::test_deleting_a_missing_key_is_not_an_error[local] PASSED [ 23%]
tests/test_storage.py::test_deleting_a_missing_key_is_not_an_error[s3] PASSED [ 26%]
tests/test_storage.py::test_no_storage_settings_means_not_configured_rather_than_a_crash PASSED [ 28%]
tests/test_storage.py::test_local_storage_refuses_a_key_that_points_outside_its_directory PASSED [ 30%]
tests/test_files_app.py::test_an_uploaded_file_downloads_through_its_link[local] PASSED [ 32%]
tests/test_files_app.py::test_an_uploaded_file_downloads_through_its_link[s3] PASSED [ 34%]
tests/test_files_app.py::test_link_works_at_3599_seconds_and_stops_at_3600[local] PASSED [ 36%]
tests/test_files_app.py::test_link_works_at_3599_seconds_and_stops_at_3600[s3] PASSED [ 39%]
tests/test_files_app.py::test_every_open_issues_a_fresh_link_with_its_own_hour[local] PASSED [ 41%]
tests/test_files_app.py::test_every_open_issues_a_fresh_link_with_its_own_hour[s3] PASSED [ 43%]
tests/test_files_app.py::test_exactly_10_mb_is_accepted[local] PASSED    [ 45%]
tests/test_files_app.py::test_exactly_10_mb_is_accepted[s3] PASSED       [ 47%]
tests/test_files_app.py::test_10_mb_plus_one_byte_is_refused_and_nothing_is_stored[local] PASSED [ 50%]
tests/test_files_app.py::test_10_mb_plus_one_byte_is_refused_and_nothing_is_stored[s3] PASSED [ 52%]
tests/test_files_app.py::test_pdf_jpeg_png_and_webp_are_accepted[local-pdf] PASSED [ 54%]
tests/test_files_app.py::test_pdf_jpeg_png_and_webp_are_accepted[local-jpeg] PASSED [ 56%]
tests/test_files_app.py::test_pdf_jpeg_png_and_webp_are_accepted[local-png] PASSED [ 58%]
tests/test_files_app.py::test_pdf_jpeg_png_and_webp_are_accepted[local-webp] PASSED [ 60%]
tests/test_files_app.py::test_pdf_jpeg_png_and_webp_are_accepted[s3-pdf] PASSED [ 63%]
tests/test_files_app.py::test_pdf_jpeg_png_and_webp_are_accepted[s3-jpeg] PASSED [ 65%]
tests/test_files_app.py::test_pdf_jpeg_png_and_webp_are_accepted[s3-png] PASSED [ 67%]
tests/test_files_app.py::test_pdf_jpeg_png_and_webp_are_accepted[s3-webp] PASSED [ 69%]
tests/test_files_app.py::test_a_gif_is_refused[local] PASSED             [ 71%]
tests/test_files_app.py::test_a_gif_is_refused[s3] PASSED                [ 73%]
tests/test_files_app.py::test_a_gif_is_refused_even_when_named_and_declared_as_a_pdf[local] PASSED [ 76%]
tests/test_files_app.py::test_a_gif_is_refused_even_when_named_and_declared_as_a_pdf[s3] PASSED [ 78%]
tests/test_files_app.py::test_the_served_type_comes_from_the_file_not_from_what_the_sender_said[local] PASSED [ 80%]
tests/test_files_app.py::test_the_served_type_comes_from_the_file_not_from_what_the_sender_said[s3] PASSED [ 82%]
tests/test_files_app.py::test_a_replaced_file_stays_openable_beside_the_current_one[local] PASSED [ 84%]
tests/test_files_app.py::test_a_replaced_file_stays_openable_beside_the_current_one[s3] PASSED [ 86%]
tests/test_files_app.py::test_deleting_an_archive_removes_its_stored_files[local] PASSED [ 89%]
tests/test_files_app.py::test_deleting_an_archive_removes_its_stored_files[s3] PASSED [ 91%]
tests/test_files_app.py::test_without_storage_the_record_is_created_without_a_file PASSED [ 93%]
tests/test_files_app.py::test_without_storage_the_rest_of_the_system_keeps_working PASSED [ 95%]
tests/test_files_app.py::test_without_storage_a_download_attempt_warns_the_file_is_unavailable[local] PASSED [ 97%]
tests/test_files_app.py::test_without_storage_a_download_attempt_warns_the_file_is_unavailable[s3] PASSED [100%]

======================== 46 passed, 1 warning in 2.62s =========================
```

要求與測試的對照：

| 要求 | 測試（`tests/` 底下） |
| --- | --- |
| 3,599 秒可開、3,600 秒不可開 | `test_links.py` 的兩個邊界測試；`test_files_app.py::test_link_works_at_3599_seconds_and_stops_at_3600`（經由 HTTP，兩種儲存） |
| 每次開啟都是新連結、連結不儲存 | `test_every_open_issues_a_fresh_link_with_its_own_hour` |
| 10 MB 收、10 MB + 1 byte 拒絕 | `test_exactly_10_mb_is_accepted`、`test_10_mb_plus_one_byte_is_refused_and_nothing_is_stored` |
| 四種類型收、GIF 拒絕 | `test_pdf_jpeg_png_and_webp_are_accepted`、`test_a_gif_is_refused`、`test_a_gif_is_refused_even_when_named_and_declared_as_a_pdf` |
| 舊檔仍可開啟 | `test_a_replaced_file_stays_openable_beside_the_current_one` |
| 刪除紀錄時刪除檔案 | `test_deleting_an_archive_removes_its_stored_files`（直接到儲存後端確認檔案不見了） |
| 未設定儲存時照常運作 | 三個 `test_without_storage_...` 測試 |

### 這些測試真的會失敗嗎

`experiments/break_each_behaviour.py` 一次故意弄壞一項行為（在暫存的複本上，不動
原始檔），重跑測試，列出哪些測試因此失敗。34 項破壞全部被測試抓到，其中與本問題
有關的 19 項如下（每項只列一個失敗的測試；完整清單執行該程式即可看到）：

| 故意弄壞的行為 | 因此失敗的測試 |
| --- | --- |
| 3,600 秒時連結仍可用 | `test_a_link_issued_3600_seconds_ago_no_longer_works` |
| 連結只活 3,599 秒 | `test_a_link_issued_3599_seconds_ago_still_resolves` |
| 過期判斷改讀系統時間 | `test_a_link_issued_3600_seconds_ago_no_longer_works` |
| 到期時間改用系統時間計算 | `test_a_link_issued_3599_seconds_ago_still_resolves` |
| 不檢查連結簽章 | `test_a_link_altered_after_issue_is_rejected` |
| 連結被記住並重複使用 | `test_every_open_issues_a_fresh_link_with_its_own_hour` |
| 10 MB + 1 byte 被接受 | `test_10_mb_plus_one_byte_is_refused_and_nothing_is_stored` |
| 剛好 10 MB 被拒絕 | `test_exactly_10_mb_is_accepted` |
| GIF 被接受 | `test_a_gif_is_refused` |
| WebP 被拒絕 | `test_pdf_jpeg_png_and_webp_are_accepted[...-webp]` |
| 類型改採上傳者宣告的 | `test_a_gif_is_refused_even_when_named_and_declared_as_a_pdf` |
| 下載時回傳上傳者宣告的類型 | `test_the_served_type_comes_from_the_file_not_from_what_the_sender_said` |
| 新檔覆蓋舊檔 | `test_a_replaced_file_stays_openable_beside_the_current_one` |
| 刪除紀錄但檔案留在儲存裡 | `test_deleting_an_archive_removes_its_stored_files` |
| 本機儲存的刪除沒作用 | `test_delete_removes_the_file_from_the_backend[local]` |
| S3 儲存的刪除沒作用 | `test_delete_removes_the_file_from_the_backend[s3]` |
| 沒有儲存設定時程式直接掛掉 | `test_without_storage_the_rest_of_the_system_keeps_working` |
| 未設定儲存時上傳失敗 | `test_without_storage_the_record_is_created_without_a_file` |
| 未設定儲存時下載沒有警告 | `test_without_storage_a_download_attempt_warns_the_file_is_unavailable` |

### 另一個選項實際試的結果

`.venv/bin/python experiments/presigned_on_moto.py` 的實際輸出（省略 `moto` 自己印
的存取紀錄）：

```
presigned URL lifetime: 2 seconds
fetched at once:         HTTP 200, 14 bytes
fetched 4 seconds later: HTTP 200, 14 bytes
```

也就是說：本機的 S3 替身不會讓 presigned URL 過期。如果過期交給物件儲存判斷，
3,599 / 3,600 這條規則在本機與測試裡就驗不到。

## 從零重現

需要 Python 3.13 與能連到 PyPI 的網路，不需要其他服務、帳號或金鑰。

```
git clone https://github.com/pitaya943/yc-report-v4
cd yc-report-v4
git checkout spike/system-design-storage-crypto
cd spike/storage_crypto
./run.sh tests/test_links.py tests/test_storage.py tests/test_files_app.py
```

`run.sh` 會建立 `.venv`、安裝 `requirements.txt` 裡固定版本的套件，然後跑測試。
預期最後一行是 `46 passed`（另有一則 deprecation 警告，可忽略）。不帶參數執行
`./run.sh` 會連同銀行帳號的測試一起跑，預期 `68 passed`。

接著可以執行（都在 `spike/storage_crypto` 目錄下）：

```
.venv/bin/python experiments/break_each_behaviour.py
.venv/bin/python experiments/presigned_on_moto.py
```

第一支預期最後一行是 `34 of 34 breaks were caught by a test`（約需一至兩分鐘）；
第二支預期印出上一節那三行。

## 建議產品採用的做法

**應用程式簽發連結並判斷過期；檔案經由應用程式下載；儲存只負責放、取、刪。**

介面（產品重新寫，不搬試作的程式碼）：

```python
class Storage(Protocol):
    configured: bool                            # 未設定時為 False
    def put(self, key: str, data: bytes) -> None: ...
    def open(self, key: str) -> Iterator[bytes]: ...   # 分塊讀出，找不到丟 FileNotStored
    def delete(self, key: str) -> None: ...            # 檔案不存在不算錯

class LinkSigner:                               # 建構時給簽章金鑰與 Clock
    def issue(self, key: str) -> str: ...       # 到期時間 = clock.now() + 3600 秒
    def resolve(self, token: str) -> str: ...   # 丟 LinkInvalid 或 LinkExpired

def check_receipt(data: bytes) -> str: ...      # 回傳偵測到的 content type，或丟出拒絕原因
```

設定（環境變數），本機與正式環境只差這幾個值：

| 變數 | 本機 / 測試 | 正式環境 |
| --- | --- | --- |
| `STORAGE_BACKEND` | `local`（測試另跑 `s3` 對 `moto`） | `s3` |
| `STORAGE_LOCAL_DIR` | 一個目錄 | 不設 |
| `S3_ENDPOINT_URL`、`S3_BUCKET`、`S3_REGION`、`S3_ACCESS_KEY_ID`、`S3_SECRET_ACCESS_KEY` | 測試時指向 `moto` | 物件儲存服務給的值 |
| `LINK_SIGNING_KEY` | 任意字串 | 一把隨機產生的密鑰 |

`STORAGE_BACKEND` 不設就是「未設定」模式，不是錯誤。

這次定下來的幾個細節：

- **類型以檔案開頭的位元組為準。** 副檔名與宣告的 content type 都是上傳的人填的，
  改一下就能偽裝；開頭位元組才是檔案實際的樣子。下載時回傳的 content type 也用
  偵測到的那個，並加上 `X-Content-Type-Options: nosniff`，所以偽裝成別種類型的檔案
  不會被瀏覽器當成網頁執行。副作用：一張副檔名寫成 `.html` 的 PNG 會被接受，並以
  `image/png` 回傳。
- **10 MB 指 10 × 1024 × 1024 = 10,485,760 bytes。**
- **每個檔案用不重複的儲存位置**（`archives/<紀錄 id>/<隨機字串>`），取代只是新增
  一筆，不覆蓋，所以舊檔自然還在。
- **連結過期回 HTTP 410，連結被竄改或檔案已刪除回 404，儲存未設定回 503 加警告
  文字。** 警告與錯誤的確切文字以規格為準，試作裡的字只是暫代。
- 同一秒內對同一個檔案開兩次會得到相同的連結字串（內容相同，簽章自然相同）；
  它仍然沒有被儲存，也仍在同一時間過期。

### 這個做法在正式環境的代價

- **每一次下載都經過應用程式**：檔案從物件儲存到應用程式、再到使用者，流量算兩段，
  應用程式主機的對外流量會計費。單檔上限 10 MB、使用者數百人，量不大，但沒有實測。
- **下載期間佔用應用程式一個工作執行緒**。試作以 64 KB 分塊串流，記憶體不隨檔案
  大小增加；同時下載的人很多時要留意執行緒數量。
- **多一把要保管的金鑰**（`LINK_SIGNING_KEY`）。換掉它會讓已發出的連結全部失效，
  最多影響一小時內發出的連結。跑多個應用程式實例時，每個實例要用同一把。

## 衡量過的另一個選項與代價

**讓物件儲存產生 presigned URL，使用者直接向物件儲存下載。**

- 好處：下載不經過應用程式，省流量也不佔執行緒。
- 代價一：過期由物件儲存用它自己的時間判斷，注入的時鐘管不到，違反「所有時間來自
  同一個可注入的時鐘」；3,599 / 3,600 的邊界在測試裡無法證明（上面實測 `moto`
  根本不檢查過期）。
- 代價二：本機目錄沒有 presigned URL，本機就得另寫一套連結機制，本機與正式環境
  不再是同一套程式，違反 S-9。
- 代價三：連結一旦發出，應用程式就收不回來；刪除紀錄後舊連結的行為取決於物件儲存。

如果之後下載流量真的成為成本問題，可以改成「應用程式先驗自己的連結，通過後轉址到
一條只活幾十秒的 presigned URL」：過期規則仍由應用程式與時鐘決定。這個折衷沒有
試作。

## 在有真正的正式服務之前無法證明的事

- `S3Storage` 只對 `moto` 跑過。Supabase Storage 的 S3 相容端點或 Cloudflare R2
  是否接受相同的設定（path-style 位址、region 的值、權限範圍）要等有帳號才能確認；
  預期只需要改設定值。
- 正式環境的下載速度、流量費用、同時下載的上限，沒有量過。
- 上傳時試作最多把 10 MB + 1 byte 讀進記憶體後才判斷大小，但沒有在更前面擋掉超大
  的請求（例如 1 GB 的上傳會先被框架寫到暫存磁碟）。產品要在應用程式或前面的代理
  層限制請求大小，這一點沒有試作。
- 刪除紀錄時「資料庫的列」與「儲存裡的檔案」不在同一個交易裡。試作的紀錄放在記憶體
  裡，沒有試中途失敗的情況（例如刪到一半儲存服務斷線會留下孤兒檔案）。
- 儲存原本有設定、後來設定被拿掉時的下載警告已試過；儲存有設定但服務暫時連不上
  （逾時、5xx）時要顯示什麼，沒有試。
