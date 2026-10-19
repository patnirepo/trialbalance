import streamlit as st
import pandas as pd
from supabase import create_client
import streamlit.components.v1 as components

st.set_page_config(page_title="Accounts", layout="wide")

# for numeric below 5 CSS lines set
st.markdown("""
<style>
td:nth-child(n+4) { text-align: right !important; }
</style>
""", unsafe_allow_html=True)

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["anon_key"])
#supabase = create_client(url, key)

# url = st.secrets["supabase"]["url"]
# key = st.secrets["supabase"]["key"]



def clean_code(x):
    try:
        if pd.isna(x) or str(x).strip()=="": return ""
        f = float(str(x).strip())
        if f.is_integer(): return str(int(f))
        return str(f).strip()
    except: return str(x).strip()

# ---------- Sidebar ----------
st.sidebar.title("Login")
pwd = st.sidebar.text_input("Password", type="password")

# Apna password yahan set karo
if pwd!= "123":
    st.sidebar.warning("Password likho (123)")
    st.stop()

st.sidebar.divider()
company_map = {1: "BOLTEN", 2: "CITY"}
co = st.sidebar.selectbox("Company", options=[1,2], format_func=lambda x: f"{x} - {company_map[x]}")
report_type = st.sidebar.selectbox("Report", ["Trial Balance", "Ledger"])

# ---------- Data Functions ----------
@st.cache_data(ttl=60)
def load_all(co):
    chart = supabase.table("chart").select("*").eq("comp", co).execute().data
    gen = supabase.table("gen").select("*").eq("co", co).execute().data
    genral = supabase.table("genral").select("*").eq("co", co).execute().data
    df_chart = pd.DataFrame(chart)
    df_gen = pd.DataFrame(gen)
    df_genral = pd.DataFrame(genral)
    if df_chart.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    df_chart.columns = [c.lower() for c in df_chart.columns]
    df_gen.columns = [c.lower() for c in df_gen.columns]
    df_genral.columns = [c.lower() for c in df_genral.columns]
    df_chart["chartid"] = df_chart["chartid"].apply(clean_code)
    df_gen["cashgen"] = df_gen["cashgen"].apply(clean_code)
    df_genral["accg2"] = df_genral["accg2"].apply(clean_code)
    return df_chart, df_gen, df_genral

