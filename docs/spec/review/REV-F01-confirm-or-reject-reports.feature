# REV-F01 確認或駁回回報
# 對照 v2 spec：B-069, B-071
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@REV-F01 @B-069 @B-071
Feature: Confirm or reject reports

  Rule: REV-R01 Ordinary and big-meter reports are reviewed on separate queues

    Scenario: The ordinary queue excludes big-meter reports
      Given PENDING reports by "Wen", "Nan", and "Big" dated within 30 days
      When "Admin1" opens the ordinary confirmation queue
      Then the queue lists the reports of "Wen" and "Nan" grouped by zone
      And the queue does not list the report of "Big"

  Rule: REV-R02 A batch acts only on reports that are still PENDING

    Scenario: Batch confirm skips non-pending rows
      Given reports R1 PENDING, R2 CONFIRMED, R3 REJECTED
      When "Admin1" batch-confirms R1, R2, R3
      Then R1 is CONFIRMED with reviewer "Admin1"
      And R2 and R3 are unchanged
      And exactly 1 audit row "REPORT_CONFIRM" is written

    Scenario: Reject excludes the report from payroll
      Given a PENDING report by "Wen" with "direct_13" = 10.0 dated "2026-11-10"
      When "Admin1" rejects it
      Then the report state is REJECTED
      And payroll for "2026-11-06" to "2026-11-20" has no gross for "Wen"

    @concurrency
    Scenario: Two administrators confirm the same report at once
      Given a PENDING report R1
      When "Admin1" and "Admin2" confirm R1 at the same instant
      Then R1 is CONFIRMED with exactly one reviewer
      And exactly 1 audit row "REPORT_CONFIRM" is written
      And shares for R1 are stored exactly once

  Rule: REV-R03 Confirmation is not undone on the queue

    Scenario: No unconfirm action exists
      Given a CONFIRMED report R1
      When "Admin1" tries to unconfirm R1 from the confirmation queue
      Then the request is rejected as CONFLICT
      And R1 is CONFIRMED
