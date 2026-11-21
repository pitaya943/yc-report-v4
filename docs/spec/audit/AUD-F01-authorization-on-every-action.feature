# AUD-F01 每個動作都重新檢查權限
# 對照 v2 spec：B-006, B-087
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@AUD-F01 @B-006 @B-087
Feature: Authorization on every action

  Rule: AUD-R01 A request without a session is turned away and not audited

    Scenario: Not signed in
      When a visitor requests any protected action
      Then the request is rejected as UNAUTHENTICATED
      And no audit row is written

  Rule: AUD-R02 The server decides by role, ownership, and state, whatever the interface showed

    Scenario Outline: Permission matrix
      Given "<actor>" is signed in
      When "<actor>" sends the request "<action>" directly
      Then the outcome is <outcome>

      Examples: Daily reporting
        | actor  | action                                   | outcome   |
        | Wen    | submit own report                        | accepted  |
        | Admin1 | submit a report                          | FORBIDDEN |
        | Wen    | view a report of "Nan"                   | FORBIDDEN |
        | Wen    | edit own CONFIRMED report                | FORBIDDEN |
        | Wei    | edit a report where Wei is collaborator  | FORBIDDEN |

      Examples: Review and payroll
        | actor  | action                    | outcome   |
        | Wen    | confirm a report          | FORBIDDEN |
        | Wen    | calculate payroll         | FORBIDDEN |
        | Wen    | view payroll of "Wei"     | FORBIDDEN |
        | Wen    | export payroll            | FORBIDDEN |
        | Admin1 | calculate payroll         | accepted  |

      Examples: Materials and ledger
        | actor  | action                          | outcome   |
        | Admin1 | request a material              | FORBIDDEN |
        | Wen    | cancel a request of "Wei"       | FORBIDDEN |
        | Wen    | adjust stock                    | FORBIDDEN |
        | Wen    | open the ledger                 | FORBIDDEN |

      Examples: Accounts and audit
        | actor  | action                          | outcome   |
        | Wen    | create an account               | FORBIDDEN |
        | Admin1 | archive "Wen"                   | accepted  |
        | Admin1 | archive "Admin2"                | FORBIDDEN |
        | Admin1 | open the audit log              | FORBIDDEN |
        | Kuei   | open the audit log              | accepted  |
        | Wen    | change the retention cap        | FORBIDDEN |

  Rule: AUD-R03 Every FORBIDDEN outcome writes ACCESS_DENIED and changes nothing else

    Scenario: A blocked attempt is recorded
      Given "Wen" is signed in
      When "Wen" sends the request "confirm a report" directly
      Then an audit row "ACCESS_DENIED" is written with actor "Wen"
      And the audit description names the attempted action
      And nothing else is written
