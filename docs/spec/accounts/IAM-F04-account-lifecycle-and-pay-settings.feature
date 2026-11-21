# IAM-F04 帳戶生命週期與薪資設定
# 對照 v2 spec：B-007, B-010, B-012, B-013, B-015, B-017, B-074, B-095
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@IAM-F04 @B-007 @B-010 @B-012 @B-013 @B-015 @B-017 @B-074 @B-095
Feature: Account lifecycle and pay settings

  Rule: IAM-R13 An administrator creates USER accounts with a unique display name

    Scenario: Create a USER
      Given "Admin1" is signed in
      When "Admin1" creates account "Lin" with role USER, zone SOUTH, and a 6-character password
      Then account "Lin" exists with role USER, zone SOUTH, and big-meter off
      And an audit row "ACCOUNT_CREATE" is written with actor "Admin1"

    Scenario Outline: Creation is validated
      Given "Admin1" is signed in
      When "Admin1" creates an account with <field> "<value>"
      Then the request is rejected as INVALID with message "<message>"
      And no account is created

      Examples:
        | field        | value          | message                      |
        | display name | (empty)        | 請輸入顯示名稱               |
        | display name | 51 characters  | 顯示名稱最多 50 個字         |
        | display name | Wen            | 此顯示名稱已被使用           |
        | password     | 5 characters   | 密碼長度須為 6 至 30 個字    |
        | password     | 31 characters  | 密碼長度須為 6 至 30 個字    |
        | zone         | EAST           | 請選擇施工區域               |
        | role         | (empty)        | 請選擇角色                   |

    Scenario Outline: Boundary values that are accepted
      Given "Admin1" is signed in
      When "Admin1" creates an account with <field> "<value>"
      Then the account is created

      Examples:
        | field        | value          |
        | display name | 50 characters  |
        | password     | 6 characters   |
        | password     | 30 characters  |

    @provisional @Q-056
    Scenario: Account management lists USER accounts only for an ADMIN
      Given "Admin1" is signed in
      When "Admin1" opens account management
      Then the list contains only USER accounts, West before South

  Rule: IAM-R14 Payment by transfer needs a 14-digit bank number

    Scenario Outline: Bank number format
      Given "Admin1" is signed in
      When "Admin1" sets the bank number of "Wen" to "<input>"
      Then the outcome is <outcome>

      Examples:
        | input              | outcome  | note                 |
        | 12345678901234     | accepted | 14 digits            |
        | 123-45678901234    | accepted | hyphens are ignored  |
        | 1234567890123      | INVALID  | 13 digits            |
        | 123456789012345    | INVALID  | 15 digits            |
        | 1234567890123A     | INVALID  | not all digits       |

    Scenario: The bank-number error message
      Given "Admin1" is signed in
      When "Admin1" sets the bank number of "Wen" to "1234567890123"
      Then the request is rejected as INVALID with message "銀行帳號須為 14 位數字（3 位分行＋11 位帳號）"

    Scenario: Switching to transfer without a bank number
      Given "Wen" is paid by CASH and has no bank number
      When "Admin1" sets the payment method of "Wen" to TRANSFER
      Then the request is rejected as CONFLICT with message "請先設定銀行帳號再改為轉帳"
      And nothing is written

  Rule: IAM-R15 Insurance has three settings: enrolled, not enrolled with a rate, not enrolled and exempt

    Scenario Outline: Insurance settings
      Given "Admin1" is signed in
      When "Admin1" sets "Wen" to <choice> with value "<value>"
      Then the outcome is <outcome> with message "<message>"

      Examples:
        | choice                | value | outcome  | message                                         |
        | enrolled              | 834   | accepted |                                                 |
        | enrolled              | 1     | accepted |                                                 |
        | enrolled              | 0     | INVALID  | 已投保時，扣除額須至少為 1                      |
        | enrolled              | -5    | INVALID  | 勞健保扣除額須為 0 或正整數                     |
        | not enrolled, rate    | 5     | accepted |                                                 |
        | not enrolled, rate    | 100.01 | INVALID | 未投保扣除比例須為 0 到 100 之間，最多兩位小數  |
        | not enrolled, rate    | 3.333 | INVALID  | 未投保扣除比例須為 0 到 100 之間，最多兩位小數  |
        | not enrolled, exempt  |       | accepted |                                                 |

    Scenario Outline: Fixed salary is a whole number of NTD, zero or more
      When "Admin1" sets the fixed salary of "Wen" to "<value>"
      Then the outcome is <outcome>

      Examples:
        | value  | outcome  |
        | 0      | accepted |
        | 5000   | accepted |
        | -1     | INVALID  |
        | 5000.5 | INVALID  |

    Scenario: Every pay-setting change is audited
      When "Admin1" sets the fixed salary of "Wen" to "5000"
      Then an audit row "ACCOUNT_UPDATE" is written with actor "Admin1"

  Rule: IAM-R16 Zone and the big-meter flag select the catalogue for new reports only

    # 依 AD-4：改 zone 或大表旗標只影響之後送出的回報。
    @assumed @AD-4
    Scenario: A zone change applies to the next report
      Given "Admin1" moved "Wen" to zone SOUTH
      When "Wen" opens the daily report form
      Then the form offers the 37 items of catalogue "SOUTH"

    Scenario: The big-meter flag is offered for USER accounts only
      When "Kuei" turns on the big-meter flag for "Admin1"
      Then the request is rejected as INVALID
      And nothing is written

  Rule: IAM-R17 Archiving blocks sign-in and hides the account from pickers; records are kept

    Scenario: Archive
      Given "Wen" has 4 reports
      When "Admin1" archives "Wen"
      Then "Wen" cannot sign in
      And "Wen" is absent from the sign-in name list and the collaborator picker
      And "Wen" still has 4 reports
      And an audit row "ACCOUNT_ARCHIVE" is written with actor "Admin1"

    # 本規格定義（AD-13）：封存時該帳戶現有的 session 立即失效。
    @assumed @AD-13
    Scenario: An archived account is signed out
      Given "Wen" is signed in
      When "Admin1" archives "Wen"
      Then a later protected request from the session of "Wen" is rejected as UNAUTHENTICATED

  Rule: IAM-R18 Restoring reverses an archive

    Scenario: Restore
      Given "Old" is archived
      When "Admin1" restores "Old"
      Then "Old" can sign in
      And "Old" is in the sign-in name list and the collaborator picker
      And an audit row "ACCOUNT_RESTORE" is written with actor "Admin1"

  Rule: IAM-R19 Accounts are never deleted or deactivated

    @Q-019 @Q-032
    Scenario Outline: No such action exists
      Given "Kuei" is signed in
      When "Kuei" tries to <action> the account "Wen"
      Then the request is rejected as INVALID
      And "Wen" and all records of "Wen" are unchanged

      Examples:
        | action             |
        | permanently delete |
        | deactivate         |
