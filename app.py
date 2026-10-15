import streamlit as st
import pandas as pd
from supabase import create_client

URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL, KEY)

# Company select
co_code = st.selectbox("Company Select karo", [1, 2], index=0)

@st.cache_data(ttl=60)
def get_trial(co):
    # 3 tables load
    gen_data = supabase.table("GEN").select("*").eq("co", co).execute().data
    genral_data = supabase.table("GENRAL").select("*").eq("co", co).execute().data
    chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data

    df_gen = pd.DataFrame(gen_data)
    df_genral = pd.DataFrame(genral_data)
    df_chart = pd.DataFrame(chart_data)

    if df_gen.empty or df_genral.empty:
        return pd.DataFrame(), 0, 0

    # Joint key
    merged = pd.merge(df_gen, df_genral, 
                      left_on=["modegen","vnogen"], 
                      right_on=["modeg","vnog2"], how="inner")

    # 1st account - accg2 (jaise Ahmed Traders, Office Exp)
    df1 = pd.DataFrame()
    df1["acc_code"] = merged["accg2"]
    df1["debit"] = merged["drg2"]
    df1["credit"] = merged["crg2"]

    # 2nd account - cashgen (cash code)
    # Cash ka ulta hota hai: agar accg2 debit hai to cash credit
    df2 = pd.DataFrame()
    df2["acc_code"] = merged["cashgen"]
    df2["debit"] = merged["crg2"]  # Ulta
    df2["credit"] = merged["drg2"] # Ulta

    # Dono ko joro
    all_entries = pd.concat([df1, df2], ignore_index=True)
    all_entries["acc_code"] = all_entries["acc_code"].astype(str)

    # Sum by code
    trial = all_entries.groupby("acc_code")[["debit","credit"]].sum().reset_index()
    
    # Chart se naam lao
    df_chart["chartid"] = df_chart["chartid"].astype(str)
    trial = pd.merge(trial, df_chart, left_on="acc_code", right_on="chartid", how="left")

    # Final format jaisa aapki photo me hai
    trial["DEBIT"] = trial["debit"] - trial["credit"]
    trial["DEBIT"] = trial["DEBIT"].apply(lambda x: x if x>0 else 0)
    trial["CREDIT"] = trial["credit"] - trial["debit"]
    trial["CREDIT"] = trial["CREDIT"].apply(lambda x: x if x>0 else 0)

    total_dr = trial["DEBIT"].sum()
    total_cr = trial["CREDIT"].sum()
    
    return trial, total_dr, total_cr

df_trial, t_dr, t_cr = get_trial(co_code)

if not df_trial.empty:
    st.write(f"### TRIAL BALANCE - Company {co_code}")
    st.write(f"**Total Debit: {t_dr:,.0f} | Total Credit: {t_cr:,.0f} | Diff: {t_dr-t_cr:,.0f}**")
    
    # Aapki photo jaisa table
    st.dataframe(df_trial[["acc_code","chartname","charttype","DEBIT","CREDIT"]].sort_values("charttype"))
else:
    st.warning("Is company ka data nahi mila, Supabase me co=1 ya 2 check karo")
