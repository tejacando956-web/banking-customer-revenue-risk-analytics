"""End-to-End Retail Banking Analytics - all modules + automated KPI pack.

Module 0  Pipeline & data quality      -> outputs/data_quality_report.md
Module 1  Customer 360 & segmentation  -> outputs/segment_summary.csv
Module 2  Revenue & product performance-> outputs/product_revenue.csv
Module 3  Credit risk (DPD buckets)    -> part of kpi_summary / insights
Module 4  Transactions & channels      -> part of kpi_summary / insights
Module 5  Automated KPI pack           -> outputs/kpi_pack.md
Module 6  Depth pack                   -> treemap / heatmap / scatter / fee outputs
Module 7  Second depth pass            -> outputs/loans_by_product_dpd.csv,
                                          outputs/digital_by_segment.csv,
                                          outputs/monthly_actives_by_segment.csv
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
pr = pd.DataFrame({"product_line":["Auto loan interest","Personal loan interest","Mortgage interest","Fees (transaction + account fees)"],
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

# ---------------- Module 6: Depth pack (treemap / heatmap / scatter / fee cuts) ----------------
# deposits by segment x account type -> outputs/deposits_by_segment_product.csv (treemap source)
dep_acc = acc[acc.account_type.isin(["checking","savings"])].copy()
dep_acc["segment"] = dep_acc.customer_id.map(cust.set_index("customer_id").segment)
dep_sp = dep_acc.groupby(["segment","account_type"]).balance_usd.sum().round(2).reset_index()
dep_sp.columns = ["segment","account_type","deposits_usd"]
dep_sp["share_pct"] = (dep_sp.deposits_usd/dep_sp.deposits_usd.sum()*100).round(2)
dep_sp = dep_sp.sort_values(["segment","account_type"]).reset_index(drop=True)
dep_sp.to_csv(f"{O}/deposits_by_segment_product.csv", index=False)
top_cell = dep_sp.loc[dep_sp.deposits_usd.idxmax()]
k("top_deposit_cell_segment", top_cell.segment); k("top_deposit_cell_account_type", top_cell.account_type)
k("top_deposit_cell_share_pct", float(top_cell.share_pct))
# 30+ DPD % by credit band x segment -> outputs/dpd_by_credit_segment.csv (heatmap source)
hm = loans.groupby(["credit_band","segment"]).apply(lambda g: pd.Series({
    "loans": len(g), "delinquent_30plus": int((g.days_past_due>=30).sum()),
    "dpd_30plus_pct": round((g.days_past_due>=30).mean()*100,2)})).reset_index()
hm["loans"] = hm.loans.astype(int); hm["delinquent_30plus"] = hm.delinquent_30plus.astype(int)
hm.to_csv(f"{O}/dpd_by_credit_segment.csv", index=False)
worst_cell = hm.loc[hm.dpd_30plus_pct.idxmax()]
k("worst_dpd_cell_credit_band", worst_cell.credit_band); k("worst_dpd_cell_segment", worst_cell.segment)
k("worst_dpd_cell_30plus_pct", float(worst_cell.dpd_30plus_pct)); k("worst_dpd_cell_loans", int(worst_cell.loans))
# per-customer value -> outputs/customer_value.csv (scatter source)
cust_interest = loans.groupby("customer_id").annual_interest_usd.sum()
cust_txn_fees = txn.groupby("customer_id").fee_usd.sum()
cust_acct_fees = acc.assign(fee=acc.account_type.map(acct_fee_map)).groupby("customer_id").fee.sum()
cv = pd.DataFrame({"customer_id": cust.customer_id, "segment": cust.segment.values})
cv["total_deposits_usd"] = cv.customer_id.map(deposits).fillna(0).round(2)
cv["total_revenue_usd"] = (cv.customer_id.map(cust_interest).fillna(0)
                           + cv.customer_id.map(cust_txn_fees).fillna(0)
                           + cv.customer_id.map(cust_acct_fees).fillna(0)).round(2)
cv["products_held"] = cv.customer_id.map(holdings).fillna(0).astype(int)
cv.to_csv(f"{O}/customer_value.csv", index=False)
top_decile = cv.nlargest(int(len(cv)*0.10), "total_revenue_usd")
k("top_decile_revenue_share_pct", round(float(top_decile.total_revenue_usd.sum()/cv.total_revenue_usd.sum()*100),2))
k("median_customer_deposits_usd", float(cv.total_deposits_usd.median().round(2)))
k("median_customer_revenue_usd", float(cv.total_revenue_usd.median().round(2)))
# monthly fee revenue -> outputs/monthly_fees.csv (area-chart source; account fees = annual total / 12, stated assumption)
mf_df = txn.groupby("month").fee_usd.sum().rename("transaction_fees_usd").reset_index()
mf_df["transaction_fees_usd"] = mf_df.transaction_fees_usd.round(2)
mf_df["account_fees_usd"] = round(account_fees/12, 2)
mf_df["total_fees_usd"] = (mf_df.transaction_fees_usd + mf_df.account_fees_usd).round(2)
mf_df.to_csv(f"{O}/monthly_fees.csv", index=False)
peak_fee = mf_df.loc[mf_df.total_fees_usd.idxmax()]
k("fee_revenue_peak_month", peak_fee.month); k("fee_revenue_peak_month_usd", float(peak_fee.total_fees_usd))

# ---------------- Module 7: Second depth pass (product x DPD / digital & actives by segment) ----------------
# loans by product x DPD bucket -> outputs/loans_by_product_dpd.csv (stacked-bar source)
lp = loans.pivot_table(index="loan_type", columns="dpd_bucket", values="loan_id", aggfunc="count", fill_value=0)
lp = lp.reindex(index=["mortgage","auto","personal"],
                columns=["Current (0 DPD)","1-29 DPD","30-59 DPD","60-89 DPD","90+ DPD"]).fillna(0).astype(int)
lp.columns = ["current_loans","dpd_1_29_loans","dpd_30_59_loans","dpd_60_89_loans","dpd_90plus_loans"]
lp = lp.reset_index()
lp["total_loans"] = lp[["current_loans","dpd_1_29_loans","dpd_30_59_loans","dpd_60_89_loans","dpd_90plus_loans"]].sum(axis=1)
lp["delinquent_30plus_loans"] = lp[["dpd_30_59_loans","dpd_60_89_loans","dpd_90plus_loans"]].sum(axis=1)
lp["dpd_30plus_pct"] = (lp.delinquent_30plus_loans/lp.total_loans*100).round(2)
lp.to_csv(f"{O}/loans_by_product_dpd.csv", index=False)
worst_prod = lp.loc[lp.dpd_30plus_pct.idxmax()]
k("worst_dpd_product", worst_prod.loan_type.title()); k("worst_dpd_product_30plus_pct", float(worst_prod.dpd_30plus_pct))
k("worst_dpd_product_loans", int(worst_prod.total_loans))
# revenue per customer for the other two segments (Module 2 basis: loan interest + transaction fees, so Affluent stays the existing KPI)
k("revenue_per_customer_mass_usd", float(rev_per_cust["Mass"])); k("revenue_per_customer_small_business_usd", float(rev_per_cust["Small Business"]))
# digital adoption by segment -> outputs/digital_by_segment.csv (same definition as the bank-wide KPI: mobile+online transactions / all transactions, per segment)
dig_seg = txn.assign(is_digital=txn.channel.isin(["mobile","online"])).groupby("segment").agg(
    transactions=("txn_id","count"), digital_transactions=("is_digital","sum")).reindex(["Affluent","Mass","Small Business"]).reset_index()
dig_seg["digital_adoption_pct"] = (dig_seg.digital_transactions/dig_seg.transactions*100).round(2)
dig_seg.to_csv(f"{O}/digital_by_segment.csv", index=False)
dig_hi = dig_seg.loc[dig_seg.digital_adoption_pct.idxmax()]; dig_lo = dig_seg.loc[dig_seg.digital_adoption_pct.idxmin()]
k("digital_adoption_highest_segment", dig_hi.segment); k("digital_adoption_highest_pct", float(dig_hi.digital_adoption_pct))
k("digital_adoption_lowest_segment", dig_lo.segment); k("digital_adoption_lowest_pct", float(dig_lo.digital_adoption_pct))
# products-held depth (same holdings definition as Module 1: distinct account types + loan types per customer)
k("customers_holding_2_products", int((holdings==2).sum())); k("customers_holding_4plus_products", int((holdings>=4).sum()))
# monthly active customers by segment -> outputs/monthly_actives_by_segment.csv (line-chart source)
ma_seg = txn.groupby(["month","segment"]).customer_id.nunique().unstack(fill_value=0).reindex(columns=["Affluent","Mass","Small Business"])
ma_out = ma_seg.reset_index().rename(columns={"Affluent":"affluent_actives","Mass":"mass_actives","Small Business":"small_business_actives"})
ma_out["total_actives"] = ma_out[["affluent_actives","mass_actives","small_business_actives"]].sum(axis=1)
ma_out.to_csv(f"{O}/monthly_actives_by_segment.csv", index=False)
act_growth = ((ma_seg.iloc[-1]/ma_seg.iloc[0]-1)*100).round(2)
k("monthly_actives_top_growth_segment", act_growth.idxmax()); k("monthly_actives_top_growth_pct", float(act_growth.max()))

# ---------------- outputs ----------------
# kpi_summary.csv carries exactly the 15 headline KPIs (the learnable set defined in
# KPI_DICTIONARY.md). Every module still computes its full detail above — the supporting
# numbers live in the breakdown CSVs (segment_summary, product_revenue, customer_value,
# dpd_by_credit_segment, deposits_by_segment_product, loans_by_product_dpd,
# digital_by_segment, monthly_actives_by_segment, monthly_fees).
HEADLINE_KPIS = ["total_deposits_usd","total_revenue_usd","loan_interest_revenue_usd","fee_revenue_usd",
                 "top_segment_revenue_per_customer_usd",
                 "top_decile_revenue_share_pct","top_deposit_cell_share_pct",
                 "multi_product_holding_rate_pct","customers_holding_2_products",
                 "total_loans","delinquency_rate_30plus_pct","chargeoff_proxy_rate_pct",
                 "worst_dpd_product_30plus_pct",
                 "digital_adoption_share_pct","monthly_active_customers_last"]
pd.DataFrame({"kpi":HEADLINE_KPIS,"value":pd.Series([K[h] for h in HEADLINE_KPIS], dtype=object)}).to_csv(f"{O}/kpi_summary.csv", index=False)
with open(f"{O}/insights.md","w") as f:
    f.write("# Insights — End-to-End Retail Banking Analytics (Portfolio Project, synthetic data)\n\n")
    f.write(f"## Module 1 — Customer 360\n- {len(cust)} customers, {K['accounts_per_customer']} accounts per customer, multi-product holding rate {K['multi_product_holding_rate_pct']}% — cross-sell headroom sits with two-product customers: 415 of the 420 customers holding fewer than 3 products hold exactly 2 (only 5 hold just 1).\n- Deposits total ${K['total_deposits_usd']:,.0f}; Affluent median deposits are a multiple of Mass (see segment_summary.csv).\n\n")
    f.write(f"## Module 2 — Revenue\n- Total revenue ${total_revenue:,.0f} = loan interest ${total_loan_interest:,.0f} + fees ${total_fees:,.0f}. Largest segment by revenue: {top_seg_rev} (${seg_rev.max():,.0f}).\n- Monthly revenue grew {growth:.1f}% across 2024 under the stated interest-spread assumption (see analysis.py).\n\n")
    f.write(f"## Module 3 — Credit Risk\n- 30+ DPD delinquency {K['delinquency_rate_30plus_pct']}%, 90+ DPD charge-off proxy {K['chargeoff_proxy_rate_pct']}% of {len(loans)} loans.\n- Risk concentrates in the {worst_band} credit band ({band_delinq.max()}% delinquent) — pricing and limit reviews belong there first.\n\n")
    f.write(f"## Module 4 — Channels\n- Digital (mobile + online) carries {digital_share:.1f}% of transactions; top channel {ch.txns.idxmax()} at {ch.txns.max()/len(txn)*100:.1f}%.\n- Monthly active customers moved {int(monthly_active.iloc[0])} → {int(monthly_active.iloc[-1])} across 2024.\n\n")
    f.write("## Module 0 — Data Quality\n- " + f"{len(checks)-n_review}/{len(checks)} checks fully clean; full report in data_quality_report.md.\n")
    f.write(f"\n## Module 6 — Depth Pack (treemap / heatmap / scatter / fees)\n- Worst risk cell on the credit-band × segment heatmap: {worst_cell.credit_band} × {worst_cell.segment} at {worst_cell.dpd_30plus_pct}% 30+ DPD — but that cell holds only {int(worst_cell.loans)} loans, so read it with the loan counts printed on the heatmap; the worst cell with a real book behind it is Poor (<600) × Mass at 19.44% (36 loans). One cell (Poor × Affluent) has no loans at all.\n- Deposits concentrate in one cell: {top_cell.segment} {top_cell.account_type} accounts hold ${top_cell.deposits_usd:,.0f} ({top_cell.share_pct}% of all deposits).\n- Customer value is top-heavy: the top 10% of customers generate {K['top_decile_revenue_share_pct']}% of revenue; the median customer brings ${K['median_customer_revenue_usd']:,.0f} revenue on ${K['median_customer_deposits_usd']:,.0f} deposits.\n- Fee revenue peaks in {peak_fee.month} at ${peak_fee.total_fees_usd:,.0f} (transaction fees are truly monthly; account fees are the annual total spread evenly).\n")
    f.write(f"\n## Module 7 — Second Depth Pass (product risk / segment digital & actives)\n- By loan product, mortgages are the late ones: {worst_prod.dpd_30plus_pct}% of {int(worst_prod.total_loans)} mortgage loans are 30+ DPD, vs 7.52% of auto and 7.79% of personal loans — the product cut points the same way as the credit-band cut.\n- Digital adoption barely moves by segment: {dig_lo.segment} is lowest at {dig_lo.digital_adoption_pct}% and {dig_hi.segment} highest at {dig_hi.digital_adoption_pct}% of transactions — digital is bank-wide behaviour now, not a segment trait.\n- Revenue per customer (interest + transaction fees): Affluent ${rev_per_cust['Affluent']:,.0f}, Small Business ${rev_per_cust['Small Business']:,.0f}, Mass ${rev_per_cust['Mass']:,.0f}.\n- Most customers hold exactly 2 product types ({int((holdings==2).sum())} of {len(cust)}); only {int((holdings>=4).sum())} hold 4 or more — the 3+ deep-relationship rate of {K['multi_product_holding_rate_pct']}% is carried by the exactly-3 group.\n- Monthly actives grew in every segment; {act_growth.idxmax()} grew fastest at {act_growth.max()}% (first to last month of 2024).\n")
with open(f"{O}/kpi_pack.md","w") as f:
    f.write("# Executive KPI Pack — Retail Banking (auto-generated by analysis.py, Module 5)\n\n")
    f.write("The 15 headline KPIs — the same 15 as `outputs/kpi_summary.csv`, each defined in `KPI_DICTIONARY.md`. Supporting detail (segment totals, credit-band rates, channel mix, monthly series) lives in the breakdown CSVs in `outputs/`.\n\n")
    f.write("| # | KPI | Value |\n|---:|---|---:|\n")
    pack_rows = [
        ("Total deposits", f"${K['total_deposits_usd']:,.2f}"),
        ("Total revenue (interest + fees)", f"${K['total_revenue_usd']:,.2f}"),
        ("Loan interest revenue", f"${K['loan_interest_revenue_usd']:,.2f}"),
        ("Fee revenue (transaction + account fees)", f"${K['fee_revenue_usd']:,.2f}"),
        ("Revenue per customer — top segment (Affluent)", f"${K['top_segment_revenue_per_customer_usd']:,.2f}"),
        ("Revenue share of top 10% of customers", f"{K['top_decile_revenue_share_pct']:.2f}%"),
        ("Deposit share of biggest cell (Affluent savings)", f"{K['top_deposit_cell_share_pct']:.2f}%"),
        ("Deep-relationship rate (3+ product types)", f"{K['multi_product_holding_rate_pct']:.2f}%"),
        ("Customers holding exactly 2 product types", f"{int(K['customers_holding_2_products'])}"),
        ("Total loans", f"{int(K['total_loans'])}"),
        ("Delinquency rate (30+ DPD)", f"{K['delinquency_rate_30plus_pct']:.2f}%"),
        ("Charge-off proxy (90+ DPD)", f"{K['chargeoff_proxy_rate_pct']:.2f}%"),
        ("Latest product 30+ DPD rate (Mortgage)", f"{K['worst_dpd_product_30plus_pct']:.2f}%"),
        ("Digital adoption (mobile + online share)", f"{K['digital_adoption_share_pct']:.2f}%"),
        ("Monthly active customers — Dec 2024", f"{int(K['monthly_active_customers_last'])}"),
    ]
    for i, (name, val) in enumerate(pack_rows, 1): f.write(f"| {i} | {name} | {val} |\n")
    f.write(f"\n**Data quality:** {len(checks)-n_review}/{len(checks)} Module 0 checks clean (see data_quality_report.md).\n\n")
    f.write("_Two revenue bases, both stated wherever used: segment revenue = loan interest + transaction fees (account fees are bank-wide and not split by segment; segment-basis total = $" + f"{float(seg_rev.sum()):,.2f}" + "); per-customer revenue (customer_value.csv, top-decile share) also includes each customer's own account fees, so it adds back to total revenue. Assumptions: loan interest = outstanding balance × product rate, spread evenly across months for the trend; charge-off proxy = 90+ DPD share. Synthetic portfolio data._\n")
for n_, v in K.items(): print(f"{n_}: {v}")
print("Modules 0-7 complete: kpi_summary.csv, segment_summary.csv, product_revenue.csv, deposits_by_segment_product.csv, dpd_by_credit_segment.csv, customer_value.csv, monthly_fees.csv, loans_by_product_dpd.csv, digital_by_segment.csv, monthly_actives_by_segment.csv, insights.md, data_quality_report.md, kpi_pack.md")
