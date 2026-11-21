# 風險試作 (d)：含繁體中文的薪資 PDF 與銀行轉帳格式的 Word 檔

- Ticket：T-02；服務情境 S-6 (d)、S-9
- 試作程式：branch `spike/system-design-scheduler-exports`（commit `925729b`），
  目錄 `spike/`。拋棄式，不合併。
- 試作日期：2026-11-22（Asia/Taipei）；環境：Ubuntu 24.04、Python 3.13.18。
- 結論：**做得到，但最舊版系統的字型做法（reportlab + 系統套件
  `fonts-noto-cjk`）在這裡實測是失敗的**，要改成把字型檔放進應用程式裡。
- 範例檔裡的姓名、帳號、金額全部是虛構的。**銀行轉帳的版型是我自己擬的，
  不是真實銀行的格式**，拿到真實範例檔後必須照它重做。

## 問題

1. 薪資 PDF：A4 橫向，繁體中文正確顯示；部署到沒有桌面字型的 Linux container
   之後也一樣。字型從哪裡來、授權、大小、對部署映像檔的影響。
2. 銀行薪資轉帳格式的 Word `.docx`：繁體中文正確。
3. 兩者都要有表格：虛構姓名（如「王小明」）、有千分位的金額、看得出來的負數。
4. 證明中文真的在檔案裡：把文字從產生的檔案讀回來比對。

## 試了什麼

### PDF 的字型來源（四種都實際跑過）

用 reportlab 5.1.0，同一行字「王小明 陳美玲 薪資總表 轉帳金額 -1,200 龘 堃 喆」：

| 字型來源 | 結果 | 實際輸出 |
| --- | --- | --- |
| 系統套件 `fonts-noto-cjk`（`NotoSansCJK-Regular.ttc`） | **失敗**，reportlab 無法載入 | `TTFError: TTF file ".../NotoSansCJK-Regular.ttc": postscript outlines are not supported` |
| reportlab 內建 CID 字型 `MSung-Light`（不內嵌） | **不可靠**：檔案只有 2,438 bytes，但字型不在檔案裡，要靠閱讀器自己有。這台機器的 poppler 就打不開 | `Syntax Error: Missing language pack for 'Adobe-CNS1' mapping`、`Syntax Error (2024): No font in show` |
| Google Fonts 的 Noto Sans TC variable font（`NotoSansTC[wght].ttf`，11.9 MB） | 能內嵌、文字讀得回來，但 reportlab 不會選字重，印出來是最細的 Thin（100），太淡 | `AAAAAA+NotoSansTC-Thin  TrueType  emb yes  sub yes  uni yes` |
| **同一個字型切出 Regular（400）的靜態 TrueType 檔，放進應用程式** | **成功** | `AAAAAA+NotoSansTC-Regular  TrueType  emb yes  sub yes  uni yes` |

第一列失敗的原因：`fonts-noto-cjk` 裡的字型是 CFF（PostScript）外框，reportlab
只能內嵌 TrueType（glyf）外框。套件下載 61 MB、安裝後 89 MB，裝了也用不上。

採用的字型：

- 檔案：`spike/fonts/NotoSansTC-Regular.ttf`，7,149,124 bytes（約 7.1 MB），
  涵蓋 20,745 個字元，包含測試用的罕見人名用字「堃」「喆」「龘」。
- 來源：`github.com/google/fonts` 的 `ofl/notosanstc/NotoSansTC[wght].ttf`，用
  fonttools 切出 `wght=400`。製作指令寫在 `spike/fonts/build_font.py`。
- 授權：SIL Open Font License 1.1（`spike/fonts/OFL.txt`）。可以隨軟體一起散布
  與修改，條件是附上授權文字、不得單獨販售字型；保留名稱只有 Adobe 的
  「Source」，切出來的檔案仍可叫 Noto Sans TC。
- 產生的 PDF 只內嵌用到的字（subset）：範例檔 21,558 bytes。

### PDF

