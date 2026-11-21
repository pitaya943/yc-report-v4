# IAM-F02 登入鎖定與頻率限制
# 對照 v2 spec：B-089, B-080
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@IAM-F02 @B-089 @B-080
Feature: Sign-in lockout and rate limit

  Rule: IAM-R04 Five wrong passwords for one account lock it for 15 minutes

    Scenario: The fifth failure locks the account
      Given "Wen" has 4 failed sign-ins in the last 15 minutes
      When "Wen" signs in with a wrong password
      Then the request is rejected as LOCKED with message "密碼錯誤次數過多，請在 15 分鐘後再試"
      And an audit row "ACCOUNT_LOCKOUT" is written with actor SYSTEM

    Scenario: A correct password during the lock is still refused
      Given "Wen" was locked 5 minutes ago
      When "Wen" signs in with the correct password
      Then the request is rejected as LOCKED with message "密碼錯誤次數過多，請在 15 分鐘後再試"

    Scenario Outline: Lock boundary
      Given "Wen" was locked <elapsed> ago
      When "Wen" signs in with the correct password
      Then the outcome is <outcome>

      Examples:
        | elapsed       | outcome   |
        | 14 min 59 sec | LOCKED    |
        | 15 min 00 sec | signed in |

  Rule: IAM-R05 The failure count resets on success, when the lock ends, and after 15 quiet minutes

    Scenario Outline: Count after a reset event
      Given "Wen" has <before> failed sign-ins
      And <event>
      When "Wen" signs in with a wrong password
      Then the failure count for "Wen" is 1
      And "Wen" is not locked

      Examples:
        | before | event                                   |
        | 3      | "Wen" then signed in successfully       |
        | 5      | the 15-minute lock has ended            |
        | 3      | 15 minutes passed with no further failure |

  Rule: IAM-R06 Failures are counted per account, not per visitor

    Scenario: Failures on one account do not lock another
      Given "Wen" has 5 failed sign-ins and is locked
      When "Wei" signs in with the correct password
      Then "Wei" is signed in

  Rule: IAM-R07 One client address may attempt sign-in at most 10 times per minute

    Scenario: The eleventh attempt in a minute is limited
      Given one client address has made 10 sign-in attempts in the last 60 seconds
      When that address attempts another sign-in with a correct password
      Then the request is rejected as RATE_LIMITED

    @concurrency
    Scenario: The limit holds across workers and restarts
      Given 2 workers serve sign-in
      When one client address makes 11 attempts in 60 seconds spread over both workers
      Then exactly 10 attempts are evaluated
