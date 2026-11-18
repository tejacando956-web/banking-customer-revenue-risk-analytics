"""Generate the 10 dashboard charts (matplotlib, dpi=150) from data/ + outputs/.

Palette — "trustworthy corporate blue" (settled banking palette):
  segments  Affluent #2F6DB3 / Mass #5B9BD5 / Small Business #3E9B4F
  products  Mortgage #2E5A88 / Auto #2F6DB3 / Personal #5B9BD5 / Fees #C44536
  DPD ramp  #5B9BD5 -> #2F6DB3 -> #D97D4A -> #C25E33 -> #B03A2E (blue warming to red
            as lateness worsens); the heatmap uses the same blue->red progression.
No yellow/gold, no navy, no pale colours; lines are vivid, never black/grey.
Every title states the chart's finding in plain words.
"""
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt, os
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter
B=os.path.dirname(__file__); D,O,I=f"{B}/data",f"{B}/outputs",f"{B}/images"; os.makedirs(I,exist_ok=True)
plt.rcParams.update({"font.size":10, "axes.titlesize":13, "axes.titleweight":"bold",
                     "axes.labelsize":11, "xtick.labelsize":10, "ytick.labelsize":10,
                     "legend.fontsize":10, "figure.facecolor":"white", "axes.facecolor":"white"})
cust=pd.read_csv(f"{D}/customers.csv"); acc=pd.read_csv(f"{D}/accounts.csv"); loans=pd.read_csv(f"{D}/loans.csv"); txn=pd.read_csv(f"{D}/transactions.csv", parse_dates=["txn_date"])
rate={"auto":7.40,"personal":11.90,"mortgage":6.60}
loans["interest"]=loans.balance_usd*loans.loan_type.map(rate)/100
loans["segment"]=loans.customer_id.map(cust.set_index("customer_id").segment)
txn["segment"]=txn.customer_id.map(cust.set_index("customer_id").segment); txn["month"]=txn.txn_date.dt.to_period("M").astype(str)
SEG_C={"Affluent":"#2F6DB3","Mass":"#5B9BD5","Small Business":"#3E9B4F"}
MIX_C={"Mortgage interest":"#2E5A88","Auto loan interest":"#2F6DB3","Personal loan interest":"#5B9BD5","Fees (transaction + account fees)":"#C44536"}
DPD_RAMP=["#5B9BD5","#2F6DB3","#D97D4A","#C25E33","#B03A2E"]
FIG=(9,4.8)

# 1 revenue trend by segment (monthly fees + evenly spread interest, stated assumption)
mf=txn.groupby(["month","segment"]).fee_usd.sum().unstack(fill_value=0)
for s in mf.columns: mf[s]+= loans[loans.segment==s].interest.sum()/12
fig,ax=plt.subplots(figsize=FIG)
for s in ["Mass","Affluent","Small Business"]:
    ax.plot(mf.index, mf[s], marker="o", linewidth=2.2, label=s, color=SEG_C[s])
    ax.annotate(f"${mf[s].iloc[-1]:,.0f}", (len(mf)-1, mf[s].iloc[-1]), textcoords="offset points",
                xytext=(8,0), va="center", fontsize=10, fontweight="bold", color=SEG_C[s])
ax.set_title("Monthly Revenue by Segment — Mass Leads Every Month of 2024")
ax.set_ylabel("Revenue ($)"); ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f"${v:,.0f}"))
ax.set_xlim(-0.3, len(mf)-0.35); ax.tick_params(axis="x", rotation=45); ax.legend(loc="center left"); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(f"{I}/revenue_trend_by_segment.png", dpi=150); plt.close(fig)

# 2 revenue mix donut (from outputs/product_revenue.csv)
pr=pd.read_csv(f"{O}/product_revenue.csv").set_index("product_line")
order=["Mortgage interest","Auto loan interest","Personal loan interest","Fees (transaction + account fees)"]
short={"Mortgage interest":"Mortgage","Auto loan interest":"Auto","Personal loan interest":"Personal","Fees (transaction + account fees)":"Fees"}
pr=pr.reindex(order)
fig,ax=plt.subplots(figsize=FIG)
wedges,_=ax.pie(pr.revenue_usd, colors=[MIX_C[k] for k in order], startangle=90, counterclock=False,
                wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2))
ax.legend(wedges, [f"{short[k]} — ${pr.loc[k,'revenue_usd']:,.0f} ({pr.loc[k,'share_pct']:.1f}%)" for k in order],
          loc="center left", bbox_to_anchor=(1.0,0.5))
