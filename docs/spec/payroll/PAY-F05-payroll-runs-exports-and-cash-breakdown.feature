# PAY-F05 薪資批次、匯出與現金面額
# 對照 v2 spec：B-053, B-059, B-072
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@PAY-F05 @B-053 @B-059 @B-072
Feature: Payroll runs, exports, and cash breakdown
  # 依 AD-1：每次計算產生一個不可變的 payroll run；頁面與匯出都出自某個 run。

  Rule: PAY-R40 A run needs a valid date range

    Scenario Outline: Date range validation
      When "Admin1" calculates payroll from "<start>" to "<end>"
      Then the outcome is <outcome> with message "<message>"

      Examples:
        | start      | end        | outcome  | message                          |
        | 2026-11-06 | 2026-11-20 | accepted |                                  |
        | 2026-11-06 | 2026-11-06 | accepted |                                  |
        | 2026-11-20 | 2026-11-06 | INVALID  | 結束日期不可早於開始日期         |
        |            | 2026-11-20 | INVALID  | 請輸入正確的開始與結束日期       |

    Scenario Outline: Payday shortcuts
      Given the clock is "2026-11-15 10:00"
      When "Admin1" chooses the "<shortcut>" shortcut
      Then the range is "<start>" to "<end>" and payday-10 is <p10>

      Examples:
        | shortcut  | start      | end        | p10 |
        | 10 號發薪 | 2026-10-21 | 2026-11-05 | on  |
        | 25 號發薪 | 2026-11-06 | 2026-11-20 | off |

    Scenario: The administrator may override the shortcut
      Given "Admin1" chose the "25 號發薪" shortcut
      When "Admin1" turns payday-10 on and calculates
      Then the run is calculated with payday-10 on

  Rule: PAY-R41 A run shows each person's breakdown and the totals

    Scenario: Totals
      Given a run with finals Wen 964 by TRANSFER, Wei 1686 by CASH, Nan 600 by CASH
      Then the grand total is 3250, the transfer total is 964, and the cash total is 2286

    Scenario: Names carry zone or type
      Given a run that lists "Wen", "Nan", and "Big"
      Then the names are marked "西區", "南區", and "大表"

    Scenario: Bank numbers are masked in the run
      Given a run that lists "Wen" paid by TRANSFER
      Then the bank number of "Wen" shows only the last four digits

  Rule: PAY-R42 The cash breakdown counts the notes and coins needed to pay each person exactly

    # 本規格定義（AD-12）：面額數量是逐人用 1000/500/100/50/10/5/1 貪婪分解後加總，
    # 不是對現金總額分解，因為現金要逐人裝袋。
    Scenario Outline: One person
      Given a run with one CASH final of <final>
      Then the breakdown is "<notes>"

      Examples:
        | final | notes                                        |
        | 1686  | 1000×1, 500×1, 100×1, 50×1, 10×3, 5×1, 1×1   |
        | 500   | 500×1                                        |
        | 0     | (none)                                       |
        | -200  | (none)                                       |

    @assumed @AD-12
    Scenario: Two people
      Given a run with CASH finals of 600 for "Wei" and 600 for "Nan"
      Then the breakdown is "500×2, 100×2"
      And the breakdown is not "1000×1, 100×2"

  Rule: PAY-R43 The Excel export is one file: a summary sheet, then one sheet per person

    @Q-014
    Scenario: Sheets
      Given a run that lists 3 people
      When "Admin1" exports the run to Excel
      Then the file is .xlsx with 4 sheets, the summary first
      And each person sheet shows quantities, unit prices, subtotals, gross, retention, net, fixed salary, insurance, uninsured deduction, and final
      And the title shows the date range
      And an audit row "EXPORT" is written

    Scenario: The PDF export carries the same figures
      Given a run that lists 3 people
      When "Admin1" exports the run to PDF
      Then every figure in the PDF equals the same figure in the run

  Rule: PAY-R44 The transfer slip lists only people paid by transfer with a positive final

    @Q-027
    Scenario: Who is on the slip
      Given a run with finals Wen 964 by TRANSFER, Wei 1686 by CASH, Wan 0 by TRANSFER, Nan -50 by TRANSFER
      When "Admin1" exports the transfer slip
      Then the .docx lists only "Wen" with the full bank number and 964

    Scenario: The slip is blocked without the encryption key
      Given the encryption key is missing
      When "Admin1" exports the transfer slip
      Then the request is rejected as BLOCKED
      And no file is produced

  Rule: PAY-R45 Exports of a run never change with later settings

    @assumed @AD-1
    Scenario: Re-exporting an old run
      Given run P1 was calculated when the WEST price of "direct_13" was 120
      And the price was later changed to 130
      When "Admin1" exports run P1 to Excel
      Then the unit price of "direct_13" in the file is 120
