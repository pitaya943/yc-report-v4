# 規格基準與 v3 原文的差異

基準來源：`pitaya943/yc-daily-report-v3` 的 `spec/`，commit
`e839d9d50556290b8ab341354d1a54dff560d3d3`（2026-11-17）。

結論：**沒有任何商業規則、例子的數字或使用者可見字串被改動。** 差異只有搬移、
索引重算、一處 scenario 改名，以及過時說明的更正。v3 在規格定稿後做出的修正決定
（它的 `docs/decisions.md` D-053 至 D-102 中改到規格的那些）在這個 commit 已經寫進
`spec/`，所以基準直接包含它們，不需要另外套用。

## 差異清單

| # | 改了什麼 | 來源 | 原因 |
| --- | --- | --- | --- |
| 1 | 檔案改依領域放：`spec/features/*.feature` 分到 `docs/spec/<領域>/`；`README.md` 拆成 `index.md`（系統說明、領域、名詞）與 `conventions.md`（寫作規約、結果類別、標籤）；`glossary.md` 併入 `index.md`；`capabilities.md` 併入 `index.md` 與各領域的 `index.md`；附錄移到 `reference/` | 本 repo 的 shilaycow 規格格式（`docs/spec/index.md` 加上每個領域一份） | 讓本 repo 的其他工具找得到，並且每個名詞只定義一次 |
| 2 | 每個 feature 檔第 3 行的註解，路徑由 `spec/background.md`、`spec/README.md` 改成 `docs/spec/background.md`、`docs/spec/conventions.md`（31 個檔各 1 行） | 第 1 項的搬移 | 註解指向的檔案換了位置 |
| 3 | `CFG-F02` 兩個同名的 `Scenario Outline: Validation` 改名為 `Uninsured rate validation` 與 `Retention rate validation`；步驟與例子表不變 | v3 `docs/pitfalls.md`：依名稱綁定 scenario 的測試工具會無聲地丟掉同名的其中一個 | 讓兩個 scenario 都會被執行；`tools/check_spec.py` 現在會擋同名 |
| 4 | scenario 總數由「251」改為 254；`MAT-F03` 由 4 改為 6、`PAY-F01` 由 12 改為 13；新增「502 個例子」的計數 | 用 Gherkin 解析器實際計數（`tools/check_spec.py`） | v3 的索引表是手算的，在後來新增 scenario 後沒有更新；v3 首頁另一處寫的「245」也是舊數字 |
| 5 | 刪除 v3 首頁的「與 v2 spec 的關係」一節（聲稱與 v2 只有三類差異） | v3 `docs/decisions.md` 之後有數十條改到規格的決定 | 該說法已不成立；v2 對照仍保留在 `reference/appendix-f-v2-map.md` |
| 6 | 刪除「Gherkin 還沒有用工具做過語法檢查」；首頁的「狀態」列改寫成「現況」 | 本 task 已做語法檢查 | 原句不再為真。「owner 沒有逐條審閱每個 scenario」與「例子的數字沒有對照舊系統實際輸出」仍然為真，記在 [`open-questions.md`](open-questions.md) |
| 7 | `definitions.md`：AD-9 的「採用 §0.2 的表」改為指向 `conventions.md` 的結果類別；理由「滿足 AGENTS.md 規則 3」改寫為「每個拒絕案例都能斷言明確的狀態碼」；「在 `docs/decisions.md` 加一列」改為「在改寫它的 task 的 trail 加一列」 | 第 1 項的搬移；本 repo 沒有 v3 的 `AGENTS.md` 與 `docs/decisions.md` | 原文指向本 repo 不存在的檔案 |
| 8 | `state-machines.md`、`reference/appendix-e-decisions.md`、`reference/appendix-f-v2-map.md` 內的檔案路徑更新（共 4 行） | 第 1 項的搬移 | 同上 |
| 9 | 每個領域新增 `index.md`（用途、情境、規則、最後更動的 task、尚未建置）；`index.md` 新增「系統刻意不做的事」 | shilaycow 規格格式；內容取自 v3 規格既有的規則與 v2 規格第 10 節 | 格式要求；沒有新增行為 |

沒有改動的檔案：`background.md` 與附錄 A、B、C、D 與原文逐字相同。

## 自己驗證

取得 v3 原文後，下面的指令列出所有 feature 檔與原文不同的行；預期只看到第 2 項的
註解行（31 組）與第 3 項的改名（2 行換 2 行）。

```bash
git clone https://github.com/pitaya943/yc-daily-report-v3 /tmp/v3 && git -C /tmp/v3 checkout e839d9d
```

```bash
for f in docs/spec/*/*.feature; do diff /tmp/v3/spec/features/$(basename $f) $f; done | grep '^[<>]' | sort | uniq -c
```

本 task 執行的結果：

```text
     31 < # 共用的固定資料見 spec/background.md；結果類別與寫作規約見 spec/README.md。
      2 <     Scenario Outline: Validation
     31 > # 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
      1 >     Scenario Outline: Retention rate validation
      1 >     Scenario Outline: Uninsured rate validation
```

## 沒有放進基準的東西

v2 有而 v3 沒帶過來的規則，以及舊 repo 留下的未回答問題，**沒有**寫成新的 scenario；
它們各有一個預設答案，列在 [`open-questions.md`](open-questions.md)，由之後建置該
領域的 task 寫進它的 brief 給 owner 核准。
