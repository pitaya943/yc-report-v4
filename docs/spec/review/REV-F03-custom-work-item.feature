# REV-F03 自訂工項
# 對照 v2 spec：B-024
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@REV-F03 @B-024
Feature: Custom work item

  Rule: REV-R20 Only an administrator attaches a custom item, one per report

    Scenario: Attach
      Given a PENDING report R1 by "Wen"
      When "Admin1" attaches custom item "夜間加班" with quantity 2.0 and unit price 500 to R1
      Then R1 has custom item "夜間加班", 2.0, 500
      And an audit row "REPORT_UPDATE" is written with actor "Admin1"

    Scenario: A USER cannot attach
      Given a PENDING report R1 by "Wen"
      When "Wen" attaches a custom item to R1
      Then the request is rejected as FORBIDDEN

    Scenario: Attaching again replaces the item
      Given R1 has custom item "夜間加班", 2.0, 500
      When "Admin1" attaches custom item "搬運" with quantity 1.0 and unit price 300 to R1
      Then R1 has exactly one custom item "搬運", 1.0, 300

  Rule: REV-R21 Clearing the name removes the item

    Scenario: Remove
      Given R1 has custom item "夜間加班", 2.0, 500
      When "Admin1" saves the custom item of R1 with an empty name
      Then R1 has no custom item

  Rule: REV-R22 Name up to 100 characters, quantity in steps of 0.1 up to 999.9, whole-NTD price

    Scenario Outline: Validation
      When "Admin1" attaches a custom item with name <name>, quantity "<qty>", price "<price>"
      Then the outcome is <outcome> with message "<message>"

      Examples:
        | name           | qty   | price | outcome  | message                                        |
        | 100 characters | 1.0   | 500   | accepted |                                                |
        | 101 characters | 1.0   | 500   | INVALID  | 自訂工項名稱最多 100 個字                      |
        | "搬運"         | 0.05  | 500   | INVALID  | 自訂工項數量須為 0 到 999.9，最小單位 0.1      |
        | "搬運"         | 1000  | 500   | INVALID  | 自訂工項數量須為 0 到 999.9，最小單位 0.1      |
        | "搬運"         | 1.0   | 99.5  | INVALID  | 自訂工項單價須為 0 或正整數                    |
        | "搬運"         | 1.0   | -1    | INVALID  | 自訂工項單價須為 0 或正整數                    |
        | "搬運"         | 0     | 0     | accepted |                                                |

  Rule: REV-R23 Custom-item money is each person's share times the item's own price

    @money
    Scenario: Money by share
      Given a CONFIRMED report with crew "Wen, Wei" and custom item quantity 0.3 at price 100
      When payroll is calculated for a period containing the report
      Then custom-item money is 20 for "Wen" and 10 for "Wei"

  Rule: REV-R24 A custom-item change on a report that is not PENDING is an administrator edit

    # 本規格定義（AD-10）：對已確認或已駁回的回報改自訂工項，等同管理員編輯，回報回到 PENDING（RPT-R12）。
    @assumed @AD-10
    Scenario: Attaching to a confirmed report
      Given a CONFIRMED report R1 with stored shares
      When "Admin1" attaches a custom item to R1
      Then R1 is PENDING and has no stored shares
      And audit rows "REPORT_UNCONFIRM" and "REPORT_UPDATE" are written
