# MAT-F03 庫存匯入與暫存區
# 對照 v2 spec：B-054, B-055
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@MAT-F03 @domain @B-054 @B-055
Feature: Inventory import and quarantine
  # A = 系統現況，B = 上傳檔。x = B.received − A.received。
  # 預期更新後的 A：received + x、remaining + x、cumulative 不變。

  Rule: MAT-R20 A row is applied only when A is consistent, x ≥ 0, and B equals the expected A
    # 多個疑點時依序只報第一個：A 不一致 → x < 0（?）→ B 不符（D-074）。
    # 不變式：實領量 = 累計使用量 + 庫存量，且三者都 ≥ 0（D-076）。

    Scenario Outline: Import decision per row
      Given the system has received <a_rec>, cumulative <a_cum>, remaining <a_rem>
      And the file has received <b_rec>, cumulative <b_cum>, remaining <b_rem>
      When the file is imported
      Then the row is <decision> with likely fault "<fault>"
      And the system has received <rec>, cumulative <cum>, remaining <rem>

      Examples:
        | a_rec | a_cum | a_rem | b_rec | b_cum | b_rem | decision    | fault | rec | cum | rem | note                 |
        | 15    | 10    | 5     | 20    | 10    | 10    | applied     | -     | 20  | 10  | 10  | normal inbound of 5  |
        | 15    | 10    | 5     | 15    | 10    | 5     | applied     | -     | 15  | 10  | 5   | x = 0                |
        | 15    | 10    | 5     | 12    | 10    | 2     | quarantined | ?     | 15  | 10  | 5   | x < 0                |
        | 15    | 10    | 4     | 20    | 10    | 10    | quarantined | A     | 15  | 10  | 4   | A breaks invariant   |
        | 15    | 10    | 5     | 20    | 12    | 7     | quarantined | B     | 15  | 10  | 5   | B differs from expected |
        | 15    | 10    | 4     | 12    | 10    | 2     | quarantined | A     | 15  | 10  | 4   | A broken and x < 0   |

    Scenario Outline: File validation
      When "Admin1" imports "<file>"
      Then the outcome is <outcome>

      Examples:
        | file                                   | outcome  |
        | stock.xlsx with both required headers  | accepted |
        | stock.csv with both required headers   | accepted |
        | stock.xlsx without header 實領量       | INVALID  |
        | stock.pdf                              | INVALID  |

  Rule: MAT-R21 Resolving quarantine restores the invariant

    Scenario Outline: Trust A or trust B
      Given a quarantined row with A (15, 10, 5), B (20, 12, 8), x = 5
      When "Admin1" resolves it with "<choice>"
      Then the system has received <rec>, cumulative <cum>, remaining <rem>
      And the row is no longer quarantined
      And an audit row "<audit>" is written

      Examples:
        | choice  | rec | cum | rem | audit            |
        | trust A | 20  | 10  | 10  | MATERIAL_KEEP_A  |
        | trust B | 20  | 12  | 8   | MATERIAL_SYNC_B  |

    # 本規格定義（AD-6）：B 三值不合不變式時不可採用 B。錯誤字串也是本規格定義的。
    @assumed @AD-6
    Scenario: Trust B is refused when B breaks the invariant
      Given a quarantined row with B (20, 12, 7)
      When "Admin1" resolves it with "trust B"
      Then the request is rejected as CONFLICT with message "B 系統數值不一致，無法採用"
      And the row stays quarantined

    # D-076：三值都須 ≥ 0
    Scenario: Trust B is refused when B has a negative value
      Given a quarantined row with B (5, 10, -5)
      When "Admin1" resolves it with "trust B"
      Then the request is rejected as CONFLICT with message "B 系統數值不一致，無法採用"
      And the row stays quarantined

    # D-075：比照 AD-6，「信任 A」的結果不合不變式時拒絕
    Scenario: Trust A is refused when the result breaks the invariant
      Given a quarantined row with A (15, 10, 4), B (20, 10, 10), x = 5
      When "Admin1" resolves it with "trust A"
      Then the request is rejected as CONFLICT with message "A 系統數值不一致，無法採用"
      And the row stays quarantined
