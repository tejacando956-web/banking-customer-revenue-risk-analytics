"""Generate the 4 dashboard charts (matplotlib, dpi=150) from data/ + outputs/."""
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt, os
B=os.path.dirname(__file__); D,O,I=f"{B}/data",f"{B}/outputs",f"{B}/images"; os.makedirs(I,exist_ok=True)
cust=pd.read_csv(f"{D}/customers.csv"); loans=pd.read_csv(f"{D}/loans.csv"); txn=pd.read_csv(f"{D}/transactions.csv", parse_dates=["txn_date"])
rate={"auto":7.40,"personal":11.90,"mortgage":6.60}
loans["interest"]=loans.balance_usd*loans.loan_type.map(rate)/100
loans["segment"]=loans.customer_id.map(cust.set_index("customer_id").segment)
txn["segment"]=txn.customer_id.map(cust.set_index("customer_id").segment); txn["month"]=txn.txn_date.dt.to_period("M").astype(str)
C={"Mass":"#4C78A8","Affluent":"#F58518","Small Business":"#54A24B"}
# 1 revenue trend by segment (monthly fees + evenly spread interest, stated assumption)
mf=txn.groupby(["month","segment"]).fee_usd.sum().unstack(fill_value=0)
for s in mf.columns: mf[s]+= loans[loans.segment==s].interest.sum()/12
fig,ax=plt.subplots(figsize=(9,4.6))
for s in mf.columns: ax.plot(mf.index, mf[s], marker="o", label=s, color=C.get(s))
ax.set_title("Monthly Revenue Trend by Segment (fees + spread loan interest)"); ax.set_ylabel("Revenue ($)")
ax.tick_params(axis="x", rotation=45); ax.legend(); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(f"{I}/revenue_trend_by_segment.png", dpi=150); plt.close(fig)
# 2 delinquency by DPD bucket
def bucket(d): return "Current\n(0 DPD)" if d==0 else "1-29 DPD" if d<30 else "30-59 DPD" if d<60 else "60-89 DPD" if d<90 else "90+ DPD"
order=["Current\n(0 DPD)","1-29 DPD","30-59 DPD","60-89 DPD","90+ DPD"]
bc=loans.days_past_due.map(bucket).value_counts().reindex(order).fillna(0)
fig,ax=plt.subplots(figsize=(8.4,4.4)); bars=ax.bar(bc.index, bc.values, color=["#54A24B","#E45756","#E45756","#B279A2","#72B7B2"])
for b_,v in zip(bars,bc.values): ax.annotate(f"{int(v)}\n{v/len(loans)*100:.1f}%", (b_.get_x()+b_.get_width()/2, v), ha="center", va="bottom")
ax.set_title("Loan Delinquency by Days-Past-Due (DPD) Bucket"); ax.set_ylabel("Loans"); fig.tight_layout(); fig.savefig(f"{I}/delinquency_by_dpd_bucket.png", dpi=150); plt.close(fig)
# 3 channel mix
ch=txn.groupby("channel").agg(n=("txn_id","count"), v=("amount_usd","sum")).reindex(["mobile","online","branch","ATM"])
fig,ax=plt.subplots(figsize=(8.4,4.4)); bars=ax.bar(ch.index, ch.n, color=["#4C78A8","#F58518","#54A24B","#B279A2"])
for b_,(n_,v) in zip(bars, ch.itertuples(index=False)): ax.annotate(f"{n_}\n{n_/len(txn)*100:.1f}%", (b_.get_x()+b_.get_width()/2, n_), ha="center", va="bottom")
ax.set_title("Transaction Volume by Channel (digital = mobile + online)"); ax.set_ylabel("Transactions"); fig.tight_layout(); fig.savefig(f"{I}/channel_mix.png", dpi=150); plt.close(fig)
# 4 customer segment balances
seg=pd.read_csv(f"{O}/segment_summary.csv")
fig,ax=plt.subplots(figsize=(8.4,4.4)); x=np.arange(len(seg)); w=.38
ax.bar(x-w/2, seg.total_deposits_usd/1e6, w, label="Total deposits ($M)", color="#4C78A8")
ax2=ax.twinx(); ax2.bar(x+w/2, seg.median_deposit_usd, w, label="Median deposit per customer ($)", color="#F58518")
ax.set_xticks(x); ax.set_xticklabels(seg.segment); ax.set_title("Customer Segment Balances: Total vs Median Deposits")
ax.set_ylabel("$M"); ax2.set_ylabel("$"); h1,l1=ax.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels(); ax.legend(h1+h2, l1+l2, loc="upper left")
fig.tight_layout(); fig.savefig(f"{I}/customer_segment_balances.png", dpi=150); plt.close(fig)
for f in ["revenue_trend_by_segment.png","delinquency_by_dpd_bucket.png","channel_mix.png","customer_segment_balances.png"]:
    print(f, os.path.getsize(f"{I}/{f}"), "bytes")
