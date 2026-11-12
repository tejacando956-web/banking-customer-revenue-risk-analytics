"""End-to-End Retail Banking Analytics - all modules + automated KPI pack.

Module 0  Pipeline & data quality      -> outputs/data_quality_report.md
Module 1  Customer 360 & segmentation  -> outputs/segment_summary.csv
Module 2  Revenue & product performance-> outputs/product_revenue.csv
Module 3  Credit risk (DPD buckets)    -> part of kpi_summary / insights
Module 4  Transactions & channels      -> part of kpi_summary / insights
Module 5  Automated KPI pack           -> outputs/kpi_pack.md
Run: python3 generate_data.py && python3 analysis.py
"""
import pandas as pd, numpy as np, os
B = os.path.dirname(__file__); D, O = f"{B}/data", f"{B}/outputs"; os.makedirs(O, exist_ok=True)
cust = pd.read_csv(f"{D}/customers.csv"); acc = pd.read_csv(f"{D}/accounts.csv")
loans = pd.read_csv(f"{D}/loans.csv"); txn = pd.read_csv(f"{D}/transactions.csv", parse_dates=["txn_date"])
prod = pd.read_csv(f"{D}/products.csv")
K = {}
def k(name, value): K[name] = value

# ---------------- Module 0: data quality ----------------
checks = []
def check(name, bad, total):
    checks.append((name, int(bad), int(total), "PASS" if bad == 0 else "REVIEW"))
    return bad == 0
for df, pk, name in [(cust,"customer_id","customers"),(acc,"account_id","accounts"),(loans,"loan_id","loans"),(txn,"txn_id","transactions")]:
    check(f"{name}: duplicate {pk}", df.duplicated(pk).sum(), len(df))
    check(f"{name}: null {pk}", df[pk].isna().sum(), len(df))
check("accounts: customer_id not in customers", (~acc.customer_id.isin(cust.customer_id)).sum(), len(acc))
check("loans: customer_id not in customers", (~loans.customer_id.isin(cust.customer_id)).sum(), len(loans))
check("transactions: customer_id not in customers", (~txn.customer_id.isin(cust.customer_id)).sum(), len(txn))
check("accounts: zero balances", (acc.balance_usd == 0).sum(), len(acc))
check("loans: negative amounts", (loans.loan_amount_usd < 0).sum(), len(loans))
check("transactions: non-positive amounts", (txn.amount_usd <= 0).sum(), len(txn))
n_review = sum(1 for *_, s in [(a,b,c,d) for a,b,c,d in checks] if s == "REVIEW")
with open(f"{O}/data_quality_report.md","w") as f:
    f.write("# Data Quality Report — Module 0 (Pipeline)\n\nGenerated automatically by `analysis.py` on every run.\n\n")
    f.write(f"Tables profiled: customers ({len(cust)}), accounts ({len(acc)}), loans ({len(loans)}), transactions ({len(txn)}), products ({len(prod)}).\n\n")
    f.write("| Check | Issues | Rows checked | Status |\n|---|---:|---:|---|\n")
    for name, bad, total, s in checks: f.write(f"| {name} | {bad} | {total} | {s} |\n")
    f.write(f"\n**Summary:** {len(checks)-n_review}/{len(checks)} checks fully clean; {n_review} flagged REVIEW (see rows above). "
            "Checks cover primary-key uniqueness, null keys, referential integrity across all fact tables, and value sanity (zero/negative amounts).\n")
k("dq_checks_total", len(checks)); k("dq_checks_review", n_review)

# ---------------- Module 1: Customer 360 & segmentation ----------------
deposits = acc[acc.account_type.isin(["checking","savings"])].groupby("customer_id").balance_usd.sum()
holdings = pd.concat([acc.assign(pt=acc.account_type), loans.assign(pt="loan:"+loans.loan_type)]).groupby("customer_id").pt.nunique()
seg = cust.groupby("segment").agg(customers=("customer_id","count"))
seg["accounts"] = acc.groupby(cust.set_index("customer_id").segment.reindex(acc.customer_id).values).size()
seg["avg_accounts_per_customer"] = (seg.accounts/seg.customers).round(2)
seg["total_deposits_usd"] = deposits.groupby(cust.set_index("customer_id").segment).sum().round(2)
seg["median_deposit_usd"] = deposits.groupby(cust.set_index("customer_id").segment).median().round(2)
seg["multi_product_rate_pct"] = (holdings.groupby(cust.set_index("customer_id").segment).apply(lambda s:(s>=3).mean()*100)).round(2)
seg.reset_index().to_csv(f"{O}/segment_summary.csv", index=False)
k("total_customers", len(cust)); k("total_accounts", len(acc))
k("accounts_per_customer", round(len(acc)/len(cust),2))
k("multi_product_holding_rate_pct", round((holdings>=3).mean()*100,2))  # deep relationship = 3+ distinct product types
k("total_deposits_usd", round(float(deposits.sum()),2))
for s_, r in seg.iterrows(): k(f"customers_{s_.replace(' ','_').lower()}", int(r.customers))

