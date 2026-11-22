# YC 日報系統（yc-report-v4）

工程人員每天回報施工內容、管理員確認、系統據以計算薪資的內部系統。目前完成的是
骨架與登入：可以登入、登出，登入後看到自己角色的頁面（日報頁與確認頁還是空殼），
管理員可以看系統狀態頁。系統做什麼寫在 [`docs/spec/`](docs/spec/index.md)。

## 需要什麼

- Python 3.13
- PostgreSQL 16（其他版本沒有試過）
- 不需要任何帳號或金鑰

## 從零開始在本機啟動

1. 安裝程式（在 repo 的根目錄）：

   ```sh
   python3 -m venv .venv
   .venv/bin/pip install -e ".[dev]"
   ```

2. 準備一個空的資料庫。已經有 PostgreSQL 的話：

   ```sh
   createdb yc_report
   export DATABASE_URL=postgresql:///yc_report
   ```

   沒有的話，用 Docker 起一個：

   ```sh
   docker run -d --name yc-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
   export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/postgres
   ```

3. 載入示範帳戶（會先需要資料庫結構，所以先執行 `migrate`）：

   ```sh
   .venv/bin/python -m app migrate
   .venv/bin/python -m app seed-demo
   ```

   `seed-demo` 載入規格共用背景的 9 個帳戶（[`docs/spec/background.md`](docs/spec/background.md)），
   並印出它們共用的示範密碼。它只能用在還沒有任何帳戶的系統，`APP_ENV=production`
   時拒絕執行。

4. 啟動：

   ```sh
   .venv/bin/python -m app serve
   ```

   `serve` 會先套用還沒套用的資料庫結構變更，失敗就不啟動。啟動後打開
   <http://127.0.0.1:8000/>：選「西區」、選「Wen」、輸入示範密碼，會看到日報頁；
   選「管理員」、選「Admin1」會看到確認頁，並且可以打開 <http://127.0.0.1:8000/status>。
   `Old` 是已封存的帳戶，不會出現在名單上。

   要換位址或埠：`python -m app serve --host 0.0.0.0 --port 8080`。

### 不用示範帳戶：建立擁有者

正式使用時，第一個帳戶（唯一的擁有者）用指令建立：

```sh
.venv/bin/python -m app create-owner
```

它會問顯示名稱與密碼（6 至 30 個字，輸入時不顯示，要輸入兩次）。密碼不能寫在
命令列上，所以不會留在 shell 的歷史紀錄。已經有擁有者時會拒絕。擁有者從登入頁的
「管理員」群組登入。

## 執行測試

```sh
.venv/bin/python -m pytest
```

- 測試需要一個可以建立資料庫的 PostgreSQL。設了 `TEST_DATABASE_URL` 就用它；沒設
  就用本機的 `initdb`、`pg_ctl` 自己起一個用完即丟的（找不到時以 `PG_BIN` 指出它們
  所在的目錄）。
- `tests/browser/` 用 Node 版的 Playwright 與 Chromium 對真的啟動起來的伺服器走一次
  登入與登出。找不到 Node 或 Playwright 時會略過並說明原因；設 `REQUIRE_BROWSER=1`
  時改為失敗。Playwright 不在預設位置時，以 `NODE_PATH` 指出它的 `node_modules`。
- 規格本身的檢查：`pip install -r tools/requirements.txt` 之後執行
  `python tools/check_spec.py`。

想讓一個指令替你啟動、登入、登出並留下截圖：
`.venv/bin/python .claude/skills/try-yc-report/try.py --evidence <目錄>`
（說明在 [`.claude/skills/try-yc-report/SKILL.md`](.claude/skills/try-yc-report/SKILL.md)）。

## 手動試「閒置 30 分鐘自動登出」

不用真的等 30 分鐘。`CLOCK_OFFSET_MINUTES` 把系統的時鐘往後撥：

1. 照上面啟動並登入，停在登入後的頁面。
2. 停掉伺服器（Ctrl-C），改用撥快 31 分鐘的時鐘再啟動：

   ```sh
   CLOCK_OFFSET_MINUTES=31 .venv/bin/python -m app serve
   ```

3. 在瀏覽器重新整理：會回到登入頁，顯示「請重新登入」。

登入狀態存在資料庫，所以重啟伺服器不會登出；是時鐘讓它逾時的。`APP_ENV=production`
時這個設定必須是 0。

## 設定

全部由環境變數給，啟動時一次檢查；有問題時列出每一項並拒絕啟動。
`python -m app check-config` 只檢查並印出每一項的狀態（不印出任何秘密）。

| 名稱 | 內容 | 沒給或不合法時 |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL 連線字串 | 拒絕啟動 |
| `APP_ENV` | `development`、`test`、`production` | 預設 `development`；其他值拒絕啟動 |
| `PASSWORD_HASH_PROFILE` | `standard` 或 `fast`（`fast` 只給測試用） | 預設 `standard`；`production` 搭配 `fast` 拒絕啟動 |
| `TRUSTED_PROXY_HOPS` | 系統前面有幾層可信任的反向代理（0 以上的整數）；決定登入頻率限制用哪一個來源位址 | 預設 0 |
| `CLOCK_OFFSET_MINUTES` | 把系統時鐘往後撥的分鐘數，手動試逾時用 | 預設 0；`production` 下不為 0 拒絕啟動 |
| `STORAGE_BACKEND` | 檔案儲存；目前只看「有沒有設定」，顯示在狀態頁 | 狀態頁顯示「未設定」 |
| `BANK_KEY` | 銀行帳號的加密金鑰；目前只看「有沒有設定」，顯示在狀態頁 | 狀態頁顯示「未設定」 |

## 指令

| 指令 | 做什麼 |
| --- | --- |
| `python -m app check-config` | 讀設定並印出每一項的狀態 |
| `python -m app migrate` | 套用尚未套用的資料庫結構變更 |
| `python -m app serve [--host H] [--port P]` | `migrate` 之後啟動伺服器（預設 `127.0.0.1:8000`） |
| `python -m app create-owner` | 建立唯一的擁有者 |
| `python -m app seed-demo` | 載入示範帳戶 |

## 容器映像

```sh
docker build -t yc-report .
docker run --rm -p 8000:8000 -e DATABASE_URL=... -e APP_ENV=production yc-report
```

映像以非 root 的使用者執行 `python -m app serve`，聽所有介面，埠是 `PORT`（沒給時
8000）；裡面沒有任何設定或秘密，同一個映像只改環境變數就能在本機或正式環境執行。
平台的健康檢查用 `/health`（資料庫連得上回 200，否則 503）。

## 文件

- [`docs/spec/`](docs/spec/index.md)：系統現在做什麼（行為規格）。
- [`docs/tasks/`](docs/tasks/)：每個 task 的 brief、設計、ticket 與決策紀錄。
- [`AGENTS.md`](AGENTS.md)：agent 在這個 repo 的工作規則。
