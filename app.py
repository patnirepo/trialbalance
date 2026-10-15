import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="Trial Balance CO-1", layout="wide", page_icon="📊")

# --- LOGIN (Sidebar) ---
st.sidebar.title("🔐 Login")
pwd = st.sidebar.text_input("Password", type="password")
# Default password 1234 hai, baad me Secrets me change kar dena
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "1234") 

if pwd != APP_PASSWORD:
    st.sidebar.warning("Password dalo")
    st.title("Trial Balance - CO 1")
    st.info("Login karo sidebar se - Default password: 1234")
    st.stop()

st.sidebar.success("Logged In ✅")

# --- SUPABASE CONNECT ---
try:
    URL = st.secrets["https://lpojxxjtworbuwtuphsl.supabase.co"]
    KEY = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxwb2p4eGp0d29yYnV3dHVwaHNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIyODQxMDgsImV4cCI6MjA5Nzg2MDEwOH0.i_VvEshWkYjBrzsQewDUZ0c_EseFP3x7xmuAWF7Ri2I"]
except Exception:
    st.error("Secrets me SUPABASE_URL aur SUPABASE_KEY dalna hai")
    st.code('''
SUPABASE_URL = "url line"
SUPABASE_KEY = "api anon key long line"
APP_PASSWORD = "1234"
    ''')
    st.stop()

supabase = create_client(URL, KEY)

st.title("📊 Trial Balance - Company 1")
st.caption("Gen (A=Cashbook, B=JV) + General | CO=1 | Live from Supabase")

@st.cache_data(ttl=60)
def load_data():
    res = supabase.table("trial_balance_co1").select("*").order("acc_code").execute()
    return pd.DataFrame(res.data)

with st.spinner("Data load ho raha hai..."):
    df = load_data()

if df.empty:
    st.warning("No data in trial_balance_co1 view - Pehle SQL View banao")
    st.stop()

# --- SEARCH ---
search = st.text_input("🔍 Account Code Search", "")
if search:
    df_filtered = df[df["acc_code"].astype(str).str.contains(search, case=False, na=False)]
else:
    df_filtered = df

# --- TOTALS ---
col1, col2, col3, col4 = st.columns(4)
total_debit = df_filtered["debit"].astype(float).sum()
total_credit = df_filtered["credit"].astype(float).sum()
# balance = df_filtered["balance"].astype(float).sum()
balance = total_debit - total_credit 


col1.metric("Total Debit", f"{total_debit:,.2f}")
col2.metric("Total Credit", f"{total_credit:,.2f}")
col3.metric("Diff", f"{balance:,.2f}")
col4.metric("Accounts", len(df_filtered))

# --- TABLE ---
st.dataframe(
    df_filtered.style.format({"total_debit":"{:,.2f}", "total_credit":"{:,.2f}", "balance":"{:,.2f}"}),
    use_container_width=True,
    height=600
)

# --- DOWNLOAD ---
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

st.download_button(
    "📥 Excel/CSV Download",
    convert_df(df_filtered),
    "trial_balance_co1.csv",
    "text/csv"
)
