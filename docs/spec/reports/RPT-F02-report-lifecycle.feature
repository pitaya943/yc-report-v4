# RPT-F02 回報生命週期
# 對照 v2 spec：B-023, B-064
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@RPT-F02 @B-023 @B-064
Feature: Report lifecycle
  # 每一列對應 §3.1 轉移表的一格。

  Rule: RPT-R10 Only the submitter may change a report, and only while it is not confirmed

    Scenario Outline: Submitter actions by state
      Given "Wen" has an own report in state <state>
      When "Wen" tries to <action> it
      Then the outcome is <outcome>
      And the report state is <after>

      Examples:
        | state     | action | outcome   | after     |
        | PENDING   | edit   | accepted  | PENDING   |
        | REJECTED  | edit   | accepted  | PENDING   |
        | CONFIRMED | edit   | FORBIDDEN | CONFIRMED |
        | PENDING   | delete | accepted  | gone      |
        | REJECTED  | delete | accepted  | gone      |
        | CONFIRMED | delete | FORBIDDEN | CONFIRMED |

    Scenario Outline: A collaborator may only view
      Given "Wei" is a collaborator on a <state> report submitted by "Wen"
      When "Wei" tries to <action> it
      Then the request is rejected as FORBIDDEN
      And nothing is written except an audit row "ACCESS_DENIED" with actor "Wei"

      Examples:
        | state   | action |
        | PENDING | edit   |
        | PENDING | delete |

  Rule: RPT-R11 An edit updates the same report and never uses quota

    Scenario: Editing does not count as a new submission
      Given "Wen" has 3 own reports dated "2026-11-15", one of them PENDING
      When "Wen" edits the PENDING report to "direct_13" = 5.0
      Then "Wen" still has 3 own reports dated "2026-11-15"
      And an audit row "REPORT_UPDATE" is written

    # 本規格定義（AD-8）：編輯不能改回報日期；要改日期就刪除後重送。錯誤字串也是本規格定義的。
    @assumed @AD-8
    Scenario: The report date cannot be changed on edit
      Given "Wen" has an own PENDING report dated "2026-11-15"
      When "Wen" edits it with report date "2026-11-14"
      Then the request is rejected as INVALID with message "回報日期送出後不可修改"
      And nothing is written

    Scenario: An edit with no change says so
      Given "Wen" has an own PENDING report
      When "Wen" saves it unchanged
      Then the audit description contains "無變更"

  Rule: RPT-R12 An administrator's edit always returns the report to PENDING

    Scenario: Editing a confirmed report discards its shares
      Given a CONFIRMED report by "Wen" with stored shares
      When "Admin1" edits it to "direct_13" = 5.0
      Then the report state is PENDING
      And the report has no stored shares
      And audit rows "REPORT_UNCONFIRM" and "REPORT_UPDATE" are written

  Rule: RPT-R13 Deletion is permanent and audited

    Scenario: Administrator deletes a confirmed report
      Given a CONFIRMED report by "Wen"
      When "Admin1" deletes it
      Then the report no longer exists
      And an audit row "REPORT_DELETE" is written with actor "Admin1"

  Rule: RPT-R14 An edit must leave at least one quantity above 0
    # D-096：與 RPT-R08 相同的規則用在編輯；自訂工項（REV-R20）有數量也算。

    Scenario: An edit that clears every quantity is refused
      Given "Wen" has an own PENDING report
      When "Wen" edits it with every quantity 0
      Then the request is rejected as INVALID with message "請至少填寫一個工項數量"
      And nothing is written

    Scenario: A custom item quantity is enough
      Given a PENDING report by "Wen" with custom item "夜間加班" quantity 2.0 at price 500
      When "Admin1" edits it with every catalogue quantity 0
      Then the outcome is accepted
      And the report state is PENDING
