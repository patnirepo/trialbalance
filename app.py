import streamlit as st
import pandas as pd
from supabase import create_client
import streamlit.components.v1 as components

# Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

@st.cache_data(ttl=60)
def get_trial(co):
    gen_data = supabase.table("gen").select("*").eq("co", co).execute().data
    genral_data = supabase.table("genral").select("*").execute().data
    chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data

    df_gen = pd.DataFrame(gen_data)
    df_genral = pd.DataFrame(genral_data)
    df_chart = pd.DataFrame(chart_data)

    # columns ko lower me karo taake ChartId / chartid ka masla khatam
    df_chart.columns = [c.lower() for c in df_chart.columns]
    df_gen.columns = [c.lower() for c in df_gen.columns]
    df_genral.columns = [c.lower() for c in df_genral.columns]

    if df_gen.empty:
        return pd.DataFrame(), 0, 0, "no data"

    df_gen["modegen"] = df_gen["modegen"].astype(str).str.strip().str.upper()
    df_gen["vnogen"] = df_gen["vnogen"].astype(str).str.strip()
    df_gen["cashgen"] = df_gen["cashgen"].astype(str).str.strip()
    df_genral["modeg"] = df_genral["modeg"].astype(str).str.strip().str.upper()
    df_genral["vnog2"] = df_genral["vnog2"].astype(str).str.strip()
    df_genral["accg2"] = df_genral["accg2"].astype(str).str.strip()

    df_chart["chartid"] = df_chart["chartid"].astype(str)
    df_chart["chartname"] = df_chart["chartname"].astype(str)
    df_chart["charttype"] = df_chart["charttype"].astype(str)
    df_chart["chartbal"] = pd.to_numeric(df_chart["chartbal"], errors='coerce').fillna(0)

    df_chart = df_chart.drop_duplicates(subset=["chartid"], keep='first')

    merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen"], right_on=["modeg","vnog2"], how="inner")
    merged["drg2"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    merged["crg2"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)

    # Contra logic - Cash 46 aur Bin 49
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

    # Opening
    df_open = df_chart[df_chart["chartbal"]!=0].copy()
    df_open["acc_code"] = df_open["chartid"].astype(str)
    df_open["debit"] = df_open["chartbal"].apply(lambda x: x if x>0 else 0)
    df_open["credit"] = df_open["chartbal"].apply(lambda x: abs(x) if x<0 else 0)
    df_open = df_open[["acc_code","debit","credit"]]

    trial = pd.concat([trial_tran, df_open], ignore_index=True)
    trial = trial.groupby("acc_code")[["debit","credit"]].sum().reset_index()

    trial = pd.merge(trial, df_chart, left_on="acc_code", right_on="chartid", how="left")
    
    trial["DEBIT"] = (trial["debit"] - trial["credit"]).apply(lambda x: x if x>0 else 0)
    trial["CREDIT"] = (trial["credit"] - trial["debit"]).apply(lambda x: x if x>0 else 0)

    # --- FIX for OTHER and None ---
    # Agar chartname khali ya None hai to usko hata do - yahi grand total galat kar raha tha
    trial["DISPLAY_NAME"] = trial["chartname"]
    trial["DISPLAY_TYPE"] = trial["charttype"]

    # None aur 'nan' ko filter
    trial = trial[trial["DISPLAY_NAME"].str.lower()!="none"]
    trial = trial[trial["DISPLAY_NAME"].str.lower()!="nan"]
    trial = trial[trial["DISPLAY_NAME"].str.strip()!=""]

    # OTHER ko sahi type me daalo
    trial.loc[trial["DISPLAY_TYPE"].str.lower()=="none", "DISPLAY_TYPE"] = "CASH"
    trial.loc[trial["DISPLAY_TYPE"].str.lower()=="nan", "DISPLAY_TYPE"] = "CASH"
    trial.loc[trial["DISPLAY_TYPE"].str.strip()=="", "DISPLAY_TYPE"] = "CASH"

    trial = trial[(trial["DEBIT"] + trial["CREDIT"]) > 0]
    return trial, trial["DEBIT"].sum(), trial["CREDIT"].sum(), "ok"

# --- Main App ---
co = 1
df_trial, t_dr, t_cr, status = get_trial(co)

if df_trial.empty:
    st.warning("No data")
    st.stop()

df_show = df_trial.sort_values(["DISPLAY_TYPE","DISPLAY_NAME"])

final_list = []
last_group = None
for g_type, group_df in df_show.groupby("DISPLAY_TYPE", sort=True):
    g_type = g_type if g_type else "CASH"
    for _, row in group_df.sort_values("DISPLAY_NAME").iterrows():
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

df_final = pd.DataFrame(final_list)
st.dataframe(df_final, use_container_width=True, hide_index=True)

# --- PRINT REPORT ---
st.markdown("### Print Report")
st.download_button("📥 Excel Download", df_final.to_csv(index=False).encode('utf-8'), "trial_balance.csv", "text/csv")

if st.button("🖨️ Print Report"):
    html = f"""
    <html><head><style>
    table {{width:100%; border-collapse:collapse; font-family: Arial; font-size:12px;}}
    th, td {{border:1px solid black; padding:5px; text-align:left;}}
    th {{background:#f2f2f2;}}
    </style></head><body onload="window.print()">
    <h2>Trial Balance</h2>
    {df_final.to_html(index=False)}
    </body></html>
    """
    components.html(html, height=700, scrolling=True)
