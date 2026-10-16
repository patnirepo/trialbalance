import streamlit as st
import pandas as pd
from supabase import create_client
import streamlit.components.v1 as components

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

@st.cache_data(ttl=60)
def get_trial(co): # naam same rakha
    chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data
    gen_data = supabase.table("gen").select("*").eq("co", co).execute().data
    genral_data = supabase.table("genral").select("*").eq("co", co).execute().data

    df_chart = pd.DataFrame(chart_data)
    df_gen = pd.DataFrame(gen_data)
    df_genral = pd.DataFrame(genral_data)

    df_chart.columns = [c.lower() for c in df_chart.columns]
    df_gen.columns = [c.lower() for c in df_gen.columns]
    df_genral.columns = [c.lower() for c in df_genral.columns]

    df_gen["modegen"] = df_gen["modegen"].astype(str).str.strip().str.upper()
    df_gen["vnogen"] = df_gen["vnogen"].astype(str).str.strip()
    df_gen["cashgen"] = df_gen["cashgen"].astype(str).str.strip()
    df_genral["modeg"] = df_genral["modeg"].astype(str).str.strip().str.upper()
    df_genral["vnog2"] = df_genral["vnog2"].astype(str).str.strip()
    df_genral["accg2"] = df_genral["accg2"].astype(str).str.strip()

    df_chart["chartid"] = df_chart["chartid"].astype(str)
    df_chart["chartbal"] = pd.to_numeric(df_chart["chartbal"], errors='coerce').fillna(0)

    # Transaction
    merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen","co"], right_on=["modeg","vnog2","co"], how="inner")
    merged["drg2"] = pd.to_numeric(merged["drg2"], errors='coerce').fillna(0)
    merged["crg2"] = pd.to_numeric(merged["crg2"], errors='coerce').fillna(0)

    df1 = merged[["accg2","drg2","crg2"]].rename(columns={"accg2":"acc_code","drg2":"debit","crg2":"credit"})
    df2 = pd.DataFrame()
    df2["acc_code"] = merged["cashgen"]
    df2["debit"] = merged["crg2"]
    df2["credit"] = merged["drg2"]
    tran = pd.concat([df1, df2], ignore_index=True).groupby("acc_code")[["debit","credit"]].sum().reset_index()

    # Opening
    df_open = df_chart[df_chart["chartbal"]!=0][["chartid","chartbal"]].copy()
    df_open["acc_code"] = df_open["chartid"]
    df_open["debit"] = df_open["chartbal"].apply(lambda x: x if x>0 else 0)
    df_open["credit"] = df_open["chartbal"].apply(lambda x: abs(x) if x<0 else 0)
    df_open = df_open[["acc_code","debit","credit"]]

    combined = pd.concat([tran, df_open], ignore_index=True).groupby("acc_code")[["debit","credit"]].sum().reset_index()
    combined["NET_DEBIT"] = (combined["debit"] - combined["credit"]).apply(lambda x: x if x>0 else 0)
    combined["NET_CREDIT"] = (combined["credit"] - combined["debit"]).apply(lambda x: x if x>0 else 0)

    t_dr = combined["NET_DEBIT"].sum()
    t_cr = combined["NET_CREDIT"].sum()

    trial = pd.merge(combined, df_chart, left_on="acc_code", right_on="chartid", how="left")
    trial["DISPLAY_NAME"] = trial["chartname"].fillna("A/c "+trial["acc_code"])
    trial["DISPLAY_TYPE"] = trial["charttype"].fillna("OTHER")
    trial.loc[trial["DISPLAY_NAME"].str.lower()=="none", "DISPLAY_NAME"] = "A/c "+trial["acc_code"]

    return trial, t_dr, t_cr

# --- Main ---
co = 1
df_trial, t_dr, t_cr = get_trial(co) # naam ab same hai

st.write(f"Opening Total: {pd.DataFrame(supabase.table('chart').select('chartbal').eq('comp',co).execute().data)['chartbal'].sum() if True else 0}")
st.write(f"Grand Debit: {t_dr:,.0f} | Grand Credit: {t_cr:,.0f} | Diff: {t_dr-t_cr:,.0f}")

df_show = df_trial.sort_values(["DISPLAY_TYPE","DISPLAY_NAME"])
final_list = []
last_group = None
for g_type, g_df in df_show.groupby("DISPLAY_TYPE", sort=True):
    for _, row in g_df.sort_values("DISPLAY_NAME").iterrows():
        if row["NET_DEBIT"]+row["NET_CREDIT"]==0: continue
        final_list.append({
            "GROUP": g_type if g_type!=last_group else "",
            "ACCOUNT TITLE": row["DISPLAY_NAME"],
            "DEBIT": f"{row['NET_DEBIT']:,.0f}" if row["NET_DEBIT"] else "",
            "CREDIT": f"{row['NET_CREDIT']:,.0f}" if row["NET_CREDIT"] else ""
        })
    last_group = g_type

final_list.append({"GROUP":"","ACCOUNT TITLE":"GRAND TOTAL","DEBIT":f"{t_dr:,.0f}","CREDIT":f"{t_cr:,.0f}"})
df_final = pd.DataFrame(final_list)
st.dataframe(df_final, use_container_width=True, hide_index=True)

st.download_button("📥 Excel", df_final.to_csv(index=False).encode(), "TB.csv")
if st.button("🖨️ Print"):
    html = f"<html><body onload='window.print()'>{df_final.to_html(index=False)}</body></html>"
    components.html(html, height=700)
