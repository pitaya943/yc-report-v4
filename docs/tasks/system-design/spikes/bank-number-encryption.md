# 風險試作：銀行帳號加密

Ticket：T-01，問題 (c)。服務情境 S-6 (c) 與 S-9「本機與正式環境同一套程式」。
試作程式在分支 `spike/system-design-storage-crypto`（commit `ea9b9d4`），不會合併；
本文件是留下來的紀錄。試作沒有用到任何真實的銀行帳號或金鑰。

## 問題

產品對銀行帳號有三項要求，要在設計定案前確認做得到：

1. 預設只顯示末四碼；帳號持有人與管理者可以看完整的 14 位數字。
2. 存下來的值不含明文帳號。
3. 加密金鑰不存在時：檢視顯示「無法讀取」；修改被拒絕，訊息是
   「銀行帳號目前無法讀取，無法修改」，而且什麼都不寫入；其他功能照常運作。

另外要回答：用哪個維護中的函式庫、金鑰怎麼由設定提供、日後怎麼換金鑰而不遺失
資料、末四碼的顯示需不需要金鑰，以及金鑰錯誤、密文損壞、金鑰不存在時各會怎樣。

## 試了什麼

`spike/bank.py`（約 150 行）加上 22 個測試，全部在本機執行。

- **加密**：`cryptography` 套件的 AES-256-GCM（`AESGCM`），屬於 authenticated
  encryption：密文被改過或金鑰不對，解密會明確失敗，不會解出亂碼。沒有自己寫任何
  密碼演算法。
- **存的格式**：`v1.<金鑰代號>.<base64(nonce + 密文 + 驗證碼)>`，一個 62 字元左右的
  字串，例如 `v1.k1.tDR9nkvaHFiN4uCe-ivN0_14QsNvSpLo1gkSFZ5j3_UBuao47Ns4JyBS`
  （這是測試用金鑰加密測試用號碼的結果）。金鑰代號跟著密文一起存，所以看一列就
  知道它是哪一把金鑰加密的。
- **綁定帳戶**：加密時把帳戶 id 當成 associated data 一起驗證，所以把甲的密文複製
  到乙的欄位會解不開。
- **金鑰由設定提供**：`BANK_KEYS="代號:金鑰,代號:金鑰"` 列出所有可用來解密的金鑰，
  `BANK_KEY_CURRENT` 指定用哪一把加密。兩個都不設就是「沒有金鑰」模式，程式照常
  啟動。
- **換金鑰**：三步驟，每一步資料都讀得到（見下方「建議」）。
- **末四碼**：解密後取末四碼，不另外存。
- 同一個 FastAPI 試作應用程式裡加了三個銀行帳號的端點，用來確認沒有金鑰時檔案
  上傳下載等其他功能照常運作。

## 結果

三項要求全部做得到；金鑰錯誤、密文損壞、金鑰不存在三種情況的行為一致：檢視顯示
「無法讀取」、修改被拒絕、原本存的值一個位元都不變。

指令 `./run.sh tests/test_bank.py` 的實際輸出（省略開頭的環境資訊與一則套件的
deprecation 警告）：

