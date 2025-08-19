import streamlit as st
import pandas as pd
import random

# --- Configuration ---
# The app will look for this file in the same directory.
# Updated to the original Excel file name.
DATA_FILE = "16 July, 2024.xlsx"

@st.cache_data
def load_data(file_path):
    """Loads data from a local Excel file and caches it."""
    try:
        # Changed from pd.read_csv to pd.read_excel
        df = pd.read_excel(file_path)
        # --- Data Preprocessing ---
        df['create_date'] = pd.to_datetime(df['create_date'])
        df['update_date'] = pd.to_datetime(df['update_date'])
        df['date_only'] = df['create_date'].dt.date
        return df
    except FileNotFoundError:
        st.error(f"Error: The data file '{file_path}' was not found.")
        st.warning("Please make sure the Excel file is in the same GitHub repository as the app.py file.")
        return None
    except Exception as e:
        st.error(f"An error occurred while loading the data: {e}")
        return None

def classify_lcvs(lcv_ids):
    """
    Classifies a list of LCV IDs into three stages.
    For demonstration, this function randomly assigns stages.
    """
    stages = ['Empty - Waiting Area', 'Filling – Safe Zone', 'Filled – Waiting Area/Moving to DBS']
    classification = {}
    # Ensure lcv_ids is a list of unique, non-null values
    unique_lcvs = [lcv for lcv in lcv_ids.unique() if pd.notna(lcv)]
    for lcv_id in unique_lcvs:
        classification[lcv_id] = random.choice(stages)
    return classification

def allocate_lcv_to_route(selected_data, lcv_stages):
    """
    Allocates the most optimal LCV to a route, prioritizing the route
    with the maximum duration.
    """
    sorted_routes = selected_data.sort_values(by='Duration', ascending=False)
    available_lcvs = list(lcv_stages.keys())
    allocated_lcvs = []
    allocations = []

    if not available_lcvs:
        st.warning("No LCVs available for allocation.")
        return pd.DataFrame()

    for index, route in sorted_routes.iterrows():
        optimal_lcv = next((lcv for lcv in available_lcvs if lcv not in allocated_lcvs), None)
        
        if optimal_lcv:
            allocations.append({
                'request_id': route['Request_id'],
                'Route_id': route['Route_id'],
                'DBS': route['DBS'],
                'Distance': route['Distance'],
                'Duration': route['Duration'],
                'Allocated_LCV': optimal_lcv,
                'LCV_Stage': lcv_stages[optimal_lcv]
            })
            allocated_lcvs.append(optimal_lcv)
        else:
            allocations.append({
                'request_id': route['Request_id'],
                'Route_id': route['Route_id'],
                'DBS': route['DBS'],
                'Distance': route['Distance'],
                'Duration': route['Duration'],
                'Allocated_LCV': 'No LCV Available',
                'LCV_Stage': 'N/A'
            })
            
    return pd.DataFrame(allocations)

# --- App Layout ---
st.set_page_config(layout="wide")
st.title('🚚 LCV Route Allocation Dashboard')

# Load the data from the local file
df = load_data(DATA_FILE)

if df is not None:
    st.sidebar.header('Filter Options')

    # --- User Inputs in Sidebar ---
    unique_dates = sorted(df['date_only'].unique())
    selected_date = st.sidebar.selectbox('Select Date', options=unique_dates)

    df_filtered_date = df[df['date_only'] == selected_date]

    unique_mgs = df_filtered_date['MGS'].unique()
    selected_mgs = st.sidebar.multiselect('Select MGS', options=unique_mgs, default=list(unique_mgs))

    df_filtered_mgs = df_filtered_date[df_filtered_date['MGS'].isin(selected_mgs)]

    unique_request_ids = df_filtered_mgs['Request_id'].unique()
    selected_request_ids = st.multiselect('Select Request IDs to Allocate', options=unique_request_ids)

    # --- LCV Classification ---
    st.header("LCV Status Overview")
    all_lcvs = df['lcv_id']
    lcv_stages = classify_lcvs(all_lcvs)
    
    col1, col2, col3 = st.columns(3)
    stages_map = {
        "Stage 1: Empty - Waiting Area": [lcv for lcv, stage in lcv_stages.items() if stage == 'Empty - Waiting Area'],
        "Stage 2: Filling – Safe Zone": [lcv for lcv, stage in lcv_stages.items() if stage == 'Filling – Safe Zone'],
        "Stage 3: Filled – Waiting Area/Moving to DBS": [lcv for lcv, stage in lcv_stages.items() if stage == 'Filled – Waiting Area/Moving to DBS']
    }
    
    with col1:
        st.info("**Stage 1: Empty - Waiting Area**")
        st.write(stages_map["Stage 1: Empty - Waiting Area"])
    with col2:
        st.warning("**Stage 2: Filling – Safe Zone**")
        st.write(stages_map["Stage 2: Filling – Safe Zone"])
    with col3:
        st.success("**Stage 3: Filled – Waiting Area/Moving to DBS**")
        st.write(stages_map["Stage 3: Filled – Waiting Area/Moving to DBS"])
    
    # --- Display Selected Request Details ---
    if selected_request_ids:
        st.header("Selected Route Details")
        selected_data = df_filtered_mgs[df_filtered_mgs['Request_id'].isin(selected_request_ids)]
        
        display_columns = ['Request_id', 'DBS', 'Route_id', 'Distance', 'Duration', 'create_date', 'update_date']
        st.dataframe(selected_data[display_columns].reset_index(drop=True))

        # --- Allocation Logic ---
        if st.button('Allocate LCVs to Selected Routes', key='allocate_button'):
            st.header("Optimal LCV Allocation")
            allocation_result = allocate_lcv_to_route(selected_data, lcv_stages)
            
            if not allocation_result.empty:
                st.write("Allocation based on prioritizing the longest duration route.")
                st.dataframe(allocation_result)
            else:
                st.warning("Could not generate allocations.")
