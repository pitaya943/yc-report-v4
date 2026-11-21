# 共用背景

所有 scenario 都從下面這組固定資料開始。測試框架在每個 scenario 執行前載入它，並使用乾淨的資料庫。個別 feature 自己的 `Background` 會加在這組資料之後。

金額單位是 NTD，時區是 Asia/Taipei。時鐘必須可由測試控制，因為許多 scenario 依賴時間（鎖定 15 分鐘、23:59 排程、跨年）。

```gherkin
# 所有 feature 預設的固定資料。金額單位 NTD，時區 Asia/Taipei。
Background:
  Given the clock is "2026-11-15 10:00" in Asia/Taipei
  And these accounts exist:
    | name   | role  | zone  | big_meter | archived |
    | Kuei   | OWNER | WEST  | no        | no       |
    | Admin1 | ADMIN | WEST  | no        | no       |
    | Admin2 | ADMIN | WEST  | no        | no       |
    | Wen    | USER  | WEST  | no        | no       |
    | Wei    | USER  | WEST  | no        | no       |
    | Wan    | USER  | WEST  | no        | no       |
    | Nan    | USER  | SOUTH | no        | no       |
    | Big    | USER  | WEST  | yes       | no       |
    | Old    | USER  | WEST  | no        | yes      |
  And unit prices, retention rates, and the retention cap are the defaults in Appendix A
```