`spike/spike_exports/payroll_pdf.py`：reportlab 的 `SimpleDocTemplate` 與
`Table`，`pagesize=landscape(A4)`，標題、製表時間（由注入的時鐘傳入）、七欄
表格與合計列。金額格式是 `45,820`；負數是前面加負號並用紅字（`-1,200`），
黑白列印時仍看得到負號。

### Word

`spike/spike_exports/bank_docx.py`：python-docx 1.2.0，A4 直向。版型：標題
「薪資轉帳明細表」、委託單位、扣款帳號、轉帳日期（民國年）、每位收款人一列
（序號、14 位數帳號、戶名、金額）、合計列（筆數與總額）、簽章欄。每一段文字
都指定東亞字型為「標楷體」。

`.docx` **不內嵌字型**：檔案裡只有文字與「請用標楷體」的要求，實際用什麼字型
畫是開檔那台電腦決定的。所以伺服器上有沒有中文字型，對 Word 檔沒有影響。

## 結果

`cd spike && ./run.sh` 的實際輸出（匯出相關的部分）：

```
tests/test_exports.py::test_pdf_text_read_back_matches_the_chinese_and_the_amounts PASSED
tests/test_exports.py::test_pdf_is_one_a4_landscape_page PASSED
tests/test_exports.py::test_pdf_carries_its_own_chinese_font PASSED
tests/test_exports.py::test_docx_text_read_back_matches_the_chinese_and_the_amounts PASSED
tests/test_exports.py::test_docx_xml_itself_contains_the_chinese_text PASSED
tests/test_exports.py::test_docx_asks_for_a_chinese_font_on_every_run_and_marks_negatives_red PASSED
tests/test_exports.py::test_docx_page_is_a4_portrait PASSED
...
============================== 30 passed in 7.58s ==============================
wrote out/payroll.pdf and out/bank-transfer.docx
```

測試怎麼證明「中文真的在檔案裡」：

- PDF：用另一個函式庫 pypdf 把整頁文字讀回來，必須**完全等於**手寫的預期內容
  （標題、表頭、四位員工每一欄、合計列）。
- Word：用 python-docx 讀回段落與表格，必須完全等於手寫的預期內容；另外不靠
  python-docx，直接解壓縮 `.docx` 檢查 `word/document.xml` 裡有這些中文字。
- 預期值都是手寫的字串（例如 `"E002 陳美玲 52,000 0 2,560 -1,200 48,240"`），
  不是用被測程式算出來的。

用系統工具再確認一次產生的 PDF（poppler 的 `pdftotext`、`pdffonts`、`pdfinfo`，
與測試用的 pypdf 無關）：

```
$ pdftotext -layout out/payroll.pdf -
2026 年 11 月 薪資總表
製表時間：2026-11-30 23:59 幣別：新臺幣（元）

  員工編號        姓名                     底薪     加給      扣款       調整      實發金額
  E001        王小明                  45,000   3,000   2,180       0     45,820
  E002        陳美玲                  52,000      0    2,560   -1,200    48,240
  E003        林志豪                  38,500   1,500   1,890       0     38,110
  E004        張堃喆                      0       0    1,200       0     -1,200
              合計                  135,500   4,500   7,830   -1,200   130,970

$ pdffonts out/payroll.pdf
name                                 type              encoding         emb sub uni
------------------------------------ ----------------- ---------------- --- --- ---
Helvetica                            Type 1            WinAnsi          no  no  no
AAAAAA+NotoSansTC-Regular            TrueType          WinAnsi          yes yes yes

$ pdfinfo out/payroll.pdf | grep "Page size"
Page size:       841.89 x 595.276 pts (A4)
```

（`pdffonts` 最右邊的 object ID 欄已省略。841.89 × 595.276 pt 就是 297 × 210 mm，A4 橫向。Helvetica 是 reportlab 固定
放進每個 PDF 的預設字型，屬於所有 PDF 閱讀器都有的標準 14 種，檔案裡沒有任何
文字用到它。）

用 LibreOffice 把 Word 範例檔轉成 PDF 再讀文字（只是為了看版面，不在測試裡）：

