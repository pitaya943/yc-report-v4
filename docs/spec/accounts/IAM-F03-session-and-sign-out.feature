# IAM-F03 Session 與登出
# 對照 v2 spec：B-061, B-079
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@IAM-F03 @B-061 @B-079
Feature: Session and sign-out

  Rule: IAM-R10 A session ends after 30 minutes without use

    Scenario Outline: Idle boundary
      Given "Wen" signed in and last used the system <idle> ago
      When "Wen" requests a protected action
      Then the outcome is <outcome>

      Examples:
        | idle          | outcome         |
        | 29 min 59 sec | accepted        |
        | 30 min 00 sec | UNAUTHENTICATED |

    Scenario: Activity restarts the idle window
      Given "Wen" signed in 40 minutes ago and last used the system 10 minutes ago
      When "Wen" requests a protected action
      Then the outcome is accepted

    Scenario: Saved data survives a timeout
      Given "Wen" saved a report and was then signed out for idle time
      When "Wen" signs in again
      Then the report is still there

    @Q-011
    Scenario: There is no remember-me
      When "Wen" signs in
      Then no credential is issued that outlives the 30-minute idle window

  Rule: IAM-R11 Signing out ends the session immediately

    Scenario: Sign-out
      Given "Wen" is signed in
      When "Wen" signs out
      Then a later protected request from that session is rejected as UNAUTHENTICATED

    Scenario: A signed-in person who opens the sign-in page goes to their landing page
      Given "Wen" is signed in
      When "Wen" opens the sign-in page
      Then "Wen" is sent to the daily report page

  Rule: IAM-R12 The session credential is protected in transit and against forgery

    # 「production」= 環境變數 APP_ENV=production（D-063）
    @api
    Scenario: Cookie attributes
      When "Wen" signs in
      Then the session cookie is HttpOnly
      And its SameSite attribute is Lax or Strict
      And it is Secure in production

    @api
    Scenario: A state-changing request without an anti-forgery token is refused
      Given "Wen" is signed in
      When a state-changing request arrives with the session but without a valid anti-forgery token
      Then the request is rejected as FORBIDDEN
      And an audit row "ACCESS_DENIED" is written with actor "Wen"
      And nothing else is written
