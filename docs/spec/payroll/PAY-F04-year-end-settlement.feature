# PAY-F04 年度結算
# 對照 v2 spec：B-090
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@PAY-F04 @B-090 @Q-023 @Q-031 @Q-037
Feature: Year-end settlement

  Rule: PAY-R30 One action settles a calendar year for every account and records each released amount

    Scenario: Settle 2026
      Given the clock is "2027-01-05 10:00"
      And the 2026 year-to-date retention is 20000 for "Wen" and 8000 for "Nan"
      When "Admin1" runs year-end settlement for 2026
      Then the released amounts recorded for 2026 are Wen 20000, Nan 8000
      And an audit row "RETENTION_YEAR_END" is written listing each person's amount

  Rule: PAY-R31 The released amount is a record only; nothing is paid inside the system

    Scenario: No payroll effect
      Given 2026 was settled with a released amount of 20000 for "Wen"
      When payroll is calculated for any period
      Then no payroll figure for "Wen" contains the 20000

  Rule: PAY-R32 The New Year reset does not depend on settlement

    Scenario: Unsettled year still resets
      Given 2026 has not been settled
      When the clock is "2027-01-01 00:00"
      Then the displayed year-to-date retention for "Wen" is 0

  Rule: PAY-R33 A year is settled once, after it has ended

    # 本規格定義（AD-11）：v2 只說「可結算的年度」。這裡定義為已結束、且尚未結算過的年度。
    @assumed @AD-11
    Scenario Outline: Which year may be settled
      Given the clock is "2027-01-05 10:00"
      And 2025 has already been settled
      When "Admin1" runs year-end settlement for <year>
      Then the outcome is <outcome>

      Examples:
        | year    | outcome  | why                 |
        | 2026    | accepted | ended, not settled  |
        | 2027    | CONFLICT | not ended           |
        | 2025    | CONFLICT | already settled     |
        | (empty) | INVALID  | 請選擇要結算的年度  |