@st.cache_data(ttl=60)
def get_trial(co):
    df_chart, df_gen, df_genral = load_all(co)
    if df_chart.empty: return pd.DataFrame(), 0, 0
    df_gen["modegen"] = df_gen["modegen"].astype(str).str.strip().str.upper()
    df_gen["vnogen"] = df_gen["vnogen"].astype(str).str.strip()
    df_genral["modeg"] = df_genral["modeg"].astype(str).str.strip().str.upper()
    df_genral["vnog2"] = df_genral["vnog2"].astype(str).str.strip()
    df_chart["chartbal"] = pd.to_numeric(df_chart.get("chartbal",0), errors='coerce').fillna(0)

    merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen","co"], right_on=["modeg","vnog2","co"], how="inner")
    merged["drg2"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    merged["crg2"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)

    df1 = merged[["accg2","drg2","crg2"]].rename(columns={"accg2":"acc_code","drg2":"debit","crg2":"credit"})
    df2 = pd.DataFrame()
    df2["acc_code"] = merged["cashgen"]
    df2["debit"] = merged["crg2"]
    df2["credit"] = merged["drg2"]
    tran = pd.concat([df1, df2], ignore_index=True).groupby("acc_code")[["debit","credit"]].sum().reset_index()

    df_open = df_chart[df_chart["chartbal"]!=0][["chartid","chartbal"]].copy()
    df_open["acc_code"] = df_open["chartid"]
    df_open["debit"] = df_open["chartbal"].apply(lambda x: x if x>0 else 0)
    df_open["credit"] = df_open["chartbal"].apply(lambda x: abs(x) if x<0 else 0)
    df_open = df_open[["acc_code","debit","credit"]]

    combined = pd.concat([tran, df_open], ignore_index=True).groupby("acc_code")[["debit","credit"]].sum().reset_index()
    combined["NET_DEBIT"] = (combined["debit"]-combined["credit"]).apply(lambda x: x if x>0 else 0)
    combined["NET_CREDIT"] = (combined["credit"]-combined["debit"]).apply(lambda x: x if x>0 else 0)
    t_dr = combined["NET_DEBIT"].sum()
    t_cr = combined["NET_CREDIT"].sum()

    trial = pd.merge(combined, df_chart, left_on="acc_code", right_on="chartid", how="inner")
    trial["DISPLAY_NAME"] = trial["chartname"].astype(str)
    trial["DISPLAY_TYPE"] = trial["charttype"].astype(str)
    trial = trial[(trial["NET_DEBIT"]+trial["NET_CREDIT"])>0]
    return trial, t_dr, t_cr

@st.cache_data(ttl=60)



def get_ledger(co, acc_code):
    df_chart, df_gen, df_genral = load_all(co)
    df_gen["modegen"] = df_gen["modegen"].astype(str).str.strip().str.upper()
    df_gen["vnogen"] = df_gen["vnogen"].astype(str).str.strip()
    df_genral["modeg"] = df_genral["modeg"].astype(str).str.strip().str.upper()
    df_genral["vnog2"] = df_genral["vnog2"].astype(str).str.strip()
    df_chart["chartbal"] = pd.to_numeric(df_chart.get("chartbal",0), errors='coerce').fillna(0)

    merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen","co"], right_on=["modeg","vnog2","co"], how="inner")
    merged["drg2"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    merged["crg2"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)

    # detailg2 ka column lower kar diya hai load_all me
    if "detailg2" not in merged.columns:
        merged["detailg2"] = ""

    leg1 = merged[merged["accg2"]==acc_code].copy()
    leg1["DEBIT"] = leg1["drg2"]
    leg1["CREDIT"] = leg1["crg2"]
    leg1["OPP"] = leg1["cashgen"]

    leg2 = merged[merged["cashgen"]==acc_code].copy()
    leg2["DEBIT"] = leg2["crg2"]
    leg2["CREDIT"] = leg2["drg2"]
    leg2["OPP"] = leg2["accg2"]

    ledger = pd.concat([leg1, leg2], ignore_index=True)
    date_col = None
    for c in ["dateg","date","vdate","gen_date","dategen"]:
        if c in ledger.columns: date_col = c; break

    opening = df_chart[df_chart["chartid"]==acc_code]["chartbal"].sum()
    return ledger, opening, date_col




# ---------- Main ----------
st.title(f"{company_map[co]} - {report_type}")

if report_type == "Trial Balance":
    df_trial, t_dr, t_cr = get_trial(co)
    if df_trial.empty:
        st.info("Data nahi hai")
        st.stop()
    df_show = df_trial.sort_values(["DISPLAY_TYPE","DISPLAY_NAME"])
    t_debit = df_show["NET_DEBIT"].sum()
    t_credit = df_show["NET_CREDIT"].sum()
    
    # Simple display - pura Trial Balance
    display_df = df_show[["DISPLAY_TYPE","DISPLAY_NAME","NET_DEBIT","NET_CREDIT"]].copy()
    display_df.columns = ["GROUP","ACCOUNT TITLE","DEBIT","CREDIT"]
    display_df.loc[len(display_df)] = ["", "GRAND TOTAL", t_debit, t_credit]
    
    # 0 ko khali dikhao, None nahi
    for c in ["DEBIT","CREDIT"]:
        display_df[c] = pd.to_numeric(display_df[c], errors='coerce').fillna(0)
        display_df[c] = display_df[c].apply(lambda x: "" if x==0 else x)

    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Excel", display_df.to_csv(index=False).encode(), f"TB_{company_map[co]}.csv")
    with c2:
        if st.button("Print"):
            html = f"<html><body onload='window.print()'><h2>Trial - {company_map[co]}</h2>{display_df.to_html(index=False)}</body></html>"
            components.html(html, height=700)

else:
    df_chart, _, _ = load_all(co)
    df_chart["label"] = df_chart["chartid"] + " - " + df_chart["chartname"].astype(str)
    acc_label = st.selectbox("Account Select karo", df_chart["label"].sort_values().tolist())
    acc_code = acc_label.split(" - ")[0]
    ledger, opening, date_col = get_ledger(co, acc_code)
    
    rows = []
    bal = opening
    rows.append({"DATE": "Opening", "VNO": "", "PARTICULAR": "Opening Balance", "DEBIT": "", "CREDIT": "", "BALANCE": opening})
    
    if date_col:
        ledger[date_col] = pd.to_datetime(ledger[date_col], errors='coerce')
        ledger = ledger.sort_values(by=date_col)
    
    for _, r in ledger.iterrows():
        bal += r["DEBIT"] - r["CREDIT"]
        opp = df_chart[df_chart["chartid"]==r["OPP"]]["chartname"].values
        opp = opp[0] if len(opp)>0 else r["OPP"]
        detail = str(r.get("detailg2","")).strip()
        part = f"{opp} - {detail}" if detail and detail.lower()!="nan" else opp
        d = r[date_col].strftime("%d-%m-%Y") if date_col and pd.notna(r[date_col]) else ""
        rows.append({"DATE": d, "VNO": f"{r.get('modeg','')}-{r.get('vnog2','')}", "PARTICULAR": part, "DEBIT": "" if r['DEBIT']==0 else r['DEBIT'], "CREDIT": "" if r['CREDIT']==0 else r['CREDIT'], "BALANCE": bal})
    
    df_leg = pd.DataFrame(rows)
    st.subheader(f"Ledger: {acc_label} | Balance: {bal:,.0f}")
    st.dataframe(df_leg, use_container_width=True, hide_index=True)
