# RPT-F01 送出日報
# 對照 v2 spec：B-062
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@RPT-F01 @B-062
Feature: Submit a daily report
  As a field employee
  I want to record today's work-item quantities, optionally with my crew
  So that the work can be confirmed and paid

  Rule: RPT-R01 The form offers exactly the submitter's catalogue

    Scenario Outline: Catalogue by zone and big-meter flag
      Given "<name>" is signed in
      When "<name>" opens the daily report form
      Then the form offers the <count> items of catalogue "<catalogue>"
      And the report date defaults to "2026-11-15"

      Examples:
        | name | catalogue | count |
        | Wen  | WEST      | 32    |
        | Nan  | SOUTH     | 37    |
        | Big  | BIG_METER | 25    |

    Scenario: A quantity for an item outside the catalogue is refused
      Given "Wen" is signed in
      When "Wen" submits a report with "s_orig_13" = 1.0
      Then the request is rejected as INVALID
      And nothing is written

  Rule: RPT-R02 The report date is today or up to 30 days back, never the future

    Scenario Outline: Report date boundary
      Given "Wen" is signed in
      When "Wen" submits a report dated "<date>" with "direct_13" = 1.0
      Then the outcome is <outcome>

      Examples:
        | date       | outcome  | note            |
        | 2026-11-15 | accepted | today           |
        | 2026-10-16 | accepted | 30 days back    |
        | 2026-10-15 | INVALID  | 31 days back    |
        | 2026-11-16 | INVALID  | tomorrow        |

    Scenario: The date error message
      Given "Wen" is signed in
      When "Wen" submits a report dated "2026-11-16" with "direct_13" = 1.0
      Then the request is rejected as INVALID with message "回報日期須為今天或往前 30 天內，不可選擇未來日期"
      And nothing is written

  Rule: RPT-R03 A quantity is 0 to 999.9 in steps of 0.1; blank means 0

    Scenario Outline: Quantity boundary
      Given "Wen" is signed in
      # D-096：另外填一個有數量的工項，讓這張表只檢查 direct_13 的邊界（全部為 0 的回報見 RPT-R08）。
      When "Wen" submits a report with "direct_13" = "<qty>" and "indirect_13" = 1.0
      Then the outcome is <outcome>
      And the stored quantity of "direct_13" is <tenths> tenths

      Examples:
        | qty    | outcome  | tenths |
        |        | accepted | 0      |
        | 0      | accepted | 0      |
        | 0.1    | accepted | 1      |
        | 2.3    | accepted | 23     |
        | 999.9  | accepted | 9999   |
        | 1000   | INVALID  | -      |
        | 0.05   | INVALID  | -      |
        | -1     | INVALID  | -      |
        | abc    | INVALID  | -      |

  Rule: RPT-R04 A person may have at most 3 own, existing reports per report date

    Scenario: The fourth own report is refused
      Given "Wen" has 3 own reports dated "2026-11-15"
      When "Wen" submits a report dated "2026-11-15" with "direct_13" = 1.0
      Then the request is rejected as CONFLICT with message "每日最多只能送出 3 筆回報"
      And nothing is written

    Scenario: Being a collaborator does not use the quota
      Given "Wen" is a collaborator on 3 reports dated "2026-11-15" submitted by "Wei"
      When "Wen" submits a report dated "2026-11-15" with "direct_13" = 1.0
      Then the report is saved as PENDING

    @Q-039
    Scenario: Deleting a pending report frees the quota
      Given "Wen" has 3 own reports dated "2026-11-15", one of them PENDING
      And "Wen" deleted that PENDING report
      When "Wen" submits a report dated "2026-11-15" with "direct_13" = 1.0
      Then the report is saved as PENDING

    @concurrency
    Scenario: Two simultaneous submits cannot exceed the cap
      Given "Wen" has 2 own reports dated "2026-11-15"
      When "Wen" submits 2 reports dated "2026-11-15" at the same instant
      Then exactly 1 is saved
      And the other is rejected as CONFLICT with message "每日最多只能送出 3 筆回報"

  Rule: RPT-R05 Collaborators are same-zone, same-type, non-archived USERs, at most 6, never the submitter
    # D-097：不符資格或重複的共同作業者一律拒絕，不再靜默略過。

    Scenario: An eligible collaborator is saved
      Given "Wen" is signed in
      When "Wen" submits a report naming collaborator "Wei"
      Then the saved crew is "Wen, Wei"

    Scenario Outline: An ineligible collaborator is refused
      Given "Wen" is signed in
      When "Wen" submits a report naming collaborator "<who>"
      Then the request is rejected as INVALID with message "共同作業者最多 6 人，且須為同一區域、同一類型的啟用員工"
      And nothing is written

      Examples:
        | who    | why                  |
        | Nan    | different zone       |
        | Big    | different type       |
        | Old    | archived             |
        | Admin1 | not a USER           |
        | Wen    | the submitter itself |

    Scenario: Naming the same collaborator twice is refused
      Given "Wen" is signed in
      When "Wen" submits a report naming collaborators "Wei" then "Wei"
      Then the request is rejected as INVALID with message "共同作業者最多 6 人，且須為同一區域、同一類型的啟用員工"
      And nothing is written

    Scenario: Crew order is the order the submitter chose
      Given "Wen" is signed in
      When "Wen" submits a report naming collaborators "Wan" then "Wei"
      Then the saved crew is "Wen, Wan, Wei" in that order

  Rule: RPT-R06 Administrators do not file daily reports

    @Q-018
    Scenario Outline: ADMIN and OWNER are turned away
      Given "<name>" is signed in
      When "<name>" submits a daily report
      Then the request is rejected as FORBIDDEN
      And nothing is written except an audit row "ACCESS_DENIED"

      Examples:
        | name   |
        | Admin1 |
        | Kuei   |

  Rule: RPT-R07 A saved report is PENDING and audited

    Scenario: Solo report
      Given "Wen" is signed in
      When "Wen" submits a report with "direct_13" = 2.0
      Then the report is saved as PENDING
      And an audit row "REPORT_CREATE" is written with actor "Wen"

    Scenario: Crew report records the crew size
      Given "Wen" is signed in
      When "Wen" submits a report naming collaborators "Wei" then "Wan"
      Then the audit description contains "共 3 人作業"

  Rule: RPT-R08 A report needs at least one quantity above 0
    # D-096：全部為 0（含空白）的回報不成立。自訂工項（REV-R20）有數量也算；編輯見 RPT-R14。

    Scenario: A report with no quantity is refused
      Given "Wen" is signed in
      When "Wen" submits a report with every quantity blank
      Then the request is rejected as INVALID with message "請至少填寫一個工項數量"
      And nothing is written
