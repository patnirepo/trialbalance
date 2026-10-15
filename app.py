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

    # Saari companies ka data sirf ye check karne ke liye ke kaunsa acc kis company ka hai
    try:
        gen_all = supabase.table("GEN").select("accg2,cashgen,co").execute().data
    except:
        gen_all = supabase.table("gen").select("accg2,cashgen,co").execute().data

    chart_data = supabase.table("chart").select("*").execute().data

    df_gen = pd.DataFrame(gen_data)
    df_genral = pd.DataFrame(genral_data)
    df_chart = pd.DataFrame(chart_data)
    df_all = pd.DataFrame(gen_all)

    if df_gen.empty:
        return pd.DataFrame(), 0, 0, f"co={co} ka data nahi"

    id_col = next((c for c in df_chart.columns if c.lower() in ["chartid","id","code"]), df_chart.columns[0])
    name_col = next((c for c in df_chart.columns if "name" in c.lower() or "title" in c.lower()), df_chart.columns[1])
    type_col = next((c for c in df_chart.columns if "type" in c.lower()), None)
    bal_col = next((c for c in df_chart.columns if "bal" in c.lower()), None)

    df_chart[id_col] = df_chart[id_col].astype(str)
    df_chart = df_chart.drop_duplicates(subset=[id_col], keep='first')

    # Current company ke transaction wale acc
    merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen"], right_on=["modeg","vnog2"], how="inner")
    df1 = pd.DataFrame()
    df1["acc_code"] = merged["accg2"].astype(str)
    df1["debit"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    df1["credit"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)
    df2 = pd.DataFrame()
    df2["acc_code"] = merged["cashgen"].astype(str)
    df2["debit"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)
    df2["credit"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    all_entries = pd.concat([df1, df2], ignore_index=True)
    trial = all_entries.groupby("acc_code")[["debit","credit"]].sum().reset_index()

    # Doosri company me kaunse acc use hue hain
    df_all["accg2"] = df_all["accg2"].astype(str)
    df_all["cashgen"] = df_all["cashgen"].astype(str)
    acc_other = set(df_all[df_all["co"]!= co]["accg2"].tolist() + df_all[df_all["co"]!= co]["cashgen"].tolist())
    acc_current = set(trial["acc_code"].tolist())

    # Opening wale acc
    if bal_col and bal_col in df_chart.columns:
        df_chart[bal_col] = pd.to_numeric(df_chart[bal_col], errors='coerce').fillna(0)
        df_open = df_chart[df_chart[bal_col]!= 0].copy()
        df_open["acc_code"] = df_open[id_col].astype(str)

        # FILTER: Agar acc sirf doosri company ka hai (Sales) to opening bhi na lao
        df_open = df_open[~((df_open["acc_code"].isin(acc_other)) & (~df_open["acc_code"].isin(acc_current)))]

        df_open["debit"] = df_open[bal_col].apply(lambda x: x if x>0 else 0)
        df_open["credit"] = df_open[bal_col].apply(lambda x: abs(x) if x<0 else 0)
        df_open = df_open[["acc_code","debit","credit"]]

        trial = pd.concat([trial, df_open], ignore_index=True)
        trial = trial.groupby("acc_code")[["debit","credit"]].sum().reset_index()

    trial = pd.merge(trial, df_chart, left_on="acc_code", right_on=id_col, how="left")
    trial["DEBIT"] = (trial["debit"] - trial["credit"]).apply(lambda x: x if x>0 else 0)
    trial["CREDIT"] = (trial["credit"] - trial["debit"]).apply(lambda x: x if x>0 else 0)
    trial["DISPLAY_NAME"] = trial[name_col]
    trial["DISPLAY_TYPE"] = trial[type_col] if type_col else "OTHER"
    trial = trial[(trial["DEBIT"] + trial["CREDIT"]) > 0]

    return trial, trial["DEBIT"].sum(), trial["CREDIT"].sum(), "ok"    



df_trial, t_dr, t_cr, msg = get_trial(co_code)

if msg!= "ok":
    st.error(msg)
else:
    df_show = df_trial.sort_values(["DISPLAY_TYPE","DISPLAY_NAME"])

    final_list = []
    last_group = None
    for g_type, group_df in df_show.groupby("DISPLAY_TYPE", sort=True):
        g_type = g_type if g_type else "OTHER"
        for i, (_, row) in enumerate(group_df.sort_values("DISPLAY_NAME").iterrows()):
            final_list.append({
                "GROUP": g_type if g_type!= last_group else "", # Sirf pehli bar group naam
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
