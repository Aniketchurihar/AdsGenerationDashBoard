import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import tempfile
import shutil
import glob
from datetime import datetime
from ads_analysis_complete import analyze_ads_data_complete
import re

def safe_int_convert(value, default=999):
    """Safely convert value to integer, handling floats and strings"""
    try:
        if pd.isna(value) or value is None or str(value).strip() == '':
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

def clear_output_folders():
    """Clear all output folders from previous runs"""
    try:
        output_dir = "output"
        if os.path.exists(output_dir):
            # Get all subdirectories in output folder
            folders_to_remove = glob.glob(os.path.join(output_dir, "*"))
            folders_removed = 0
            
            for folder_path in folders_to_remove:
                if os.path.isdir(folder_path):
                    shutil.rmtree(folder_path)
                    folders_removed += 1
                elif os.path.isfile(folder_path):
                    os.remove(folder_path)
                    folders_removed += 1
            
            if folders_removed > 0:
                st.toast(f"🗑️ Cleared {folders_removed} output folders/files!", icon="✅")
            else:
                st.toast("📁 No output folders to clear", icon="ℹ️")
        else:
            st.toast("📁 No output directory found", icon="ℹ️")
    except Exception as e:
        st.toast(f"❌ Error clearing folders: {str(e)}", icon="🚨")

# Page configuration
st.set_page_config(
    page_title="Ads Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #2c3e50;
        margin: 1rem 0;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.5rem;
    }
    .metric-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #007bff;
        margin: 0.5rem 0;
    }
    
    /* Dark theme support */
    .stApp[data-theme="dark"] .main-header {
        color: #58a6ff;
    }
    .stApp[data-theme="dark"] .section-header {
        color: #f0f6fc;
        border-bottom-color: #58a6ff;
    }
    .stApp[data-theme="dark"] .metric-container {
        background-color: #21262d;
        border-left-color: #58a6ff;
    }