```
collecting ... collected 22 items

tests/test_bank.py::test_by_default_only_the_last_four_digits_are_shown PASSED [  4%]
tests/test_bank.py::test_the_holder_can_reveal_the_full_number PASSED    [  9%]
tests/test_bank.py::test_an_administrator_can_reveal_the_full_number PASSED [ 13%]
tests/test_bank.py::test_another_employee_cannot_reveal_the_full_number PASSED [ 18%]
tests/test_bank.py::test_the_stored_value_never_contains_the_plain_number PASSED [ 22%]
tests/test_bank.py::test_the_same_number_stored_twice_gives_two_different_values PASSED [ 27%]
tests/test_bank.py::test_a_number_that_is_not_14_digits_is_refused PASSED [ 31%]
tests/test_bank.py::test_missing_key_viewing_shows_unreadable PASSED     [ 36%]
tests/test_bank.py::test_missing_key_editing_is_refused_and_nothing_is_written PASSED [ 40%]
tests/test_bank.py::test_missing_key_every_other_feature_keeps_working PASSED [ 45%]
tests/test_bank.py::test_wrong_key_shows_unreadable_and_refuses_editing PASSED [ 50%]
tests/test_bank.py::test_a_value_whose_key_id_is_not_configured_shows_unreadable PASSED [ 54%]
tests/test_bank.py::test_corrupted_ciphertext_shows_unreadable_and_refuses_editing[tag-changed] PASSED [ 59%]
tests/test_bank.py::test_corrupted_ciphertext_shows_unreadable_and_refuses_editing[ciphertext-changed] PASSED [ 63%]
tests/test_bank.py::test_corrupted_ciphertext_shows_unreadable_and_refuses_editing[truncated] PASSED [ 68%]
tests/test_bank.py::test_corrupted_ciphertext_shows_unreadable_and_refuses_editing[empty-payload] PASSED [ 72%]
tests/test_bank.py::test_corrupted_ciphertext_shows_unreadable_and_refuses_editing[not-a-stored-value] PASSED [ 77%]
tests/test_bank.py::test_corrupted_ciphertext_shows_unreadable_and_refuses_editing[plain-number-in-the-column] PASSED [ 81%]
tests/test_bank.py::test_a_value_copied_onto_another_account_does_not_decrypt PASSED [ 86%]
tests/test_bank.py::test_rotating_the_key_loses_no_data PASSED           [ 90%]
tests/test_bank.py::test_keys_are_read_from_configuration PASSED         [ 95%]
tests/test_bank.py::test_no_key_settings_means_no_key_rather_than_a_crash PASSED [100%]

======================== 22 passed, 1 warning in 0.32s =========================
```

要求與測試的對照：

| 要求 | 測試（`tests/test_bank.py`） |
| --- | --- |
| 預設只顯示末四碼 | `test_by_default_only_the_last_four_digits_are_shown`（`12345678905678` 顯示為 `**********5678`） |
| 持有人與管理者可看完整號碼，其他人不行 | `test_the_holder_can_reveal_the_full_number`、`test_an_administrator_can_reveal_the_full_number`、`test_another_employee_cannot_reveal_the_full_number` |
| 存的值不含明文 | `test_the_stored_value_never_contains_the_plain_number`、`test_the_same_number_stored_twice_gives_two_different_values` |
| 金鑰不存在：檢視顯示「無法讀取」 | `test_missing_key_viewing_shows_unreadable` |
| 金鑰不存在：修改被拒絕且不寫入 | `test_missing_key_editing_is_refused_and_nothing_is_written` |
| 金鑰不存在：其他功能照常 | `test_missing_key_every_other_feature_keeps_working`（經由 HTTP：健康檢查、上傳、發連結、下載都成功） |
| 金鑰錯誤 | `test_wrong_key_shows_unreadable_and_refuses_editing`、`test_a_value_whose_key_id_is_not_configured_shows_unreadable` |
| 密文損壞 | `test_corrupted_ciphertext_shows_unreadable_and_refuses_editing`（六種損壞方式） |
| 換金鑰不遺失資料 | `test_rotating_the_key_loses_no_data` |
| 金鑰來自設定 | `test_keys_are_read_from_configuration`、`test_no_key_settings_means_no_key_rather_than_a_crash` |

試作過程中測試抓到一個真的錯誤：被截短的密文會讓函式庫丟出一般的 `ValueError`
而不是「驗證失敗」，頁面會因此出錯而不是顯示「無法讀取」。已在試作中修正
（`truncated` 與 `empty-payload` 兩個案例）；產品實作時要記得這一點。

量了一下成本：對 850 個帳戶（brief 的容量目標）各解密一次並遮成末四碼，總共約
2 毫秒。

### 這些測試真的會失敗嗎

`experiments/break_each_behaviour.py` 一次故意弄壞一項行為（在暫存的複本上），重跑
測試，列出哪些測試因此失敗。34 項破壞全部被抓到，其中與本問題有關的 15 項如下
（每項只列一個失敗的測試）：

