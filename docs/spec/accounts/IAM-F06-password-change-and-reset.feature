# IAM-F06 密碼變更與重設
# 對照 v2 spec：B-008
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@IAM-F06 @B-008
Feature: Password change and reset

  Rule: IAM-R30 Changing one's own password needs the current password and a matching confirmation

    Scenario Outline: Own password change
      Given "<who>" is signed in
      When "<who>" changes their password with current "<current>", new "<new>", confirmation "<confirm>"
      Then the outcome is <outcome> with message "<message>"

      Examples:
        | who    | current | new      | confirm  | outcome  | message                    |
        | Wen    | correct | newpass1 | newpass1 | accepted |                            |
        | Wen    | wrong   | newpass1 | newpass1 | INVALID  | 目前密碼不正確             |
        | Wen    | correct | newpass1 | newpass2 | INVALID  | 兩次輸入的密碼不一致       |
        | Wen    | correct | short    | short    | INVALID  | 密碼長度須為 6 至 30 個字  |
        | Admin1 | correct | newpass1 | newpass1 | accepted |                            |
        | Admin1 | wrong   | newpass1 | newpass1 | INVALID  | 目前密碼不正確             |

    @provisional @Q-053
    Scenario: The owner also enters the current password
      Given "Kuei" is signed in
      When "Kuei" changes their password with a wrong current password
      Then the request is rejected as INVALID with message "目前密碼不正確"

    Scenario: A password change is audited without the password
      Given "Wen" is signed in
      When "Wen" changes their password successfully
      Then an audit row "PASSWORD_CHANGE" is written with actor "Wen"
      And the audit description contains neither the old nor the new password

  Rule: IAM-R31 An administrator resets a USER password without the current password

    Scenario: Reset
      Given "Admin1" is signed in
      When "Admin1" resets the password of "Wen" to "newpass1"
      Then "Wen" can sign in with "newpass1"
      And an audit row "PASSWORD_CHANGE" is written with actor "Admin1"

  Rule: IAM-R32 There is no self-service password recovery

    Scenario: Forgotten password
      When a visitor asks to recover the password of "Wen"
      Then no such action exists
      # 員工請管理員重設；owner 的密碼在系統外重設（Q-046）。