</style>
""", unsafe_allow_html=True)



def parse_source_info(source_name):
    """Parse source name to extract model and prompt information"""
    if pd.isna(source_name) or source_name == '':
        return 'Unknown', 'Unknown', source_name, 999
    
    source_str = str(source_name)
    
    # Check if it's a model-based source
    if 'Model:' in source_str and 'Prompt' in source_str:
        try:
            # Extract model name
            model_part = source_str.split('Model:')[1].split('.')[0].strip()
            model_name = model_part.replace('openai:', '').replace('gpt-4o-2024-11-20', 'GPT-4o')
            
            # Extract prompt number for ordering
            if 'Prompt #' in source_str:
                prompt_part = source_str.split('Prompt #')[1].split('.')[0].strip()
                prompt_name = f"Prompt #{prompt_part}"
                try:
                    prompt_order = safe_int_convert(prompt_part, 999)
                except:
                    prompt_order = 999
            else:
                prompt_name = 'Unknown Prompt'
                prompt_order = 999
            
            return model_name, prompt_name, source_str, prompt_order
        except:
            return 'Model-based', 'Unknown', source_str, 999
    else:
        # Non-model sources (like default_asset)
        return 'Other', source_str, source_str, 0

def enhance_analysis_with_parsed_sources(analysis_results):
    """Enhance analysis results with parsed source information"""
    
    # Parse source information for source analysis
    if 'source_analysis' in analysis_results:
        source_df = analysis_results['source_analysis'].copy()
        
        # Parse source names
        parsed_info = source_df['Source'].apply(parse_source_info)
        source_df['Model'] = [info[0] for info in parsed_info]
        source_df['Prompt'] = [info[1] for info in parsed_info]
        source_df['Prompt_Order'] = [info[3] for info in parsed_info]
        source_df['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
        
        # Sort by prompt order for consistent display
        source_df = source_df.sort_values('Prompt_Order')
        
        analysis_results['source_analysis_enhanced'] = source_df
    
    # Parse for source + asset type analysis
    if 'source_asset_analysis' in analysis_results:
        source_asset_df = analysis_results['source_asset_analysis'].copy()
        
        parsed_info = source_asset_df['Source'].apply(parse_source_info)
        source_asset_df['Model'] = [info[0] for info in parsed_info]
        source_asset_df['Prompt'] = [info[1] for info in parsed_info]
        source_asset_df['Prompt_Order'] = [info[3] for info in parsed_info]
        source_asset_df['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
        
        # Sort by prompt order
        source_asset_df = source_asset_df.sort_values('Prompt_Order')
        
        analysis_results['source_asset_analysis_enhanced'] = source_asset_df
    
    # Parse for detailed analysis
    if 'detailed_analysis' in analysis_results:
        detailed_df = analysis_results['detailed_analysis'].copy()
        
        parsed_info = detailed_df['Source'].apply(parse_source_info)
        detailed_df['Model'] = [info[0] for info in parsed_info]
        detailed_df['Prompt'] = [info[1] for info in parsed_info]
        detailed_df['Prompt_Order'] = [info[3] for info in parsed_info]
        detailed_df['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
        
        # Sort by prompt order
        detailed_df = detailed_df.sort_values('Prompt_Order')
        
        analysis_results['detailed_analysis_enhanced'] = detailed_df
    
    return analysis_results



def club_similar_errors(error_reasons_df):
    """Club similar errors together by replacing numbers/variables with placeholders"""
    if len(error_reasons_df) == 0:
        return error_reasons_df
    
    clubbed_errors = []
    
    for _, row in error_reasons_df.iterrows():
        error_text = str(row['ReasonForError'])
        count = row['Count']
        percentage = row['Percentage']
        
        # Club similar errors by replacing numbers and specific words
        clubbed_text = error_text
        
        import re
        
        # Replace headline/description numbers
        clubbed_text = re.sub(r'Headline\d+', 'Headline X', clubbed_text)
        clubbed_text = re.sub(r'Description\d+', 'Description X', clubbed_text)
        
        # Replace specific words in quotes with placeholder
        clubbed_text = re.sub(r"'[^']*'", "'Y'", clubbed_text)
        
        # Replace specific forbidden phrases/words with X
        clubbed_text = re.sub(r'forbidden phrase: [^.]+\.', 'forbidden phrase: X.', clubbed_text)
        clubbed_text = re.sub(r'non compliant words: [^.]+\.', 'non compliant words: X.', clubbed_text)
        
        # Replace size/length numbers
        clubbed_text = re.sub(r'more than \d+', 'more than X', clubbed_text)
        clubbed_text = re.sub(r'less than \d+', 'less than X', clubbed_text)
        
        # Replace other common patterns
        clubbed_text = re.sub(r'\d+', 'X', clubbed_text)
        
        # Additional specific patterns
        clubbed_text = re.sub(r'must be an unique asset', 'must be an unique asset', clubbed_text)
        clubbed_text = re.sub(r'must not start with the same CTA', 'must not start with the same CTA', clubbed_text)
        
        clubbed_errors.append({
            'Original_Error': error_text,
            'Clubbed_Error': clubbed_text,
            'Count': count,
            'Percentage': percentage
        })
    
    # Group by clubbed error
    clubbed_df = pd.DataFrame(clubbed_errors)
    grouped = clubbed_df.groupby('Clubbed_Error').agg({
        'Count': 'sum',
        'Percentage': 'sum',
        'Original_Error': list
    }).reset_index()
    
    # Fix percentage calculation for clubbed errors
    total_count = grouped['Count'].sum()
    grouped['Percentage'] = grouped['Count'].apply(
        lambda x: max(0.1, round(x / total_count * 100, 2)) if x > 0 else 0.0
    )
    
    # Sort by count
    grouped = grouped.sort_values('Count', ascending=False)
    
    return grouped

def categorize_error_reasons(error_reasons_df):
    """Categorize error reasons into meaningful groups"""
    if error_reasons_df is None or len(error_reasons_df) == 0:
        return None, {}
    
    # Check which column contains the error reasons
    reason_column = None
    if 'ReasonForError' in error_reasons_df.columns:
        reason_column = 'ReasonForError'
    elif 'Error Reason' in error_reasons_df.columns:
        reason_column = 'Error Reason'
    else:
        # Try to find any column that might contain error reasons
        for col in error_reasons_df.columns:
            if 'reason' in col.lower() or 'error' in col.lower():
                reason_column = col
                break
    
    if reason_column is None:
        return None, {}
    
    # Define error categories with keywords
    categories = {
        'Forbidden Words/Phrases': [
            'forbidden phrase', 'forbidden word', 'non compliant words', 
            'help', 'advice', 'medical', 'health', 'diagnosis'
        ],
        'Length Issues': [
            'too long', 'too short', 'character limit', 'exceeds', 'length'
        ],
        'Content Policy': [
            'policy', 'compliance', 'guideline', 'violation', 'restricted'
        ],
        'Grammar/Format': [
            'grammar', 'punctuation', 'format', 'capitalization', 'spelling'
        ],
        'Duplicate Content': [
            'duplicate', 'similar', 'repetitive', 'already exists'
        ],
        'Technical Issues': [
            'technical', 'system', 'processing', 'timeout', 'error'
        ]
    }
    
    # Create categorized data and detailed mapping
    categorized_data = []
    category_details = {}
    
    for category, keywords in categories.items():
        category_count = 0
        category_percentage = 0
        category_errors = []
        
        for _, row in error_reasons_df.iterrows():
            reason = str(row[reason_column]).lower()
            if any(keyword in reason for keyword in keywords):
                category_count += row['Count']
                category_percentage += row['Percentage']
                category_errors.append({
                    'Error Reason': row[reason_column],
                    'Count': row['Count'],
                    'Percentage': row['Percentage']
                })
        
        if category_count > 0:
            categorized_data.append({
                'Category': category,
                'Count': category_count,
                'Percentage': round(category_percentage, 2)
            })
            category_details[category] = pd.DataFrame(category_errors).sort_values('Count', ascending=False)
    
    # Add "Other" category for uncategorized errors
    total_categorized = sum(item['Count'] for item in categorized_data)
    total_errors = error_reasons_df['Count'].sum()
    other_count = total_errors - total_categorized
    
    if other_count > 0:
        other_percentage = round((other_count / total_errors * 100), 2)
        categorized_data.append({
            'Category': 'Other',
            'Count': other_count,
            'Percentage': other_percentage
        })
        
        # Find uncategorized errors
        categorized_reasons = set()
        for details in category_details.values():
            categorized_reasons.update(details['Error Reason'].tolist())
        
        other_errors = []
        for _, row in error_reasons_df.iterrows():
            if row[reason_column] not in categorized_reasons:
                other_errors.append({
                    'Error Reason': row[reason_column],
                    'Count': row['Count'],
                    'Percentage': row['Percentage']
                })
        
        if other_errors:
            category_details['Other'] = pd.DataFrame(other_errors).sort_values('Count', ascending=False)
    
    return pd.DataFrame(categorized_data).sort_values('Count', ascending=False), category_details

def analyze_errors_from_ads_generation(combined_df):
    """Analyze errors based on ErrorsFromAdsGeneration column"""
    
    # Split data based on ErrorsFromAdsGeneration
    ads_gen_errors = combined_df[combined_df['ErrorFromAdsGeneration'] == 'Yes']
    ads_review_errors = combined_df[combined_df['ErrorFromAdsGeneration'] == 'No']
    
    analysis = {
        'ads_generation': {
            'total': len(ads_gen_errors),
            'by_source': ads_gen_errors['Source'].value_counts().reset_index() if len(ads_gen_errors) > 0 else pd.DataFrame(),
            'by_asset_type': ads_gen_errors['AssetType'].value_counts().reset_index() if len(ads_gen_errors) > 0 else pd.DataFrame()
        },
        'ads_review': {
            'total': len(ads_review_errors),
            'by_source': ads_review_errors['Source'].value_counts().reset_index() if len(ads_review_errors) > 0 else pd.DataFrame(),
            'by_asset_type': ads_review_errors['AssetType'].value_counts().reset_index() if len(ads_review_errors) > 0 else pd.DataFrame()
        }
    }
    
    # Fix column names
    for key in ['ads_generation', 'ads_review']:
        if len(analysis[key]['by_source']) > 0:
            analysis[key]['by_source'].columns = ['Source', 'Count']
        if len(analysis[key]['by_asset_type']) > 0:
            analysis[key]['by_asset_type'].columns = ['Asset Type', 'Count']
    
    return analysis

def main():
    st.markdown('<h1 class="main-header">📊 Ads Analysis Dashboard</h1>', unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("📁 Upload & Settings")
        
        # Clear output folders option
        st.subheader("🎛️ Settings")
        if st.button("🗑️ Clear Output Folders", help="Remove all previous analysis output folders"):
            clear_output_folders()
        
        st.markdown("---")
        
        uploaded_file = st.file_uploader(
            "Choose your Excel file",
            type=['xlsx', 'xls'],
            help="Upload an Excel file with 'Results', 'Errors', and optionally 'Prompts' tabs"
        )
        
        if uploaded_file is not None:
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            
    # Main content area
    if uploaded_file is not None:
        # Process the uploaded file
        with st.spinner("🔄 Processing your file..."):
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                temp_path = tmp_file.name
            
            try:
                # Run analysis
                analysis_results, timestamp = analyze_ads_data_complete(temp_path, "output")
                
                if analysis_results is None:
                    st.error("❌ Error processing the file. Please check the file format.")
                    return
                
                # Read raw data for additional analysis
                results_df = pd.read_excel(temp_path, sheet_name='Results')
                errors_df = pd.read_excel(temp_path, sheet_name='Errors')
                
                # Try to read Prompts tab (optional)
                prompts_config = None
                try:
                    prompts_config = pd.read_excel(temp_path, sheet_name='Prompts')
                except:
                    pass  # Prompts tab is optional
                
                # Combine for ErrorsFromAdsGeneration analysis
                results_df['DataSource'] = 'Results'
                errors_df['DataSource'] = 'Errors'
                common_columns = list(set(results_df.columns) & set(errors_df.columns))
                combined_df = pd.concat([results_df[common_columns], errors_df[common_columns]], ignore_index=True)
                
                # Keep the full errors dataframe for error analysis (includes ReasonForError)
                full_errors_df = errors_df.copy()
                
                # Clean up temp file
                os.unlink(temp_path)
                
                # Show brief success notification
                if 'last_file_processed' not in st.session_state or st.session_state.last_file_processed != uploaded_file.name:
                    st.session_state.last_file_processed = uploaded_file.name
                    st.toast("✅ Analysis completed successfully!", icon="🎉")
                
                # Enhance analysis with parsed source information
                analysis_results = enhance_analysis_with_parsed_sources(analysis_results)
                
                # Display analysis with tabs
                display_tabbed_analysis(analysis_results, combined_df, full_errors_df)
                
            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
    else:
        st.markdown("""
        ## 🚀 Welcome to the Ads Analysis Dashboard!
        
        ### 🎯 **Key Features:**
        - **Performance Overview** - Key metrics and success rates
        - **Source Analysis** - Performance breakdown by source
        - **Ad Group Focus** - Detailed ad group performance analysis
        - **Error Categorization** - Smart grouping of error reasons
        - **Error Analysis** - Ads Generation vs Review errors
        
        ### 📋 **Requirements:**
        - Excel file with **'Results'** and **'Errors'** tabs
        - Optional **'Prompts'** tab for prompts analysis
        - Required columns: AccountID, CampaignName, AdGroups, AssetType, Asset, Source, ErrorFromAdsGeneration
        - Errors tab also needs: ReasonForError
        - Prompts tab should include: MaximumNumberOfAdsToGeneratePerPrompt, MaximumNumberOfDescriptionsToGeneratePerPrompt, NumberOfHeadlinesPerPrompt, NumberOfDescriptionsPerPrompt
        
        ---
        **📤 Upload your Excel file to begin!**
        """)

def display_tabbed_analysis(analysis_results, combined_df, full_errors_df):
    """Display comprehensive overview on homepage with detailed tabs"""
    
    overall = analysis_results['overall']
    
    st.markdown('<div class="section-header">📈 Performance Summary</div>', unsafe_allow_html=True)
    
    # Key metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Assets",
            value=f"{overall['total_assets']:,}",
            delta=f"Success: {overall['success_rate']}%"
        )
    
    with col2:
        st.metric(
            label="Success Rate",
            value=f"{overall['success_rate']}%",
            delta=f"{overall['total_results']:,} successful"
        )
    
    with col3:
        st.metric(
            label="Error Rate", 
            value=f"{overall['error_rate']}%",
            delta=f"{overall['total_errors']:,} errors"
        )
    
    with col4:
        st.metric(
            label="Coverage",
            value="100%",
            delta=f"{overall['unique_sources']} sources, {overall['unique_adgroups']} ad groups"
        )
    
            # Create tabs - Homepage with overview + detailed tabs
    tab_overview, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🏠 Complete Overview",
        "🎯 Source Details", 
        "📊 Campaign Details",
        "👥 Ad Group Details",
        "🧪 Prompts Analysis",
        "🔍 Ads Generation Error Vs Ads Review",
        "❌ Error Categories",
        "📥 Downloads"
    ])
    
    with tab_overview:
        display_complete_overview(analysis_results, combined_df, full_errors_df)
    
    with tab1:
        display_source_analysis(analysis_results)
    
    with tab2:
        display_campaign_analysis(analysis_results)
    
    with tab3:
        display_adgroup_analysis(analysis_results)
    
    with tab4:
        display_prompts_analysis(analysis_results)
    
    with tab5:
        display_error_source_analysis(combined_df, full_errors_df, analysis_results)
    
    with tab6:
        display_error_categories(full_errors_df, analysis_results)
    
    with tab7:
        display_downloads(analysis_results)

def display_complete_overview(analysis_results, combined_df, full_errors_df):
    """Display comprehensive overview with all key analysis on homepage"""
    st.subheader("🏠 Complete Analysis Overview")
    st.info("📊 This page shows all key insights. Use the other tabs for detailed analysis and filtering.")
    
    # 1. Source Performance Overview
    st.markdown("### 🎯 Source Performance Overview")
    source_df = analysis_results['source_analysis_enhanced'] if 'source_analysis_enhanced' in analysis_results else analysis_results['source_analysis']
    
    # Model and Prompt filtering
    col1, col2 = st.columns(2)
    with col1:
        available_models = source_df['Model'].unique() if 'Model' in source_df.columns else ['All']
        selected_models = st.multiselect(
            "Filter by Model:",
            options=available_models,
            default=available_models,
            key="overview_model_filter"
        )
    
    with col2:
        available_prompts = source_df['Prompt'].unique() if 'Prompt' in source_df.columns else ['All']
        selected_prompts = st.multiselect(
            "Filter by Prompt:",
            options=available_prompts,
            default=available_prompts,
            key="overview_prompt_filter"
        )
    
    # Filter data
    filtered_source_df = source_df.copy()
    if 'Model' in source_df.columns and selected_models:
        filtered_source_df = filtered_source_df[filtered_source_df['Model'].isin(selected_models)]
    if 'Prompt' in source_df.columns and selected_prompts:
        filtered_source_df = filtered_source_df[filtered_source_df['Prompt'].isin(selected_prompts)]
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Use display names for cleaner visualization (horizontal layout)
        display_names = filtered_source_df['Display_Name'] if 'Display_Name' in filtered_source_df.columns else filtered_source_df['Source']
        
        # Source performance chart with simple colors
        fig_source_overview = go.Figure()
        
        fig_source_overview.add_trace(go.Bar(
            name='Successful',
            x=display_names,
            y=filtered_source_df['Results Count'],
            marker_color='#2ecc71',
            text=filtered_source_df['Results Count'],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Successful: %{y}<extra></extra>'
        ))
        
        fig_source_overview.add_trace(go.Bar(
            name='Errors',
            x=display_names,
            y=filtered_source_df['Errors Count'],
            marker_color='#e74c3c',
            text=filtered_source_df['Errors Count'],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Errors: %{y}<extra></extra>'
        ))
        
        fig_source_overview.update_layout(
            title="Source Performance: Success vs Errors",
            barmode='group',
            height=450,
            showlegend=True,
            xaxis_tickangle=0
        )
        
        st.plotly_chart(fig_source_overview, config={'displayModeBar': False})
    
    with col2:
        # Top sources table (excluding manual sources)
        st.markdown("**Top Sources by Volume:**")
        
        # Exclude manual sources like default_asset
        model_sources = filtered_source_df[filtered_source_df['Model'] != 'Other'] if 'Model' in filtered_source_df.columns else filtered_source_df
        top_sources = model_sources.head(5)
        
        # Choose columns to display based on what's available
        if 'Display_Name' in top_sources.columns:
            display_cols = ['Display_Name', 'Total Assets', 'Error Rate %']
            col_names = {'Display_Name': 'Source'}
        else:
            display_cols = ['Source', 'Total Assets', 'Error Rate %']
            col_names = {}
        
        if len(top_sources) > 0:
            st.dataframe(
                top_sources[display_cols].rename(columns=col_names).style.format({
                    'Total Assets': '{:,}',
                    'Error Rate %': '{:.1f}%'
                }),
                width='stretch'
            )
        else:
            st.info("No model-based sources found")
        
        # Model/Prompt summary if available
        if 'Model' in filtered_source_df.columns and len(model_sources) > 0:
            st.markdown("**Model Performance:**")
            model_summary = model_sources.groupby('Model').agg({
                'Total Assets': 'sum',
                'Error Rate %': 'mean'
            }).reset_index().sort_values('Total Assets', ascending=False)
            
            st.dataframe(
                model_summary.style.format({
                    'Total Assets': '{:,}',
                    'Error Rate %': '{:.1f}%'
                }),
                width='stretch'
            )
    
    # 2. Asset Type + Source Matrix
    st.markdown("### 🔗 Source + Asset Type Performance Matrix")
    source_asset_df = analysis_results['source_asset_analysis_enhanced'] if 'source_asset_analysis_enhanced' in analysis_results else analysis_results['source_asset_analysis']
    
    # Filter source_asset_df based on selected models and prompts
    filtered_source_asset_df = source_asset_df.copy()
    if 'Model' in source_asset_df.columns and selected_models:
        filtered_source_asset_df = filtered_source_asset_df[filtered_source_asset_df['Model'].isin(selected_models)]
    if 'Prompt' in source_asset_df.columns and selected_prompts:
        filtered_source_asset_df = filtered_source_asset_df[filtered_source_asset_df['Prompt'].isin(selected_prompts)]
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Heatmap with cleaner names
        if len(filtered_source_asset_df) > 0:
            # Use display names for heatmap
            heatmap_df = filtered_source_asset_df.copy()
            if 'Display_Name' in heatmap_df.columns:
                pivot_data = heatmap_df.pivot(
                    index='Display_Name', 
                    columns='Asset Type', 
                    values='Success Rate %'
                )
            else:
                pivot_data = heatmap_df.pivot(
                    index='Source', 
                    columns='Asset Type', 
                    values='Success Rate %'
                )
            
            fig_heatmap = px.imshow(
                pivot_data,
                title="Success Rate Heatmap (Source vs Asset Type)",
                color_continuous_scale='RdYlGn',
                aspect='auto',
                height=350,
                text_auto=True  # Add numbers on heatmap
            )
            st.plotly_chart(fig_heatmap, config={'displayModeBar': False})
    
    with col2:
        # Asset type distribution
        asset_type_df = analysis_results['asset_type_analysis']
        
        fig_asset_pie = px.pie(
            asset_type_df,
            values='Total Assets',
            names='Asset Type',
            title="Asset Type Distribution",
            height=300
        )
        st.plotly_chart(fig_asset_pie, config={'displayModeBar': False})
    
    # Removed top ad groups performance section as requested
    adgroup_df = analysis_results['adgroup_analysis']
    
    # 3. Top Campaigns Performance
    st.markdown("### 📊 Top Campaigns Performance")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Campaign summary
        campaign_summary = adgroup_df.groupby('Campaign Name').agg({
            'Total Assets': 'sum',
            'Success Rate %': 'mean'
        }).reset_index().sort_values('Total Assets', ascending=False).head(5)
        
        st.markdown("**Top 5 Campaigns:**")
        st.dataframe(
            campaign_summary.style.format({
                'Total Assets': '{:,}',
                'Success Rate %': '{:.1f}%'
            }),
            width='stretch',
            height=250  # Increased height and width
        )
    
    # 4. Error Analysis Overview
    st.markdown("### ❌ Error Analysis Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # ErrorsFromAdsGeneration split
        error_source_analysis = analyze_errors_from_ads_generation(combined_df)
        ads_gen_total = error_source_analysis['ads_generation']['total']
        ads_review_total = error_source_analysis['ads_review']['total']
        
        fig_error_split = go.Figure(data=[go.Pie(
            labels=['Ads Generation Errors', 'Ads Review Errors'],
            values=[ads_gen_total, ads_review_total],
            marker_colors=['#ff6b6b', '#ffa726']
        )])
        
        fig_error_split.update_layout(
            title="Error Source Split",
            height=300
        )
        st.plotly_chart(fig_error_split, config={'displayModeBar': False})
    
    with col2:
        # Errors by source with Display_Name
        if 'error_analysis' in analysis_results and 'error_by_source' in analysis_results['error_analysis']:
            error_by_source = analysis_results['error_analysis']['error_by_source'].copy()
            
            # Parse source names to get display names
            if 'Display_Name' not in error_by_source.columns:
                parsed_info = error_by_source['Source'].apply(parse_source_info)
                error_by_source['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
            
            fig_errors_source = px.bar(
                error_by_source.head(5),
                x='Display_Name',
                y='Error Count',
                title="Top 5 Error Sources",
                color='Error Count',
                color_continuous_scale='Reds',
                height=300
            )
            fig_errors_source.update_layout(xaxis_tickangle=0)
            st.plotly_chart(fig_errors_source, config={'displayModeBar': False})
    
    # 5. Key Insights Summary
    st.markdown("### 💡 Key Insights Summary")
    
    # Get categorized errors for insights
    categorized_errors = None
    if 'error_analysis' in analysis_results and 'error_reasons' in analysis_results['error_analysis']:
        error_reasons_df = analysis_results['error_analysis']['error_reasons']
        categorized_errors, _ = categorize_error_reasons(error_reasons_df)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🎯 **Performance Highlights:**")
        
        # Best performing source (excluding manual sources)
        model_sources_for_best = source_df[source_df['Model'] != 'Other'] if 'Model' in source_df.columns else source_df
        if len(model_sources_for_best) > 0:
            best_source = model_sources_for_best.loc[model_sources_for_best['Error Rate %'].idxmin()]
            display_name = best_source['Display_Name'] if 'Display_Name' in best_source else best_source['Source']
            st.success(f"🏆 **Best Model Source**: {display_name} ({100-best_source['Error Rate %']:.1f}% success rate)")
        
        # Highest volume source
        highest_volume = source_df.loc[source_df['Total Assets'].idxmax()]
        display_name_vol = highest_volume['Display_Name'] if 'Display_Name' in highest_volume else highest_volume['Source']
        st.info(f"📊 **Highest Volume**: {display_name_vol} ({highest_volume['Total Assets']:,} assets)")
        
        # Best ad group
        best_adgroup = adgroup_df.loc[adgroup_df['Success Rate %'].idxmax()]
        st.success(f"🎯 **Best Ad Group**: {best_adgroup['Ad Group'][:50]}... ({best_adgroup['Success Rate %']:.1f}% success)")
    
    with col2:
        st.markdown("#### ⚠️ **Areas for Improvement:**")
        
        # Worst performing source
        worst_source = source_df.loc[source_df['Error Rate %'].idxmax()]
        st.error(f"🔴 **Needs Attention**: {worst_source['Source']} ({worst_source['Error Rate %']:.1f}% error rate)")
        
        # Main error category
        if categorized_errors is not None and len(categorized_errors) > 0:
            main_error = categorized_errors.iloc[0]
            st.warning(f"❌ **Main Error Type**: {main_error['Category']} ({main_error['Count']:,} errors)")
        
        # Error generation vs review insight
        if ads_gen_total > 0 and ads_review_total > 0:
            if ads_gen_total > ads_review_total:
                st.warning(f"🤖 **Focus Area**: Ads Generation ({ads_gen_total:,} errors vs {ads_review_total:,} review errors)")
            else:
                st.warning(f"👁️ **Focus Area**: Ads Review ({ads_review_total:,} errors vs {ads_gen_total:,} generation errors)")
    
    # 6. Quick Action Items
    st.markdown("### 🚀 Quick Action Items")
    
    action_items = []
    
    # Source-based recommendations
    if worst_source['Error Rate %'] > 50:
        action_items.append(f"🔧 **Optimize {worst_source['Source']}** - {worst_source['Error Rate %']:.1f}% error rate needs immediate attention")
    
    # Error category recommendations
    if categorized_errors is not None and len(categorized_errors) > 0:
        top_error_category = categorized_errors.iloc[0]
        if top_error_category['Percentage'] > 30:
            action_items.append(f"📝 **Address {top_error_category['Category']}** - {top_error_category['Percentage']:.1f}% of all errors")
    
    # Asset type recommendations
    if len(asset_type_df) > 1:
        asset_performance = asset_type_df.sort_values('Error Rate %', ascending=False)
        worst_asset_type = asset_performance.iloc[0]
        if worst_asset_type['Error Rate %'] > 40:
            action_items.append(f"📦 **Improve {worst_asset_type['Asset Type']} Assets** - {worst_asset_type['Error Rate %']:.1f}% error rate")
    
    # Process recommendations
    if ads_gen_total > ads_review_total * 2:
        action_items.append("🤖 **Focus on Generation Process** - Most errors occur during ads generation")
    elif ads_review_total > ads_gen_total * 2:
        action_items.append("👁️ **Review Process Optimization** - Most errors caught during review")
    
    if action_items:
        for item in action_items[:4]:  # Show top 4 action items
            st.markdown(f"- {item}")
    else:
        st.success("🎉 **Great Performance!** - No major issues identified. Continue monitoring.")
    
    st.markdown("---")
    st.info("💡 **Need more details?** Use the tabs above to dive deeper into specific areas: Source Details, Ad Group Details, Error Analysis, etc.")

def display_campaign_analysis(analysis_results):
    """Display campaign performance analysis with source and asset type breakdown"""
    st.subheader("📊 Campaign Performance Analysis")
    
    # Use enhanced data if available
    detailed_df = analysis_results['detailed_analysis_enhanced'] if 'detailed_analysis_enhanced' in analysis_results else analysis_results['detailed_analysis']
    campaign_df = analysis_results['campaign_analysis']
    asset_type_df = analysis_results['asset_type_analysis']
    
    # Enhanced filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if 'Model' in detailed_df.columns:
            available_models = detailed_df['Model'].unique()
            selected_models = st.multiselect(
                "Filter Models:",
                options=available_models,
                default=available_models,
                key="campaign_model_filter"
            )
        else:
            selected_models = []
    
    with col2:
        if 'Prompt' in detailed_df.columns:
            available_prompts = detailed_df['Prompt'].unique()
            selected_prompts = st.multiselect(
                "Filter Prompts:",
                options=available_prompts,
                default=available_prompts,
                key="campaign_prompt_filter"
            )
        else:
            selected_prompts = []
    
    with col3:
        selected_campaigns = st.multiselect(
            "Filter Campaigns:",
            options=campaign_df['Campaign Name'].tolist(),
            default=[],
            key="campaign_filter",
            help="Leave empty to show all campaigns"
        )
    
    with col4:
        selected_asset_types = st.multiselect(
            "Filter Asset Types:",
            options=asset_type_df['Asset Type'].tolist(),
            default=asset_type_df['Asset Type'].tolist(),
            key="campaign_asset_filter"
        )
    
    # Apply filters
    filtered_detailed_df = detailed_df.copy()
    
    # Apply Model/Prompt filters if available
    if 'Model' in detailed_df.columns and selected_models:
        filtered_detailed_df = filtered_detailed_df[filtered_detailed_df['Model'].isin(selected_models)]
    
    if 'Prompt' in detailed_df.columns and selected_prompts:
        filtered_detailed_df = filtered_detailed_df[filtered_detailed_df['Prompt'].isin(selected_prompts)]
    
    # Apply campaign filter if specified
    if selected_campaigns:
        filtered_detailed_df = filtered_detailed_df[filtered_detailed_df['Campaign Name'].isin(selected_campaigns)]
    
    # Always apply asset type filter
    filtered_detailed_df = filtered_detailed_df[filtered_detailed_df['Asset Type'].isin(selected_asset_types)]
    
    # Generate campaign summary from filtered data
    if len(filtered_detailed_df) > 0:
        campaign_summary = filtered_detailed_df.groupby('Campaign Name').agg({
            'Total Assets': 'sum',
            'Results Count': 'sum',
            'Errors Count': 'sum'
        }).reset_index()
        
        campaign_summary['Success Rate %'] = (campaign_summary['Results Count'] / campaign_summary['Total Assets'] * 100).round(2)
        campaign_summary = campaign_summary.sort_values('Total Assets', ascending=False)
    else:
        campaign_summary = pd.DataFrame()
    
    # Top campaigns table
    if len(campaign_summary) > 0:
        st.markdown("### 📊 Top Campaigns by Volume")
        top_campaigns = campaign_summary.head(15)
        st.dataframe(
            top_campaigns[['Campaign Name', 'Total Assets', 'Results Count', 'Errors Count', 'Success Rate %']].style.format({
                'Total Assets': '{:,}',
                'Results Count': '{:,}',
                'Errors Count': '{:,}',
                'Success Rate %': '{:.1f}%'
            }),
            width='stretch',
            height=400
        )
    else:
        st.info("No data available for the selected filters")
    
    # Source and Asset Type breakdown for campaigns
    if len(filtered_detailed_df) > 0:
        st.markdown("### 📈 Campaign Source & Asset Type Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Source distribution for filtered campaigns
            if 'Display_Name' in filtered_detailed_df.columns:
                source_dist = filtered_detailed_df.groupby('Display_Name')['Total Assets'].sum().sort_values(ascending=False)
            else:
                source_dist = filtered_detailed_df.groupby('Source')['Total Assets'].sum().sort_values(ascending=False)
            
            fig_source_dist = px.pie(
                values=source_dist.values,
                names=source_dist.index,
                title="Source Distribution (Filtered Campaigns)",
                height=350
            )
            st.plotly_chart(fig_source_dist, config={'displayModeBar': False})
        
        with col2:
            # Asset type distribution for filtered campaigns
            asset_dist = filtered_detailed_df.groupby('Asset Type')['Total Assets'].sum().sort_values(ascending=False)
            
            fig_asset_dist = px.pie(
                values=asset_dist.values,
                names=asset_dist.index,
                title="Asset Type Distribution (Filtered Campaigns)",
                height=350
            )
            st.plotly_chart(fig_asset_dist, config={'displayModeBar': False})
        
        # Campaign Summary (moved from Ad Group tab)
        st.markdown("### 📈 Campaign Summary")
        
        # Generate campaign summary from filtered data
        if len(filtered_detailed_df) > 0:
            campaign_summary_detailed = filtered_detailed_df.groupby('Campaign Name').agg({
                'Total Assets': 'sum',
                'Results Count': 'sum',
                'Errors Count': 'sum'
            }).reset_index()
            
            campaign_summary_detailed['Success Rate %'] = (campaign_summary_detailed['Results Count'] / campaign_summary_detailed['Total Assets'] * 100).round(2)
            campaign_summary_detailed = campaign_summary_detailed.sort_values('Total Assets', ascending=False)
            
            st.dataframe(
                campaign_summary_detailed.style.format({
                    'Total Assets': '{:,}',
                    'Results Count': '{:,}',
                    'Errors Count': '{:,}',
                    'Success Rate %': '{:.1f}%'
                }),
                width='stretch',
                height=300
            )
        
        # Campaign + Source + Asset Type detailed table with grouping
        st.markdown("### 📋 Detailed Campaign Analysis (Grouped by Source & Asset Type)")
        
        # Show detailed breakdown with grouping
        display_detailed_df = filtered_detailed_df.copy()
        
        # Use Display_Name if available, otherwise use Source
        if 'Display_Name' in display_detailed_df.columns:
            # Drop original Source column to avoid duplication, then rename Display_Name
            if 'Source' in display_detailed_df.columns:
                display_detailed_df = display_detailed_df.drop(columns=['Source'])
            display_detailed_df = display_detailed_df.rename(columns={'Display_Name': 'Source'})
        
        # Group by Campaign, Source, and Asset Type for better readability
        grouped_detailed = display_detailed_df.groupby(['Campaign Name', 'Source', 'Asset Type']).agg({
            'Total Assets': 'sum',
            'Results Count': 'sum',
            'Errors Count': 'sum'
        }).reset_index()
        
        grouped_detailed['Success Rate %'] = (grouped_detailed['Results Count'] / grouped_detailed['Total Assets'] * 100).round(2)
        grouped_detailed = grouped_detailed.sort_values(['Campaign Name', 'Total Assets'], ascending=[True, False])
        
        st.dataframe(
            grouped_detailed.style.format({
                'Total Assets': '{:,}',
                'Results Count': '{:,}',
                'Errors Count': '{:,}',
                'Success Rate %': '{:.1f}%'
            }),
            width='stretch',
            height=500
        )

def display_source_analysis(analysis_results):
    """Display source performance analysis with enhanced model/prompt filtering"""
    st.subheader("🎯 Source Performance Analysis")
    
    # Use enhanced data if available
    source_df = analysis_results['source_analysis_enhanced'] if 'source_analysis_enhanced' in analysis_results else analysis_results['source_analysis']
    source_asset_df = analysis_results['source_asset_analysis_enhanced'] if 'source_asset_analysis_enhanced' in analysis_results else analysis_results['source_asset_analysis']
    asset_type_df = analysis_results['asset_type_analysis']
    
    # Enhanced filters with Model/Prompt separation
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if 'Model' in source_df.columns:
            available_models = source_df['Model'].unique()
            selected_models = st.multiselect(
                "Filter Models:",
                options=available_models,
                default=available_models,
                key="source_model_filter"
            )
        else:
            selected_models = []
    
    with col2:
        if 'Prompt' in source_df.columns:
            available_prompts = source_df['Prompt'].unique()
            selected_prompts = st.multiselect(
                "Filter Prompts:",
                options=available_prompts,
                default=available_prompts,
                key="source_prompt_filter"
            )
        else:
            selected_prompts = []
    
    with col3:
        selected_sources = st.multiselect(
            "Filter Sources:",
            options=source_df['Source'].tolist(),
            default=[],
            key="source_filter",
            help="Leave empty to use Model/Prompt filters"
        )
    
    with col4:
        selected_asset_types = st.multiselect(
            "Filter Asset Types:",
            options=asset_type_df['Asset Type'].tolist(),
            default=asset_type_df['Asset Type'].tolist(),
            key="source_asset_filter"
        )
    
    # Apply filters - prioritize Model/Prompt filters over source filter
    filtered_source_df = source_df.copy()
    filtered_source_asset_df = source_asset_df.copy()
    
    # Apply Model/Prompt filters if available and selected
    if 'Model' in source_df.columns and selected_models:
        filtered_source_df = filtered_source_df[filtered_source_df['Model'].isin(selected_models)]
        filtered_source_asset_df = filtered_source_asset_df[filtered_source_asset_df['Model'].isin(selected_models)]
    
    if 'Prompt' in source_df.columns and selected_prompts:
        filtered_source_df = filtered_source_df[filtered_source_df['Prompt'].isin(selected_prompts)]
        filtered_source_asset_df = filtered_source_asset_df[filtered_source_asset_df['Prompt'].isin(selected_prompts)]
    
    # Apply source filter if specified (overrides model/prompt filters)
    if selected_sources:
        filtered_source_df = filtered_source_df[filtered_source_df['Source'].isin(selected_sources)]
        filtered_source_asset_df = filtered_source_asset_df[filtered_source_asset_df['Source'].isin(selected_sources)]
    
    # Always apply asset type filter
    filtered_source_asset_df = filtered_source_asset_df[filtered_source_asset_df['Asset Type'].isin(selected_asset_types)]
    
    # Main visualizations
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Source performance stacked bar chart with simple colors
        display_names = filtered_source_df['Display_Name'] if 'Display_Name' in filtered_source_df.columns else filtered_source_df['Source']
        
        fig_source = go.Figure()
        
        fig_source.add_trace(go.Bar(
            name='Successful Assets',
            x=display_names,
            y=filtered_source_df['Results Count'],
            marker_color='#2ecc71',
            text=filtered_source_df['Results Count'],
            textposition='inside',
            hovertemplate='<b>%{x}</b><br>Successful: %{y}<extra></extra>'
        ))
        
        fig_source.add_trace(go.Bar(
            name='Error Assets',
            x=display_names,
            y=filtered_source_df['Errors Count'],
            marker_color='#e74c3c',
            text=filtered_source_df['Errors Count'],
            textposition='inside',
            hovertemplate='<b>%{x}</b><br>Errors: %{y}<extra></extra>'
        ))
        
        fig_source.update_layout(
            title="Source Performance: Success vs Errors",
            barmode='stack',
            height=450,
            xaxis_title="Source",
            yaxis_title="Number of Assets",
            xaxis_tickangle=0
        )
        
        st.plotly_chart(fig_source, config={'displayModeBar': False})
    
    with col2:
        # Asset type distribution
        fig_asset_pie = px.pie(
            asset_type_df[asset_type_df['Asset Type'].isin(selected_asset_types)],
            values='Total Assets',
            names='Asset Type',
            title="Asset Type Distribution",
            height=400
        )
        st.plotly_chart(fig_asset_pie, config={'displayModeBar': False})
    
    # Source + Asset Type combination analysis
    st.subheader("🔗 Source + Asset Type Performance Matrix")
    
    if len(filtered_source_asset_df) > 0:
        # Heatmap for success rates
        pivot_data = filtered_source_asset_df.pivot(
            index='Source', 
            columns='Asset Type', 
            values='Success Rate %'
        )
        
        fig_heatmap = px.imshow(
            pivot_data,
            title="Success Rate Heatmap (Source vs Asset Type)",
            color_continuous_scale='RdYlGn',
            aspect='auto',
            height=300
        )
        fig_heatmap.update_layout(
            xaxis_title="Asset Type",
            yaxis_title="Source"
        )
        st.plotly_chart(fig_heatmap, config={'displayModeBar': False})
        
        # Grouped bar chart for source + asset type
        fig_grouped = px.bar(
            filtered_source_asset_df,
            x='Source',
            y='Total Assets',
            color='Asset Type',
            title="Asset Volume by Source and Asset Type",
            barmode='group',
            height=400
        )
        st.plotly_chart(fig_grouped, config={'displayModeBar': False})
    
    # Data tables
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Source Performance Details")
        st.dataframe(
            filtered_source_df.style.format({
                'Total Assets': '{:,}',
                'Results Count': '{:,}',
                'Errors Count': '{:,}',
                'Error Rate %': '{:.1f}%'
            }),
            width='stretch'
        )
    
    with col2:
        st.subheader("🔗 Source + Asset Type Details")
        st.dataframe(
            filtered_source_asset_df.style.format({
                'Total Assets': '{:,}',
                'Results Count': '{:,}',
                'Errors Count': '{:,}',
                'Success Rate %': '{:.1f}%',
                'Error Rate %': '{:.1f}%'
            }),
            width='stretch'
        )

def display_adgroup_analysis(analysis_results):
    """Display ad group performance analysis with source and asset type context"""
    st.subheader("👥 Ad Group Performance Analysis")
    
    adgroup_df = analysis_results['adgroup_analysis']
    detailed_df = analysis_results['detailed_analysis']
    source_df = analysis_results['source_analysis']
    asset_type_df = analysis_results['asset_type_analysis']
    
    st.info(f"📊 Analyzing {len(adgroup_df):,} ad groups across {analysis_results['overall']['unique_campaigns']} campaigns")
    
    # Filters for ad groups
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        min_assets = st.slider("Minimum Assets:", 0, safe_int_convert(adgroup_df['Total Assets'].max(), 100), 10, key="adgroup_min_assets")
    
    with col2:
        min_success_rate = st.slider("Minimum Success Rate (%):", 0, 100, 0, key="adgroup_min_success")
    
    with col3:
        selected_sources = st.multiselect(
            "Filter by Source:",
            options=source_df['Source'].tolist(),
            default=[],
            key="adgroup_source_filter"
        )
    
    with col4:
        selected_asset_types = st.multiselect(
            "Filter by Asset Type:",
            options=asset_type_df['Asset Type'].tolist(),
            default=[],
            key="adgroup_asset_type_filter"
        )
    
    # Apply filters to detailed analysis for source/asset type filtering
    filtered_detailed = detailed_df.copy()
    if selected_sources:
        filtered_detailed = filtered_detailed[filtered_detailed['Source'].isin(selected_sources)]
    if selected_asset_types:
        filtered_detailed = filtered_detailed[filtered_detailed['Asset Type'].isin(selected_asset_types)]
    
    # Get campaign names from filtered detailed analysis
    filtered_campaigns = filtered_detailed['Campaign Name'].unique() if len(filtered_detailed) > 0 else []
    
    # Apply filters to ad groups
    filtered_adgroups = adgroup_df[
        (adgroup_df['Total Assets'] >= min_assets) &
        (adgroup_df['Success Rate %'] >= min_success_rate)
    ]
    
    if len(filtered_campaigns) > 0:
        filtered_adgroups = filtered_adgroups[filtered_adgroups['Campaign Name'].isin(filtered_campaigns)]
    
    # Display results
    if len(filtered_adgroups) > 0:
        # Top performing ad groups
        top_adgroups = filtered_adgroups.head(20)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Horizontal bar chart for top ad groups
            fig_adgroups = px.bar(
                top_adgroups,
                x='Total Assets',
                y='Ad Group',
                color='Success Rate %',
                color_continuous_scale='RdYlGn',
                orientation='h',
                title=f"Top {len(top_adgroups)} Ad Groups (Filtered)",
                height=600,
                hover_data=['Campaign Name', 'Results Count', 'Errors Count']
            )
            
            fig_adgroups.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_adgroups, config={'displayModeBar': False})
        
        with col2:
            # Source distribution for filtered ad groups
            if len(filtered_detailed) > 0:
                source_summary = filtered_detailed.groupby('Source')['Total Assets'].sum().reset_index()
                source_summary = source_summary.sort_values('Total Assets', ascending=False)
                
                fig_source_pie = px.pie(
                    source_summary,
                    values='Total Assets',
                    names='Source',
                    title="Source Distribution (Filtered)",
                    height=300
                )
                st.plotly_chart(fig_source_pie, config={'displayModeBar': False})
                
                # Asset type distribution
                asset_summary = filtered_detailed.groupby('Asset Type')['Total Assets'].sum().reset_index()
                asset_summary = asset_summary.sort_values('Total Assets', ascending=False)
                
                fig_asset_pie = px.pie(
                    asset_summary,
                    values='Total Assets',
                    names='Asset Type',
                    title="Asset Type Distribution (Filtered)",
                    height=300
                )
                st.plotly_chart(fig_asset_pie, config={'displayModeBar': False})
        
        # Ad Group Source & Asset Type Analysis
        if len(filtered_detailed) > 0:
            st.subheader("📈 Ad Group Source & Asset Type Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Source distribution for filtered ad groups
                if 'Display_Name' in filtered_detailed.columns:
                    source_dist = filtered_detailed.groupby('Display_Name')['Total Assets'].sum().sort_values(ascending=False)
                else:
                    source_dist = filtered_detailed.groupby('Source')['Total Assets'].sum().sort_values(ascending=False)
                
                fig_source_dist = px.pie(
                    values=source_dist.values,
                    names=source_dist.index,
                    title="Source Distribution (Filtered Ad Groups)",
                    height=350
                )
                st.plotly_chart(fig_source_dist, config={'displayModeBar': False})
            
            with col2:
                # Asset type distribution for filtered ad groups
                asset_dist = filtered_detailed.groupby('Asset Type')['Total Assets'].sum().sort_values(ascending=False)
                
                fig_asset_dist = px.pie(
                    values=asset_dist.values,
                    names=asset_dist.index,
                    title="Asset Type Distribution (Filtered Ad Groups)",
                    height=350
                )
                st.plotly_chart(fig_asset_dist, config={'displayModeBar': False})
        
        # Ad Group Summary (filtered)
        st.subheader("📈 Ad Group Summary (Filtered)")
        
        # Generate ad group summary with source and asset type breakdown
        if len(filtered_detailed) > 0:
            # Get ad groups from detailed analysis that match our filters
            adgroup_summary = filtered_detailed.groupby(['Campaign Name', 'Source', 'Asset Type']).agg({
                'Total Assets': 'sum',
                'Results Count': 'sum',
                'Errors Count': 'sum'
            }).reset_index()
            
            adgroup_summary['Success Rate %'] = (adgroup_summary['Results Count'] / adgroup_summary['Total Assets'] * 100).round(2)
            
            # Use Display_Name if available
            if 'Display_Name' in filtered_detailed.columns:
                display_mapping = dict(zip(filtered_detailed['Source'], filtered_detailed['Display_Name']))
                adgroup_summary['Source'] = adgroup_summary['Source'].map(display_mapping).fillna(adgroup_summary['Source'])
            
            adgroup_summary = adgroup_summary.sort_values(['Campaign Name', 'Total Assets'], ascending=[True, False])
            
            st.dataframe(
                adgroup_summary.style.format({
                    'Total Assets': '{:,}',
                    'Results Count': '{:,}',
                    'Errors Count': '{:,}',
                    'Success Rate %': '{:.1f}%'
                }),
                width='stretch',
                height=400
            )
        
        # Data tables
        col1, col2 = st.columns(2)
        
        with col1:
            # Top Ad Groups by Performance
            st.subheader("🏆 Top Ad Groups by Success Rate")
            top_adgroups_by_success = filtered_adgroups.sort_values('Success Rate %', ascending=False).head(15)
            st.dataframe(
                top_adgroups_by_success[['Ad Group', 'Campaign Name', 'Total Assets', 'Success Rate %']].style.format({
                    'Total Assets': '{:,}',
                    'Success Rate %': '{:.1f}%'
                }),
                width='stretch',
                height=400
            )
        
        with col2:
            # Top Ad Groups by Volume
            st.subheader("📊 Top Ad Groups by Volume")
            top_adgroups_by_volume = filtered_adgroups.sort_values('Total Assets', ascending=False).head(15)
            st.dataframe(
                top_adgroups_by_volume[['Ad Group', 'Campaign Name', 'Total Assets', 'Success Rate %']].style.format({
                    'Total Assets': '{:,}',
                    'Success Rate %': '{:.1f}%'
                }),
                width='stretch',
                height=400
            )
        
        # Detailed ad group table
        st.subheader("📋 Ad Group Details")
        st.dataframe(
            filtered_adgroups.style.format({
                'Total Assets': '{:,}',
                'Results Count': '{:,}',
                'Errors Count': '{:,}',
                'Success Rate %': '{:.1f}%'
            }),
            width='stretch'
        )
        
        # Ad Groups with Low Asset Generation (Only Default Assets)
        st.markdown("### ⚠️ Ad Groups Needing Attention")
        
        # Find ad groups with only default assets or high default asset ratio
        # Use detailed_adgroup_analysis if available (has Ad Group column), otherwise fall back to detailed_analysis
        if 'detailed_adgroup_analysis' in analysis_results:
            detailed_df_for_analysis = analysis_results['detailed_adgroup_analysis']
        elif 'detailed_analysis_enhanced' in analysis_results:
            detailed_df_for_analysis = analysis_results['detailed_analysis_enhanced']
        else:
            detailed_df_for_analysis = analysis_results['detailed_analysis']
        
        # Filter for default assets
        default_assets = detailed_df_for_analysis[detailed_df_for_analysis['Source'].str.contains('default_asset', na=False)]
        
        if len(default_assets) > 0 and 'Ad Group' in detailed_df_for_analysis.columns:
            # Group by ad group and campaign to find those with high default asset counts
            default_summary = default_assets.groupby(['Ad Group', 'Campaign Name']).agg({
                'Total Assets': 'sum'
            }).reset_index()
            
            # Find ad groups with more than 5 default assets
            high_default = default_summary[default_summary['Total Assets'] >= 5].sort_values('Total Assets', ascending=False)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🚨 **Ad Groups with High Default Assets (≥5)**")
                if len(high_default) > 0:
                    st.warning(f"Found {len(high_default)} ad groups with 5+ default assets - these need immediate attention!")
                    st.dataframe(
                        high_default.style.format({
                            'Total Assets': '{:,}'
                        }),
                        width='stretch',
                        height=400
                    )
                else:
                    st.success("✅ No ad groups found with 5+ default assets")
            
            with col2:
                # Find ad groups with ONLY default assets (100% default)
                if 'Ad Group' in detailed_df_for_analysis.columns:
                    all_adgroups_assets = detailed_df_for_analysis.groupby(['Ad Group', 'Campaign Name']).agg({
                        'Total Assets': 'sum'
                    }).reset_index()
                    
                    # Merge to find ratio
                    merged = all_adgroups_assets.merge(default_summary, on=['Ad Group', 'Campaign Name'], how='left', suffixes=('_total', '_default'))
                    merged['Default_Ratio'] = (merged['Total Assets_default'].fillna(0) / merged['Total Assets_total'] * 100).round(1)
                    
                    only_default = merged[merged['Default_Ratio'] == 100.0].sort_values('Total Assets_default', ascending=False)
                    
                    st.markdown("#### 🔴 **Ad Groups with ONLY Default Assets**")
                    if len(only_default) > 0:
                        st.error(f"Found {len(only_default)} ad groups with 100% default assets - no valid assets generated!")
                        st.dataframe(
                            only_default[['Ad Group', 'Campaign Name', 'Total Assets_default']].rename(columns={'Total Assets_default': 'Default Assets'}).style.format({
                                'Default Assets': '{:,}'
                            }),
                            width='stretch',
                            height=400
                        )
                    else:
                        st.success("✅ No ad groups found with 100% default assets")
                else:
                    st.info("ℹ️ Ad Group information not available in detailed analysis")
        else:
            st.info("ℹ️ No default assets found in the current dataset")
    else:
        st.warning("No ad groups match the current filters. Try adjusting the filter criteria.")

def display_error_source_analysis(combined_df, full_errors_df, analysis_results):
    """Display ErrorsFromAdsGeneration analysis with source and asset type breakdown"""
    st.subheader("🔍 Ads Generation Error Vs Ads Review")
    

    
    error_source_analysis = analyze_errors_from_ads_generation(combined_df)
    
    # Overall comparison
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🤖 Ads Generation Errors")
        ads_gen_total = error_source_analysis['ads_generation']['total']
        st.metric("Total Ads Generation Errors", f"{ads_gen_total:,}")
        
        if ads_gen_total > 0:
            ads_gen_source = error_source_analysis['ads_generation']['by_source']
            if len(ads_gen_source) > 0:
                fig_ads_gen = px.pie(
                    ads_gen_source,
                    values='Count',
                    names='Source',
                    title="Ads Generation Errors by Source")
                st.plotly_chart(fig_ads_gen, config={'displayModeBar': False})
        else:
            st.info("No ads generation errors found")
    
    with col2:
        st.markdown("### 👁️ Ads Review Errors")
        ads_review_total = error_source_analysis['ads_review']['total']
        st.metric("Total Ads Review Errors", f"{ads_review_total:,}")
        
        if ads_review_total > 0:
            ads_review_source = error_source_analysis['ads_review']['by_source']
            if len(ads_review_source) > 0:
                fig_ads_review = px.pie(
                    ads_review_source,
                    values='Count',
                    names='Source',
                    title="Ads Review Errors by Source")
                st.plotly_chart(fig_ads_review, config={'displayModeBar': False})
        else:
            st.info("No ads review errors found")
    
    # Asset Type breakdown for both error types
    st.subheader("📦 Asset Type Breakdown by Error Source")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🤖 Ads Generation Errors by Asset Type")
        if ads_gen_total > 0:
            ads_gen_asset = error_source_analysis['ads_generation']['by_asset_type']
            if len(ads_gen_asset) > 0:
                fig_ads_gen_asset = px.bar(
                    ads_gen_asset,
                    x='Asset Type',
                    y='Count',
                    title="Ads Generation Errors by Asset Type",
                    color='Count',
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig_ads_gen_asset, config={'displayModeBar': False})
                st.dataframe(ads_gen_asset, width='stretch')
        else:
            st.info("No ads generation errors by asset type")
    
    with col2:
        st.markdown("#### 👁️ Ads Review Errors by Asset Type")
        if ads_review_total > 0:
            ads_review_asset = error_source_analysis['ads_review']['by_asset_type']
            if len(ads_review_asset) > 0:
                fig_ads_review_asset = px.bar(
                    ads_review_asset,
                    x='Asset Type',
                    y='Count',
                    title="Ads Review Errors by Asset Type",
                    color='Count',
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig_ads_review_asset, config={'displayModeBar': False})
                st.dataframe(ads_review_asset, width='stretch')
        else:
            st.info("No ads review errors by asset type")
    
    # Combined Source + Asset Type analysis for errors
    st.subheader("🔗 Source + Asset Type Error Matrix")
    
    # Filter only error data
    error_data = combined_df[combined_df['DataSource'] == 'Errors']
    
    if len(error_data) > 0:
        # Create error matrix by source, asset type, and error generation flag
        error_matrix = error_data.groupby(['Source', 'AssetType', 'ErrorFromAdsGeneration']).size().reset_index(name='Count')
        
        # Pivot for heatmap
        error_pivot = error_data.groupby(['Source', 'AssetType']).size().reset_index(name='Total Errors')
        
        if len(error_pivot) > 0:
            fig_error_matrix = px.bar(
                error_pivot,
                x='Source',
                y='Total Errors',
                color='AssetType',
                title="Error Distribution: Source vs Asset Type",
                barmode='group'
            )
            st.plotly_chart(fig_error_matrix, config={'displayModeBar': False})
            
            # Data table for error matrix
            st.subheader("📊 Error Matrix Details")
            st.dataframe(
                error_pivot.style.format({
                    'Total Errors': '{:,}'
                }),
                width='stretch'
            )
    
    # Error Categories Analysis
    st.markdown("### 📊 Error Categories by Source")
    
    # Get error data from full_errors_df (which has ReasonForError column)
    error_data = full_errors_df[full_errors_df['ReasonForError'].notna()].copy()
    
    if len(error_data) > 0:
        # Parse source info if not already done
        if 'Display_Name' not in error_data.columns:
            parsed_info = error_data['Source'].apply(parse_source_info)
            error_data['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
        
        # Categorize errors
        error_reasons_df = error_data['ReasonForError'].value_counts().reset_index()
        error_reasons_df.columns = ['ReasonForError', 'Count']
        # Fix percentage calculation to avoid 0.0% when count > 0
        total_errors = error_reasons_df['Count'].sum()
        error_reasons_df['Percentage'] = error_reasons_df['Count'].apply(
            lambda x: max(0.1, round(x / total_errors * 100, 2)) if x > 0 else 0.0
        )
        
        # Club similar errors
        clubbed_errors = club_similar_errors(error_reasons_df)
        
        # Categorize errors
        categorized_errors, category_details = categorize_error_reasons(error_reasons_df)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Error categories pie chart
            if categorized_errors is not None and len(categorized_errors) > 0:
                fig_error_cat = px.pie(
                    categorized_errors,
                    values='Count',
                    names='Category',
                    title="Error Categories Distribution",
                    height=350
                )
                st.plotly_chart(fig_error_cat, config={'displayModeBar': False})
            else:
                st.info("No error categories available")
        
        with col2:
            # Error source breakdown
            error_by_source = error_data.groupby(['Display_Name', 'ErrorFromAdsGeneration']).size().reset_index(name='Count')
            
            fig_error_source = px.bar(
                error_by_source,
                x='Display_Name',
                y='Count',
                color='ErrorFromAdsGeneration',
                title="Errors by Source and Type",
                height=350,
                color_discrete_map={'Yes': '#e74c3c', 'No': '#f39c12'}
            )
            fig_error_source.update_layout(xaxis_tickangle=0)
            st.plotly_chart(fig_error_source, config={'displayModeBar': False})
        
        # Clubbed errors with expandable details
        st.markdown("### 🔍 Clubbed Error Analysis")
        st.info("Similar errors are grouped together. Click to expand for detailed breakdown.")
        
        for _, row in clubbed_errors.head(10).iterrows():
            clubbed_error = row['Clubbed_Error']
            total_count = row['Count']
            total_percentage = row['Percentage']
            original_errors = row['Original_Error']
            
            with st.expander(f"**{clubbed_error}** - {total_count:,} occurrences ({total_percentage:.1f}%)"):
                # If only one error type, show assets directly
                if len(original_errors) == 1:
                    err = original_errors[0]
                    # Get all assets with this specific error
                    assets_with_error = full_errors_df[full_errors_df['ReasonForError'] == err].copy()
                    
                    if len(assets_with_error) > 0:
                        # Show asset details directly
                        st.markdown("**Assets with this error:**")
                        
                        # Create a clean display of assets
                        asset_display = assets_with_error[['Asset', 'Source', 'AssetType', 'CampaignName', 'AdGroups', 'ErrorFromAdsGeneration']].copy()
                        
                        # Parse source names for better display
                        if 'Display_Name' not in asset_display.columns:
                            parsed_info = asset_display['Source'].apply(parse_source_info)
                            asset_display['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
                        
                        # Replace original Source with Display_Name and rename columns
                        if 'Display_Name' in asset_display.columns:
                            asset_display = asset_display.drop(columns=['Source'])
                            asset_display = asset_display.rename(columns={'Display_Name': 'Source'})
                        
                        asset_display = asset_display.rename(columns={
                            'AssetType': 'Asset Type',
                            'CampaignName': 'Campaign',
                            'AdGroups': 'Ad Group',
                            'ErrorFromAdsGeneration': 'Error Type'
                        })
                        
                        # Replace Error Type values for clarity
                        asset_display['Error Type'] = asset_display['Error Type'].map({
                            'Yes': 'Ads Generation',
                            'No': 'Ads Review'
                        })
                        
                        # Display the assets table
                        st.dataframe(
                            asset_display[['Asset', 'Source', 'Asset Type', 'Campaign', 'Ad Group', 'Error Type']],
                            width='stretch',
                            height=min(400, len(asset_display) * 35 + 50)
                        )
                        
                        # Show summary stats
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Assets", len(asset_display))
                        with col2:
                            ads_gen_count = len(asset_display[asset_display['Error Type'] == 'Ads Generation'])
                            st.metric("Ads Generation", ads_gen_count)
                        with col3:
                            ads_review_count = len(asset_display[asset_display['Error Type'] == 'Ads Review'])
                            st.metric("Ads Review", ads_review_count)
                    else:
                        st.info("No asset details available for this error.")
                
                else:
                    # Multiple error types - show breakdown with nested expandables
                    st.markdown("**Detailed Breakdown:**")
                    
                    # Show individual errors within this club with clickable details
                    for err in sorted(original_errors, key=lambda x: error_reasons_df[error_reasons_df['ReasonForError'] == x]['Count'].iloc[0], reverse=True):
                        count = error_reasons_df[error_reasons_df['ReasonForError'] == err]['Count'].iloc[0]
                        
                        with st.expander(f"🔍 {err} - {count:,} occurrences"):
                            # Get all assets with this specific error
                            assets_with_error = full_errors_df[full_errors_df['ReasonForError'] == err].copy()
                            
                            if len(assets_with_error) > 0:
                                # Show asset details
                                st.markdown("**Assets with this error:**")
                                
                                # Create a clean display of assets
                                asset_display = assets_with_error[['Asset', 'Source', 'AssetType', 'CampaignName', 'AdGroups', 'ErrorFromAdsGeneration']].copy()
                                
                                # Parse source names for better display
                                if 'Display_Name' not in asset_display.columns:
                                    parsed_info = asset_display['Source'].apply(parse_source_info)
                                    asset_display['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
                                
                                # Replace original Source with Display_Name and rename columns
                                if 'Display_Name' in asset_display.columns:
                                    asset_display = asset_display.drop(columns=['Source'])
                                    asset_display = asset_display.rename(columns={'Display_Name': 'Source'})
                                
                                asset_display = asset_display.rename(columns={
                                    'AssetType': 'Asset Type',
                                    'CampaignName': 'Campaign',
                                    'AdGroups': 'Ad Group',
                                    'ErrorFromAdsGeneration': 'Error Type'
                                })
                                
                                # Replace Error Type values for clarity
                                asset_display['Error Type'] = asset_display['Error Type'].map({
                                    'Yes': 'Ads Generation',
                                    'No': 'Ads Review'
                                })
                                
                                # Display the assets table
                                st.dataframe(
                                    asset_display[['Asset', 'Source', 'Asset Type', 'Campaign', 'Ad Group', 'Error Type']],
                                    width='stretch',
                                    height=min(400, len(asset_display) * 35 + 50)
                                )
                                
                                # Show summary stats
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total Assets", len(asset_display))
                                with col2:
                                    ads_gen_count = len(asset_display[asset_display['Error Type'] == 'Ads Generation'])
                                    st.metric("Ads Generation", ads_gen_count)
                                with col3:
                                    ads_review_count = len(asset_display[asset_display['Error Type'] == 'Ads Review'])
                                    st.metric("Ads Review", ads_review_count)
                            else:
                                st.info("No asset details available for this error.")
    
    # Suggestions for Error Reduction
    st.markdown("### 💡 Suggestions for Error Reduction")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🤖 **Ads Generation Errors**")
        st.markdown("""
        **Common Issues & Solutions:**
        - **Headline/Description Uniqueness**: Ensure diverse content generation
        - **Consecutive Words**: Improve prompt engineering to avoid repetition
        - **CTA Consistency**: Review call-to-action guidelines in prompts
        - **Punctuation Rules**: Add punctuation validation in generation process
        
        **Recommended Actions:**
        1. **Review Prompts**: Update prompts to emphasize uniqueness
        2. **Add Validation**: Implement pre-checks before asset creation
        3. **Diversify Sources**: Use multiple prompt variations
        4. **Quality Control**: Add automated content quality checks
        """)
    
    with col2:
        st.markdown("#### 👁️ **Ads Review Errors**")
        st.markdown("""
        **Common Issues & Solutions:**
        - **Policy Violations**: Review content against advertising policies
        - **Brand Guidelines**: Ensure compliance with brand standards
        - **Regulatory Issues**: Check against industry regulations
        - **Quality Standards**: Maintain consistent quality thresholds
        
        **Recommended Actions:**
        1. **Policy Training**: Update review guidelines regularly
        2. **Automated Screening**: Implement policy violation detection
        3. **Reviewer Training**: Ensure consistent review standards
        4. **Feedback Loop**: Share common issues with generation team
        """)
    
    # Action Items
    st.markdown("### 🎯 **Priority Action Items**")
    
    if len(error_data) > 0:
        ads_gen_errors = len(error_data[error_data['ErrorFromAdsGeneration'] == 'Yes'])
        ads_review_errors = len(error_data[error_data['ErrorFromAdsGeneration'] == 'No'])
        
        if ads_gen_errors > ads_review_errors:
            st.warning(f"**Focus on Generation**: {ads_gen_errors:,} generation errors vs {ads_review_errors:,} review errors. Priority: Improve prompt engineering and validation.")
        else:
            st.warning(f"**Focus on Review Process**: {ads_review_errors:,} review errors vs {ads_gen_errors:,} generation errors. Priority: Enhance review guidelines and training.")
        
        # Top error category
        if categorized_errors is not None and len(categorized_errors) > 0:
            top_category = categorized_errors.iloc[0]
            st.info(f"**Top Error Category**: {top_category['Category']} ({top_category['Count']} errors). Focus improvement efforts here first.")

def display_error_categories(full_errors_df, analysis_results):
    """Display categorized error analysis with source and asset type breakdown"""
    st.subheader("❌ Error Categories")
    

    
    if 'error_analysis' in analysis_results and 'error_reasons' in analysis_results['error_analysis']:
        error_reasons_df = analysis_results['error_analysis']['error_reasons']
        categorized_errors, category_details = categorize_error_reasons(error_reasons_df)
        
        if categorized_errors is not None and len(categorized_errors) > 0:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Horizontal bar chart for error categories
                fig_error_cat = px.bar(
                    categorized_errors,
                    x='Count',
                    y='Category',
                    orientation='h',
                    title="Error Categories (Grouped)",
                    color='Count',
                    color_continuous_scale='Reds'
                )
                fig_error_cat.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_error_cat, config={'displayModeBar': False})
            
            with col2:
                # Pie chart for error category distribution
                fig_error_pie = px.pie(
                    categorized_errors,
                    values='Count',
                    names='Category',
                    title="Error Category Distribution")
                st.plotly_chart(fig_error_pie, config={'displayModeBar': False})
            
            # Source and Asset Type breakdown for errors
            st.subheader("🔗 Error Distribution by Source and Asset Type")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Errors by source
                if 'error_by_source' in analysis_results['error_analysis']:
                    error_by_source = analysis_results['error_analysis']['error_by_source'].copy()
                    
                    # Parse source names to get display names
                    if 'Display_Name' not in error_by_source.columns:
                        parsed_info = error_by_source['Source'].apply(parse_source_info)
                        error_by_source['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
                    
                    fig_source_errors = px.bar(
                        error_by_source,
                        x='Display_Name',
                        y='Error Count',
                        title="Errors by Source",
                        color='Error Count',
                        color_continuous_scale='Reds'
                    )
                    fig_source_errors.update_layout(xaxis_tickangle=0)
                    st.plotly_chart(fig_source_errors, config={'displayModeBar': False})
                    
                    st.dataframe(
                        error_by_source.style.format({
                            'Error Count': '{:,}',
                            'Percentage': '{:.1f}%'
                        }),
                        width='stretch'
                    )
            
            with col2:
                # Errors by asset type
                if 'error_by_asset_type' in analysis_results['error_analysis']:
                    error_by_asset_type = analysis_results['error_analysis']['error_by_asset_type']
                    
                    fig_asset_errors = px.pie(
                        error_by_asset_type,
                        values='Error Count',
                        names='Asset Type',
                        title="Errors by Asset Type")
                    st.plotly_chart(fig_asset_errors, config={'displayModeBar': False})
                    
                    st.dataframe(
                        error_by_asset_type.style.format({
                            'Error Count': '{:,}',
                            'Percentage': '{:.1f}%'
                        }),
                        width='stretch'
                    )
            
            # Error categories with clickable details
            st.subheader("📋 Error Categories - Click to View Details")
            
            for _, row in categorized_errors.iterrows():
                category = row['Category']
                count = row['Count']
                percentage = row['Percentage']
                
                with st.expander(f"🔍 {category} - {count:,} errors ({percentage:.1f}%)"):
                    if category in category_details:
                        details_df = category_details[category]
                        
                        st.markdown("**Specific Error Reasons:**")
                        
                        # Show each error reason as clickable expandable
                        for _, error_row in details_df.iterrows():
                            error_reason = error_row['Error Reason']
                            error_count = error_row['Count']
                            
                            with st.expander(f"🔍 {error_reason} - {error_count:,} occurrences"):
                                # Get all assets with this specific error
                                assets_with_error = full_errors_df[full_errors_df['ReasonForError'] == error_reason].copy()
                                
                                if len(assets_with_error) > 0:
                                    # Show asset details
                                    st.markdown("**Assets with this error:**")
                                    
                                    # Create a clean display of assets
                                    asset_display = assets_with_error[['Asset', 'Source', 'AssetType', 'CampaignName', 'AdGroups', 'ErrorFromAdsGeneration']].copy()
                                    
                                    # Parse source names for better display
                                    if 'Display_Name' not in asset_display.columns:
                                        parsed_info = asset_display['Source'].apply(parse_source_info)
                                        asset_display['Display_Name'] = [info[1] if info[0] != 'Other' else info[1] for info in parsed_info]
                                    
                                    # Replace original Source with Display_Name and rename columns
                                    if 'Display_Name' in asset_display.columns:
                                        asset_display = asset_display.drop(columns=['Source'])
                                        asset_display = asset_display.rename(columns={'Display_Name': 'Source'})
                                    
                                    asset_display = asset_display.rename(columns={
                                        'AssetType': 'Asset Type',
                                        'CampaignName': 'Campaign',
                                        'AdGroups': 'Ad Group',
                                        'ErrorFromAdsGeneration': 'Error Type'
                                    })
                                    
                                    # Replace Error Type values for clarity
                                    asset_display['Error Type'] = asset_display['Error Type'].map({
                                        'Yes': 'Ads Generation',
                                        'No': 'Ads Review'
                                    })
                                    
                                    # Display the assets table
                                    st.dataframe(
                                        asset_display[['Asset', 'Source', 'Asset Type', 'Campaign', 'Ad Group', 'Error Type']],
                                        width='stretch',
                                        height=min(400, len(asset_display) * 35 + 50)
                                    )
                                    
                                    # Show summary stats
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Total Assets", len(asset_display))
                                    with col2:
                                        ads_gen_count = len(asset_display[asset_display['Error Type'] == 'Ads Generation'])
                                        st.metric("Ads Generation", ads_gen_count)
                                    with col3:
                                        ads_review_count = len(asset_display[asset_display['Error Type'] == 'Ads Review'])
                                        st.metric("Ads Review", ads_review_count)
                                else:
                                    st.info("No asset details available for this error.")

                    else:
                        st.info("No detailed breakdown available for this category.")
        else:
            st.info("No error categorization available")
    else:
        st.info("No error analysis data available")

def display_prompts_analysis(analysis_results):
    """Display prompts performance analysis with configuration context"""
    st.subheader("🧪 Prompts Performance Analysis")
    
    if 'prompts_analysis' not in analysis_results:
        st.info("📋 No prompts analysis available. Make sure your Excel file has a 'Prompts' tab with configuration variables.")
        st.markdown("""
        ### Required Configuration Variables in Prompts Tab:
        - `MaximumNumberOfAdsToGeneratePerPrompt`: How many headlines to generate per prompt
        - `MaximumNumberOfDescriptionsToGeneratePerPrompt`: How many descriptions to generate per prompt  
        - `NumberOfHeadlinesPerPrompt`: How many headlines to select per prompt (target)
        - `NumberOfDescriptionsPerPrompt`: How many descriptions to select per prompt (target)
        """)
        return
    
    prompts_data = analysis_results['prompts_analysis']
    
    if len(prompts_data['prompt_performance']) == 0:
        st.warning("⚠️ No prompt data found in the source names. Make sure your sources contain 'Prompt #X' format.")
        return
    
    # Define gap formatting functions (used throughout the analysis)
    def format_generation_gap(value):
        if value > 0:
            return f"{value}"  # Under-generated (positive) - show as is
        elif value < 0:
            return f"{abs(value)}"  # Over-generated (negative) - show as positive number
        else:
            return "0"  # Exact match
    
    def format_selection_gap(value):
        if value < 0:
            return f"{abs(value)}"  # Show shortage as positive number
        else:
            return "0"  # Show 0 for sufficient assets
    
    # Define color formatting functions
    def color_gap(val):
        # This function will be replaced by a more sophisticated approach
        return ''
    
    def color_selection_gap(val):
        if isinstance(val, str) and val != '0':
            return 'color: red'  # Any shortage shown in red
        return ''
    
    # Display configuration
    st.markdown("### 📋 Configuration Settings")
    prompt_configs = prompts_data['prompt_configs']
    
    if prompt_configs:
        # Show per-prompt configuration
        config_df_data = []
        for prompt_num, config in sorted(prompt_configs.items()):
            config_df_data.append({
                'Prompt': f'Prompt #{prompt_num}',
                'Max Headlines to Generate': config.get('MaximumNumberOfAdsToGeneratePerPrompt', 'Not Set'),
                'Max Descriptions to Generate': config.get('MaximumNumberOfDescriptionsToGeneratePerPrompt', 'Not Set'),
                'Target Headlines to Select': config.get('NumberOfHeadlinesPerPrompt', 'Not Set'),
                'Target Descriptions to Select': config.get('NumberOfDescriptionsPerPrompt', 'Not Set')
            })
        
        config_df = pd.DataFrame(config_df_data)
        st.dataframe(config_df, width='stretch')
        
        st.info(f"📋 Configuration loaded for {len(prompt_configs)} prompts. Each row in your Prompts tab represents a different prompt configuration.")
    else:
        st.info("No configuration data available")
    
    st.markdown("---")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        available_prompts = sorted(prompts_data['prompt_performance']['Prompt Number'].unique())
        # Format prompt numbers as "Prompt #X"
        prompt_options = [f"Prompt #{p}" for p in available_prompts]
        selected_prompt_labels = st.multiselect(
            "Filter by Prompt:",
            options=prompt_options,
            default=prompt_options,
            key="prompts_filter"
        )
        # Convert back to numbers
        selected_prompts = [safe_int_convert(p.split('#')[1], 999) for p in selected_prompt_labels]
    
    with col2:
        available_asset_types = prompts_data['prompt_performance']['Asset Type'].unique()
        selected_asset_types = st.multiselect(
            "Filter by Asset Type:",
            options=available_asset_types,
            default=available_asset_types,
            key="prompts_asset_filter"
        )
    
    with col3:
        if len(prompts_data['campaign_prompt_analysis']) > 0:
            available_campaigns = prompts_data['campaign_prompt_analysis']['Campaign Name'].unique()
            selected_campaigns = st.multiselect(
                "Filter by Campaign:",
                options=available_campaigns,
                default=[],
                key="prompts_campaign_filter",
                help="Leave empty to show all campaigns"
            )
        else:
            selected_campaigns = []
    
    with col4:
        performance_filter = st.selectbox(
            "Performance Filter:",
            options=["All", "Over Generated", "Under Generated", "Over Selected", "Under Selected"],
            key="performance_filter",
            help="Filter by generation/selection performance"
        )
    
    # Filter data
    filtered_prompt_perf = prompts_data['prompt_performance'].copy()
    filtered_adgroup_analysis = prompts_data['adgroup_prompt_analysis'].copy()
    filtered_campaign_analysis = prompts_data['campaign_prompt_analysis'].copy()
    
    if selected_prompts:
        filtered_prompt_perf = filtered_prompt_perf[filtered_prompt_perf['Prompt Number'].isin(selected_prompts)]
        filtered_adgroup_analysis = filtered_adgroup_analysis[filtered_adgroup_analysis['Prompt Number'].isin(selected_prompts)]
        filtered_campaign_analysis = filtered_campaign_analysis[filtered_campaign_analysis['Prompt Number'].isin(selected_prompts)]
    
    if selected_asset_types:
        filtered_prompt_perf = filtered_prompt_perf[filtered_prompt_perf['Asset Type'].isin(selected_asset_types)]
        filtered_adgroup_analysis = filtered_adgroup_analysis[filtered_adgroup_analysis['Asset Type'].isin(selected_asset_types)]
        filtered_campaign_analysis = filtered_campaign_analysis[filtered_campaign_analysis['Asset Type'].isin(selected_asset_types)]
    
    if selected_campaigns:
        filtered_adgroup_analysis = filtered_adgroup_analysis[filtered_adgroup_analysis['Campaign Name'].isin(selected_campaigns)]
        filtered_campaign_analysis = filtered_campaign_analysis[filtered_campaign_analysis['Campaign Name'].isin(selected_campaigns)]
    
    # Apply performance filter to ad group analysis
    if performance_filter != "All" and len(filtered_adgroup_analysis) > 0:
        if performance_filter == "Over Generated":
            filtered_adgroup_analysis = filtered_adgroup_analysis[filtered_adgroup_analysis['Generation_Gap'] > 0]
        elif performance_filter == "Under Generated":
            filtered_adgroup_analysis = filtered_adgroup_analysis[filtered_adgroup_analysis['Generation_Gap'] < 0]
        elif performance_filter == "Over Selected":
            filtered_adgroup_analysis = filtered_adgroup_analysis[filtered_adgroup_analysis['Selection_Gap'] > 0]
        elif performance_filter == "Under Selected":
            filtered_adgroup_analysis = filtered_adgroup_analysis[filtered_adgroup_analysis['Selection_Gap'] < 0]
    
    # Overall Prompt Performance
    st.markdown("### 📊 Overall Prompt Performance")
    
    if len(filtered_prompt_perf) > 0:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Create performance chart with Prompt # labels
            chart_data = filtered_prompt_perf.copy()
            chart_data['Prompt Label'] = chart_data['Prompt Number'].apply(lambda x: f'Prompt #{x}')
            
            fig = px.bar(
                chart_data,
                x='Prompt Label',
                y='Total Generated',
                color='Asset Type',
                title="Assets Generated by Prompt",
                text='Results Assets'
            )
            fig.update_traces(textposition='inside')
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        with col2:
            # Success rate chart
            fig_success = px.bar(
                chart_data,
                x='Prompt Label',
                y='Success Rate %',
                color='Asset Type',
                title="Success Rate by Prompt",
                text='Success Rate %'
            )
            fig_success.update_traces(textposition='inside')
            fig_success.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig_success, use_container_width=True, config={'displayModeBar': False})
    
    
    # Campaign Level Summary
    if len(filtered_campaign_analysis) > 0:
        combined_analysis = filtered_adgroup_analysis.groupby(['Campaign Name', 'Ad Group', 'Asset Type']).agg({
            'Total Generated': 'sum',
            'Results Assets': 'sum',
            'Errors Count': 'sum',
            'Max_To_Generate': 'sum',  # Sum max generation across all prompts (each prompt can have different values)
            'Target_Assets': 'sum'  # Sum target across all prompts
        }).reset_index()
        
        # Calculate generation gap - Sum of Max Generation across all prompts MINUS Total Generated
        # Max_To_Generate is already summed in the aggregation above
        # Positive = under-generated (red), Negative = over-generated (green)
        combined_analysis['Generation_Gap'] = combined_analysis['Max_To_Generate'] - combined_analysis['Total Generated']
        
        # For selection gap, we need to account for default assets
        # Get default assets count per ad group + asset type
        default_assets_data = prompts_data.get('default_assets_analysis', pd.DataFrame())
        if len(default_assets_data) > 0:
            default_counts = default_assets_data.groupby(['Campaign Name', 'Ad Group', 'Asset Type'])['Total Default Assets'].sum().reset_index()
            combined_analysis = combined_analysis.merge(
                default_counts, 
                on=['Campaign Name', 'Ad Group', 'Asset Type'], 
                how='left'
            )
            combined_analysis['Total Default Assets'] = combined_analysis['Total Default Assets'].fillna(0)
        else:
            combined_analysis['Total Default Assets'] = 0
        
        # Calculate available assets for selection (Results + Defaults)
        combined_analysis['Available for Selection'] = combined_analysis['Results Assets'] + combined_analysis['Total Default Assets']
        combined_analysis['Selection_Gap'] = combined_analysis['Available for Selection'] - combined_analysis['Target_Assets']
        
        # Calculate success rate
        combined_analysis['Success Rate %'] = (combined_analysis['Results Assets'] / combined_analysis['Total Generated'] * 100).round(2)
        
    st.markdown("---")
    
    # Campaign Level Summary
    if len(filtered_campaign_analysis) > 0:
        st.markdown("### 📊 Campaign Level Summary")
        
        # Format the display data with Prompt # labels
        display_campaign_data = filtered_campaign_analysis.copy()
        display_campaign_data['Prompt'] = display_campaign_data['Prompt Number'].apply(lambda x: f'Prompt #{x}')
        
        st.dataframe(
            display_campaign_data[['Campaign Name', 'Prompt', 'Asset Type', 
                                 'Total Generated', 'Results Assets', 'Success Rate %', 'Ad Groups Count']],
            width='stretch'
        )
        
        # Performance insights
        st.markdown("#### 💡 Performance Insights")
        
        # Calculate insights
        under_generated = filtered_adgroup_analysis[filtered_adgroup_analysis['Generation_Gap'] < 0]
        under_selected = filtered_adgroup_analysis[filtered_adgroup_analysis['Selection_Gap'] < 0]
        
        # Create hierarchical expandable sections for different performance categories
        # Row 1: Under-Generated Assets (full width)
        if len(under_generated) > 0:
            # Calculate unique ad group counts and asset type breakdown
            unique_adgroups = under_generated.groupby(['Campaign Name', 'Ad Group']).size().shape[0]
            headlines_count = len(under_generated[under_generated['Asset Type'].str.contains('headline', case=False, na=False)])
            descriptions_count = len(under_generated[under_generated['Asset Type'].str.contains('description', case=False, na=False)])
            
            st.warning(f"⚠️ {len(under_generated)} records under-generated assets across {unique_adgroups} unique campaign-adgroup combinations ({headlines_count} headlines, {descriptions_count} descriptions)")
            with st.expander("View Under-Generated Assets"):
                # Create hierarchical summary by Campaign + Ad Group
                under_gen_summary = under_generated.groupby(['Campaign Name', 'Ad Group']).agg({
                    'Total Generated': 'sum',
                    'Results Assets': 'sum', 
                    'Errors Count': 'sum',
                    'Generation_Gap': 'sum',  # Sum the gaps
                    'Max_To_Generate': 'sum'  # Sum max generation across all prompts
                }).reset_index()
                
                under_gen_summary['Records Count'] = under_generated.groupby(['Campaign Name', 'Ad Group']).size().values
                under_gen_summary['Success Rate %'] = (under_gen_summary['Results Assets'] / under_gen_summary['Total Generated'] * 100).round(2)
                
                # Calculate Generation Gap similar to Combined Ad Group Analysis
                under_gen_summary['Generation Gap'] = under_gen_summary['Max_To_Generate'] - under_gen_summary['Total Generated']
                
                st.markdown("**📋 Campaign & Ad Group Summary**")
                
                # Add pagination for summary table
                summary_page_size = st.selectbox("Rows per page (Summary)", [10, 25, 50], index=1, key="under_gen_summary_page_size")
                total_summary_rows = len(under_gen_summary)
                total_summary_pages = (total_summary_rows - 1) // summary_page_size + 1 if total_summary_rows > 0 else 1
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    summary_current_page = st.number_input(
                        f"Page (1-{total_summary_pages})",
                        min_value=1,
                        max_value=total_summary_pages,
                        value=1,
                        key="under_gen_summary_current_page"
                    )
                with col2:
                    st.info(f"Showing {total_summary_rows:,} campaign-adgroup combinations across {total_summary_pages} pages")
                
                # Paginate summary data
                summary_start_idx = (summary_current_page - 1) * summary_page_size
                summary_end_idx = min(summary_start_idx + summary_page_size, total_summary_rows)
                paginated_summary = under_gen_summary.iloc[summary_start_idx:summary_end_idx]
                
                # Style the summary table with red highlighting for Generation Gap
                def style_summary_generation_gap(val):
                    if isinstance(val, (int, float)) and val != 0:
                        return 'color: red'
                    return ''
                
                summary_styled = paginated_summary[['Campaign Name', 'Ad Group', 'Records Count', 'Total Generated', 
                                                  'Results Assets', 'Errors Count', 'Success Rate %', 'Generation Gap']].style.applymap(
                    style_summary_generation_gap, subset=['Generation Gap']
                )
                
                st.dataframe(summary_styled, width='stretch', height=300)
                
                # Detailed breakdown by asset type and prompt
                st.markdown("**🔍 Detailed Breakdown by Asset Type & Prompt**")
                
                # Add filters for detailed breakdown
                col1, col2, col3 = st.columns(3)
                with col1:
                    campaigns_list = ['All'] + sorted(under_generated['Campaign Name'].unique().tolist())
                    selected_detail_campaign = st.selectbox("Filter by Campaign", campaigns_list, key="under_gen_detail_campaign")
                
                with col2:
                    if selected_detail_campaign != 'All':
                        adgroups_list = ['All'] + sorted(under_generated[under_generated['Campaign Name'] == selected_detail_campaign]['Ad Group'].unique().tolist())
                    else:
                        adgroups_list = ['All'] + sorted(under_generated['Ad Group'].unique().tolist())
                    selected_detail_adgroup = st.selectbox("Filter by Ad Group", adgroups_list, key="under_gen_detail_adgroup")
                
                with col3:
                    max_sections = st.selectbox("Max sections to show", [5, 10, 20, 50], index=1, key="under_gen_max_sections")
                
                # Apply filters
                filtered_under_gen = under_generated.copy()
                if selected_detail_campaign != 'All':
                    filtered_under_gen = filtered_under_gen[filtered_under_gen['Campaign Name'] == selected_detail_campaign]
                if selected_detail_adgroup != 'All':
                    filtered_under_gen = filtered_under_gen[filtered_under_gen['Ad Group'] == selected_detail_adgroup]
                
                # Limit the number of sections to prevent UI overload
                grouped_data = list(filtered_under_gen.groupby(['Campaign Name', 'Ad Group']))
                limited_groups = grouped_data[:max_sections]
                
                if len(grouped_data) > max_sections:
                    st.warning(f"⚠️ Showing {max_sections} of {len(grouped_data)} campaign-adgroup combinations. Use filters to see specific ones.")
                
                # Group by Campaign + Ad Group + Asset Type for second level
                for (campaign, adgroup), group_data in limited_groups:
                    with st.expander(f"📁 {campaign} → {adgroup} ({len(group_data)} records)"):
                        # Asset type summary
                        asset_summary = group_data.groupby('Asset Type').agg({
                            'Total Generated': 'sum',
                            'Results Assets': 'sum',
                            'Errors Count': 'sum',
                            'Generation_Gap': 'sum'
                        }).reset_index()
                        asset_summary['Records Count'] = group_data.groupby('Asset Type').size().values
                        
                        st.markdown("**Asset Type Summary:**")
                        
                        # Style asset summary with red highlighting for negative gaps
                        def style_negative_values_under_gen(val):
                            if isinstance(val, (int, float)) and val < 0:
                                return 'color: red'
                            return ''
                        
                        asset_summary_styled = asset_summary.style.applymap(
                            style_negative_values_under_gen, subset=['Generation_Gap']
                        )
                        
                        st.dataframe(asset_summary_styled, width='stretch')
                        
                        # Individual prompt details
                        st.markdown("**Individual Prompt Details:**")
                        prompt_display = group_data.copy()
                        prompt_display['Prompt'] = prompt_display['Prompt Number'].apply(lambda x: f'Prompt #{x}')
                        prompt_display['Generation Gap Display'] = prompt_display['Generation_Gap'].apply(format_generation_gap)
                        
                        # Style individual prompt details with red highlighting
                        def style_prompt_gaps(val):
                            if isinstance(val, str) and val != '0':
                                return 'color: red'
                            return ''
                        
                        # Sort by Asset Type (Headlines first), then Prompt Number
                        prompt_display['Asset_Type_Order'] = prompt_display['Asset Type'].apply(lambda x: 0 if 'Headline' in str(x) else 1)
                        prompt_sorted = prompt_display.sort_values(['Asset_Type_Order', 'Prompt Number'])
                        
                        # Style the prompt details dataframe
                        prompt_styled = prompt_sorted[['Prompt', 'Asset Type', 'Max_To_Generate', 'Total Generated', 
                                                      'Results Assets', 'Errors Count', 'Success Rate %', 'Generation Gap Display']].style.applymap(
                            style_prompt_gaps, subset=['Generation Gap Display']
                        )
                        
                        st.dataframe(prompt_styled, width='stretch')
        else:
            st.success("✅ All records met generation targets!")
        
        # Row 2: Over-Generated Assets (full width) - based on Results Assets vs Max to Generate
        # Calculate Results-based generation gap: Results Assets - Max to Generate
        filtered_adgroup_analysis['Results_Generation_Gap'] = filtered_adgroup_analysis['Results Assets'] - filtered_adgroup_analysis['Max_To_Generate']
        over_generated = filtered_adgroup_analysis[filtered_adgroup_analysis['Results_Generation_Gap'] > 0]
        if len(over_generated) > 0:
            # Calculate unique ad group counts and asset type breakdown for over-generated
            over_unique_adgroups = over_generated.groupby(['Campaign Name', 'Ad Group']).size().shape[0]
            over_headlines_count = len(over_generated[over_generated['Asset Type'].str.contains('headline', case=False, na=False)])
            over_descriptions_count = len(over_generated[over_generated['Asset Type'].str.contains('description', case=False, na=False)])
            
            st.info(f"ℹ️ {len(over_generated)} records over-generated assets across {over_unique_adgroups} unique campaign-adgroup combinations ({over_headlines_count} headlines, {over_descriptions_count} descriptions)")
            with st.expander("View Over-Generated Assets"):
                # Create hierarchical summary by Campaign + Ad Group
                over_gen_summary = over_generated.groupby(['Campaign Name', 'Ad Group']).agg({
                    'Total Generated': 'sum',
                    'Results Assets': 'sum',
                    'Errors Count': 'sum',
                    'Results_Generation_Gap': 'sum',  # Sum the results gaps
                    'Max_To_Generate': 'sum'  # Sum max generation across all prompts
                }).reset_index()
                
                over_gen_summary['Records Count'] = over_generated.groupby(['Campaign Name', 'Ad Group']).size().values
                over_gen_summary['Success Rate %'] = (over_gen_summary['Results Assets'] / over_gen_summary['Total Generated'] * 100).round(2)
                
                # Calculate Generation Gap (Results Assets - Max to Generate)
                over_gen_summary['Generation Gap'] = over_gen_summary['Results Assets'] - over_gen_summary['Max_To_Generate']
                
                st.markdown("**📋 Campaign & Ad Group Summary**")
                
                # Add pagination for over-generated summary table
                over_summary_page_size = st.selectbox("Rows per page (Summary)", [10, 25, 50], index=1, key="over_gen_summary_page_size")
                total_over_summary_rows = len(over_gen_summary)
                total_over_summary_pages = (total_over_summary_rows - 1) // over_summary_page_size + 1 if total_over_summary_rows > 0 else 1
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    over_summary_current_page = st.number_input(
                        f"Page (1-{total_over_summary_pages})",
                        min_value=1,
                        max_value=total_over_summary_pages,
                        value=1,
                        key="over_gen_summary_current_page"
                    )
                with col2:
                    st.info(f"Showing {total_over_summary_rows:,} campaign-adgroup combinations across {total_over_summary_pages} pages")
                
                # Paginate over-generated summary data
                over_summary_start_idx = (over_summary_current_page - 1) * over_summary_page_size
                over_summary_end_idx = min(over_summary_start_idx + over_summary_page_size, total_over_summary_rows)
                paginated_over_summary = over_gen_summary.iloc[over_summary_start_idx:over_summary_end_idx]
                
                # Style the over-generated summary table with red highlighting for Generation Gap
                def style_over_summary_generation_gap(val):
                    if isinstance(val, (int, float)) and val != 0:
                        return 'color: red'
                    return ''
                
                over_summary_styled = paginated_over_summary[['Campaign Name', 'Ad Group', 'Records Count', 'Total Generated', 
                                                            'Results Assets', 'Errors Count', 'Success Rate %', 'Generation Gap']].style.applymap(
                    style_over_summary_generation_gap, subset=['Generation Gap']
                )
                
                st.dataframe(over_summary_styled, width='stretch', height=300)
                
                # Detailed breakdown by asset type and prompt
                st.markdown("**🔍 Detailed Breakdown by Asset Type & Prompt**")
                
                # Add filters for over-generated detailed breakdown
                col1, col2, col3 = st.columns(3)
                with col1:
                    over_campaigns_list = ['All'] + sorted(over_generated['Campaign Name'].unique().tolist())
                    selected_over_detail_campaign = st.selectbox("Filter by Campaign", over_campaigns_list, key="over_gen_detail_campaign")
                
                with col2:
                    if selected_over_detail_campaign != 'All':
                        over_adgroups_list = ['All'] + sorted(over_generated[over_generated['Campaign Name'] == selected_over_detail_campaign]['Ad Group'].unique().tolist())
                    else:
                        over_adgroups_list = ['All'] + sorted(over_generated['Ad Group'].unique().tolist())
                    selected_over_detail_adgroup = st.selectbox("Filter by Ad Group", over_adgroups_list, key="over_gen_detail_adgroup")
                
                with col3:
                    over_max_sections = st.selectbox("Max sections to show", [5, 10, 20, 50], index=1, key="over_gen_max_sections")
                
                # Apply filters for over-generated
                filtered_over_gen = over_generated.copy()
                if selected_over_detail_campaign != 'All':
                    filtered_over_gen = filtered_over_gen[filtered_over_gen['Campaign Name'] == selected_over_detail_campaign]
                if selected_over_detail_adgroup != 'All':
                    filtered_over_gen = filtered_over_gen[filtered_over_gen['Ad Group'] == selected_over_detail_adgroup]
                
                # Limit the number of sections to prevent UI overload
                over_grouped_data = list(filtered_over_gen.groupby(['Campaign Name', 'Ad Group']))
                over_limited_groups = over_grouped_data[:over_max_sections]
                
                if len(over_grouped_data) > over_max_sections:
                    st.warning(f"⚠️ Showing {over_max_sections} of {len(over_grouped_data)} campaign-adgroup combinations. Use filters to see specific ones.")
                
                # Group by Campaign + Ad Group for second level
                for (campaign, adgroup), group_data in over_limited_groups:
                    with st.expander(f"📁 {campaign} → {adgroup} ({len(group_data)} records)"):
                        # Asset type summary
                        asset_summary = group_data.groupby('Asset Type').agg({
                            'Total Generated': 'sum',
                            'Results Assets': 'sum',
                            'Errors Count': 'sum',
                            'Results_Generation_Gap': 'sum'
                        }).reset_index()
                        asset_summary['Records Count'] = group_data.groupby('Asset Type').size().values
                        
                        st.markdown("**Asset Type Summary:**")
                        
                        # Style asset summary with red highlighting for negative gaps
                        def style_negative_values_over_gen(val):
                            if isinstance(val, (int, float)) and val < 0:
                                return 'color: red'
                            return ''
                        
                        asset_summary_styled_over = asset_summary.style.applymap(
                            style_negative_values_over_gen, subset=['Results_Generation_Gap']
                        )
                        
                        st.dataframe(asset_summary_styled_over, width='stretch')
                        
                        # Individual prompt details
                        st.markdown("**Individual Prompt Details:**")
                        prompt_display = group_data.copy()
                        prompt_display['Prompt'] = prompt_display['Prompt Number'].apply(lambda x: f'Prompt #{x}')
                        prompt_display['Results Gap'] = prompt_display['Results_Generation_Gap'].apply(format_generation_gap)
                        
                        # Style individual prompt details with red highlighting
                        def style_prompt_gaps_over(val):
                            if isinstance(val, str) and val != '0':
                                return 'color: red'
                            return ''
                        
                        # Sort by Asset Type (Headlines first), then Prompt Number
                        prompt_display['Asset_Type_Order'] = prompt_display['Asset Type'].apply(lambda x: 0 if 'Headline' in str(x) else 1)
                        prompt_sorted = prompt_display.sort_values(['Asset_Type_Order', 'Prompt Number'])
                        
                        # Style the prompt details dataframe
                        prompt_styled_over = prompt_sorted[['Prompt', 'Asset Type', 'Max_To_Generate', 'Total Generated', 
                                                          'Results Assets', 'Errors Count', 'Success Rate %', 'Results Gap']].style.applymap(
                            style_prompt_gaps_over, subset=['Results Gap']
                        )
                        
                        st.dataframe(prompt_styled_over, width='stretch')
        else:
            st.success("✅ No over-generated assets found!")
        
        # Row 3: Under-Selected Assets
        if len(under_selected) > 0:
            # Calculate unique ad group counts and asset type breakdown for under-selected
            under_sel_unique_adgroups = under_selected.groupby(['Campaign Name', 'Ad Group']).size().shape[0]
            under_sel_headlines_count = len(under_selected[under_selected['Asset Type'].str.contains('headline', case=False, na=False)])
            under_sel_descriptions_count = len(under_selected[under_selected['Asset Type'].str.contains('description', case=False, na=False)])
            
            st.warning(f"⚠️ {len(under_selected)} records insufficient for selection across {under_sel_unique_adgroups} unique campaign-adgroup combinations ({under_sel_headlines_count} headlines, {under_sel_descriptions_count} descriptions)")
            with st.expander("View Under-Selected Assets"):
                # Create hierarchical summary by Campaign + Ad Group
                under_sel_summary = under_selected.groupby(['Campaign Name', 'Ad Group']).agg({
                    'Total Generated': 'sum',
                    'Results Assets': 'sum',
                    'Errors Count': 'sum',
                    'Target_Assets': 'sum',
                    'Selection_Gap': 'sum'  # Sum the selection gaps
                }).reset_index()
                
                under_sel_summary['Records Count'] = under_selected.groupby(['Campaign Name', 'Ad Group']).size().values
                under_sel_summary['Success Rate %'] = (under_sel_summary['Results Assets'] / under_sel_summary['Total Generated'] * 100).round(2)
                
                # Calculate Selection Gap (Target Assets - Results Assets, show as positive if shortage)
                under_sel_summary['Selection Gap'] = under_sel_summary['Target_Assets'] - under_sel_summary['Results Assets']
                under_sel_summary['Selection Gap'] = under_sel_summary['Selection Gap'].apply(lambda x: max(0, x))  # Show only positive shortages
                
                st.markdown("**📋 Campaign & Ad Group Summary**")
                
                # Add pagination for under-selected summary table
                under_sel_summary_page_size = st.selectbox("Rows per page (Summary)", [10, 25, 50], index=1, key="under_sel_summary_page_size")
                total_under_sel_summary_rows = len(under_sel_summary)
                total_under_sel_summary_pages = (total_under_sel_summary_rows - 1) // under_sel_summary_page_size + 1 if total_under_sel_summary_rows > 0 else 1
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    under_sel_summary_current_page = st.number_input(
                        f"Page (1-{total_under_sel_summary_pages})",
                        min_value=1,
                        max_value=total_under_sel_summary_pages,
                        value=1,
                        key="under_sel_summary_current_page"
                    )
                with col2:
                    st.info(f"Showing {total_under_sel_summary_rows:,} campaign-adgroup combinations across {total_under_sel_summary_pages} pages")
                
                # Paginate under-selected summary data
                under_sel_summary_start_idx = (under_sel_summary_current_page - 1) * under_sel_summary_page_size
                under_sel_summary_end_idx = min(under_sel_summary_start_idx + under_sel_summary_page_size, total_under_sel_summary_rows)
                paginated_under_sel_summary = under_sel_summary.iloc[under_sel_summary_start_idx:under_sel_summary_end_idx]
                
                # Style the under-selected summary table with red highlighting for Selection Gap
                def style_under_sel_summary_selection_gap(val):
                    if isinstance(val, (int, float)) and val != 0:
                        return 'color: red'
                    return ''
                
                under_sel_summary_styled = paginated_under_sel_summary[['Campaign Name', 'Ad Group', 'Records Count', 'Total Generated', 
                                                                      'Results Assets', 'Target_Assets', 'Errors Count', 'Success Rate %', 'Selection Gap']].style.applymap(
                    style_under_sel_summary_selection_gap, subset=['Selection Gap']
                )
                
                st.dataframe(under_sel_summary_styled, width='stretch', height=300)
                
                # Detailed breakdown by asset type and prompt
                st.markdown("**🔍 Detailed Breakdown by Asset Type & Prompt**")
                
                # Add filters for under-selected detailed breakdown
                col1, col2, col3 = st.columns(3)
                with col1:
                    under_sel_campaigns_list = ['All'] + sorted(under_selected['Campaign Name'].unique().tolist())
                    selected_under_sel_detail_campaign = st.selectbox("Filter by Campaign", under_sel_campaigns_list, key="under_sel_detail_campaign")
                
                with col2:
                    if selected_under_sel_detail_campaign != 'All':
                        under_sel_adgroups_list = ['All'] + sorted(under_selected[under_selected['Campaign Name'] == selected_under_sel_detail_campaign]['Ad Group'].unique().tolist())
                    else:
                        under_sel_adgroups_list = ['All'] + sorted(under_selected['Ad Group'].unique().tolist())
                    selected_under_sel_detail_adgroup = st.selectbox("Filter by Ad Group", under_sel_adgroups_list, key="under_sel_detail_adgroup")
                
                with col3:
                    under_sel_max_sections = st.selectbox("Max sections to show", [5, 10, 20, 50], index=1, key="under_sel_max_sections")
                
                # Apply filters for under-selected
                filtered_under_sel = under_selected.copy()
                if selected_under_sel_detail_campaign != 'All':
                    filtered_under_sel = filtered_under_sel[filtered_under_sel['Campaign Name'] == selected_under_sel_detail_campaign]
                if selected_under_sel_detail_adgroup != 'All':
                    filtered_under_sel = filtered_under_sel[filtered_under_sel['Ad Group'] == selected_under_sel_detail_adgroup]
                
                # Limit the number of sections to prevent UI overload
                under_sel_grouped_data = list(filtered_under_sel.groupby(['Campaign Name', 'Ad Group']))
                under_sel_limited_groups = under_sel_grouped_data[:under_sel_max_sections]
                
                if len(under_sel_grouped_data) > under_sel_max_sections:
                    st.warning(f"⚠️ Showing {under_sel_max_sections} of {len(under_sel_grouped_data)} campaign-adgroup combinations. Use filters to see specific ones.")
                
                # Group by Campaign + Ad Group for second level
                for (campaign, adgroup), group_data in under_sel_limited_groups:
                    with st.expander(f"📁 {campaign} → {adgroup} ({len(group_data)} records)"):
                        # Asset type summary
                        asset_summary = group_data.groupby('Asset Type').agg({
                            'Total Generated': 'sum',
                            'Results Assets': 'sum',
                            'Errors Count': 'sum',
                            'Target_Assets': 'sum',
                            'Selection_Gap': 'sum'
                        }).reset_index()
                        asset_summary['Records Count'] = group_data.groupby('Asset Type').size().values
                        
                        st.markdown("**Asset Type Summary:**")
                        
                        # Style asset summary with red highlighting for negative gaps
                        def style_negative_values_under_sel(val):
                            if isinstance(val, (int, float)) and val < 0:
                                return 'color: red'
                            return ''
                        
                        asset_summary_styled_sel = asset_summary.style.applymap(
                            style_negative_values_under_sel, subset=['Selection_Gap']
                        )
                        
                        st.dataframe(asset_summary_styled_sel, width='stretch')
                        
                        # Individual prompt details
                        st.markdown("**Individual Prompt Details:**")
                        prompt_display = group_data.copy()
                        prompt_display['Prompt'] = prompt_display['Prompt Number'].apply(lambda x: f'Prompt #{x}')
                        prompt_display['Selection Gap Display'] = prompt_display['Selection_Gap'].apply(format_selection_gap)
                        
                        # Style individual prompt details with red highlighting
                        def style_prompt_gaps_sel(val):
                            if isinstance(val, str) and val != '0':
                                return 'color: red'
                            return ''
                        
                        # Sort by Asset Type (Headlines first), then Prompt Number
                        prompt_display['Asset_Type_Order'] = prompt_display['Asset Type'].apply(lambda x: 0 if 'Headline' in str(x) else 1)
                        prompt_sorted = prompt_display.sort_values(['Asset_Type_Order', 'Prompt Number'])
                        
                        # Style the prompt details dataframe
                        prompt_styled_sel = prompt_sorted[['Prompt', 'Asset Type', 'Total Generated', 'Results Assets', 
                                                          'Target_Assets', 'Errors Count', 'Success Rate %', 'Selection Gap Display']].style.applymap(
                            style_prompt_gaps_sel, subset=['Selection Gap Display']
                        )
                        
                        st.dataframe(prompt_styled_sel, width='stretch')
        else:
            st.success("✅ All records have sufficient assets for selection!")
    
    st.markdown("---")
    
    # Default Assets Analysis
    st.markdown("### 🔧 Default Assets Analysis")
    st.caption("Ad groups using default assets that need attention")
    
    if 'default_assets_analysis' in prompts_data and len(prompts_data['default_assets_analysis']) > 0:
        default_assets_data = prompts_data['default_assets_analysis']
        
        # Apply campaign filter if selected
        filtered_default_assets = default_assets_data.copy()
        if selected_campaigns:
            filtered_default_assets = filtered_default_assets[filtered_default_assets['Campaign Name'].isin(selected_campaigns)]
        
        if len(filtered_default_assets) > 0:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_default_adgroups = filtered_default_assets.groupby(['Campaign Name', 'Ad Group']).size().shape[0]
                st.metric("Ad Groups with Default Assets", total_default_adgroups)
            
            with col2:
                total_default_assets = filtered_default_assets['Total Default Assets'].sum()
                st.metric("Total Default Assets", total_default_assets)
            
            with col3:
                total_asset_types = filtered_default_assets['Asset Type'].nunique()
                st.metric("Asset Types with Defaults", total_asset_types)
            
            with col4:
                total_campaigns = filtered_default_assets['Campaign Name'].nunique()
                st.metric("Campaigns with Defaults", total_campaigns)
            
            # Default assets table
            st.markdown("#### 📋 Ad Groups Using Default Assets")
            
            # Add asset type filter for default assets
            col1, col2 = st.columns(2)
            with col1:
                default_asset_types = filtered_default_assets['Asset Type'].unique()
                selected_default_asset_types = st.multiselect(
                    "Filter Default Asset Types:",
                    options=default_asset_types,
                    default=default_asset_types,
                    key="default_assets_filter"
                )
            
            with col2:
                default_sort_by = st.selectbox(
                    "Sort by",
                    options=['Campaign Name', 'Total Default Assets'],
                    key="default_assets_sort"
                )
            
            # Apply asset type filter
            if selected_default_asset_types:
                filtered_default_assets = filtered_default_assets[filtered_default_assets['Asset Type'].isin(selected_default_asset_types)]
            
            # Sort data
            sorted_default_data = filtered_default_assets.sort_values(default_sort_by, ascending=False)
            
            st.dataframe(
                sorted_default_data[['Campaign Name', 'Ad Group', 'Asset Type', 
                                   'Total Default Assets']],
                width='stretch',
                height=300
            )
            
            # Insights for default assets
            st.markdown("#### 💡 Default Assets Insights")
            
            high_default_usage = filtered_default_assets[filtered_default_assets['Total Default Assets'] >= 5]
            
            # Insights - Full width
            if len(high_default_usage) > 0:
                st.warning(f"⚠️ {len(high_default_usage)} ad groups have high default asset usage (≥5 assets)")
                with st.expander("View High Default Usage"):
                    st.dataframe(
                        high_default_usage[['Campaign Name', 'Ad Group', 'Asset Type', 'Total Default Assets']],
                        width='stretch'
                    )
            else:
                st.success("✅ No ad groups with excessive default asset usage")
        else:
            st.info("No default assets found for selected campaigns")
    else:
        st.success("✅ No default assets found - all assets are generated by prompts!")

def display_downloads(analysis_results):
    """Display download options with source and asset type data"""
    st.subheader("📥 Download Analysis Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🎯 Source Analysis")
        if st.button("Download Source Analysis", key="download_source"):
            csv = analysis_results['source_analysis'].to_csv(index=False)
            st.download_button(
                label="📊 Download CSV",
                data=csv,
                file_name=f"source_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="source_csv"
            )
        
        st.markdown("### 📦 Asset Type Analysis")
        if st.button("Download Asset Type Analysis", key="download_asset_type"):
            csv = analysis_results['asset_type_analysis'].to_csv(index=False)
            st.download_button(
                label="📊 Download CSV",
                data=csv,
                file_name=f"asset_type_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="asset_type_csv"
            )
    
    with col2:
        st.markdown("### 👥 Ad Group Analysis")
        if st.button("Download Ad Group Analysis", key="download_adgroup"):
            csv = analysis_results['adgroup_analysis'].to_csv(index=False)
            st.download_button(
                label="📊 Download CSV",
                data=csv,
                file_name=f"adgroup_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="adgroup_csv"
            )
        
        st.markdown("### 🔗 Source + Asset Type")
        if st.button("Download Source+Asset Combinations", key="download_source_asset"):
            csv = analysis_results['source_asset_analysis'].to_csv(index=False)
            st.download_button(
                label="📊 Download CSV",
                data=csv,
                file_name=f"source_asset_combinations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="source_asset_csv"
            )
    
    with col3:
        st.markdown("### ❌ Error Analysis")
        if 'error_analysis' in analysis_results and 'error_reasons' in analysis_results['error_analysis']:
            if st.button("Download Error Analysis", key="download_errors"):
                csv = analysis_results['error_analysis']['error_reasons'].to_csv(index=False)
                st.download_button(
                    label="📊 Download CSV",
                    data=csv,
                    file_name=f"error_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="error_csv"
                )
        
        st.markdown("### 🔍 Detailed Combinations")
        if st.button("Download Detailed Analysis", key="download_detailed"):
            csv = analysis_results['detailed_analysis'].to_csv(index=False)
            st.download_button(
                label="📊 Download CSV",
                data=csv,
                file_name=f"detailed_combinations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="detailed_csv"
            )
        
        # Prompts Analysis Downloads
        if 'prompts_analysis' in analysis_results:
            st.markdown("### 🧪 Prompts Analysis")
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button("Download Prompt Performance", key="download_prompt_perf"):
                    csv = analysis_results['prompts_analysis']['prompt_performance'].to_csv(index=False)
                    st.download_button(
                        label="📊 Download CSV",
                        data=csv,
                        file_name=f"prompt_performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="prompt_perf_csv"
                    )
            
            with col_b:
                if st.button("Download Ad Group Prompts", key="download_adgroup_prompts"):
                    csv = analysis_results['prompts_analysis']['adgroup_prompt_analysis'].to_csv(index=False)
                    st.download_button(
                        label="📊 Download CSV",
                        data=csv,
                        file_name=f"adgroup_prompts_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="adgroup_prompts_csv"
                    )
            
            with col_c:
                if 'default_assets_analysis' in analysis_results['prompts_analysis'] and len(analysis_results['prompts_analysis']['default_assets_analysis']) > 0:
                    if st.button("Download Default Assets", key="download_default_assets"):
                        csv = analysis_results['prompts_analysis']['default_assets_analysis'].to_csv(index=False)
                        st.download_button(
                            label="📊 Download CSV",
                            data=csv,
                            file_name=f"default_assets_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="default_assets_csv"
                        )

if __name__ == "__main__":
    main() 