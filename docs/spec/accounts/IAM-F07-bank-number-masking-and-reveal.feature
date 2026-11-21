# IAM-F07 銀行帳號遮罩與顯示
# 對照 v2 spec：B-014, B-081, B-082, B-093
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@IAM-F07 @B-014 @B-081 @B-082 @B-093
Feature: Bank number masking and reveal

  Background:
    Given "Wen" has bank number "12345678901234"

  Rule: IAM-R40 Only the last four digits are shown by default

    Scenario Outline: Default view
      Given "<viewer>" is signed in
      When "<viewer>" views the bank number of "Wen"
      Then the value shown ends with "1234" and shows no other digit
      And no audit row is written

      Examples:
        | viewer |
        | Wen    |
        | Admin1 |
        | Kuei   |

  Rule: IAM-R41 Revealing the full number is allowed to the holder and administrators, and is audited

    Scenario Outline: Reveal
      Given "<viewer>" is signed in
      When "<viewer>" reveals the bank number of "Wen"
      Then the value shown is "12345678901234"
      And an audit row "BANK_REVEAL" is written with actor "<viewer>" naming "Wen"

      Examples:
        | viewer |
        | Wen    |
        | Admin1 |

  Rule: IAM-R42 A USER never sees another person's financial fields

    Scenario Outline: Other people's figures
      Given "Wei" is signed in
      When "Wei" requests the <field> of "Wen"
      Then the request is rejected as FORBIDDEN
      And nothing is written except an audit row "ACCESS_DENIED" with actor "Wei"

      Examples:
        | field              |
        | bank number        |
        | insurance amount   |
        | uninsured rate     |
        | retention          |
        | payroll figures    |

  Rule: IAM-R43 Without the encryption key the number is unreadable, never stored in plain text, and nothing else stops

    @Q-022
    Scenario: View without the key
      Given the encryption key is missing
      When "Admin1" views the bank number of "Wen"
      Then the value shown is "無法讀取"

    Scenario: Edit without the key
      Given the encryption key is missing
      When "Admin1" sets the bank number of "Wen" to "98765432109876"
      Then the request is rejected as BLOCKED with message "銀行帳號目前無法讀取，無法修改"
      And nothing is written

    Scenario: Other features keep working
      Given the encryption key is missing
      When "Wen" submits a report with "direct_13" = 1.0
      Then the report is saved as PENDING

    @api
    Scenario: Storage never holds the plain number
      When "Admin1" sets the bank number of "Wen" to "98765432109876"
      Then the stored value does not contain "98765432109876"
