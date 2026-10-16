import streamlit as st
import pandas as pd
from supabase import create_client
import streamlit.components.v1 as components

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

@st.cache_data(ttl=60)
def get_trial_without_contra(co):
    # 1. Data
    chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data
    gen_data = supabase.table("gen").select("*").eq("co", co).execute().data
    genral_data = supabase.table("genral").select("*").eq("co", co).execute().data

    df_chart = pd.DataFrame(chart_data)
    df_gen = pd.DataFrame(gen_data)
    df_genral = pd.DataFrame(genral_data)

    df_chart.columns = [c.lower() for c in df_chart.columns]
    df_gen.columns = [c.lower() for c in df_gen.columns]
    df_genral.columns = [c.lower() for c in df_genral.columns]

    # 2. Joint keys - aapke bataye hue hisab se
    # GEN (modegen, vnogen, co) = GENRAL (modeg, vnog2, co)
    df_gen["modegen"] = df_gen["modegen"].astype(str).str.strip().str.upper()
    df_gen["vnogen"] = df_gen["vnogen"].astype(str).str.strip()
    df_gen["cashgen"] = df_gen["cashgen"].astype(str).str.strip()
    
    df_genral["modeg"] = df_genral["modeg"].astype(str).str.strip().str.upper()
    df_genral["vnog2"] = df_genral["vnog2"].astype(str).str.strip()
    df_genral["accg2"] = df_genral["accg2"].astype(str).str.strip()

    # 3. Merge - VB wala join
    merged = pd.merge(
        df_gen, 
        df_genral, 
        left_on=["modegen","vnogen","co"], 
        right_on=["modeg","vnog2","co"], 
        how="inner"
    )

    merged["drg2"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    merged["crg2"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)

    # 4. Bina contra ke - sirf 2 entry
    # Entry 1: GENRAL ka account (accg2)
    df_acc = merged[["accg2","drg2","crg2"]].copy()
    df_acc.rename(columns={"accg2":"acc_code","drg2":"debit","crg2":"credit"}, inplace=True)

    # Entry 2: GEN ka cash account (cashgen) - ulta
    df_cash = merged[["cashgen","drg2","crg2"]].copy()
    df_cash["debit"] = merged["crg2"]
    df_cash["credit"] = merged["drg2"]
    df_cash.rename(columns={"cashgen":"acc_code"}, inplace=True)
    df_cash = df_cash[["acc_code","debit","credit"]]

    all_tran = pd.concat([df_acc, df_cash], ignore_index=True)
    trial = all_tran.groupby("acc_code")[["debit","credit"]].sum().reset_index()

    # 5. Chart se naam aur group lao
    df_chart["chartid"] = df_chart["chartid"].astype(str)
    trial = pd.merge(trial, df_chart, left_on="acc_code", right_on="chartid", how="inner") # inner = OTHER khatam

    trial["DEBIT"] = (trial["debit"] - trial["credit"]).apply(lambda x: x if x>0 else 0)
    trial["CREDIT"] = (trial["credit"] - trial["debit"]).apply(lambda x: x if x>0 else 0)

    trial = trial[(trial["DEBIT"]+trial["CREDIT"])>0]

    # Filter None
    trial = trial[trial["chartname"].notna()]
    trial = trial[trial["chartname"].astype(str).str.strip()!=""]
    trial = trial[trial["chartname"].str.lower()!="none"]

    trial["DISPLAY_NAME"] = trial["chartname"]
    trial["DISPLAY_TYPE"] = trial["charttype"].fillna("CASH / BANK")
    
    return trial, trial["DEBIT"].sum(), trial["CREDIT"].sum()

# --- App ---
co = 1 # ya 2
df_trial, t_dr, t_cr = get_trial_without_contra(co)

df_show = df_trial.sort_values(["DISPLAY_TYPE","DISPLAY_NAME"])

final_list = []
last_group = None
for g_type, g_df in df_show.groupby("DISPLAY_TYPE", sort=True):
    for _, row in g_df.sort_values("DISPLAY_NAME").iterrows():
        final_list.append({
            "GROUP": g_type if g_type!=last_group else "",
            "ACCOUNT TITLE": row["DISPLAY_NAME"],
            "DEBIT": f"{row['DEBIT']:,.0f}" if row["DEBIT"] else "",
            "CREDIT": f"{row['CREDIT']:,.0f}" if row["CREDIT"] else ""
        })
    last_group = g_type

final_list.append({"GROUP":"","ACCOUNT TITLE":"GRAND TOTAL","DEBIT":f"{t_dr:,.0f}","CREDIT":f"{t_cr:,.0f}"})

df_final = pd.DataFrame(final_list)
st.dataframe(df_final, use_container_width=True, hide_index=True)

# Print
st.download_button("📥 Excel", df_final.to_csv(index=False).encode(), "TB.csv")
if st.button("🖨️ Print"):
    html = f"<html><body onload='window.print()'>{df_final.to_html(index=False)}</body></html>"
    components.html(html, height=600)