ax.text(0,0,f"${pr.revenue_usd.sum()/1e6:.2f}M\ntotal revenue", ha="center", va="center", fontsize=12, fontweight="bold")
ax.set_title("Revenue Mix — Mortgage Interest Is 70.5% of Revenue; Fees Only 2.4%")
fig.tight_layout(); fig.savefig(f"{I}/revenue_mix_donut.png", dpi=150); plt.close(fig)

# 3 deposits treemap: segment x account type (manual squarified layout, sizes proportional to deposits)
def _squarify(sizes, x, y, w, h):
    sizes=[s*w*h/sum(sizes) for s in sizes]; rects=[]; row=[]
    def worst(r, side):
        s=sum(r); return max(side*side*max(r)/(s*s), (s*s)/(side*side*min(r)))
    def layout(r, x, y, w, h):
        if w>=h:
            cw=sum(r)/h; cy=y
            for s in r: rects.append((x,cy,cw,s/cw)); cy+=s/cw
            return x+cw, y, w-cw, h
        rh=sum(r)/w; cx=x
        for s in r: rects.append((cx,y,s/rh,rh)); cx+=s/rh
        return x, y+rh, w, h-rh
    while sizes:
        if not row or worst(row+[sizes[0]], min(w,h)) <= worst(row, min(w,h)): row.append(sizes.pop(0))
        else: x,y,w,h=layout(row,x,y,w,h); row=[]
    if row: layout(row,x,y,w,h)
    return rects
def _shade(hexcol, f):
    hexcol=hexcol.lstrip("#"); r,g,b=(int(hexcol[i:i+2],16)/255 for i in (0,2,4)); return (r*f,g*f,b*f)
dsp=pd.read_csv(f"{O}/deposits_by_segment_product.csv")
seg_order=["Affluent","Mass","Small Business"]; type_factor={"checking":1.0,"savings":0.68}
fig,ax=plt.subplots(figsize=FIG); W,H=100.0,56.0
seg_totals=[dsp[dsp.segment==s].deposits_usd.sum() for s in seg_order]
for s, (rx,ry,rw,rh) in zip(seg_order, _squarify(seg_totals, 0, 0, W, H)):
    sub=dsp[dsp.segment==s].sort_values("deposits_usd", ascending=False)
    for (_,cell), (cx,cy,cw,ch) in zip(sub.iterrows(), _squarify(list(sub.deposits_usd), rx, ry, rw, rh)):
        ax.add_patch(mpatches.Rectangle((cx,cy), cw, ch, facecolor=_shade(SEG_C[s], type_factor[cell.account_type]),
                                        edgecolor="white", linewidth=2))
        ax.text(cx+cw/2, cy+ch/2, f"{s}\n{cell.account_type.title()}\n${cell.deposits_usd/1e6:.2f}M · {cell.share_pct:.1f}%",
                ha="center", va="center", color="white", fontsize=10 if min(cw,ch)>=16 else 8.5, fontweight="bold")
ax.set_xlim(0,W); ax.set_ylim(0,H); ax.axis("off")
ax.set_title("Deposits Treemap — One Cell (Affluent Savings) Holds 40.0% of All Deposits")
fig.tight_layout(); fig.savefig(f"{I}/deposits_treemap.png", dpi=150); plt.close(fig)

# 4 DPD heatmap: 30+ DPD % by credit band x segment (single blue->red progression)
hm=pd.read_csv(f"{O}/dpd_by_credit_segment.csv")
bands=["Poor (<600)","Fair (600-669)","Good (670-739)","Excellent (740+)"]; segs=["Affluent","Mass","Small Business"]
piv=hm.pivot(index="credit_band", columns="segment", values="dpd_30plus_pct").reindex(index=bands, columns=segs)
cnt=hm.pivot(index="credit_band", columns="segment", values="loans").reindex(index=bands, columns=segs)
cmap=LinearSegmentedColormap.from_list("dpd_ramp", DPD_RAMP)
fig,ax=plt.subplots(figsize=FIG)
ax.imshow(np.ma.masked_invalid(piv.values.astype(float)), cmap=cmap, aspect="auto", vmin=0, vmax=25)
ax.set_xticks(range(len(segs))); ax.set_xticklabels(segs); ax.set_yticks(range(len(bands))); ax.set_yticklabels(bands)
ax.set_xlabel("Customer segment"); ax.set_ylabel("Credit band")
for i in range(len(bands)):
    for j in range(len(segs)):
        v=piv.values[i,j]
        txt="no loans" if pd.isna(v) else f"{v:.2f}%\n({int(cnt.values[i,j])} loans)"
        ax.text(j, i, txt, ha="center", va="center", color="#333333" if pd.isna(v) else "white", fontsize=10, fontweight="bold")
