# MAT-F02 審核材料申請
# 對照 v2 spec：B-056, B-070
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@MAT-F02 @B-056 @B-070
Feature: Review material requests
  # 不變式：received = cumulative usage + remaining，任何時刻都成立。

  Background:
    Given material "PVC-20" has received 30, cumulative usage 20, remaining 10

  Rule: MAT-R10 Approval moves stock from remaining to cumulative usage

    Scenario Outline: Approval by stock level
      Given a PENDING request by "Wen" for <qty> of "PVC-20"
      When "Admin1" approves it
      Then the outcome is <outcome>
      And the request status is <status>
      And "PVC-20" has received 30, cumulative usage <cum>, remaining <rem>

      Examples:
        | qty | outcome  | status   | cum | rem | note                |
        | 4   | accepted | APPROVED | 24  | 6   | enough stock        |
        | 10  | accepted | APPROVED | 30  | 0   | exactly enough      |
        | 11  | CONFLICT | PENDING  | 20  | 10  | one short           |

    Scenario: The insufficient-stock message
      Given a PENDING request by "Wen" for 11 of "PVC-20"
      When "Admin1" approves it
      Then the request is rejected as CONFLICT with message "庫存不足，無法核准"
      And nothing is written

  Rule: MAT-R11 Only a PENDING request can be reviewed

    Scenario Outline: A second review is refused
      Given a request by "Wen" for 4 of "PVC-20" with status <status>
      When "Admin1" tries to <action> it
      Then the request is rejected as CONFLICT
      And "PVC-20" stock is unchanged

      Examples:
        | status   | action  |
        | APPROVED | approve |
        | APPROVED | reject  |
        | REJECTED | approve |
        | REJECTED | reject  |

    @concurrency
    Scenario: Two administrators approve the same request at once
      Given a PENDING request by "Wen" for 4 of "PVC-20"
      When "Admin1" and "Admin2" approve it at the same instant
      Then "PVC-20" has remaining 6
      And exactly 1 audit row "MATERIAL_APPROVE" is written

    @concurrency
    Scenario: Two requests compete for the last stock
      Given PENDING requests by "Wen" for 6 and by "Wei" for 6 of "PVC-20"
      When "Admin1" and "Admin2" each approve one at the same instant
      Then exactly 1 request is APPROVED
      And "PVC-20" has remaining 4

  Rule: MAT-R12 Batch and single review follow the same rules

    # 本規格定義（AD-5）：批次逐筆獨立處理，依畫面順序；失敗的那筆留在 PENDING 並個別回報原因。
    @assumed @AD-5
    Scenario: A batch applies each request independently, in order
      Given PENDING requests Q1 for 6, Q2 for 6, Q3 for 4 of "PVC-20"
      When "Admin1" batch-approves Q1, Q2, Q3 in that order
      Then Q1 and Q3 are APPROVED and Q2 is PENDING
      And "PVC-20" has remaining 0
      And the administrator sees "庫存不足，無法核准" for Q2

  Rule: MAT-R13 Rejecting never changes stock

    Scenario: Reject
      Given a PENDING request by "Wen" for 4 of "PVC-20"
      When "Admin1" rejects it
      Then the request status is REJECTED
      And "PVC-20" stock is unchanged
      And an audit row "MATERIAL_REJECT" is written
