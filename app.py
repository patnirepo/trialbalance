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
        # Table naam small me try karo - Supabase aksar small naam banata hai
        # Agar aapka naam GEN hai to "GEN" rakho, agar gen hai to gen
        try:
            gen_data = supabase.table("GEN").select("*").eq("co", co).execute().data
        except:
            gen_data = supabase.table("gen").select("*").eq("co", co).execute().data

        try:
            genral_data = supabase.table("GENRAL").select("*").eq("co", co).execute().data
        except:
            genral_data = supabase.table("genral").select("*").eq("co", co).execute().data
            
        try:
            chart_data = supabase.table("chart").select("*").execute().data
            # chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data
        except:
            chart_data = supabase.table("CHART").select("*").execute().data
            # chart_data = supabase.table("chart").select("*").eq("comp", co).execute().data

        df_gen = pd.DataFrame(gen_data)
        df_genral = pd.DataFrame(genral_data)
        df_chart = pd.DataFrame(chart_data)

        if df_gen.empty or df_genral.empty:
            return pd.DataFrame(), 0, 0, "gen ya Genral me co="+str(co)+" ka data nahi mila"

        merged = pd.merge(df_gen, df_genral, left_on=["modegen","vnogen"], right_on=["modeg","vnog2"], how="inner")
        
        if merged.empty:
            return pd.DataFrame(), 0, 0, "gen aur genral ka joint (modegen=modeg, vnogen=vnog2) nahi mila"

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
        
        df_chart["chartid"] = df_chart["chartid"].astype(str)
        trial = pd.merge(trial, df_chart, left_on="acc_code", right_on="chartid", how="left")

        trial["DEBIT"] = (trial["debit"] - trial["credit"]).apply(lambda x: x if x>0 else 0)
        trial["CREDIT"] = (trial["credit"] - trial["debit"]).apply(lambda x: x if x>0 else 0)

        return trial, trial["DEBIT"].sum(), trial["CREDIT"].sum(), "ok"

    except Exception as e:
        return pd.DataFrame(), 0, 0, f"ERROR: {str(e)}"

df_trial, t_dr, t_cr, msg = get_trial(co_code)

if msg != "ok":
    st.error(msg)
    st.info("Supabase > Table Editor me jaake check karo: Table ka sahi naam kya hai? GEN, gen, ya kuch aur? Aur RLS Policy ON hai to usko OFF karo ya Policy banao: ENABLE READ for anon")
else:
    if not df_trial.empty:
        st.write(f"### TRIAL BALANCE - Co {co_code}")
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Debit", f"{t_dr:,.0f}")
        c2.metric("Total Credit", f"{t_cr:,.0f}")
        c3.metric("Diff", f"{t_dr-t_cr:,.0f}")
        st.dataframe(df_trial[["acc_code","chartname","charttype","DEBIT","CREDIT"]])
