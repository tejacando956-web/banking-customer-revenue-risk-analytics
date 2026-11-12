-- End-to-End Retail Banking Analytics - SQL highlights (SQLite/Postgres-compatible syntax)
-- One pipeline, five modules. Assumes tables: customers, accounts, loans, transactions, products.

-- MODULE 1 | Q1: Segment 360 summary - customers, accounts per customer, deposits
SELECT c.segment, COUNT(DISTINCT c.customer_id) AS customers,
       COUNT(a.account_id) AS accounts,
       ROUND(COUNT(a.account_id)*1.0/COUNT(DISTINCT c.customer_id),2) AS accounts_per_customer,
       SUM(CASE WHEN a.account_type IN ('checking','savings') THEN a.balance_usd END) AS total_deposits
FROM customers c LEFT JOIN accounts a ON a.customer_id = c.customer_id
GROUP BY c.segment ORDER BY total_deposits DESC;

-- MODULE 1 | Q2: Multi-product holding - customers with 3+ distinct product types (deep relationship)
WITH holdings AS (
  SELECT customer_id, account_type AS ptype FROM accounts
  UNION ALL SELECT customer_id, 'loan_'||loan_type FROM loans)
SELECT ROUND(100.0*SUM(CASE WHEN n_types>=3 THEN 1 ELSE 0 END)/COUNT(*),2) AS deep_relationship_pct
FROM (SELECT customer_id, COUNT(DISTINCT ptype) AS n_types FROM holdings GROUP BY customer_id) h;

-- MODULE 1 | Q3: Cohort-style account opening trend by quarter
SELECT SUBSTR(open_date,1,4)||'-Q'||((CAST(SUBSTR(open_date,6,2) AS INTEGER)-1)/3+1) AS open_quarter,
       COUNT(*) AS accounts_opened
FROM accounts GROUP BY open_quarter ORDER BY open_quarter;

-- MODULE 2 | Q4: Revenue by segment with window-function share of total
WITH rev AS (
  SELECT c.segment, SUM(l.balance_usd * CASE l.loan_type WHEN 'auto' THEN .074 WHEN 'personal' THEN .119 ELSE .066 END) AS interest_rev
  FROM loans l JOIN customers c ON c.customer_id = l.customer_id GROUP BY c.segment)
SELECT segment, ROUND(interest_rev,2) AS interest_revenue,
       ROUND(100.0*interest_rev/SUM(interest_rev) OVER (),2) AS share_pct
FROM rev ORDER BY interest_revenue DESC;

-- MODULE 2 | Q5: Monthly revenue trend with LAG growth %
WITH m AS (SELECT SUBSTR(txn_date,1,7) AS month, SUM(fee_usd) AS fee_rev FROM transactions GROUP BY month)
SELECT month, ROUND(fee_rev,2) AS fee_revenue,
       ROUND(100.0*(fee_rev - LAG(fee_rev) OVER (ORDER BY month))/NULLIF(LAG(fee_rev) OVER (ORDER BY month),0),2) AS mom_growth_pct
FROM m ORDER BY month;

-- MODULE 2 | Q6: Product revenue ranking (loan interest by product)
SELECT loan_type, COUNT(*) AS loans, ROUND(SUM(balance_usd),2) AS outstanding,
       ROUND(SUM(balance_usd * CASE loan_type WHEN 'auto' THEN .074 WHEN 'personal' THEN .119 ELSE .066 END),2) AS annual_interest
FROM loans GROUP BY loan_type ORDER BY annual_interest DESC;

-- MODULE 3 | Q7: Delinquency by DPD bucket
SELECT CASE WHEN days_past_due=0 THEN 'Current (0)' WHEN days_past_due<30 THEN '1-29' WHEN days_past_due<60 THEN '30-59'
            WHEN days_past_due<90 THEN '60-89' ELSE '90+' END AS dpd_bucket,
       COUNT(*) AS loans, ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS share_pct, ROUND(SUM(balance_usd),2) AS balance_at_risk
FROM loans GROUP BY dpd_bucket ORDER BY MIN(days_past_due);

-- MODULE 3 | Q8: Delinquency rate by credit band
SELECT CASE WHEN c.credit_score<600 THEN 'Poor (<600)' WHEN c.credit_score<670 THEN 'Fair (600-669)'
            WHEN c.credit_score<740 THEN 'Good (670-739)' ELSE 'Excellent (740+)' END AS credit_band,
       COUNT(*) AS loans,
       ROUND(100.0*SUM(CASE WHEN l.days_past_due>=30 THEN 1 ELSE 0 END)/COUNT(*),2) AS delinquency_30plus_pct
FROM loans l JOIN customers c ON c.customer_id=l.customer_id GROUP BY credit_band ORDER BY delinquency_30plus_pct DESC;

-- MODULE 3 | Q9: Delinquency by segment x loan type (risk concentration matrix)
SELECT c.segment, l.loan_type, COUNT(*) AS loans,
       ROUND(100.0*SUM(CASE WHEN l.days_past_due>=30 THEN 1 ELSE 0 END)/COUNT(*),2) AS delinquency_pct
FROM loans l JOIN customers c ON c.customer_id=l.customer_id
GROUP BY c.segment, l.loan_type ORDER BY delinquency_pct DESC;

-- MODULE 4 | Q10: Channel mix and digital adoption share
SELECT channel, COUNT(*) AS txns, ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS share_pct, ROUND(SUM(amount_usd),2) AS value_usd
FROM transactions GROUP BY channel ORDER BY txns DESC;
-- digital share = SUM(share_pct) WHERE channel IN ('mobile','online')

-- MODULE 4 | Q11: Monthly active customers trend
SELECT SUBSTR(txn_date,1,7) AS month, COUNT(DISTINCT customer_id) AS monthly_active_customers,
       COUNT(*) AS txns FROM transactions GROUP BY month ORDER BY month;

-- MODULE 0 | Q12: Data-quality checks - orphan keys and duplicate primary keys
SELECT 'accounts_orphans' AS check_name, COUNT(*) AS issues FROM accounts a
  LEFT JOIN customers c ON c.customer_id=a.customer_id WHERE c.customer_id IS NULL
UNION ALL SELECT 'duplicate_customer_ids', COUNT(*) FROM (SELECT customer_id FROM customers GROUP BY customer_id HAVING COUNT(*)>1);
