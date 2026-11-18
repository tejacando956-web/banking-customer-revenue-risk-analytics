# KPI Dictionary — End-to-End Retail Banking Analytics

The project's **15 headline KPIs** — the exact contents of `outputs/kpi_summary.csv` —
in plain words: what each one means, the exact calculation behind it, and where the
number comes from. All values below are the current ones — regenerate everything
with `python3 analysis.py`.

## Words used everywhere in this dictionary

- **Segment** — the bank's three customer groups: **Affluent** (wealthy customers),
  **Mass** (everyday customers), **Small Business**.
- **DPD (days past due)** — how many days late a loan payment is. Loans are sorted
  into five buckets: **Current (0 DPD)** = not late at all · **1–29 DPD** = 1 to 29
  days late · **30–59 DPD** · **60–89 DPD** · **90+ DPD** = 90 or more days late.
- **30+ DPD rate** — the share of loans that are 30 or more days late:
  `loans with days_past_due ≥ 30 ÷ all loans × 100`. This is the headline
  "delinquency" (late-loan) rate used across the whole project.
- **Credit band** — a group based on the customer's credit score:
  **Poor (<600)** = score under 600 · **Fair (600–669)** · **Good (670–739)** ·
  **Excellent (740+)** = 740 or more.
- **Deposits** — money customers keep in checking and savings accounts. Credit-card
  balances are NOT deposits (a credit-card balance is money the customer owes, so
  it is stored as a negative number and left out of every deposit total).
- **Product type** — each different kind of product a customer holds counts once:
  the account types (checking, savings, credit card) plus each loan type
  (auto loan, personal loan, mortgage). Holding a checking account and an auto
  loan = 2 product types.
- **Revenue** — money the bank earns, in three parts:
  **loan interest** (see below) + **transaction fees** (the `fee_usd` charged on
  transactions) + **account fees** (a set yearly fee per account: checking $60,
  savings $12, credit card $47). Total revenue is always the sum of the three.
- **Loan interest** — for each loan: `balance still owed × the product's yearly
  interest rate`. Rates: mortgage 6.60%, auto 7.40%, personal 11.90%.
- **Digital adoption** — the share of transactions done on the digital channels:
  `(mobile + online transactions) ÷ all transactions × 100`. Branch and ATM are
  not digital.

## The 15 headline KPIs

### Deposits and customer value

| KPI | What it means | How it is calculated | Source |
|---|---|---|---|
| `total_deposits_usd` = $13,780,468.73 | All the money customers keep in checking and savings | Sum of `balance_usd` over every checking and savings account (credit-card accounts excluded — that money is owed, not kept) | `outputs/segment_summary.csv` (per segment) |
| `top_deposit_cell_share_pct` = 40.04 | How much of all deposit money sits in the single biggest segment × account-type group ("cell") — Affluent savings | Split deposits by segment × account type (6 cells); the biggest cell is Affluent savings at $5,517,722.17; `that cell ÷ total deposits × 100` = $5,517,722 ÷ $13,780,469 × 100 | `outputs/deposits_by_segment_product.csv` |
| `top_decile_revenue_share_pct` = 45.77 | Share of all revenue earned from the top 10% of customers | Rank customers by their own revenue (loan interest + transaction fees + their account fees, per customer); add up the top 80 customers (10% of 800) = $1,365,083.95; `their revenue ÷ total revenue × 100` | `outputs/customer_value.csv` |

### Revenue

| KPI | What it means | How it is calculated | Source |
|---|---|---|---|
| `total_revenue_usd` = $2,982,737.43 | All money the bank earned in the year | `loan_interest_revenue_usd + fee_revenue_usd` (and fee revenue itself is transaction fees + account fees — see the rows below) | `outputs/product_revenue.csv` |
| `loan_interest_revenue_usd` = $2,911,566.37 | Interest earned on loans | For every loan: `balance still owed × product rate` (mortgage 6.60%, auto 7.40%, personal 11.90%), then add all loans together | `outputs/product_revenue.csv` |
| `fee_revenue_usd` = $71,171.06 | All fee income | `transaction fees (sum of fee_usd in transactions.csv = $9,316.06) + account fees ($61,855.00 = 668 checking × $60 + 432 savings × $12 + 353 credit cards × $47)` | `outputs/product_revenue.csv` |
| `top_segment_revenue_per_customer_usd` = $5,508.92 | Revenue per customer in the segment that earns the most per customer — Affluent | For each segment: `segment revenue ÷ segment customers`; the largest wins. Affluent: $1,068,729.86 ÷ 194 (segment revenue basis — see the two-bases note below). The other segments on the same basis: Small Business $3,554.86, Mass $2,943.34 | `outputs/segment_summary.csv` + `outputs/product_revenue.csv` |