# ---------------- Module 2: Revenue & product performance ----------------
rate = {"auto":7.40,"personal":11.90,"mortgage":6.60}
loans["annual_interest_usd"] = loans.balance_usd * loans.loan_type.map(rate)/100
loans["segment"] = loans.customer_id.map(cust.set_index("customer_id").segment)
txn["segment"] = txn.customer_id.map(cust.set_index("customer_id").segment)
rev_rows = []
for lt, g in loans.groupby("loan_type"):
    rev_rows.append((lt.title()+" Loans (interest)", g.segment.iloc[0] if False else "All", g.annual_interest_usd.sum()))
prod_rev = loans.groupby("loan_type").annual_interest_usd.sum().rename(lambda x: x.title()+" loan interest")
fee_rev = txn.groupby("txn_type").fee_usd.sum()
acct_fee_map = {"checking": 60, "savings": 12, "credit_card": 47}  # blended annual product fees (see products.csv)
account_fees = float(acc.account_type.map(acct_fee_map).sum())
total_loan_interest = loans.annual_interest_usd.sum(); total_fees = txn.fee_usd.sum() + account_fees
pr = pd.DataFrame({"product_line":["Auto loan interest","Personal loan interest","Mortgage interest","Transaction fees"],
                   "revenue_usd":[prod_rev.get("Auto loan interest",0),prod_rev.get("Personal loan interest",0),prod_rev.get("Mortgage loan interest",0),total_fees]})
pr["share_pct"] = (pr.revenue_usd/pr.revenue_usd.sum()*100).round(2); pr = pr.round(2)
pr.to_csv(f"{O}/product_revenue.csv", index=False)
total_revenue = total_loan_interest + total_fees
k("total_revenue_usd", round(float(total_revenue),2)); k("loan_interest_revenue_usd", round(float(total_loan_interest),2))
k("fee_revenue_usd", round(float(total_fees),2)); k("account_fee_revenue_usd", round(account_fees,2))
# monthly revenue trend: monthly fees + 1/12 of annual loan interest spread evenly (stated assumption)
txn["month"] = txn.txn_date.dt.to_period("M").astype(str)
monthly_fees = txn.groupby("month").fee_usd.sum()
monthly_rev = monthly_fees + total_loan_interest/12
growth = (monthly_rev.iloc[-1]/monthly_rev.iloc[0]-1)*100
k("monthly_revenue_first_usd", round(float(monthly_rev.iloc[0]),2)); k("monthly_revenue_last_usd", round(float(monthly_rev.iloc[-1]),2))
k("monthly_revenue_growth_pct", round(float(growth),2))
seg_rev = loans.groupby("segment").annual_interest_usd.sum() + txn.groupby("segment").fee_usd.sum()
top_seg_rev = seg_rev.idxmax(); k("top_revenue_segment", top_seg_rev); k("top_revenue_segment_usd", round(float(seg_rev.max()),2))
rev_per_cust = (seg_rev / cust.segment.value_counts()).round(2)
k("top_segment_revenue_per_customer", rev_per_cust.idxmax()); k("top_segment_revenue_per_customer_usd", float(rev_per_cust.max()))

# ---------------- Module 3: Credit risk ----------------
def bucket(d): return "Current (0 DPD)" if d==0 else "1-29 DPD" if d<30 else "30-59 DPD" if d<60 else "60-89 DPD" if d<90 else "90+ DPD"
loans["dpd_bucket"] = loans.days_past_due.map(bucket)
k("total_loans", len(loans)); k("total_loan_balance_usd", round(float(loans.balance_usd.sum()),2))
k("delinquency_rate_30plus_pct", round((loans.days_past_due>=30).mean()*100,2))
k("chargeoff_proxy_rate_pct", round((loans.days_past_due>=90).mean()*100,2))
def band(s): return "Poor (<600)" if s<600 else "Fair (600-669)" if s<670 else "Good (670-739)" if s<740 else "Excellent (740+)"
loans["credit_band"] = loans.customer_id.map(cust.set_index("customer_id").credit_score).map(band)
band_delinq = loans.groupby("credit_band").apply(lambda g:(g.days_past_due>=30).mean()*100).round(2)
worst_band = band_delinq.idxmax(); k("worst_credit_band", worst_band); k("worst_credit_band_delinquency_pct", float(band_delinq.max()))
seg_delinq = loans.groupby("segment").apply(lambda g:(g.days_past_due>=30).mean()*100).round(2)

