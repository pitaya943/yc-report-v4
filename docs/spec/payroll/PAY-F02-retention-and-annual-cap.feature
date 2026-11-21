# PAY-F02 保留金與年度上限
# 對照 v2 spec：B-046, B-047, B-048, B-035
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@PAY-F02 @domain @money @B-046 @B-047 @B-048 @B-035
Feature: Retention and annual cap
  # period retention = max(0, min(period raw, cap − ytd before))

  Rule: PAY-R10 Retention applies only to the retention items of the person's zone
    # 個人費率只覆寫本來就有保留金的項目；非保留金項目與大表帳戶一律為 0（D-070）。

    Scenario Outline: Who and what attracts retention
      Given "<name>" has a confirmed share of 10.0 of "<item>"
      When payroll is calculated
      Then period retention for "<name>" is <ret>

      Examples:
        | name | item        | ret | why                                 |
        | Wen  | direct_13   | 200 | WEST retention item                 |
        | Wen  | dsv_13      | 0   | not a WEST retention item           |
        | Nan  | s_dsv_13    | 200 | SOUTH retention item                |
        | Nan  | s_orig_13   | 0   | not a SOUTH retention item          |
        | Big  | bm_50_down  | 0   | big-meter accounts have no retention |

    Scenario: A personal item rate overrides the zone rate
      Given "Wen" has a personal retention rate of 50 for "direct_13"
      And "Wen" has a confirmed share of 10.0 of "direct_13"
      When payroll is calculated
      Then period retention for "Wen" is 500

  Rule: PAY-R11 Year-to-date retention never exceeds the cap of its calendar year

    Scenario Outline: Cap arithmetic
      Given the cap is <cap>
      And "Wen" has year-to-date retention of <ytd> before the period
      And the period raw retention for "Wen" is <raw>
      When payroll is calculated
      Then period retention for "Wen" is <ret>

      Examples:
        | cap   | ytd   | raw  | ret  | note                    |
        | 60000 | 0     | 200  | 200  | far below the cap       |
        | 60000 | 55000 | 8000 | 5000 | v2 Example C            |
        | 60000 | 59000 | 3000 | 1000 | v2 BDD-010              |
        | 60000 | 60000 | 3000 | 0    | cap already reached     |
        | 80000 | 59000 | 3000 | 3000 | cap raised              |
        | 0     | 0     | 3000 | 0    | cap 0 means no retention |
        | 50000 | 59000 | 3000 | 0    | cap lowered below ytd   |

  Rule: PAY-R12 Retention is scoped to the calendar year in Taiwan time

    Scenario: The new year starts at zero
      Given "Wen" had year-to-date retention of 20000 and an offset of 1000 in 2026
      When the clock is "2027-01-01 00:00"
      Then the displayed year-to-date retention for "Wen" is 0
      And the 2026 figures for "Wen" are still 20000 and 1000

    # 本規格定義（AD-3）：每筆回報的保留金歸屬於它自己回報日期的年度，
    # 跨年區間等於兩個年度各算一次再相加；每個年度各自 half-up 到整數後再相加（D-071）。
    @assumed @AD-3
    Scenario: A payroll period that spans New Year
      Given "Wen" has year-to-date retention of 59000 for 2026 before "2026-12-21"
      And "Wen" has confirmed "direct_13" shares of 100.0 on "2026-12-30" and 10.0 on "2027-01-03"
      When payroll is calculated for "2026-12-21" to "2027-01-05"
      # 2026: raw 2000, room 1000 → 1000. 2027: raw 200, ytd 0 → 200.
      Then period retention for "Wen" is 1200

  Rule: PAY-R13 A cap change applies from the current year and rewrites nothing already calculated

    # 本規格定義（AD-1）：每次按下計算都存成一個「薪資批次」(payroll run)，
    # 內含每人結果與當時使用的單價、費率、上限。批次存下後不可變；匯出一律出自某個批次。
    @Q-050 @assumed @AD-1
    Scenario: A saved run is unchanged by a later cap change
      Given "Admin1" calculated payroll for "2026-11-06" to "2026-11-20" with cap 60000 as run P1
      And run P1 shows period retention 1000 for "Wen"
      When "Admin1" changes the cap to 80000
      Then run P1 still shows period retention 1000 for "Wen"

    @Q-050 @assumed @AD-1
    Scenario: Calculating again creates a new run with current settings
      Given run P1 for "2026-11-06" to "2026-11-20" shows period retention 1000 for "Wen"
      And the cap was then changed to 80000
      When "Admin1" calculates payroll for "2026-11-06" to "2026-11-20"
      Then a new run P2 shows period retention 3000 for "Wen"
      And run P1 still shows period retention 1000 for "Wen"

    Scenario Outline: Cap validation
      When "Admin1" sets the cap to "<value>"
      Then the outcome is <outcome>

      Examples:
        | value | outcome  |
        | 0     | accepted |
        | 80000 | accepted |
        | -1    | INVALID  |
        | 60000.5 | INVALID |

Rule: PAY-R14 An administrator may set a person's year-to-date retention for one year
    # 目標可為負；上限比較的是加上 offset 後的淨額，負的目標代表多出可扣的空間（D-072）。
    # 目標範圍 −999999～999999，超出為 INVALID（D-073）。

    # 管理員輸入「目標年度累計」，系統存 offset = 目標 − 計算值；offset 按年度分開存，不帶到下一年。
    Scenario: Setting a target stores the offset for that year only
      Given the calculated 2026 retention for "Wen" is 12000
      When "Admin1" sets the 2026 retention target of "Wen" to 15000
      Then the 2026 offset of "Wen" is 3000
      And the displayed 2026 year-to-date retention of "Wen" is 15000
      And an audit row "RETENTION_SET" is written

    Scenario: A negative offset
      Given the calculated 2026 retention for "Wen" is 12000
      When "Admin1" sets the 2026 retention target of "Wen" to 10000
      Then the 2026 offset of "Wen" is -2000

    Scenario: The offset counts toward the cap
      Given the calculated 2026 retention for "Wen" is 12000 and the 2026 offset is 47000
      And the period raw retention for "Wen" is 3000
      When payroll is calculated
      Then period retention for "Wen" is 1000

    Scenario Outline: Target validation
      When "Admin1" sets the retention target of "Wen" to "<value>"
      Then the outcome is <outcome>

      Examples:
        | value  | outcome  |
        | -500   | accepted |
        | 0      | accepted |
        | 100.5  | INVALID  |
        | abc    | INVALID  |
        | 1000000 | INVALID |
