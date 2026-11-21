# ARC-F01 日月報檔案庫
# 對照 v2 spec：B-077, B-078
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@ARC-F01 @B-077 @B-078
Feature: Scheduled and manual archives

  Rule: ARC-R01 Every day at 23:59 the day's confirmed reports are archived

    Scenario: Daily archive
      Given confirmed reports dated "2026-11-15" by "Wen", "Nan", and "Big", and a pending one by "Wei"
      When the clock reaches "2026-11-15 23:59"
      Then a DAILY archive for "2026-11-15" exists with source auto and generator SYSTEM
      And its Excel file has sheets "西區", "南區", "大表"
      And the file contains "Wen", "Nan", and "Big" with quantities and amount subtotals
      And the file does not contain "Wei"

  Rule: ARC-R02 On the last day of each month at 23:59 the month is archived

    Scenario Outline: Month end
      When the clock reaches "<moment>"
      Then a MONTHLY archive covering "<from>" to "<to>" exists with a payroll-summary sheet

      Examples:
        | moment           | from       | to         |
        | 2026-11-30 23:59 | 2026-11-01 | 2026-11-30 |
        | 2027-02-28 23:59 | 2027-02-01 | 2027-02-28 |
        | 2028-02-29 23:59 | 2028-02-01 | 2028-02-29 |

  Rule: ARC-R03 There is at most one automatic archive per type and date

    Scenario: A restart does not duplicate
      Given an automatic DAILY archive for "2026-11-15" exists
      When the daily job runs again for "2026-11-15"
      Then there is still exactly 1 automatic DAILY archive for "2026-11-15"

    @concurrency
    Scenario: Two workers run the job at once
      Given 2 workers
      When both run the daily job for "2026-11-15" at the same instant
      Then there is exactly 1 automatic DAILY archive for "2026-11-15"

  Rule: ARC-R04 A manual archive is added beside existing ones

    Scenario: Manual daily
      Given an automatic DAILY archive for "2026-11-15" exists
      When "Admin1" generates a DAILY archive for "2026-11-15"
      Then there are 2 DAILY archives for "2026-11-15"
      And the new one has source manual and generator "Admin1"

    Scenario: A second manual copy gets a numeric suffix
      Given a manual DAILY archive for "2026-11-15" exists
      When "Admin1" generates a DAILY archive for "2026-11-15"
      Then the new file name ends with a numeric suffix

    @Q-016
    Scenario: A manual monthly archive covers the 1st through the chosen date
      When "Admin1" generates a MONTHLY archive for "2026-11-15"
      Then the archive covers "2026-11-01" to "2026-11-15"

    Scenario: Type and date are required
      When "Admin1" generates an archive without a type
      Then the request is rejected as INVALID with message "請選擇報表類型與日期"

  Rule: ARC-R05 Downloads use a fresh 3,600-second link and are audited; deleting removes the files

    Scenario: Download
      When "Admin1" downloads an archive
      Then a new download link is issued that lives 3,600 seconds
      And an audit row "FILE_DOWNLOAD" is written

    Scenario: Delete
      When "Admin1" deletes an archive
      Then the archive record and its stored files no longer exist

  Rule: ARC-R06 Without file storage the record exists and the download warns

    Scenario: No storage
      Given file storage is not configured
      When the daily job runs
      Then a DAILY archive record exists without a file
      And downloading it warns that the file is unavailable