```
                      薪資轉帳明細表
委託單位：範例工程行
扣款帳號：00400000000001
轉帳日期：民國 115 年 12 月 5 日

序號            收款帳號             戶名       轉帳金額
1             00412345678901   王小明              45,820
2             00498765432109   陳美玲              48,240
3             01200011122233   林志豪              38,110
4             01255566677788   張堃喆              -1,200
合計            共4筆                              130,970

委託單位簽章：＿＿＿＿＿＿＿＿                銀行收件章：＿＿＿＿＿＿＿＿
```

這台機器沒有標楷體，LibreOffice 自動改用文泉驛正黑顯示，文字都在；這正好示範
了「Word 檔用什麼字型由開檔的電腦決定」。

已產生的範例檔放在試作 branch 的 `spike/samples/`，可以直接下載打開：
`payroll.pdf`、`payroll-page1.png`（PDF 第一頁的畫面）、`bank-transfer.docx`。

逐一破壞行為後，對應的測試都失敗（`./run.sh prove` 的輸出）：

```
caught  1/1 runs failed  pdf: portrait instead of landscape
caught  1/1 runs failed  pdf: table drawn in Helvetica (no Chinese glyphs)
caught  1/1 runs failed  pdf: built-in CID font, not embedded
caught  1/1 runs failed  amounts: no thousands separators
caught  1/1 runs failed  amounts: minus sign dropped
caught  1/1 runs failed  docx: names forced to ASCII
caught  1/1 runs failed  docx: East Asian font not set
caught  1/1 runs failed  docx: negative amounts not red
caught  1/1 runs failed  docx: landscape page
```

沒有自動測試、只有我親眼看過的部分：PDF 轉成圖片後字形正確、字重正常、負數是
紅字（`spike/samples/payroll-page1.png`）。PDF 的紅字沒有測試；負號有。

關於「沒有桌面字型的 container」：這台機器其實裝有文泉驛正黑，所以不能用
「這裡看得到」當證據。證據是 `pdffonts` 的 `emb yes` 與測試
`test_pdf_carries_its_own_chinese_font`：字型在 PDF 檔案裡，產生時只讀取
`spike/fonts/` 下的檔案，不查系統字型。

## 從零重現

需要：git、Python 3.11 以上、PostgreSQL 的執行檔（同一個指令也會跑排程的測試；
見 `scheduled-jobs.md`）。不需要安裝任何字型。

```
git clone https://github.com/pitaya943/yc-report-v4.git
cd yc-report-v4
git checkout spike/system-design-scheduler-exports
cd spike
./run.sh
```

預期看到：`30 passed`，最後一行
`wrote out/payroll.pdf and out/bank-transfer.docx`。打開 `spike/out/` 的兩個檔案
應該與上面的內容相同。只跑匯出的測試（不需要 PostgreSQL）：
`.venv/bin/python -m pytest tests/test_exports.py -v`。要看破壞清單：
`./run.sh prove`，或只看匯出的：`.venv/bin/python prove_fail.py pdf`、
`prove_fail.py docx`、`prove_fail.py amounts`。

要用系統工具自己檢查 PDF（選用）：`apt install poppler-utils` 後執行上面的
`pdftotext`、`pdffonts`、`pdfinfo`。

要重現「系統字型套件不能用」（選用）：

```
apt-get download fonts-noto-cjk && dpkg -x fonts-noto-cjk_*.deb x
.venv/bin/python -c "from reportlab.pdfbase.ttfonts import TTFont; TTFont('N', 'x/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')"
```

預期：`TTFError: ... postscript outlines are not supported`。

## 建議產品採用的做法

- **PDF：reportlab，字型檔放在應用程式的套件目錄裡一起進版控與部署。**
  部署映像檔不需要裝任何字型套件或系統函式庫；本機、測試、正式環境產生的 PDF
  用的是同一個字型檔，沒有設定差異。代價是 repo 與映像檔各多 7.1 MB（只有
  Regular 一種字重；要真正的粗體得再放一個約 7 MB 的檔案，試作用底色區分表頭，
  沒有用粗體）。