### Relationships (how many products each customer holds)

| KPI | What it means | How it is calculated | Source |
|---|---|---|---|
| `multi_product_holding_rate_pct` = 47.5 | Share of customers with a deep relationship — they hold 3 or more different product types | For each customer, count distinct product types (account types + loan types, see "Product type" above); then `customers with a count of 3 or more ÷ all customers × 100` = 380 ÷ 800 × 100 | `outputs/segment_summary.csv` (per segment) |
| `customers_holding_2_products` = 415 | How many customers hold exactly 2 product types — the biggest single group, and the cross-sell opportunity (one more product makes them a deep relationship) | Count of customers whose distinct product-type count is exactly 2 | `outputs/customer_value.csv` (products_held column) |

### Loan risk (late payments)

| KPI | What it means | How it is calculated | Source |
|---|---|---|---|
| `total_loans` = 904 | How many loans the bank has | Number of rows in `data/loans.csv` | `outputs/kpi_summary.csv` |
| `delinquency_rate_30plus_pct` = 8.41 | The headline late rate: share of loans 30+ days late | `loans with days_past_due ≥ 30 ÷ all loans × 100` = 76 ÷ 904 × 100 | `outputs/dpd_by_credit_segment.csv` (by band × segment) |
| `chargeoff_proxy_rate_pct` = 1.33 | Share of loans so late (90+ days) they are likely to be written off — a stand-in measure, not real write-offs | `loans with days_past_due ≥ 90 ÷ all loans × 100` = 12 ÷ 904 × 100 | `outputs/kpi_summary.csv` |
| `worst_dpd_product_30plus_pct` = 11.17 | The worst late rate of any loan product — it belongs to **Mortgage** | For each loan product (mortgage, auto, personal): compute its 30+ DPD rate; the highest wins. Mortgage: 22 of its 197 loans are 30+ days late (auto 7.52%, personal 7.79%) | `outputs/loans_by_product_dpd.csv` |

### Channels and monthly activity

| KPI | What it means | How it is calculated | Source |
|---|---|---|---|
| `digital_adoption_share_pct` = 70.52 | How much banking happens on digital channels | `(mobile + online transactions) ÷ all transactions × 100` = 3,526 ÷ 5,000 × 100 (see "Digital adoption" above) | `outputs/digital_by_segment.csv` (by segment) |
| `monthly_active_customers_last` = 401 | How many different customers transacted in the last month (Dec 2024) | Count of distinct customer IDs in that month's transactions. The first month (Jan 2024) was 271 — the full monthly series is in the source file | `outputs/monthly_actives_by_segment.csv` (by segment) |

## The two revenue bases (read this before quoting segment revenue)

Revenue is measured on two bases in this project, and both are stated wherever
they are used:

- **Segment basis** — a segment's revenue = its customers' **loan interest +
  transaction fees**. Account fees are bank-wide and are not split by segment,
  so the three segments add up to $2,920,882.43 (interest $2,911,566.37 +
  transaction fees $9,316.06), not to total revenue. Revenue-per-customer KPIs
  use this basis.
- **Per-customer basis** — a customer's revenue = their loan interest + their
  transaction fees + **their own account fees** (`outputs/customer_value.csv`).
  On this basis the customers add back up to total revenue, $2,982,737.43.
  The top-decile share (45.77%) uses this basis.

## Supporting detail

The 15 KPIs above are the headline set. Everything else the analysis computes
lives in the breakdown files in `outputs/`, ready to open in an interview:
per-segment customers, accounts, deposits and medians (`segment_summary.csv`);
revenue by product line (`product_revenue.csv`); the full credit-band × segment
late-rate grid behind the heatmap — including the Poor band's 21.05% and the
50.00% Poor × Small Business cell that rests on only 2 loans
(`dpd_by_credit_segment.csv`); deposits by segment × account type
(`deposits_by_segment_product.csv`); one row per customer with deposits, revenue
and products held (`customer_value.csv` — including the 53 customers holding 4+
product types); loans by product × DPD bucket (`loans_by_product_dpd.csv`);
digital adoption inside each segment — 70.49% to 70.62%, flat
(`digital_by_segment.csv`); monthly actives by segment, including Jan 2024's 271
and Affluent's fastest growth of +59.38% (`monthly_actives_by_segment.csv`);
monthly fee revenue (`monthly_fees.csv`); plus the Module 0 data-quality report
(14 checks, all clean) in `data_quality_report.md` and the auto-generated
executive pack in `kpi_pack.md`.
