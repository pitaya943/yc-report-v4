# REV-F02 小組分配與份額保存
# 對照 v2 spec：B-044, B-091
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@REV-F02 @domain @money @B-044 @B-091
Feature: Crew split and stored shares
  # 純函式：split(tenths, crew_size) -> shares。先用表格鎖住數字，再用不變式鎖住性質。

  Rule: REV-R10 Split in tenths; the remainder goes to the submitter first, then crew order

    Scenario Outline: Split examples
      Given a crew of <n> in order "<crew>"
      When a quantity of <qty> units is split
      Then the shares in crew order are "<shares>"

      Examples:
        | qty   | n | crew                | shares                                     |
        | 7.0   | 1 | A                   | 7.0                                        |
        | 6.0   | 2 | A, B                | 3.0, 3.0                                   |
        | 7.0   | 3 | A, B, C             | 2.4, 2.3, 2.3                              |
        | 7.0   | 3 | A, C, B             | 2.4, 2.3, 2.3                              |
        | 1.0   | 3 | A, B, C             | 0.4, 0.3, 0.3                              |
        | 0.1   | 3 | A, B, C             | 0.1, 0.0, 0.0                              |
        | 0.5   | 3 | A, B, C             | 0.2, 0.2, 0.1                              |
        | 999.9 | 7 | A, B, C, D, E, F, G | 142.9, 142.9, 142.9, 142.8, 142.8, 142.8, 142.8 |
        | 0     | 3 | A, B, C             | 0.0, 0.0, 0.0                              |

    Scenario: Split invariants hold for every input
      Given any quantity from 0 to 999.9 in steps of 0.1 and any crew size from 1 to 7
      When the quantity is split
      Then the shares sum exactly to the quantity
      And the largest and smallest share differ by at most 0.1
      And no later crew member has a larger share than an earlier one

  Rule: REV-R11 Shares are stored at confirmation and are the only source for confirmed quantities

    Scenario: Confirmation stores one share per crew member per item
      Given a PENDING report by "Wen" with crew "Wen, Wei, Wan" and "direct_13" = 7.0
      When "Admin1" confirms it
      Then the stored shares of "direct_13" are Wen 2.4, Wei 2.3, Wan 2.3

    Scenario: Payroll uses stored shares, not the current crew
      Given a CONFIRMED report with stored shares Wen 2.4, Wei 2.3, Wan 2.3 of "direct_13"
      And "Wan" was archived after the confirmation
      When payroll is calculated for a period containing the report
      Then the "direct_13" quantities are Wen 2.4, Wei 2.3, Wan 2.3

    # 本規格定義（AD-7）：crew 在送出時凍結，資格只在送出時檢查；
    # 之後成員被封存或改 zone，核准時仍照原 crew 分配。
    @assumed @AD-7
    Scenario: A collaborator archived before approval still gets a share
      Given a PENDING report by "Wen" with crew "Wen, Wei, Wan" and "direct_13" = 7.0
      And "Wan" was archived after the report was submitted
      When "Admin1" confirms it
      Then the stored shares of "direct_13" are Wen 2.4, Wei 2.3, Wan 2.3

    Scenario: The custom item is split by the same rule
      Given a PENDING report with crew "Wen, Wei" and custom item quantity 0.3 at price 100
      When "Admin1" confirms it
      Then the stored custom-item shares are Wen 0.2, Wei 0.1
