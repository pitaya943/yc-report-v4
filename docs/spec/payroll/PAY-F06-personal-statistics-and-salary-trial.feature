# PAY-F06 個人統計與薪資試算
# 對照 v2 spec：B-068
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@PAY-F06 @B-068 @Q-013
Feature: Personal statistics and salary trial

  Rule: PAY-R50 Item totals cover reports the person submitted or collaborated on

    Scenario Outline: Totals by confirmation filter
      Given "Wen" has a CONFIRMED solo report with "direct_13" = 4.0
      And "Wei" has a PENDING report with crew "Wei, Wen" and "direct_13" = 3.0
      When "Wen" queries item totals with filter "<filter>"
      Then the "direct_13" total is <total>

      Examples:
        | filter           | total | note                                   |
        | confirmed only   | 4.0   | stored share                           |
        | unconfirmed only | 1.5   | preview split of 3.0 between 2         |
        | all              | 5.5   |                                        |

    Scenario: A rejected report is not counted
      Given "Wen" has a REJECTED report with "direct_13" = 9.0
      When "Wen" queries item totals with filter "all"
      Then the "direct_13" total does not include the 9.0

  Rule: PAY-R51 The trial uses confirmed reports only and every payroll component

    Scenario: The trial equals the official calculation under the same settings
      Given "Wen" has confirmed "direct_13" shares of 10.0 in the period, fixed salary 5000, insurance 834
      When "Wen" runs a salary trial for the period with payday-10 on
      Then the trial shows gross 1200, retention 200, fixed 5000, insurance 834, uninsured deduction 0, final 5166

    Scenario: The employee chooses whether the trial is a payday-10
      Given the same data
      When "Wen" runs a salary trial for the period with payday-10 off
      Then the trial shows final 1000

    Scenario: A trial is never saved as a run
      When "Wen" runs a salary trial
      Then no payroll run is created
      And no audit row is written

  Rule: PAY-R52 Big-meter accounts see no retention

    Scenario: Big-meter trial
      Given "Big" has confirmed "bm_50_down" shares of 2.0 in the period
      When "Big" runs a salary trial for the period
      Then the trial shows gross 2200 and retention 0
      And year-to-date retention is not shown

  Rule: PAY-R53 Administrators have no personal statistics

    @Q-018
    Scenario Outline: Sent to the summary page
      Given "<name>" is signed in
      When "<name>" opens personal statistics
      Then "<name>" is sent to the summary page

      Examples:
        | name   |
        | Admin1 |
        | Kuei   |