| 故意弄壞的行為 | 因此失敗的測試 |
| --- | --- |
| 預設就顯示完整號碼 | `test_by_default_only_the_last_four_digits_are_shown` |
| 任何人都能看完整號碼 | `test_another_employee_cannot_reveal_the_full_number` |
| 管理者不能看完整號碼 | `test_an_administrator_can_reveal_the_full_number` |
| 持有人不能看完整號碼 | `test_the_holder_can_reveal_the_full_number` |
| 存進去的是明文 | `test_the_stored_value_never_contains_the_plain_number` |
| 每次都用同一個 nonce | `test_the_same_number_stored_twice_gives_two_different_values` |
| 讀不到時顯示空白而不是「無法讀取」 | `test_missing_key_viewing_shows_unreadable` |
| 沒有金鑰時修改會清掉原值 | `test_missing_key_editing_is_refused_and_nothing_is_written` |
| 沒有金鑰時拒絕訊息不同 | `test_missing_key_editing_is_refused_and_nothing_is_written` |
| 讀不到的舊值可以被覆寫 | `test_wrong_key_shows_unreadable_and_refuses_editing` |
| 金鑰錯誤或密文損壞時程式出錯 | `test_corrupted_ciphertext_shows_unreadable_and_refuses_editing[tag-changed]` |
| 密文沒有綁定帳戶 | `test_a_value_copied_onto_another_account_does_not_decrypt` |
| 忽略密文上的金鑰代號 | `test_rotating_the_key_loses_no_data` |
| 重新加密沒有作用 | `test_rotating_the_key_loses_no_data` |
| 13 位數字也被接受 | `test_a_number_that_is_not_14_digits_is_refused` |

## 從零重現

需要 Python 3.13 與能連到 PyPI 的網路，不需要其他服務、帳號或金鑰。

```
git clone https://github.com/pitaya943/yc-report-v4
cd yc-report-v4
git checkout spike/system-design-storage-crypto
cd spike/storage_crypto
./run.sh tests/test_bank.py
```

`run.sh` 會建立 `.venv`、安裝 `requirements.txt` 裡固定版本的套件，然後跑測試。
預期最後一行是 `22 passed`（另有一則 deprecation 警告，可忽略）。不帶參數執行
`./run.sh` 會連同檔案儲存的測試一起跑，預期 `68 passed`。

接著可以執行：

```
.venv/bin/python experiments/break_each_behaviour.py
```

預期最後一行是 `34 of 34 breaks were caught by a test`（約需一至兩分鐘）。

想親眼看存下來的值長什麼樣子：

```
.venv/bin/python -c "
from spike.bank import BankNumbers, Keyring
rows = {}
bank = BankNumbers(Keyring({'k1': bytes(32)}, 'k1'), rows)
bank.set('amy', '12345678905678')
print(rows['amy'])
print(bank.masked('amy'))
print(BankNumbers(Keyring({}, None), rows).masked('amy'))
"
```

預期印出三行：一個 `v1.k1.` 開頭、每次都不同的字串；`**********5678`；`無法讀取`。

## 建議產品採用的做法

**用 `cryptography` 的 AES-256-GCM，密文帶金鑰代號並綁定帳戶 id；末四碼由解密
得出，不另外存。**

介面（產品重新寫，不搬試作的程式碼）：

```python
class Keyring:                       # 由設定建立；current 可以是 None（沒有金鑰）
    current: str | None

def encrypt(keyring, account_id: str, number: str) -> str: ...   # "v1.<代號>.<base64>"
def decrypt(keyring, account_id: str, stored: str) -> str: ...   # 讀不到一律丟 BankNumberUnreadable

class BankNumbers:
    def masked(self, account_id) -> str: ...            # "**********5678" 或「無法讀取」
    def reveal(self, account_id, *, viewer_id, viewer_is_admin) -> str: ...
    def set(self, account_id, number) -> None: ...      # 讀不到現值或沒有金鑰時拒絕，不寫入
    def reencrypt_all(self) -> int: ...                 # 換金鑰用
```