# ---------------- Module 4: Transactions & channels ----------------
ch = txn.groupby("channel").agg(txns=("txn_id","count"), value=("amount_usd","sum"))
digital_share = ch.loc[["mobile","online"],"txns"].sum()/len(txn)*100
k("total_transactions", len(txn)); k("digital_adoption_share_pct", round(float(digital_share),2))
k("top_channel", ch.txns.idxmax()); k("top_channel_share_pct", round(float(ch.txns.max()/len(txn)*100),2))
monthly_active = txn.groupby("month").customer_id.nunique()
k("monthly_active_customers_first", int(monthly_active.iloc[0])); k("monthly_active_customers_last", int(monthly_active.iloc[-1]))

# ---------------- outputs ----------------
pd.DataFrame({"kpi":list(K.keys()),"value":list(K.values())}).to_csv(f"{O}/kpi_summary.csv", index=False)
with open(f"{O}/insights.md","w") as f:
    f.write("# Insights — End-to-End Retail Banking Analytics (Portfolio Project, synthetic data)\n\n")
    f.write(f"## Module 1 — Customer 360\n- {len(cust)} customers, {K['accounts_per_customer']} accounts per customer, multi-product holding rate {K['multi_product_holding_rate_pct']}% — cross-sell headroom sits with single-product Mass customers.\n- Deposits total ${K['total_deposits_usd']:,.0f}; Affluent median deposits are a multiple of Mass (see segment_summary.csv).\n\n")
    f.write(f"## Module 2 — Revenue\n- Total revenue ${total_revenue:,.0f} = loan interest ${total_loan_interest:,.0f} + fees ${total_fees:,.0f}. Largest segment by revenue: {top_seg_rev} (${seg_rev.max():,.0f}).\n- Monthly revenue grew {growth:.1f}% across 2024 under the stated interest-spread assumption (see analysis.py).\n\n")
    f.write(f"## Module 3 — Credit Risk\n- 30+ DPD delinquency {K['delinquency_rate_30plus_pct']}%, 90+ DPD charge-off proxy {K['chargeoff_proxy_rate_pct']}% of {len(loans)} loans.\n- Risk concentrates in the {worst_band} credit band ({band_delinq.max()}% delinquent) — pricing and limit reviews belong there first.\n\n")
    f.write(f"## Module 4 — Channels\n- Digital (mobile + online) carries {digital_share:.1f}% of transactions; top channel {ch.txns.idxmax()} at {ch.txns.max()/len(txn)*100:.1f}%.\n- Monthly active customers moved {int(monthly_active.iloc[0])} → {int(monthly_active.iloc[-1])} across 2024.\n\n")
    f.write("## Module 0 — Data Quality\n- " + f"{len(checks)-n_review}/{len(checks)} checks fully clean; full report in data_quality_report.md.\n")
with open(f"{O}/kpi_pack.md","w") as f:
    f.write("# Executive KPI Pack — Retail Banking (auto-generated by analysis.py, Module 5)\n\n")
    f.write(f"**Customers:** {len(cust)} | **Accounts:** {len(acc)} | **Deposits:** ${K['total_deposits_usd']:,.0f} | **Loans:** {len(loans)} (${K['total_loan_balance_usd']:,.0f} outstanding)\n\n")
    f.write(f"**Revenue:** ${total_revenue:,.0f} total (interest ${total_loan_interest:,.0f} + fees ${total_fees:,.0f}); top segment {top_seg_rev}; monthly growth {growth:.1f}% in 2024.\n\n")
    f.write(f"**Risk:** 30+ DPD delinquency {K['delinquency_rate_30plus_pct']}% | 90+ DPD charge-off proxy {K['chargeoff_proxy_rate_pct']}% | worst band {worst_band} at {band_delinq.max()}%.\n\n")
    f.write(f"**Channels:** digital share {digital_share:.1f}% of {len(txn)} transactions | monthly actives {int(monthly_active.iloc[0])} → {int(monthly_active.iloc[-1])}.\n\n")
    f.write(f"**Engagement:** multi-product holding {K['multi_product_holding_rate_pct']}% | accounts per customer {K['accounts_per_customer']}.\n\n")
    f.write("**Data quality:** " + f"{len(checks)-n_review}/{len(checks)} checks clean (Module 0 report).\n\n_Assumptions: loan interest = outstanding balance × product rate, spread evenly across months for the trend; charge-off proxy = 90+ DPD share. Synthetic portfolio data._\n")
for n_, v in K.items(): print(f"{n_}: {v}")
print("Modules 0-5 complete: kpi_summary.csv, segment_summary.csv, product_revenue.csv, insights.md, data_quality_report.md, kpi_pack.md")
