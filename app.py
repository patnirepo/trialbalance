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
    import pandas as pd
    gen_data = supabase.table("gen").select("*").eq("co", co).execute().data
    genral_data = supabase.table("genral").select("*").eq("co", co).execute().data
    chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data

    df_gen = pd.DataFrame(gen_data)
    df_genral = pd.DataFrame(genral_data)
    df_chart = pd.DataFrame(chart_data)

    id_col = next((c for c in df_chart.columns if c.lower() in ["chartid","id","code"]), df_chart.columns[0])
    name_col = next((c for c in df_chart.columns if "name" in c.lower() or "title" in c.lower()), df_chart.columns[1])
    bal_col = next((c for c in df_chart.columns if "bal" in c.lower()), None)

    df_chart[id_col] = df_chart[id_col].astype(str)

    # Cash aur Bin ka Chart ID nikalo
    cash_ids = df_chart[df_chart[name_col].str.contains("Cash in hand", case=False, na=False)][id_col].tolist()
    bin_ids = df_chart[df_chart[name_col].str.contains("Bin", case=False, na=False)][id_col].tolist()

    st.write(f"Cash IDs: {cash_ids} | Bin IDs: {bin_ids}")

    df_genral["accg2"] = df_genral["accg2"].astype(str)
    df_gen["cashgen"] = df_gen["cashgen"].astype(str)

    merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen"], right_on=["modeg","vnog2"], how="inner")

    # Sirf Cash aur Bin se related entries
    target_ids = cash_ids + bin_ids
    m = merged[(merged["accg2"].isin(target_ids)) | (merged["cashgen"].isin(target_ids))]

    # 682k aur 519k wali entry dhoondo
    m["drg2"] = pd.to_numeric(m["drg2"], errors='coerce').fillna(0)
    m["crg2"] = pd.to_numeric(m["crg2"], errors='coerce').fillna(0)

    m_target = m[(m["drg2"].isin([682000, 519830])) | (m["crg2"].isin([682000, 519830])) | (m["accg2"].isin(target_ids)) | (m["cashgen"].isin(target_ids))]

    st.dataframe(m_target[["modegen","vnogen","cashgen","accg2","drg2","crg2","contra"]].head(20))

    return pd.DataFrame(), 0, 0, "debug mode"




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
