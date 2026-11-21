# PAY-F03 封存帳戶的薪資
# 對照 v2 spec：B-012, B-017
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@PAY-F03 @money @B-012 @B-017 @Q-038 @Q-040 @Q-041
Feature: Archived accounts in payroll

  Background:
    Given "Wan" has fixed salary 5000 with every-period on
    And "Wan" was archived on "2026-11-10"

  Rule: PAY-R20 Work reported before the archive is still paid, and the name is marked

    Scenario Outline: Reports of an archived account
      Given "Wan" has a report dated "2026-11-08" with "direct_13" = 10.0 that was <timing>
      When payroll is calculated for "2026-11-06" to "2026-11-20"
      Then gross for "Wan" is 1200
      And the name of "Wan" is marked "封存"

      Examples:
        | timing                                                  |
        | confirmed on 2026-11-09, before the archive             |
        | submitted on 2026-11-08 and confirmed on 2026-11-12     |

  Rule: PAY-R21 In the period that contains the archive date, fixed salary follows the usual rules and may be adjusted

    Scenario: Counted by default, even with no reports
      Given "Wan" has no confirmed report in the period
      When payroll is calculated for "2026-11-06" to "2026-11-20"
      Then fixed salary applied for "Wan" is 5000
      And "Wan" is listed

    Scenario: Manual adjustment
      When payroll is calculated for "2026-11-06" to "2026-11-20" with the fixed salary of "Wan" adjusted to 2000
      Then fixed salary applied for "Wan" is 2000

    Scenario Outline: Adjustment validation
      When payroll is calculated with the fixed salary of "Wan" adjusted to "<value>"
      Then the outcome is <outcome>

      Examples:
        | value | outcome  |
        | 0     | accepted |
        | -1    | INVALID  |
        | 20.5  | INVALID  |

  Rule: PAY-R22 In later periods fixed salary is not counted unless the administrator adds it back

    Scenario: Not counted by default
      When payroll is calculated for "2026-11-21" to "2026-12-05"
      Then fixed salary applied for "Wan" is 0
      And "Wan" is not listed

    Scenario: Added back
      When payroll is calculated for "2026-11-21" to "2026-12-05" with the fixed salary of "Wan" added back
      Then fixed salary applied for "Wan" is 5000
      And "Wan" is listed and marked "封存"

    Scenario: Restoring returns to the usual rules
      Given "Admin1" restored "Wan" on "2026-11-25"
      When payroll is calculated for "2026-12-06" to "2026-12-20"
      Then fixed salary applied for "Wan" is 5000
      And the name of "Wan" is not marked "封存"
