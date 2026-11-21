# LED-F02 證據檔與作廢
# 對照 v2 spec：B-085, B-098
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@LED-F02 @B-085 @B-098
Feature: Evidence files and voiding

  Rule: LED-R10 An entry that has ever had an evidence file can be voided, never deleted

    Scenario Outline: Delete by evidence history
      Given a ledger entry that <history>
      When "Admin1" deletes it
      Then the outcome is <outcome>

      Examples:
        | history                              | outcome  |
        | never had a file                     | accepted |
        | has a current file                   | CONFLICT |
        | had a file that was later replaced   | CONFLICT |

    Scenario: The delete error message
      Given a ledger entry with a receipt
      When "Admin1" deletes it
      Then the request is rejected as CONFLICT with message "此紀錄有證據檔案，不能刪除，只能作廢"
      And nothing is written

  Rule: LED-R11 A voided entry is terminal and excluded from every total

    @provisional @Q-061
    Scenario: Voiding removes the amount from totals but keeps the row
      Given ledger entries: income 2000 on "2026-11-01", expense 500 on "2026-11-10" with a receipt
      When "Admin1" voids the expense
      Then the expense total through "2026-11-10" is 0
      And the petty-cash balance through "2026-11-10" is 2000
      And the entry is listed and marked "作廢"
      And an audit row "LEDGER_VOID" is written

    @provisional @Q-061
    Scenario Outline: Nothing can be done to a voided entry
      Given a voided ledger entry
      When "Admin1" tries to <action> it
      Then the request is rejected as CONFLICT with message "此紀錄已作廢"

      Examples:
        | action |
        | edit   |
        | settle |
        | void   |

  Rule: LED-R12 Every open of a file issues a fresh link that lives 3,600 seconds

    Scenario: An old receipt still opens
      Given a ledger entry dated 120 days ago with a PDF receipt
      When "Admin1" opens the receipt
      Then a new download link is issued
      And an audit row "FILE_DOWNLOAD" is written

    Scenario Outline: Link lifetime boundary
      Given a download link issued <age> seconds ago
      When anyone uses it
      Then the link <result>

      Examples:
        | age  | result          |
        | 3599 | opens the file  |
        | 3600 | no longer works |

    Scenario: Replaced files stay openable
      Given a ledger entry whose receipt was replaced once
      When "Admin1" opens the entry
      Then both the current file and the earlier file can be opened

  Rule: LED-R13 Receipts are PDF, JPEG, PNG, or WebP up to 10 MB

    Scenario Outline: Upload validation
      When "Admin1" attaches a <type> file of <size>
      Then the outcome is <outcome> with message "<message>"

      Examples:
        | type | size      | outcome  | message                                           |
        | PDF  | 10 MB     | accepted |                                                   |
        | PDF  | 10 MB + 1 | INVALID  | 憑證檔案超過 10MB 上限                            |
        | GIF  | 1 MB      | INVALID  | 憑證格式不支援（僅接受 PDF / JPG / PNG / WebP）   |
