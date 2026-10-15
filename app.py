import streamlit as st
import pandas as pd
from supabase import create_client

# --- Supabase Connection ---
# Agar aapke secrets me naam alag hai to yahan change kar dena
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]

supabase = create_client(url, key)

@st.cache_data(ttl=60)
def get_trial(co):
    gen_data = supabase.table("gen").select("*").eq("co", co).execute().data
    genral_data = supabase.table("genral").select("*").execute().data
    chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data

    df_gen = pd.DataFrame(gen_data)
    df_genral = pd.DataFrame(genral_data)
    df_chart = pd.DataFrame(chart_data)

    if df_gen.empty:
        return pd.DataFrame(), 0, 0, "no data"

    df_gen["modegen"] = df_gen["modegen"].astype(str).str.strip().str.upper()
    df_gen["vnogen"] = df_gen["vnogen"].astype(str).str.strip()
    df_gen["cashgen"] = df_gen["cashgen"].astype(str).str.strip()
    df_genral["modeg"] = df_genral["modeg"].astype(str).str.strip().str.upper()
    df_genral["vnog2"] = df_genral["vnog2"].astype(str).str.strip()
    df_genral["accg2"] = df_genral["accg2"].astype(str).str.strip()

    id_col = next((c for c in df_chart.columns if c.lower() in ["chartid","id","code"]), df_chart.columns[0])
    name_col = next((c for c in df_chart.columns if "name" in c.lower() or "title" in c.lower()), df_chart.columns[1])
    type_col = next((c for c in df_chart.columns if "type" in c.lower()), None)
    bal_col = next((c for c in df_chart.columns if "bal" in c.lower()), None)

    df_chart[id_col] = df_chart[id_col].astype(str)
    df_chart = df_chart.drop_duplicates(subset=[id_col], keep='first')
    if bal_col:
        df_chart[bal_col] = pd.to_numeric(df_chart[bal_col], errors='coerce').fillna(0)

    merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen"], right_on=["modeg","vnog2"], how="inner")
    merged["drg2"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    merged["crg2"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)

    df1 = pd.DataFrame()
    df1["acc_code"] = merged["accg2"]
    df1["debit"] = merged["drg2"]
    df1["credit"] = merged["crg2"]

    df2 = pd.DataFrame()
    df2["acc_code"] = merged["cashgen"]
    df2["debit"] = merged["crg2"]
    df2["credit"] = merged["drg2"]

    all_entries = pd.concat([df1, df2], ignore_index=True)
    trial_tran = all_entries.groupby("acc_code")[["debit","credit"]].sum().reset_index()

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
    trial["DISPLAY_NAME"] = trial[name_col] if name_col in trial.columns else trial["acc_code"]
    trial["DISPLAY_TYPE"] = trial[type_col].fillna("OTHER") if type_col and type_col in trial.columns else "OTHER"
    trial = trial[(trial["DEBIT"] + trial["CREDIT"]) > 0]
    return trial, trial["DEBIT"].sum(), trial["CREDIT"].sum(), "ok"

# --- Main ---
co = 1
df_trial, t_dr, t_cr, status = get_trial(co)

if df_trial.empty:
    st.warning("No data")
    st.stop()

if "DISPLAY_TYPE" in df_trial.columns and "DISPLAY_NAME" in df_trial.columns:
    df_show = df_trial.sort_values(["DISPLAY_TYPE", "DISPLAY_NAME"])
else:
    df_show = df_trial.sort_values(["DISPLAY_NAME"])

final_list = []
last_group = None
for g_type, group_df in df_show.groupby("DISPLAY_TYPE", sort=True):
    g_type = g_type if g_type else "OTHER"
    for i, (_, row) in enumerate(group_df.sort_values("DISPLAY_NAME").iterrows()):
        final_list.append({
            "GROUP": g_type if g_type!= last_group else "",
            "ACCOUNT TITLE": row["DISPLAY_NAME"],
            "DEBIT": f"{row['DEBIT']:,.0f}" if row["DEBIT"] else "",
            "CREDIT": f"{row['CREDIT']:,.0f}" if row["CREDIT"] else ""
        })
    last_group = g_type

final_list.append({
    "GROUP": "",
    "ACCOUNT TITLE": "GRAND TOTAL",
    "DEBIT": f"{t_dr:,.0f}",
    "CREDIT": f"{t_cr:,.0f}"
})

st.dataframe(pd.DataFrame(final_list), use_container_width=True, hide_index=True)
