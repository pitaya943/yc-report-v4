# AUD-F02 稽核軌跡
# 對照 v2 spec：B-037, B-067, B-083, B-097
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@AUD-F02 @B-037 @B-067 @B-083 @B-097
Feature: Audit trail

  Rule: AUD-R10 Every change, export, download, bank reveal, and blocked attempt writes one row

    @Q-049
    Scenario Outline: What is logged
      When "<actor>" completes the action "<action>"
      Then exactly 1 audit row "<type>" is written with actor "<actor>"

      Examples:
        | actor  | action                         | type                |
        | Wen    | submit a report                | REPORT_CREATE       |
        | Wen    | reveal own bank number         | BANK_REVEAL         |
        | Wen    | export history                 | EXPORT              |
        | Admin1 | confirm a report               | REPORT_CONFIRM      |
        | Admin1 | open a ledger receipt          | FILE_DOWNLOAD       |
        | Admin1 | change a unit price            | SYSTEM_CONFIG       |
        | Admin1 | void a ledger entry            | LEDGER_VOID         |
        | Kuei   | switch a role                  | ACCOUNT_ROLE_CHANGE |
        | Kuei   | change the retention cap       | SYSTEM_CONFIG       |
        | Wen    | attempt to confirm a report    | ACCESS_DENIED       |

    Scenario: A row says who, when, what kind, and what changed
      When "Admin1" changes the retention cap from 60000 to 80000
      Then the audit row has the Taipei time, actor "Admin1", type "SYSTEM_CONFIG"
      And the description contains "60000" and "80000"

  Rule: AUD-R11 Viewing writes nothing

    Scenario Outline: Not logged
      When "<actor>" <action>
      Then no audit row is written

      Examples:
        | actor  | action                                   |
        | Wen    | opens history                            |
        | Admin1 | opens the payroll page                   |
        | Admin1 | views a masked bank number               |

    @provisional @Q-058
    Scenario Outline: Sign-in and sign-out are not logged
      When "Wen" <action>
      Then no audit row is written

      Examples:
        | action                       |
        | signs in                     |
        | signs out                    |
        | fails a sign-in once         |

  Rule: AUD-R12 Only the owner reads the log

    Scenario: Owner view and filters
      Given audit rows by "Wen" and "Admin1" on "2026-11-10" and "2026-11-12"
      When "Kuei" filters the log by actor "Admin1" and dates "2026-11-11" to "2026-11-12"
      Then only the row by "Admin1" on "2026-11-12" is listed

    Scenario Outline: Everyone else is refused
      When "<name>" opens the audit log
      Then the request is rejected as FORBIDDEN
      And an audit row "ACCESS_DENIED" is written with actor "<name>"

      Examples:
        | name   |
        | Wen    |
        | Admin1 |

    Scenario: The owner's own actions are logged too
      When "Kuei" archives "Admin2"
      Then an audit row "ACCOUNT_ARCHIVE" is written with actor "Kuei"

  Rule: AUD-R13 Rows are permanent and immutable

    @provisional @Q-059
    Scenario Outline: No edit or delete
      When "Kuei" tries to <action> an audit row
      Then the request is rejected as INVALID
      And the row is unchanged

      Examples:
        | action |
        | edit   |
        | delete |

  Rule: AUD-R14 Automatic actions are attributed to SYSTEM

    Scenario Outline: System actor
      When <event>
      Then the audit row "<type>" has actor SYSTEM

      Examples:
        | event                                        | type            |
        | the fifth wrong password locks an account    | ACCOUNT_LOCKOUT |
