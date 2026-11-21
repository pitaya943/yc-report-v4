# IAM-F01 登入
# 對照 v2 spec：B-060
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@IAM-F01 @B-060
Feature: Sign-in
  As a person with an account
  I want to pick my group and name and enter my password
  So that I reach the landing page for my role

  Rule: IAM-R01 The name list shows only non-archived accounts of the chosen group

    Scenario Outline: Group picker lists the right accounts
      When a visitor chooses group "<group>"
      Then the name list is exactly "<names>"

      Examples:
        | group | names                  |
        | admin | Admin1, Admin2, Kuei   |
        | west  | Big, Wan, Wei, Wen     |
        | south | Nan                    |

    # Kuei 出現在 admin 群組是暫定答案
    @provisional @Q-052
    Scenario: The owner is listed under the admin group
      When a visitor chooses group "admin"
      Then the name list includes "Kuei"

  Rule: IAM-R02 A correct password signs the person in and lands them by role

    Scenario Outline: Landing page by role
      When "<name>" signs in with the correct password
      Then "<name>" is signed in
      And the landing page is "<page>"

      Examples:
        | name   | page         |
        | Wen    | daily report |
        | Admin1 | confirmation |
        | Kuei   | confirmation |

  Rule: IAM-R03 Wrong password, unknown account, and archived account are indistinguishable

    Scenario Outline: Failed sign-in reveals nothing about the account
      When a visitor signs in as "<name>" with "<password>"
      Then the request is rejected as UNAUTHENTICATED with message "密碼錯誤，請重試"
      And nobody is signed in

      Examples:
        | name    | password | why                |
        | Wen     | wrong    | wrong password     |
        | Nobody  | any      | unknown account    |
        | Old     | correct  | archived account   |