ax.set_title("Late Loans Concentrate in Poor Credit — Worst Book: Poor × Mass, 19.44%")
fig.tight_layout(); fig.savefig(f"{I}/dpd_heatmap.png", dpi=150); plt.close(fig)

# 5 customer value scatter: one dot per customer, deposits vs revenue, coloured by segment
cv=pd.read_csv(f"{O}/customer_value.csv")
fig,ax=plt.subplots(figsize=FIG)
for s in ["Mass","Affluent","Small Business"]:
    g=cv[cv.segment==s]
    ax.scatter(g.total_deposits_usd, g.total_revenue_usd, s=16, alpha=0.75, color=SEG_C[s], label=f"{s} (n={len(g)})")
top_dep=cv.loc[cv.total_deposits_usd.idxmax()]
ax.annotate(f"${top_dep.total_deposits_usd:,.0f} in deposits,\nonly ${top_dep.total_revenue_usd:,.0f} revenue (no loans)",
            (top_dep.total_deposits_usd, top_dep.total_revenue_usd), textcoords="offset points", xytext=(-168,14),
            fontsize=9.5, fontweight="bold", color="#2E5A88",
            arrowprops=dict(arrowstyle="->", color="#2E5A88", lw=1.2))
ax.set_xlabel("Total deposits per customer ($)"); ax.set_ylabel("Total revenue per customer ($)")
ax.set_title("Revenue Follows Loans, Not Balances — Top 10% Earn 45.77% of Revenue")
ax.legend(); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(f"{I}/customer_value_scatter.png", dpi=150); plt.close(fig)

# 6 monthly fees area: transaction fees + account fees (annual total / 12)
mf2=pd.read_csv(f"{O}/monthly_fees.csv")
fig,ax=plt.subplots(figsize=FIG); x=np.arange(len(mf2))
ax.stackplot(x, mf2.transaction_fees_usd, mf2.account_fees_usd,
             labels=["Transaction fees","Account fees (annual total ÷ 12)"], colors=["#C44536","#5B9BD5"], alpha=0.95)
peak=mf2.total_fees_usd.idxmax()
ax.annotate(f"Dec peak: ${mf2.total_fees_usd.max():,.0f}", (peak, mf2.total_fees_usd.max()),
            textcoords="offset points", xytext=(-118,12), fontsize=10, fontweight="bold", color="#C44536")
ax.set_xticks(x); ax.set_xticklabels(mf2.month, rotation=45)
ax.set_ylabel("Fee revenue ($)"); ax.set_title("Fee Revenue Grows Through 2024 — Transaction Fees Do the Climbing")
ax.legend(loc="upper left"); ax.set_ylim(0, mf2.total_fees_usd.max()*1.22)
fig.tight_layout(); fig.savefig(f"{I}/monthly_fees_area.png", dpi=150); plt.close(fig)

# 7 loans by product x DPD bucket (stacked bars, from outputs/loans_by_product_dpd.csv)
DPD_COLS=["current_loans","dpd_1_29_loans","dpd_30_59_loans","dpd_60_89_loans","dpd_90plus_loans"]
DPD_LBL={"current_loans":"Current (0 DPD)","dpd_1_29_loans":"1-29 DPD","dpd_30_59_loans":"30-59 DPD","dpd_60_89_loans":"60-89 DPD","dpd_90plus_loans":"90+ DPD"}
lp=pd.read_csv(f"{O}/loans_by_product_dpd.csv")
fig,ax=plt.subplots(figsize=FIG); x=np.arange(len(lp)); bottom=np.zeros(len(lp))
for col, c in zip(DPD_COLS, DPD_RAMP):
    ax.bar(x, lp[col], bottom=bottom, label=DPD_LBL[col], color=c); bottom+=lp[col].values
for xi,(_,r) in zip(x, lp.iterrows()):
    ax.annotate(f"{int(r.total_loans)} loans\n{r.dpd_30plus_pct:.2f}% are 30+ DPD", (xi, r.total_loans), ha="center", va="bottom", fontsize=10, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels([t.title() for t in lp.loan_type]); ax.set_ylabel("Loans")
ax.set_title("Loans by Product × DPD Bucket — Mortgages Run Latest (11.17% at 30+ DPD)")
ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.09)); ax.set_ylim(0, lp.total_loans.max()*1.22)
fig.tight_layout(); fig.savefig(f"{I}/loans_by_product_dpd.png", dpi=150); plt.close(fig)

