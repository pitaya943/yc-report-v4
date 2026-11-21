# CFG-F02 費率
# 對照 v2 spec：B-033, B-034, B-092
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@CFG-F02 @B-033 @B-034 @B-092
Feature: Rates

  Rule: CFG-R10 Each zone has a default uninsured rate from 0 to 100 with at most two decimals

    Scenario Outline: Uninsured rate validation
      When "Admin1" saves the WEST uninsured rate as "<value>"
      Then the outcome is <outcome>

      Examples:
        | value  | outcome  |
        | 0      | accepted |
        | 3      | accepted |
        | 100    | accepted |
        | 100.01 | INVALID  |
        | -0.01  | INVALID  |
        | 3.333  | INVALID  |

    Scenario: Zones are independent
      When "Admin1" saves the SOUTH uninsured rate as 4
      Then the WEST uninsured rate is still 3

  Rule: CFG-R11 Each zone has a global retention rate, a whole number from 0 to 9999 NTD per unit

    Scenario Outline: Retention rate validation
      When "Admin1" saves the WEST retention rate as "<value>"
      Then the outcome is <outcome>

      Examples:
        | value | outcome  |
        | 0     | accepted |
        | 9999  | accepted |
        | 10000 | INVALID  |
        | -1    | INVALID  |
        | 20.5  | INVALID  |

    Scenario: A rate of 0 means no retention
      Given the WEST retention rate is 0
      And "Wen" has a confirmed share of 10.0 of "direct_13"
      When payroll is calculated
      Then period retention for "Wen" is 0

  Rule: CFG-R12 A person's item rates can be reset to the zone rate

    Scenario: Reset
      Given "Wen" has a personal retention rate of 50 for "direct_13"
      When "Admin1" resets the item rates of "Wen"
      Then the retention rate of "Wen" for "direct_13" is the WEST rate of 20
      And an audit row "RETENTION_RESET" is written

  Rule: CFG-R13 Every settings change is audited with the old and new value

    Scenario: Rate change
      When "Admin1" saves the WEST retention rate as "25"
      Then an audit row "SYSTEM_CONFIG" is written containing "20" and "25"
