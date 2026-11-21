# PAY-F01 毛額、淨額與實發
# 對照 v2 spec：B-045, B-049, B-050, B-051
# 共用的固定資料見 docs/spec/background.md；結果類別與寫作規約見 docs/spec/conventions.md。
@PAY-F01 @domain @money @B-045 @B-049 @B-050 @B-051
Feature: Gross, net, and final pay
  # 公式：
  #   gross  = Σ(share × unit price) + custom-item money
  #   net    = gross − period retention
  #   final  = net + fixed salary applied − insurance applied − uninsured deduction
  # 預設：WEST 單價 direct_13 = 120，保留金 20/unit，未投保比例 3%。

  Rule: PAY-R01 Fixed salary and insurance apply on payday-10; the uninsured deduction applies on every run
    # 已加保 = insurance > 0（D-064）。exempt 只免除未投保扣除，不影響固定薪資與保險（D-065）。
    # every-period 只讓固定薪資每期套用，保險仍只在 payday-10 扣（D-066）。實發為負數時照實列出（D-068）。

    Scenario Outline: Components by run type and enrolment
      Given "Wen" has confirmed "direct_13" shares of <qty> in the period
      And "Wen" has fixed salary <fixed>, insurance <ins>, every-period "<every>", exempt "<exempt>"
      When payroll is calculated with payday-10 "<p10>"
      Then for "Wen" gross is <gross>, retention <ret>, fixed applied <fa>, insurance applied <ia>, uninsured deduction <ud>, final <final>

      Examples:
        | qty | fixed | ins | every | exempt | p10 | gross | ret | fa   | ia  | ud | final | note                         |
        | 10  | 0     | 0   | no    | no     | no  | 1200  | 200 | 0    | 0   | 36 | 964   | v2 Example A                 |
        | 10  | 5000  | 834 | no    | no     | yes | 1200  | 200 | 5000 | 834 | 0  | 5166  | v2 Example B                 |
        | 10  | 5000  | 834 | no    | no     | no  | 1200  | 200 | 0    | 0   | 0  | 1000  | enrolled, not payday-10      |
        | 10  | 5000  | 0   | yes   | no     | no  | 1200  | 200 | 5000 | 0   | 36 | 5964  | every-period fixed salary    |
        | 10  | 0     | 0   | no    | yes    | no  | 1200  | 200 | 0    | 0   | 0  | 1000  | exempt                       |
        | 0   | 5000  | 0   | no    | no     | yes | 0     | 0   | 5000 | 0   | 0  | 5000  | fixed salary only            |
        | 10  | 5000  | 834 | no    | yes    | yes | 1200  | 200 | 5000 | 834 | 0  | 5166  | exempt keeps fixed and ins   |
        | 10  | 5000  | 834 | yes   | no     | no  | 1200  | 200 | 5000 | 0   | 0  | 6000  | every-period, ins only p10   |
        | 0   | 0     | 834 | no    | no     | yes | 0     | 0   | 0    | 834 | 0  | -834  | negative final listed as is  |

  Rule: PAY-R02 The uninsured deduction base is work-item gross only

    @Q-033
    Scenario: Fixed salary is not in the base
      Given "Wen" has gross 10000 and fixed salary 5000 with every-period on
      When payroll is calculated
      Then the uninsured deduction for "Wen" is 300

    Scenario: A personal rate overrides the zone rate
      Given "Wen" has gross 10000 and a personal uninsured rate of 5%
      When payroll is calculated
      Then the uninsured deduction for "Wen" is 500

    # 自訂工項也是工項，計入基數（D-067）
    Scenario: Custom-item money is in the base
      Given "Wen" has work-item gross 9000 and custom-item money 1000
      When payroll is calculated
      Then the uninsured deduction for "Wen" is 300

  Rule: PAY-R03 Money is rounded half-up to whole NTD at payroll only

    Scenario: A fractional deduction rounds half-up
      Given "Wen" has gross 10001
      When payroll is calculated
      Then the uninsured deduction for "Wen" is 300

    # 300.03 → 300；另一個方向：gross 10017 × 3% = 300.51 → 301
    Scenario: Rounding up
      Given "Wen" has gross 10017
      When payroll is calculated
      Then the uninsured deduction for "Wen" is 301

    # 本規格定義（AD-2）：gross、retention、uninsured deduction 各自四捨五入到整數元，
    # final 用四捨五入後的組成相加。未投保扣除用未四捨五入的 gross 當基數。
    @assumed @AD-2
    Scenario: Each component is rounded, then summed
      Given "Wen" has a confirmed "indirect_13" share of 2.3 at price 75
      # exact: gross 172.5, retention 46, uninsured 5.175
      When payroll is calculated
      Then for "Wen" gross is 173, retention 46, uninsured deduction 5, final 122

    @assumed @AD-2
    Scenario: The displayed components always add up to the final amount
      Given any payroll result
      Then final equals gross − retention + fixed applied − insurance applied − uninsured deduction, using the displayed whole-NTD figures

  Rule: PAY-R04 Each report is priced by the catalogue it was filed under

    Scenario Outline: Price set by account type
      Given "<name>" has a confirmed share of 1.0 of "<item>"
      When payroll is calculated
      Then gross for "<name>" is <gross>

      Examples:
        | name | item       | gross |
        | Wen  | direct_13  | 120   |
        | Nan  | direct_13  | 140   |
        | Big  | bm_50_down | 1100  |

    # 本規格定義（AD-4）：回報在送出時記下它的 catalogue；之後帳戶改 zone 或切換大表，
    # 舊回報仍用原 catalogue 的現行單價與保留金規則。
    @assumed @AD-4
    Scenario: A zone change does not re-price earlier reports
      Given "Wen" has a confirmed share of 1.0 of "direct_13" filed under catalogue WEST
      And "Wen" was later moved to zone SOUTH
      When payroll is calculated for a period containing that report
      Then gross for "Wen" from that report is 120

  Rule: PAY-R05 Incomplete unit prices block payroll

    @Q-024
    Scenario: A missing price for a needed item
      Given the SOUTH price of "direct_13" is unset
      And "Nan" has a confirmed share of 1.0 of "direct_13" in the period
      When payroll is calculated
      Then the request is rejected as BLOCKED with message "單價尚未設定完整，無法計算薪資，請先補齊單價"
      And no payroll result is produced for anyone

    Scenario: A missing price for an unused catalogue does not block
      Given the BIG_METER price of "bm_hole" is unset
      And no big-meter report is in the period
      When payroll is calculated
      Then a payroll result is produced

  Rule: PAY-R06 An account with zero gross and zero final is not listed

    Scenario Outline: Row visibility
      Given "Wen" has gross <gross> and final <final> after rounding
      When payroll is calculated
      Then "Wen" is <listed>

      Examples:
        | gross | final | listed     |
        | 0     | 0     | not listed |
        | 0     | 5000  | listed     |
        | 1200  | 0     | listed     |
