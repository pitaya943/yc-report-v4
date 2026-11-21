# MAT-F04 庫存管理
# 對照 v2 spec：B-026, B-027, B-029, B-036, B-066
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@MAT-F04 @B-026 @B-027 @B-029 @B-036 @B-066
Feature: Inventory administration

  Rule: MAT-R30 A material needs a name and a unit

    Scenario: Add
      When "Admin1" adds material name "PVC 管", unit "支", code "PVC-25", initial remaining 12, tab 2
      Then the material has received 12, cumulative usage 0, remaining 12 on tab 2
      And an audit row "MATERIAL_ADD" is written

    Scenario Outline: Validation
      When "Admin1" adds a material with <field> "<value>"
      Then the request is rejected as INVALID with message "<message>"

      Examples:
        | field         | value          | message                    |
        | name          | (empty)        | 請輸入材料名稱             |
        | name          | 101 characters | 材料名稱最多 100 個字      |
        | unit          | (empty)        | 請輸入單位                 |
        | unit          | 21 characters  | 單位最多 20 個字           |
        | code          | 51 characters  | 材料編號最多 50 個字       |
        | specification | 201 characters | 規格最多 200 個字          |
        | tab           | 11             | 分頁須為 1 到 10           |

  Rule: MAT-R31 A direct adjustment sets remaining and cumulative usage; received is recomputed

    Scenario: Adjust
      Given a material with received 30, cumulative usage 20, remaining 10
      When "Admin1" adjusts it to remaining 7 and cumulative usage 25
      Then the material has received 32, cumulative usage 25, remaining 7
      And an audit row "MATERIAL_UPDATE" is written

    Scenario Outline: Quantity validation
      When "Admin1" adjusts remaining to "<value>"
      Then the outcome is <outcome>

      Examples:
        | value  | outcome  |
        | 0      | accepted |
        | 1.125  | accepted |
        | 1.1255 | INVALID  |
        | -1     | INVALID  |

    Scenario: The invariant holds after every stock operation
      Given any sequence of approvals, adjustments, imports, and quarantine resolutions
      Then for every material received equals cumulative usage plus remaining

  Rule: MAT-R32 Hiding removes a material from employees, not from administrators

    Scenario: Hide
      When "Admin1" hides "PVC-20"
      Then "Wen" does not see "PVC-20"
      And "Admin1" sees "PVC-20" marked "已隱藏"

  Rule: MAT-R33 There are up to 10 tabs; a tab with an empty name is hidden

    Scenario: Naming a tab shows it
      Given tab 2 has no name
      When "Admin1" names tab 2 "管件"
      Then "Wen" sees tab "管件"
      And an audit row "SYSTEM_CONFIG" is written

    Scenario Outline: Moving a material
      When "Admin1" moves "PVC-20" to tab <tab>
      Then the outcome is <outcome>

      Examples:
        | tab | outcome  |
        | 1   | accepted |
        | 10  | accepted |
        | 0   | INVALID  |
        | 11  | INVALID  |

    Scenario: Tab name length
      When "Admin1" names tab 2 with 51 characters
      Then the request is rejected as INVALID with message "分頁名稱最多 50 個字"

    Scenario: Reordering within a tab
      Given tab 1 lists "A", "B", "C" in that order
      When "Admin1" moves "C" up once
      Then tab 1 lists "A", "C", "B" for everyone

  Rule: MAT-R34 Deleting a material also removes its PENDING requests

    Scenario: Delete
      Given "PVC-20" has 2 PENDING requests
      When "Admin1" deletes "PVC-20"
      Then "PVC-20" and its 2 PENDING requests no longer exist
      And an audit row "MATERIAL_DELETE" is written

  Rule: MAT-R35 Reset restores the default catalogue with every quantity at zero

    @Q-029
    Scenario: Reset
      Given materials with stock, hidden items, quarantined items, and a comparison label
      When "Admin1" resets inventory and confirms
      Then the materials are exactly the default catalogue
      And every quantity is 0, nothing is hidden or quarantined, and every item is on tab 1
      And the comparison label is cleared
      And an audit row "MATERIAL_RESET" is written

  Rule: MAT-R36 A successful import leaves a comparison label

    Scenario: Label
      When "Admin1" imports "2026-11盤點.xlsx" successfully
      Then the materials page shows "已對比：2026-11盤點"
      And an audit row "MATERIAL_IMPORT" is written

  Rule: MAT-R37 The inventory export lists every non-quarantined material

    Scenario: Export
      Given 5 materials of which 1 is hidden and 1 is quarantined
      When "Admin1" exports inventory to Excel
      Then the file has 4 data rows including the hidden one
      And the columns are tab name, code, name, specification, unit, cumulative usage, received, remaining, hidden
      And an audit row "EXPORT" is written
