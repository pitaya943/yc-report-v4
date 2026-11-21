# PAY-F07 跨帳戶統計總表
# 對照 v2 spec：B-073
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@PAY-F07 @B-073
Feature: Cross-account summary

  Rule: PAY-R60 The summary totals confirmed, stored shares per person

    Scenario: Per-person and grand totals
      Given a CONFIRMED report with stored "direct_13" shares Wen 2.4, Wei 2.3, Wan 2.3
      And a PENDING report by "Wen" with "direct_13" = 9.0
      When "Admin1" queries the ordinary summary for a range containing both
      Then the "direct_13" totals are Wen 2.4, Wei 2.3, Wan 2.3
      And the grand total of "direct_13" is 7.0

    Scenario Outline: Filters
      Given confirmed reports by "Wen" and "Nan"
      When "Admin1" queries the ordinary summary filtered by <filter>
      Then the people listed are "<people>"

      Examples:
        | filter      | people |
        | zone SOUTH  | Nan    |
        | account Wen | Wen    |

  Rule: PAY-R61 Big-meter people have their own summary

    Scenario: Separation
      Given confirmed reports by "Wen" and "Big"
      When "Admin1" queries the ordinary summary
      Then "Big" is not listed
      And "Big" is listed on the big-meter summary

  Rule: PAY-R62 The summary exports to Excel and PDF with one decimal place

    Scenario: Export
      When "Admin1" exports the summary to Excel
      Then quantities are written with one decimal place
      And an audit row "EXPORT" is written
