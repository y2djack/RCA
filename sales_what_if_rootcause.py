import pandas as pd
import streamlit as st

# --- Loading Data --- 
@st.cache_data
def load_data():
    return pd.read_csv("E:/whatif/sales_data.csv")

df = load_data()

st.title("🔍 KPI Dependency & Root Cause Analyzer")

# --- Select Filters in Sidebar --- 
st.sidebar.header("📌 Select Filters")

# 1. Select DSM first
dsm_list = sorted(df['DSM'].dropna().unique()) 
selected_dsm = st.sidebar.selectbox("Select DSM", ["All DSMs"] + dsm_list)

# 2. All ASE filter immediately after dsm
if selected_dsm == "All DSMs":
    ase_list = sorted(df['ASE'].dropna().unique()) 
else:
    ase_df = df[df['DSM'] == selected_dsm]
    ase_list = sorted(ase_df['ASE'].dropna().unique()) 
selected_ase = st.sidebar.selectbox("Select ASE", ["All ASEs"] + ase_list)

# 3. Territory should appear only if a specific ASE is selected
if selected_ase != "All ASEs":
    territory_df = df[(df['DSM'] == selected_dsm) & (df['ASE'] == selected_ase)]

    territory_list = sorted(territory_df['SO_Territory'].dropna().unique()) 
    selected_territory = st.sidebar.selectbox("Select Territory", ["All Territories"] + territory_list)
elif selected_dsm != "All DSMs":
    territory_df = df[df['DSM'] == selected_dsm]
    territory_list = sorted(territory_df['SO_Territory'].dropna().unique()) 
    selected_territory = st.sidebar.selectbox("Select Territory", ["All Territories"] + territory_list)
else:
    territory_list = sorted(df['SO_Territory'].dropna().unique()) 
    selected_territory = st.sidebar.selectbox("Select Territory", ["All Territories"] + territory_list)

# --- Apply Filters --- 
filtered_df = df.copy()

if selected_dsm != "All DSMs":
    filtered_df = filtered_df[filtered_df['DSM'] == selected_dsm]

if selected_ase != "All ASEs":
    filtered_df = filtered_df[filtered_df['ASE'] == selected_ase]

if selected_territory != "All Territories":
    filtered_df = filtered_df[filtered_df['SO_Territory'] == selected_territory]

if filtered_df.empty:
    st.error("No data found for your selection.")
    st.stop()

# --- Summary Cards --- 
total_manpower_plan = int(filtered_df["Manpower Plan"].sum()) if "Manpower Plan" in filtered_df else 0
vacant_positions = total_manpower_plan - int(filtered_df["Manpower Actual"].sum()) if "Manpower Actual" in filtered_df else 0
total_secondary = float(filtered_df["Secondary INR Actual"].sum()) if "Secondary INR Actual" in filtered_df else 0

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Manpower (Plan)", total_manpower_plan)

with col2:
    st.metric("Vacant Positions", vacant_positions)

with col3:
    st.metric("Secondary Billing (₹)", f"{total_secondary:.2f}L")

st.markdown("---")

# --- Actual Values --- 
def sum_or_zero(col): 
    return filtered_df[col].sum() if col in filtered_df else 0.0

mp_actual = sum_or_zero("Manpower Actual")
mandays_actual = sum_or_zero("Mandays Actual")
routes_actual = sum_or_zero("Unique Routes Actual")
callage_actual = sum_or_zero("Unique Callage Actual")
prod_actual = sum_or_zero("Productivity Actual")
sec_actual = sum_or_zero("Secondary INR Actual")
ubo_actual = sum_or_zero("UBO Actual")
uls_retailer = sum_or_zero("ULS Retailer")
uls_db = sum_or_zero("ULS DB")
tp_per_outlet = filtered_df["TP per Outlet Actual"].mean() if "TP per Outlet Actual" in filtered_df else 0.0

lines_per_outlet_actual = uls_retailer / ubo_actual if ubo_actual > 0 else 0
lines_per_db_actual = uls_db / ubo_actual if ubo_actual > 0 else 0
lines_per_average = (lines_per_outlet_actual + lines_per_db_actual) / 2

# --- Plan Values --- 
mp_plan = sum_or_zero("Manpower Plan")
mandays_plan = mp_plan * 24
routes_plan = sum_or_zero("Unique Routes Plan")
callage_plan = routes_plan * 40
prod_plan = callage_plan * 0.8
sec_plan = sum_or_zero("Secondary INR Plan")
uls_db_plan = lines_per_db_actual if ubo_actual > 0 else 0
lines_per_outlet_plan = uls_db_plan * 0.8
lines_per_average_plan = (lines_per_outlet_plan + uls_db_plan) / 2
tp_per_outlet_plan = filtered_df["TP per Outlet Plan"].mean() if "TP per Outlet Plan" in filtered_df else 0.0
ubo_plan = sum_or_zero("UBO Plan") if "UBO Plan" in df else 0

# --- Evaluation Flags --- 
def is_good(actual, plan, threshold=0.9):
    return actual >= threshold * plan if plan != 0 else False