資料庫只需要一個文字欄位存 `v1.…` 字串。設定只有兩個環境變數，本機與正式環境只差
值：`BANK_KEYS` 與 `BANK_KEY_CURRENT`；本機與測試用臨時產生的金鑰。

這次定下來的幾個決定：

- **末四碼需要金鑰。** 理由有三：規格要求金鑰不存在時檢視顯示「無法讀取」，如果
  末四碼另外存，沒有金鑰時它還是顯示得出來，與規格不符；同一個號碼只有一個存放處，
  不會出現末四碼與密文對不起來的情況；資料庫裡不留任何一段明文。代價是每次顯示都
  要解密一次，實測 850 筆約 2 毫秒，可以忽略。
- **讀不到現值就不准改，三種原因一視同仁**（金鑰不存在、金鑰錯誤、密文損壞），
  訊息都是「銀行帳號目前無法讀取，無法修改」。規格只寫了金鑰不存在的情況；金鑰
  錯誤多半是設定出錯，修好設定資料就回來了，這時讓人覆寫反而會毀掉還救得回來的
  資料。代價：真的損壞的那一列，使用者自己修不了，需要另外給管理者一個清除的
  方法。這一點需要 owner 確認，建議列入未決問題清單。
- **還沒填過銀行帳號的帳戶，在沒有金鑰時也不能填**（沒有金鑰可以加密），訊息相同。
- **換金鑰三步驟**，每一步之後所有資料都讀得到：
  1. 在 `BANK_KEYS` 加入新金鑰，`BANK_KEY_CURRENT` 改指向它，重新部署。舊資料用
     舊金鑰讀，新寫入的用新金鑰。
  2. 執行一次重新加密，把還用舊金鑰的列改用新金鑰。
  3. 確認沒有任何一列還帶舊代號後，把舊金鑰從 `BANK_KEYS` 拿掉。
- **金鑰代號不能含 `.`**，金鑰必須是 32 bytes；不符合時程式啟動就報錯，不會默默
  用錯。

## 衡量過的另一個選項與代價

**同一個套件裡的 Fernet / MultiFernet。**

- 好處：格式完全由函式庫決定，不必自己定義 `v1.<代號>.<內容>`；`MultiFernet`
  內建換金鑰（`rotate`）。
- 代價一：密文裡沒有金鑰代號，解密時是把每一把金鑰依序試一遍；想知道「還有幾列
  用舊金鑰」只能全部解一次。
- 代價二：Fernet 會把加密當下的系統時間寫進密文，等於多一個不經過注入時鐘的時間
  來源（可以改呼叫 `encrypt_at_time` 避開，但容易忘）。
- 代價三：不支援 associated data，密文無法綁定帳戶，甲的密文搬到乙的欄位照樣解得
  開。

選 AES-GCM 的代價是那個三段式格式由我們自己負責（試作裡約 30 行），並且要自己
記得每次加密都用新的隨機 nonce（已有測試看守）。

沒有考慮的做法：交給資料庫加密（例如 `pgcrypto`）。金鑰會出現在 SQL 裡，也讓
「沒有金鑰時其他功能照常」變得難以在應用程式這一層控制。

## 在有真正的正式服務之前無法證明的事

- 金鑰在正式環境怎麼設定與保管（例如放在 Railway 的環境變數）、誰看得到、怎麼
  備份。金鑰遺失等於所有銀行帳號永久讀不到；資料庫備份與金鑰必須分開保存。
- 換金鑰的第 2 步在真正的 PostgreSQL 資料表上怎麼跑（分批、交易、執行到一半中斷
  後能不能接著跑）。試作的「資料表」是記憶體裡的一個 dict。
- 「誰看了完整號碼」是否要記入稽核紀錄、怎麼記，屬於產品功能，試作沒有做。
- 試作用 HTTP 標頭假裝登入身分；真正的持有人與管理者判斷要等登入功能完成。
