# LED-F01 流水帳紀錄與餘額
# 對照 v2 spec：B-030, B-031, B-076
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@LED-F01 @B-030 @B-031 @B-076
Feature: Ledger entries and balances

  Rule: LED-R01 An entry has a date, a type, a positive whole amount, and a summary

    Scenario: Create
      When "Admin1" creates an EXPENSE of 500 dated "2026-11-10" with summary "買手套" and category "雜支"
      Then the entry exists
      And an audit row "LEDGER_CREATE" is written with actor "Admin1"

    Scenario Outline: Validation
      When "Admin1" creates an entry with <field> "<value>"
      Then the request is rejected as INVALID with message "<message>"

      Examples:
        | field    | value          | message                |
        | date     | (empty)        | 請輸入記帳日期         |
        | type     | (empty)        | 請選擇收入或支出       |
        | amount   | 0              | 金額必須為正整數       |
        | amount   | -500           | 金額必須為正整數       |
        | amount   | 10.5           | 金額必須為正整數       |
        | summary  | (empty)        | 請輸入摘要             |
        | summary  | 201 characters | 摘要最多 200 個字      |
        | category | 交際費         | 請選擇有效的分類       |
        | note     | 101 characters | 備註最多 100 個字      |

    Scenario: The type, not a sign, says income or expense
      When "Admin1" creates an EXPENSE of 500
      Then the stored amount is 500 and the type is EXPENSE

  Rule: LED-R02 Only an expense can name a payer

    Scenario Outline: Payer
      When "Admin1" creates an <type> with payer "<payer>"
      Then the outcome is <outcome> with message "<message>"

      Examples:
        | type    | payer     | outcome  | message               |
        | EXPENSE | Wen       | accepted |                       |
        | EXPENSE | (company) | accepted |                       |
        | INCOME  | Wen       | INVALID  | 僅支出可指定支出者    |

  Rule: LED-R03 Totals follow the current filter; the petty-cash balance is cumulative from the first entry through the filter end date, or through today

    Background:
      Given the clock is "2026-11-15 10:00"
      And ledger entries: INCOME 2000 on "2026-11-01", EXPENSE 500 on "2026-11-10", EXPENSE 300 on "2026-11-20"

    @Q-015 @Q-034
    Scenario Outline: Totals and balance
      When "Admin1" views the ledger with <filter>
      Then the income total is <income>, the expense total is <expense>, and the petty-cash balance is <balance>

      Examples:
        | filter                          | income | expense | balance | note                               |
        | dates 2026-11-05 to 2026-11-10  | 0      | 500     | 1500    | balance still counts the 1 Nov income |
        | dates 2026-11-01 to 2026-11-30  | 2000   | 800     | 1200    |                                    |
        | no date filter                  | 2000   | 800     | 1500    | balance stops at today, 15 Nov     |
        | type EXPENSE, no date filter    | 0      | 800     | 1500    | balance ignores the type filter    |

  Rule: LED-R05 Settling an employee's advance makes the company the payer

    Scenario: Settle
      Given an EXPENSE with payer "Wen"
      When "Admin1" settles it
      Then the payer is the company
      And an audit row "LEDGER_SETTLE" is written

    Scenario: Already the company
      Given an EXPENSE with payer the company
      When "Admin1" settles it
      Then nothing is written
      And the administrator is told the payer is already the company

  Rule: LED-R06 Editing is audited; the export matches the filter

    Scenario: Edit
      Given an EXPENSE of 500
      When "Admin1" changes the amount to 600
      Then an audit row "LEDGER_UPDATE" is written

    @provisional @Q-061
    Scenario: Export includes voided entries, marked
      Given 3 entries under the current filter, 1 of them voided
      When "Admin1" exports the ledger to Excel
      Then the file has 3 data rows and the voided one is marked "作廢"
      And an audit row "EXPORT" is written

  Rule: LED-R07 An entry can be saved when file storage is not configured

    Scenario: No storage
      Given file storage is not configured
      When "Admin1" creates an entry with a receipt
      Then the entry is saved without a file
      And the administrator is warned that the receipt could not be stored
