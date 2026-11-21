# CFG-F01 單價
# 對照 v2 spec：B-032, B-075, B-094
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@CFG-F01 @B-032 @B-075 @B-094
Feature: Unit prices

  Rule: CFG-R01 WEST, SOUTH, and BIG_METER prices are saved as separate sets

    Scenario: Saving one set leaves the others
      When "Admin1" saves the WEST price of "direct_13" as 130
      Then the SOUTH price of "direct_13" is still 140
      And an audit row "SYSTEM_CONFIG" is written with the old and new value

  Rule: CFG-R02 A price is zero or more with at most two decimals

    Scenario Outline: Validation
      When "Admin1" saves a price of "<value>"
      Then the outcome is <outcome>

      Examples:
        | value  | outcome  |
        | 0      | accepted |
        | 0.01   | accepted |
        | 120    | accepted |
        | 0.001  | INVALID  |
        | -1     | INVALID  |

    Scenario: The price error message
      When "Admin1" saves a price of "-1"
      Then the request is rejected as INVALID with message "單價須為 0 或正數，最多兩位小數"

  Rule: CFG-R03 The next calculation uses the saved price, on every worker

    @concurrency
    Scenario: No stale price
      Given 2 workers
      And "Admin1" saved the WEST price of "direct_13" as 130 through worker 1
      When payroll is calculated through worker 2 immediately afterwards
      Then the price used for "direct_13" is 130

  Rule: CFG-R04 There is no fallback between price sets

    @Q-024
    Scenario: A missing SOUTH price does not borrow the WEST price
      Given the SOUTH price of "direct_13" is unset and the WEST price is 120
      When payroll is calculated for a period with a SOUTH "direct_13" share
      Then the request is rejected as BLOCKED with message "單價尚未設定完整，無法計算薪資，請先補齊單價"