# 8 digital adoption by segment (from outputs/digital_by_segment.csv; same definition as the bank-wide 70.52% KPI)
dbs=pd.read_csv(f"{O}/digital_by_segment.csv").set_index("segment").reindex(["Affluent","Mass","Small Business"])
fig,ax=plt.subplots(figsize=FIG); bars=ax.bar(dbs.index, dbs.digital_adoption_pct, color=[SEG_C[s] for s in dbs.index])
for b_,v in zip(bars, dbs.digital_adoption_pct): ax.annotate(f"{v:.2f}%", (b_.get_x()+b_.get_width()/2, v), ha="center", va="bottom", fontsize=11, fontweight="bold")
overall_dig=txn.channel.isin(["mobile","online"]).mean()*100
ax.axhline(overall_dig, color="#C44536", linestyle="--", linewidth=1.4)
ax.text(0.01, 0.96, f"Dashed line = bank-wide {overall_dig:.2f}%", transform=ax.transAxes, color="#C44536", ha="left", va="top", fontsize=10, fontweight="bold")
ax.set_ylabel("Digital adoption (% of transactions)"); ax.set_ylim(0, 82)
ax.set_title("Digital Adoption Is the Same in Every Segment — About 70.5% (a null result)")
fig.tight_layout(); fig.savefig(f"{I}/digital_adoption_by_segment.png", dpi=150); plt.close(fig)

# 9 customers by products held (distinct account types + loan types per customer, Module 1 definition)
hold=pd.concat([acc.assign(pt=acc.account_type), loans.assign(pt="loan:"+loans.loan_type)]).groupby("customer_id").pt.nunique()
bins={"1":int((hold==1).sum()), "2":int((hold==2).sum()), "3":int((hold==3).sum()), "4+":int((hold>=4).sum())}
fig,ax=plt.subplots(figsize=FIG)
bars=ax.bar(list(bins.keys()), list(bins.values()), color=["#5B9BD5","#2F6DB3","#3E9B4F","#3E9B4F"])
for b_,v in zip(bars, bins.values()): ax.annotate(f"{v}\n{v/len(cust)*100:.1f}%", (b_.get_x()+b_.get_width()/2, v), ha="center", va="bottom", fontsize=11, fontweight="bold")
ax.set_xlabel("Distinct product types held"); ax.set_ylabel("Customers")
ax.text(0.99, 0.96, "Green bars = 3+ product types\n(deep relationship)", transform=ax.transAxes,
        ha="right", va="top", fontsize=10, fontweight="bold", color="#3E9B4F")
ax.set_title("Most Customers Hold Exactly 2 Product Types — the Cross-Sell Opportunity")
ax.set_ylim(0, max(bins.values())*1.18); fig.tight_layout(); fig.savefig(f"{I}/products_per_customer_hist.png", dpi=150); plt.close(fig)

# 10 monthly active customers by segment (from outputs/monthly_actives_by_segment.csv)
mas=pd.read_csv(f"{O}/monthly_actives_by_segment.csv")
fig,ax=plt.subplots(figsize=FIG)
for col,lbl in [("mass_actives","Mass"),("affluent_actives","Affluent"),("small_business_actives","Small Business")]:
    ax.plot(mas.month, mas[col], marker="o", linewidth=2.2, label=lbl, color=SEG_C[lbl])
ax.annotate(f"Total: {int(mas.total_actives.iloc[0])} → {int(mas.total_actives.iloc[-1])}", (0.02, 0.94),
            xycoords="axes fraction", fontsize=11, fontweight="bold", color="#2E5A88")
ax.set_title("Monthly Actives Grew in Every Segment, 2024 — Affluent Fastest (+59.38%)")
ax.set_ylabel("Active customers"); ax.tick_params(axis="x", rotation=45); ax.legend(loc="center left"); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(f"{I}/monthly_actives_by_segment.png", dpi=150); plt.close(fig)

for f in ["revenue_trend_by_segment.png","revenue_mix_donut.png","deposits_treemap.png","dpd_heatmap.png",
          "customer_value_scatter.png","monthly_fees_area.png","loans_by_product_dpd.png",
          "digital_adoption_by_segment.png","products_per_customer_hist.png","monthly_actives_by_segment.png"]:
    print(f, os.path.getsize(f"{I}/{f}"), "bytes")