flags = {
    "callage": is_good(callage_actual, callage_plan),
    "routes": is_good(routes_actual, routes_plan),
    "productivity": is_good(prod_actual, prod_plan),
    "lines": is_good(lines_per_average, lines_per_average_plan),
    "tp": is_good(tp_per_outlet, tp_per_outlet_plan),
    "secondary": is_good(sec_actual, sec_plan),
    "manday": (mandays_actual >= mp_plan * 24) if mp_plan > 0 else False
}

# --- Main Layout --- 
col1, col2 = st.columns([2, 1])

with col1:
    # --- Dependency Flow --- 
    st.subheader("🧠 Dependency Flow Analysis")
    if flags['callage']:
        st.success("✅ Unique Callage is OK")
        if flags['productivity']:
            st.success("✅ Productivity is OK")
            if flags['secondary']:
                st.success("✅ Secondary is OK ➝ Expected Primary to Perform")
            else:
                st.warning("⚠ Productivity is OK but Secondary is lacking.")
                if flags['lines']:
                    st.info("🔍 Lines per Outlet is OK — Check Product Mix.")
                else:
                    st.error("❌ Lines per Outlet under Threshold.")
        else:
            st.warning("⚠ Callage is OK but Productivity is not.")
    else:
        st.error("❌ Unique Callage is below Threshold.")
        if flags['routes']:
            st.info("📍 Routes are OK — Issue in Callage.")
        elif flags['manday']:
            st.info("📍 Mandays fully utilized — May be poor execution.")
        else:
            st.error("❌ Check Mandays or Manpower Deployment.")
            

    st.markdown("---")

    if flags['lines']:
        st.success("✅ Lines per Outlet is OK.")
        if flags['tp']:
            st.success("✅ TP per Outlet is OK.")
            st.info("➥ Few lines with high price or many lines with reasonable price.")
            if flags['secondary']:
                st.success("✅ Secondary is Good — Primary should follow.")
            else:
                st.warning("⚠ TP OK but Secondary is weak.")
        else:
            st.warning("⚠ TP per Outlet is weak.")
            st.info("➥ They billed many lines but total value is low.")
    elif not flags['lines']:
        st.error("❌ Lines per Outlet under Threshold.")
        if flags['tp']:
            st.success("✅ TP per Outlet is OK.")
            st.info("➥ Few lines with high price — total is reasonable.")
        else:
            st.error("❌ TP per Outlet is weak.")
            st.info("➥ Few lines and low price — weak selling.")
            

    st.markdown("-----------------")
    st.subheader("📊 KPI Performance Overview")
    kpis = [
        ("Manpower", mp_actual, mp_plan),
        ("Mandays", mandays_actual, mandays_plan),
        ("Unique Routes", routes_actual, routes_plan),
        ("Unique Callage", callage_actual, callage_plan),
        ("Productivity", prod_actual, prod_plan),
        ("UBO", ubo_actual, ubo_plan),
        ("Lines per Outlet", lines_per_average, lines_per_average_plan),
        ("Lines per DB", lines_per_db_actual, lines_per_outlet_plan),
        ("TP per Outlet", tp_per_outlet, tp_per_outlet_plan),
        ("Secondary INR", sec_actual, sec_plan),
    ]

    summary_df = pd.DataFrame(kpis, columns=['Metric', 'Actual', 'Plan'])
    summary_df["% Achieved"] = (summary_df["Actual"] / summary_df["Plan"] * 100).round(2).astype(str) + "%"

    st.dataframe(summary_df, use_container_width=True)

with col2:
    st.markdown("<h2 style='text-align: center;'>🏅 Top Performers and Bottom Performers</h2>", unsafe_allow_html=True)

    ase_stats = df.groupby("ASE")["Secondary INR Actual"].sum()
    territory_stats = df.groupby("SO_Territory")["Secondary INR Actual"].sum()

    top_1_ase = ase_stats.sort_values(ascending=False).head(1).reset_index()
    bottom_3_ase = ase_stats.sort_values(ascending=False).tail(3).reset_index()

    top_1_territory = territory_stats.sort_values(ascending=False).head(1).reset_index()
    bottom_3_territory = territory_stats.sort_values(ascending=False).tail(3).reset_index()

    st.markdown("<h4 style='text-align: center;'>Top 1 ASE</h4>", unsafe_allow_html=True)
    st.dataframe(top_1_ase, use_container_width=True)

    st.markdown("<h4 style='text-align: center;'>Bottom 3 ASE</h4>", unsafe_allow_html=True)
    st.dataframe(bottom_3_ase, use_container_width=True)

    st.markdown("<h4 style='text-align: center;'>Top Territory</h4>", unsafe_allow_html=True)
    st.dataframe(top_1_territory, use_container_width=True)

    st.markdown("<h4 style='text-align: center;'>Bottom 3 Territory</h4>", unsafe_allow_html=True)
    st.dataframe(bottom_3_territory, use_container_width=True)