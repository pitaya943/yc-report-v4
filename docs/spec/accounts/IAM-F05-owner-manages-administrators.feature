# IAM-F05 Owner 管理管理員
# 對照 v2 spec：B-096
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@IAM-F05 @B-096
Feature: Owner manages administrators

  Rule: IAM-R20 Only the owner may add, modify, archive, restore, or re-role an ADMIN account

    Scenario Outline: An ADMIN cannot touch another ADMIN
      Given "Admin1" is signed in
      When "Admin1" tries to <action> "Admin2"
      Then the request is rejected as FORBIDDEN
      And nothing is written except an audit row "ACCESS_DENIED" with actor "Admin1"

      Examples:
        | action               |
        | archive              |
        | restore              |
        | reset the password of |
        | change the zone of   |
        | change the role of   |

    Scenario: An ADMIN cannot create an ADMIN
      Given "Admin1" is signed in
      When "Admin1" creates an account with role "ADMIN"
      Then the request is rejected as FORBIDDEN
      And no account is created

    Scenario: The owner archives and restores an ADMIN
      Given "Kuei" is signed in
      When "Kuei" archives "Admin2"
      Then "Admin2" cannot sign in
      And an audit row "ACCOUNT_ARCHIVE" is written with actor "Kuei"

  Rule: IAM-R21 Role switches are owner-only and need the big-meter flag off

    Scenario: USER to ADMIN
      Given "Kuei" is signed in
      When "Kuei" switches "Wen" to role "ADMIN"
      Then "Wen" has role "ADMIN"
      And an audit row "ACCOUNT_ROLE_CHANGE" is written

    @provisional @Q-057
    Scenario: A big-meter account cannot become ADMIN
      Given "Kuei" is signed in
      When "Kuei" switches "Big" to role "ADMIN"
      Then the request is rejected as CONFLICT with message "請先關閉大表旗標，再切換為管理員"
      And nothing is written

  Rule: IAM-R22 The owner account cannot be archived; an ADMIN cannot archive or re-role itself

    Scenario Outline: Self-protection
      Given "<actor>" is signed in
      When "<actor>" tries to <action>
      Then the request is rejected as <outcome> with message "<message>"

      Examples:
        | actor  | action                 | outcome   | message                        |
        | Kuei   | archive "Kuei"         | CONFLICT  | owner 帳戶不能封存             |
        | Admin1 | archive "Admin1"       | CONFLICT  | 不能封存自己目前登入的帳戶     |