- **Word：python-docx**，每段文字指定東亞字型；不需要任何伺服器端字型。
- 金額格式集中在一個函式；負數用負號加紅字。
- 製表時間由注入的時鐘傳入，不讀系統時間。

介面（產品重寫時的形狀）：

```python
def render_payroll_pdf(period: str, rows: list[PayrollRow], generated_at: datetime) -> bytes
def render_bank_transfer_docx(company: str, payer_account: str,
                              transfer_date: date, rows: list[TransferRow]) -> bytes
def format_amount(amount: int) -> str      # 45820 -> "45,820"；-1200 -> "-1,200"
```

兩個函式都只回傳 bytes，不碰檔案系統與資料庫；存到哪裡、怎麼下載由檔案儲存
那一層決定（T-01）。

相依套件安裝後的大小：reportlab 6.8 MB，加上它需要的 Pillow 5.9 MB；python-docx
2.8 MB，加上它需要的 lxml 12 MB。pypdf 只有測試用。都是 PyPI 上有現成 wheel 的
套件，不需要編譯。

## 衡量過的另一個做法與代價

- **系統套件 `fonts-noto-cjk` + reportlab（最舊版的做法）**：實測不能用（見上表）。
  即使換成能用的系統 TrueType 字型套件，也表示正式環境的映像檔要多裝一個套件，
  本機與測試機也得各自安裝，字型版本各環境可能不同；用 Railway 的自動建置時
  還要另外設定 apt 套件或改寫 Dockerfile。
- **內建 CID 字型**：映像檔與 PDF 都最小，但顯示結果取決於收件人的閱讀器，
  這台機器的 poppler 就失敗。薪資單不能冒這個險。
- **HTML 轉 PDF（例如 WeasyPrint）**：版面用 HTML/CSS 寫比較好維護，也能用 CFF
  字型，但需要 Pango 等系統函式庫進映像檔。**這個做法沒有實際試**，只是評估；
  reportlab 已經足夠做出這張表。
- **Word：拿銀行的原始 `.docx` 當範本填值**，而不是用程式畫版型。拿到真實範例
  檔後這很可能是更好的做法（版型百分之百相同）。python-docx 可以開啟既有檔案
  並填表格，但因為沒有真實檔案，**沒有試**。

## 需要設計或 owner 決定的事

1. **銀行的真實版型。** 目前的 Word 版型是擬的。拿到範例檔後要決定：照樣用
   程式重畫，或把銀行的檔案當範本填值。
2. **實發金額是負數的人怎麼出現在轉帳檔。** 試作依 ticket 要求放了一列負數來
   示範顯示方式，但銀行不可能轉出負的金額；規格需要決定這種人是排除、列為 0、
   還是擋下整批。
3. **人名裡有字型沒有的字時怎麼辦。** reportlab 遇到字型裡沒有的字會靜靜地印出
   空白方框，不會報錯。Noto Sans TC 涵蓋 20,745 個字元，常見與多數罕見人名用字
   都有，但不是全部。建議產品在產生 PDF 前檢查每個字都在字型裡，缺字時明確
   提示。試作沒有做這個檢查。
4. 字型選黑體（Noto Sans TC）還是明體（Noto Serif TC，同授權、做法相同）。

## 在有真實正式環境之前無法證明的事

- 在真的 Railway container 裡產生 PDF。依設計它只需要 Python 套件與 repo 裡的
  字型檔，沒有理由不同，但沒有在那裡跑過。
- 用真的 Microsoft Word（Windows）與銀行端的系統開啟 `.docx`。這裡只用
  python-docx 讀回，以及 LibreOffice 轉檔看過版面。
- 真實資料量下的速度與分頁：範例只有 4 列、1 頁；約 850 人的薪資表會有很多頁，
  表頭已設定每頁重複，但沒有量過產生時間，也沒有測試跨頁。
- 實際列印出來的樣子（邊界、字級是否合用）。
