# MAT-F01 申請材料
# 對照 v2 spec：B-028, B-057, B-065
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@MAT-F01 @B-028 @B-057 @B-065
Feature: Request materials

  Background:
    Given material "PVC-20" is on tab 1 with remaining 10

  Rule: MAT-R01 A USER sees visible, non-quarantined materials in named tabs

    Scenario Outline: Visibility
      Given material "X" is <state>
      When "Wen" opens materials
      Then "X" is <shown>

      Examples:
        | state                   | shown     |
        | on tab 1, visible       | shown     |
        | hidden                  | not shown |
        | quarantined             | not shown |
        | on a tab with no name   | not shown |

  Rule: MAT-R02 A request is for 1 to 99 of one material, with an optional note

    Scenario Outline: Quantity boundary
      Given "PVC-20" has remaining 200
      When "Wen" requests <qty> of "PVC-20"
      Then the outcome is <outcome>

      Examples:
        | qty | outcome  |
        | 0   | INVALID  |
        | 1   | accepted |
        | 99  | accepted |
        | 100 | INVALID  |
        | 1.5 | INVALID  |

    Scenario: The quantity error message
      When "Wen" requests 0 of "PVC-20"
      Then the request is rejected as INVALID with message "申請數量須為 1 到 99 的整數"
      And nothing is written

    Scenario: A saved request waits for review
      When "Wen" requests 4 of "PVC-20" with note "明天用"
      Then the request is PENDING
      And "PVC-20" stock is unchanged
      And an audit row "MATERIAL_REQUEST" is written with actor "Wen"

    Scenario: A long note is truncated
      When "Wen" requests 4 of "PVC-20" with a 60-character note
      Then the saved note is the first 50 characters

  Rule: MAT-R03 The server refuses a request the stock or the item's state cannot serve

    Scenario Outline: Refusals
      Given "PVC-20" is <state>
      When "Wen" sends a request for <qty> of "PVC-20" directly
      Then the request is rejected as CONFLICT with message "<message>"
      And nothing is written

      Examples:
        | state                | qty | message                  |
        | at remaining 0       | 1   | 庫存不足，無法申請       |
        | at remaining 10      | 11  | 庫存不足，無法申請       |
        | hidden               | 1   | 此材料目前不可申請       |
        | quarantined          | 1   | 此材料目前不可申請       |

  Rule: MAT-R04 A USER may cancel only their own PENDING requests

    Scenario Outline: Cancel
      Given a request by "<owner>" with status <status>
      When "Wen" cancels it
      Then the outcome is <outcome>

      Examples:
        | owner | status   | outcome   |
        | Wen   | PENDING  | accepted  |
        | Wen   | APPROVED | CONFLICT  |
        | Wen   | REJECTED | CONFLICT  |
        | Wei   | PENDING  | FORBIDDEN |

    Scenario: Cancelling removes the request
      Given a PENDING request by "Wen"
      When "Wen" cancels it
      Then the request no longer exists
      And an audit row "MATERIAL_CANCEL" is written

  Rule: MAT-R05 Administrators do not request materials

    Scenario: ADMIN request
      When "Admin1" requests 1 of "PVC-20"
      Then the request is rejected as FORBIDDEN
