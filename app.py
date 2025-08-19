import streamlit as st
import pandas as pd
import random
import numpy as np

# --- Configuration ---
# The app will look for this file in the same directory.
DATA_FILE = "16 July, 2024.xlsx"

@st.cache_data
def load_data(file_path):
    """Loads data from a local Excel file and caches it."""
    try:
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

def classify_lcvs_equally(lcv_ids, seed=None):
    """
    Classifies a list of LCV IDs into three stages as equally as possible.
    Uses a seed for reproducible randomness for a given date.
    """
    stages = ['Empty - Waiting Area', 'Filling – Safe Zone', 'Filled – Waiting Area/Moving to DBS']
    classification = {}
    
    unique_lcvs = [lcv for lcv in lcv_ids.unique() if pd.notna(lcv)]
    
    if seed is not None:
        random.seed(seed)
    random.shuffle(unique_lcvs)
    
    lcv_splits = np.array_split(unique_lcvs, 3)
    
    for i, stage in enumerate(stages):
        for lcv_id in lcv_splits[i]:
            classification[lcv_id] = stage
            
    return classification

def allocate_lcv_to_route(selected_data, available_lcvs_in_stage, all_lcv_stages_classification, selected_stage_name):
    """
    Allocates LCVs with primary and secondary logic.
    Primary: Allocates from selected stage to longest duration routes.
    Secondary: If > 7 requests, re-allocates LCVs from other stages to shortest unassigned routes.
    """
    # --- Primary Allocation ---
    sorted_routes_desc = selected_data.sort_values(by='Duration', ascending=False)
    lcvs_to_allocate = list(available_lcvs_in_stage)
    allocations = []

    for index, route in sorted_routes_desc.iterrows():
        allocation_info = {
            'request_id': route['Request_id'],
            'Route_id': route['Route_id'],
            'DBS': route['DBS'],
            'Distance': route['Distance'],
            'Duration': route['Duration'],
            'Allocated_LCV': None,
            'Comment': ''
        }
        if lcvs_to_allocate:
            allocation_info['Allocated_LCV'] = lcvs_to_allocate.pop(0)
        else:
            allocation_info['Allocated_LCV'] = 'Pending Re-allocation'
        
        allocations.append(allocation_info)

    # --- Secondary Allocation (Constraint Logic) ---
    if len(selected_data) > 7:
        # Find routes that need re-allocation
        unassigned_routes = [alloc for alloc in allocations if alloc['Allocated_LCV'] == 'Pending Re-allocation']
        
        if unassigned_routes:
            # Find available LCVs from other stages
            primary_assigned_lcvs = [alloc['Allocated_LCV'] for alloc in allocations if alloc['Allocated_LCV'] is not None and alloc['Allocated_LCV'] != 'Pending Re-allocation']
            
            lcvs_from_other_stages = []
            for lcv, stage in all_lcv_stages_classification.items():
                # Check if the stage is not the selected one and the LCV is not already used
                if stage != selected_stage_name and lcv not in primary_assigned_lcvs:
                    lcvs_from_other_stages.append(lcv)

            # Sort unassigned routes by LEAST duration
            unassigned_routes_sorted_asc = sorted(unassigned_routes, key=lambda x: x['Duration'])

            for route_to_reassign in unassigned_routes_sorted_asc:
                if lcvs_from_other_stages:
                    reallocated_lcv = lcvs_from_other_stages.pop(0)
                    # Find the original allocation record and update it
                    for original_alloc in allocations:
                        if original_alloc['request_id'] == route_to_reassign['request_id']:
                            original_alloc['Allocated_LCV'] = reallocated_lcv
                            original_alloc['Comment'] = 'Re-allocated from another stage'
                            break
    
    # Final cleanup of any remaining unassigned routes
    for alloc in allocations:
        if alloc['Allocated_LCV'] == 'Pending Re-allocation':
            alloc['Allocated_LCV'] = 'No LCV Available'

    return pd.DataFrame(allocations)

# --- App Layout ---
st.set_page_config(layout="wide")
st.title('🚚 LCV Route Allocation Dashboard')

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

    # --- LCV Classification (in the background) ---
    all_lcvs = df['lcv_id']
    date_seed = selected_date.toordinal()
    lcv_stages_classification = classify_lcvs_equally(all_lcvs, seed=date_seed)
    
    stage1_lcvs = [lcv for lcv, stage in lcv_stages_classification.items() if stage == 'Empty - Waiting Area']
    stage2_lcvs = [lcv for lcv, stage in lcv_stages_classification.items() if stage == 'Filling – Safe Zone']
    stage3_lcvs = [lcv for lcv, stage in lcv_stages_classification.items() if stage == 'Filled – Waiting Area/Moving to DBS']
    
    # --- Display Selected Request Details & Get Stage Input ---
    if selected_request_ids:
        st.header("Selected Route Details")
        selected_data = df_filtered_mgs[df_filtered_mgs['Request_id'].isin(selected_request_ids)]
        
        display_columns = ['Request_id', 'DBS', 'Route_id', 'Distance', 'Duration', 'create_date', 'update_date']
        st.dataframe(selected_data[display_columns].reset_index(drop=True))

        st.header("Allocation Options")
        
        stage_options = {
            "Stage 1: Empty - Waiting Area": stage1_lcvs,
            "Stage 2: Filling – Safe Zone": stage2_lcvs,
            "Stage 3: Filled – Waiting Area/Moving to DBS": stage3_lcvs
        }
        selected_stage_name = st.selectbox(
            'Select a Stage to allocate LCVs from',
            options=list(stage_options.keys())
        )
        
        available_lcvs_for_stage = stage_options[selected_stage_name]
        st.write(f"**LCVs available in {selected_stage_name}:**")
        st.write(available_lcvs_for_stage)

        # --- Allocation Logic ---
        if st.button('Allocate LCVs to Selected Routes', key='allocate_button'):
            st.header("Optimal LCV Allocation")
            
            if len(selected_request_ids) > 7:
                st.warning("More than 7 requests selected. Applying secondary allocation logic for unassigned routes.")

            allocation_result = allocate_lcv_to_route(
                selected_data, 
                available_lcvs_for_stage,
                lcv_stages_classification,
                selected_stage_name
            )
            
            if not allocation_result.empty:
                st.dataframe(allocation_result)
