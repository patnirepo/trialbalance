import streamlit as st
import pandas as pd
from supabase import create_client

URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
APP_PW = st.secrets["APP_PASSWORD"]

# Login
if "logged" not in st.session_state:
    st.session_state.logged = False
pw = st.text_input("Password", type="password")
if st.button("Login"):
    if pw == APP_PW:
        st.session_state.logged = True
        st.rerun()
if not st.session_state.logged:
    st.stop()

st.success("Logged In")
supabase = create_client(URL, KEY)

co_code = st.selectbox("Company Select karo", [1, 2], index=0)


@st.cache_data(ttl=60)
def get_trial(co):
    try:
        gen_data = supabase.table("GEN").select("*").eq("co", co).execute().data
    except:
        gen_data = supabase.table("gen").select("*").eq("co", co).execute().data
    try:
        genral_data = supabase.table("GENRAL").select("*").eq("co", co).execute().data
    except:
        genral_data = supabase.table("genral").select("*").eq("co", co).execute().data
    try:
        chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data
    except:
        chart_data = supabase.table("chart").select("*").eq("Comp", co).execute().data

    df_gen = pd.DataFrame(gen_data)
    df_genral = pd.DataFrame(genral_data)
    df_chart = pd.DataFrame(chart_data)

    id_col = next((c for c in df_chart.columns if c.lower() in ["chartid","id","code"]), df_chart.columns[0])
    name_col = next((c for c in df_chart.columns if "name" in c.lower() or "title" in c.lower()), df_chart.columns[1])
    type_col = next((c for c in df_chart.columns if "type" in c.lower()), None)
    bal_col = next((c for c in df_chart.columns if "bal" in c.lower()), None)
    contra_col = next((c for c in df_genral.columns if "contra" in c.lower()), None)

    df_chart[id_col] = df_chart[id_col].astype(str)
    df_chart = df_chart.drop_duplicates(subset=[id_col], keep='first')
    if bal_col:
        df_chart[bal_col] = pd.to_numeric(df_chart[bal_col], errors='coerce').fillna(0)

    merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen"], right_on=["modeg","vnog2"], how="inner")

    # Contra wali 9 entries
    if contra_col:
        merged[contra_col] = merged[contra_col].astype(str).str.upper()

    # 1. GEN.cashgen se -> ye har entry me aayega (9 contra wali bhi)
    df_cash = pd.DataFrame()
    df_cash["acc_code"] = merged["cashgen"].astype(str)
    df_cash["debit"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)
    df_cash["credit"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)

    # 2. GENRAL.accg2 se -> ye contra ka reflection hai (yehi 9 extra CASH me)
    df_other = pd.DataFrame()
    df_other["acc_code"] = merged["accg2"].astype(str)
    df_other["debit"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    df_other["credit"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)

    all_entries = pd.concat([df_cash, df_other], ignore_index=True)
    trial_tran = all_entries.groupby("acc_code")[["debit","credit"]].sum().reset_index()

    # Opening - sirf isi comp ke
    if bal_col:
        df_open = df_chart[df_chart[bal_col]!=0].copy()
        df_open["acc_code"] = df_open[id_col].astype(str)
        df_open["debit"] = df_open[bal_col].apply(lambda x: x if x>0 else 0)
        df_open["credit"] = df_open[bal_col].apply(lambda x: abs(x) if x<0 else 0)
        df_open = df_open[["acc_code","debit","credit"]]
        trial = pd.concat([trial_tran, df_open], ignore_index=True)
        trial = trial.groupby("acc_code")[["debit","credit"]].sum().reset_index()
    else:
        trial = trial_tran

    trial = pd.merge(trial, df_chart, left_on="acc_code", right_on=id_col, how="left")
    trial["DEBIT"] = (trial["debit"] - trial["credit"]).apply(lambda x: x if x>0 else 0)
    trial["CREDIT"] = (trial["credit"] - trial["debit"]).apply(lambda x: x if x>0 else 0)
    trial["DISPLAY_NAME"] = trial[name_col]
    trial["DISPLAY_TYPE"] = trial[type_col] if type_col else "OTHER"
    trial = trial[(trial["DEBIT"] + trial["CREDIT"]) > 0]

    return trial, trial["DEBIT"].sum(), trial["CREDIT"].sum(), "ok"



df_trial, t_dr, t_cr, msg = get_trial(co_code)

if "ERROR" in msg:
    st.error(msg)
else:
    # st.caption(msg) -> ye line hata do ya comment karo
    df_show = df_trial.sort_values(["DISPLAY_TYPE","DISPLAY_NAME"])

    final_list = []
    last_group = None
    for g_type, group_df in df_show.groupby("DISPLAY_TYPE", sort=True):
        g_type = g_type if g_type else "OTHER"
        for i, (_, row) in enumerate(group_df.sort_values("DISPLAY_NAME").iterrows()):
            final_list.append({
                "GROUP": g_type if g_type != last_group else "",
                "ACCOUNT TITLE": row["DISPLAY_NAME"],
                "DEBIT": f"{row['DEBIT']:,.0f}" if row['DEBIT']>0 else "",
                "CREDIT": f"{row['CREDIT']:,.0f}" if row['CREDIT']>0 else ""
            })
            last_group = g_type

    final_list.append({
        "GROUP": "",
        "ACCOUNT TITLE": "GRAND TOTAL",
        "DEBIT": f"{t_dr:,.0f}",
        "CREDIT": f"{t_cr:,.0f}"
    })

    st.dataframe(pd.DataFrame(final_list), use_container_width=True, hide_index=True)
