import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import os
from datetime import datetime
import re
import traceback

def safe_int_convert(value, default=999):
    """Safely convert value to integer, handling floats and strings"""
    try:
        if pd.isna(value) or value is None or str(value).strip() == '':
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

def parse_source_for_prompt_number(source_name):
    """Extract prompt number from source name"""
    if pd.isna(source_name) or source_name == '':
        return None
    
    source_str = str(source_name)
    
    # Look for "Prompt #X" pattern
    if 'Prompt #' in source_str:
        try:
            prompt_part = source_str.split('Prompt #')[1].split('.')[0].strip()
            return safe_int_convert(prompt_part, None)
        except:
            return None
    
    return None

def analyze_default_assets(combined_df):
    """
    Analyze ad groups that use default assets
    """
    print("  📊 Starting default assets analysis...")
    
    try:
        # Filter for default assets (sources that don't contain "Model:" or "Prompt")
        default_assets_data = combined_df[
            (~combined_df['Source'].str.contains('Model:', na=False)) |
            (~combined_df['Source'].str.contains('Prompt', na=False))
        ].copy()
        
        print(f"  📊 Found {len(default_assets_data)} default asset records")
        
        if len(default_assets_data) == 0:
            print("  📊 No default assets found")
            return pd.DataFrame()
        
        # Group by Campaign, Ad Group, and Asset Type
        default_analysis = default_assets_data.groupby(['CampaignName', 'AdGroups', 'AssetType']).agg({
            'Asset': 'count',
            'DataSource': lambda x: (x == 'Results').sum()
        }).reset_index()
        
        # Note: Not including error counts and success rates for default assets as they don't make sense in this context
        
        # Rename columns for consistency
        default_analysis = default_analysis.rename(columns={
            'CampaignName': 'Campaign Name',
            'AdGroups': 'Ad Group',
            'AssetType': 'Asset Type',
            'Asset': 'Total Default Assets',
            'DataSource': 'Results Assets'
        })
        
        # Sort by Campaign Name, then Ad Group
        if len(default_analysis) > 0:
            default_analysis = default_analysis.sort_values(['Campaign Name', 'Ad Group', 'Asset Type'])
        else:
            print("  📊 No default assets data to sort")
        
        print(f"  📊 Default assets analysis completed: {len(default_analysis)} records")
        return default_analysis
        
    except Exception as e:
        print(f"  ❌ Error in default assets analysis: {e}")
        print(f"  ❌ Traceback: {traceback.format_exc()}")
        return pd.DataFrame()

def analyze_prompts_performance(combined_df, prompts_config):
    """
    Analyze prompt performance based on per-prompt configuration variables from Prompts tab
    Each row in prompts_config represents a different prompt configuration
    """
    print("  📊 Starting prompts performance analysis...")
    
    try:
        # Parse per-prompt configuration - each row is a different prompt
        prompt_configs = {}
        
        print(f"  📊 Processing {len(prompts_config)} prompt configurations...")
        
        for idx, row in prompts_config.iterrows():
            # Row 0 = Prompt #1, Row 1 = Prompt #2, etc. 
            # (pandas read_excel automatically handles headers, so row 0 is the first data row)
            prompt_num = idx + 1
            
            prompt_configs[prompt_num] = {
                'MaximumNumberOfAdsToGeneratePerPrompt': safe_int_convert(row.get('MaximumNumberOfAdsToGeneratePerPrompt'), 999),
                'MaximumNumberOfDescriptionsToGeneratePerPrompt': safe_int_convert(row.get('MaximumNumberOfDescriptionsToGeneratePerPrompt'), 999),
                'NumberOfHeadlinesPerPrompt': safe_int_convert(row.get('NumberOfHeadlinesPerPrompt'), 999),
                'NumberOfDescriptionsPerPrompt': safe_int_convert(row.get('NumberOfDescriptionsPerPrompt'), 999)
            }
        
        print(f"  📊 Parsed {len(prompt_configs)} prompt configurations")
        
        # Add prompt number to combined_df
        print("  📊 Extracting prompt numbers from source names...")
        combined_df_with_prompt = combined_df.copy()
        combined_df_with_prompt['PromptNumber'] = combined_df_with_prompt['Source'].apply(parse_source_for_prompt_number)
        
        # Filter only rows with valid prompt numbers
        prompt_data = combined_df_with_prompt[combined_df_with_prompt['PromptNumber'].notna()].copy()
        
        print(f"  📊 Found {len(prompt_data)} records with valid prompt numbers")
        
        if len(prompt_data) == 0:
            print("  📊 No prompt data found")
            return {
                'prompt_configs': prompt_configs,
                'prompt_performance': pd.DataFrame(),
                'adgroup_prompt_analysis': pd.DataFrame(),
                'campaign_prompt_analysis': pd.DataFrame(),
                'default_assets_analysis': pd.DataFrame()
            }
        
        print("  📊 Performing ad group prompt analysis...")
        # Analysis by Ad Group and Prompt
        adgroup_prompt_analysis = prompt_data.groupby(['CampaignName', 'AdGroups', 'PromptNumber', 'AssetType']).agg({
            'Asset': 'count',
            'DataSource': lambda x: (x == 'Results').sum()
        }).reset_index()
        
        adgroup_prompt_analysis['Errors Count'] = prompt_data.groupby(['CampaignName', 'AdGroups', 'PromptNumber', 'AssetType'])['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
        adgroup_prompt_analysis['Success Rate %'] = (adgroup_prompt_analysis['DataSource'] / adgroup_prompt_analysis['Asset'] * 100).round(2)
        
        print(f"  📊 Ad group prompt analysis: {len(adgroup_prompt_analysis)} records")

        
        # Apply configuration for both generation and selection targets
        def get_prompt_specific_config(row):
            prompt_num = safe_int_convert(row['PromptNumber'], 999)
            asset_type = str(row['AssetType'])
            
            if prompt_num in prompt_configs:
                config = prompt_configs[prompt_num]
                if 'headline' in asset_type.lower():
                    max_to_generate = safe_int_convert(config.get('MaximumNumberOfAdsToGeneratePerPrompt'), 999)
                    target_to_select = safe_int_convert(config.get('NumberOfHeadlinesPerPrompt'), 999)
                else:  # Description
                    max_to_generate = safe_int_convert(config.get('MaximumNumberOfDescriptionsToGeneratePerPrompt'), 999)
                    target_to_select = safe_int_convert(config.get('NumberOfDescriptionsPerPrompt'), 999)
            else:
                # Default values - use 999 to indicate missing config
                max_to_generate = 999
                target_to_select = 999
            
            return max_to_generate, target_to_select
        
        print("  📊 Applying prompt configurations...")
        # Apply the configuration - only if we have data
        if len(adgroup_prompt_analysis) > 0:
            config_values = adgroup_prompt_analysis.apply(get_prompt_specific_config, axis=1, result_type='expand')
            adgroup_prompt_analysis['Max_To_Generate'] = config_values[0]
            adgroup_prompt_analysis['Target_Assets'] = config_values[1]
            
            # Calculate gaps (actual - target)
            # Positive = over target, Negative = under target
            adgroup_prompt_analysis['Generation_Gap'] = adgroup_prompt_analysis['Asset'] - adgroup_prompt_analysis['Max_To_Generate']
            adgroup_prompt_analysis['Selection_Gap'] = adgroup_prompt_analysis['DataSource'] - adgroup_prompt_analysis['Target_Assets']
        else:
            print("  ⚠️ No ad group prompt data to configure")
            # Add empty columns for consistency
            adgroup_prompt_analysis['Max_To_Generate'] = []
            adgroup_prompt_analysis['Target_Assets'] = []
            adgroup_prompt_analysis['Generation_Gap'] = []
            adgroup_prompt_analysis['Selection_Gap'] = []
        
        adgroup_prompt_analysis = adgroup_prompt_analysis.rename(columns={
            'CampaignName': 'Campaign Name',
            'AdGroups': 'Ad Group',
            'PromptNumber': 'Prompt Number',
            'AssetType': 'Asset Type',
            'Asset': 'Total Generated',
            'DataSource': 'Results Assets'
        })
        
        # Sort by Campaign Name, Ad Group, Asset Type (Headlines first), then Prompt Number for better organization
        if len(adgroup_prompt_analysis) > 0:
            adgroup_prompt_analysis['Asset_Type_Order'] = adgroup_prompt_analysis['Asset Type'].apply(lambda x: 0 if 'Headline' in str(x) else 1)
            adgroup_prompt_analysis = adgroup_prompt_analysis.sort_values(['Campaign Name', 'Ad Group', 'Asset_Type_Order', 'Prompt Number'])
            adgroup_prompt_analysis = adgroup_prompt_analysis.drop(columns=['Asset_Type_Order'])
        else:
            print("  ⚠️ No ad group data to sort")
        
        print("  �� Performing overall prompt performance analysis...")
        # Overall prompt performance summary
        prompt_performance = prompt_data.groupby(['PromptNumber', 'AssetType']).agg({
            'Asset': 'count',
            'DataSource': lambda x: (x == 'Results').sum()
        }).reset_index()
        
        prompt_performance['Errors Count'] = prompt_data.groupby(['PromptNumber', 'AssetType'])['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
        prompt_performance['Success Rate %'] = (prompt_performance['DataSource'] / prompt_performance['Asset'] * 100).round(2)
        
        # Add per-prompt configuration context
        def get_prompt_config_values(row):
            # Handle float to int conversion safely
            prompt_num = safe_int_convert(row['PromptNumber'], 999)
            asset_type = str(row['AssetType'])
            
            if prompt_num in prompt_configs:
                config = prompt_configs[prompt_num]
                if 'headline' in asset_type.lower():
                    expected = safe_int_convert(config.get('MaximumNumberOfAdsToGeneratePerPrompt'), 999)
                    target = safe_int_convert(config.get('NumberOfHeadlinesPerPrompt'), 999)
                else:
                    expected = safe_int_convert(config.get('MaximumNumberOfDescriptionsToGeneratePerPrompt'), 999)
                    target = safe_int_convert(config.get('NumberOfDescriptionsPerPrompt'), 999)
            else:
                # Default values - use 999 to indicate missing config
                expected = 999
                target = 999
            
            return expected, target
        
        # Apply configuration only if we have data
        if len(prompt_performance) > 0:
            config_values = prompt_performance.apply(get_prompt_config_values, axis=1, result_type='expand')
            prompt_performance['Expected_Per_AdGroup'] = config_values[0]
            prompt_performance['Target_Per_AdGroup'] = config_values[1]
        else:
            print("  ⚠️ No prompt performance data to configure")
            # Add empty columns for consistency
            prompt_performance['Expected_Per_AdGroup'] = []
            prompt_performance['Target_Per_AdGroup'] = []
        
        prompt_performance = prompt_performance.rename(columns={
            'PromptNumber': 'Prompt Number',
            'AssetType': 'Asset Type',
            'Asset': 'Total Generated',
            'DataSource': 'Results Assets'
        })
        
        # Sort by Prompt Number
        if len(prompt_performance) > 0:
            prompt_performance = prompt_performance.sort_values(['Prompt Number', 'Asset Type'])
        else:
            print("  ⚠️ No prompt performance data to sort")
        
        print(f"  �� Prompt performance analysis: {len(prompt_performance)} records")
        
        print("  📊 Performing campaign prompt analysis...")
        # Campaign level analysis
        campaign_prompt_analysis = prompt_data.groupby(['CampaignName', 'PromptNumber', 'AssetType']).agg({
            'Asset': 'count',
            'DataSource': lambda x: (x == 'Results').sum(),
            'AdGroups': 'nunique'
        }).reset_index()
        
        campaign_prompt_analysis['Errors Count'] = prompt_data.groupby(['CampaignName', 'PromptNumber', 'AssetType'])['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
        campaign_prompt_analysis['Success Rate %'] = (campaign_prompt_analysis['DataSource'] / campaign_prompt_analysis['Asset'] * 100).round(2)
        
        campaign_prompt_analysis = campaign_prompt_analysis.rename(columns={
            'CampaignName': 'Campaign Name',
            'PromptNumber': 'Prompt Number',
            'AssetType': 'Asset Type',
            'Asset': 'Total Generated',
            'DataSource': 'Results Assets',
            'AdGroups': 'Ad Groups Count'
        })
        
        # Sort by Campaign Name, then Prompt Number
        if len(campaign_prompt_analysis) > 0:
            campaign_prompt_analysis = campaign_prompt_analysis.sort_values(['Campaign Name', 'Prompt Number', 'Asset Type'])
        else:
            print("  ⚠️ No campaign prompt data to sort")
        
        print(f"  📊 Campaign prompt analysis: {len(campaign_prompt_analysis)} records")
        
        # Default Assets Analysis
        print("  📊 Analyzing default assets...")
        default_assets_analysis = analyze_default_assets(combined_df)
        
        print("  📊 Prompts performance analysis completed successfully")
        
        return {
            'prompt_configs': prompt_configs,
            'prompt_performance': prompt_performance,
            'adgroup_prompt_analysis': adgroup_prompt_analysis,
            'campaign_prompt_analysis': campaign_prompt_analysis,
            'default_assets_analysis': default_assets_analysis
        }
        
    except Exception as e:
        print(f"  ❌ Error in prompts performance analysis: {e}")
        print(f"  ❌ Traceback: {traceback.format_exc()}")
        return {
            'prompt_configs': {},
            'prompt_performance': pd.DataFrame(),
            'adgroup_prompt_analysis': pd.DataFrame(),
            'campaign_prompt_analysis': pd.DataFrame(),
            'default_assets_analysis': pd.DataFrame()
        }

def analyze_ads_data_complete(file_path, output_dir="output"):
    """
    Complete analysis of ads data - NO LIMITS on data size
    Includes all combinations including Asset Type + Source analysis
    """
    
    print(f"🚀 Starting complete ads data analysis...")
    print(f"📂 Loading data from: {file_path}")
    
    try:
        # Create output directory if it doesn't exist
        print(f"📁 Creating output directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        
        # Read the Excel file
        print(f"📖 Reading Excel file...")
        
        # Check if file exists first
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None
        
        print(f"📖 File exists, reading tabs...")
        
        # Read all tabs
        try:
            print(f"📖 Reading Results tab...")
            results_df = pd.read_excel(file_path, sheet_name='Results')
            print(f"✅ Results tab loaded: {len(results_df)} rows")
        except Exception as e:
            print(f"❌ Error reading Results tab: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            return None
        
        try:
            print(f"📖 Reading Errors tab...")
            errors_df = pd.read_excel(file_path, sheet_name='Errors')
            print(f"✅ Errors tab loaded: {len(errors_df)} rows")
        except Exception as e:
            print(f"❌ Error reading Errors tab: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            return None
        
        # Try to read Prompts tab (optional)
        prompts_config = None
        try:
            print(f"📖 Reading Prompts tab...")
            prompts_config = pd.read_excel(file_path, sheet_name='Prompts')
            print(f"✅ Prompts tab loaded: {len(prompts_config)} rows")
        except Exception as prompts_e:
            print(f"⚠️ Prompts tab not found or error reading: {prompts_e}")
        
        print(f"📊 Data loading summary:")
        print(f"  - Results tab: {len(results_df)} rows")
        print(f"  - Errors tab: {len(errors_df)} rows")
        if prompts_config is not None:
            print(f"  - Prompts tab: {len(prompts_config)} rows")
        
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return None
    
    try:
        print(f"🔄 Combining dataframes...")
        # Combine both dataframes for comprehensive analysis
        results_df['DataSource'] = 'Results'
        errors_df['DataSource'] = 'Errors'
        
        # Get common columns between both dataframes
        common_columns = list(set(results_df.columns) & set(errors_df.columns))
        print(f"📊 Common columns found: {len(common_columns)}")
        print(f"📊 Common columns: {common_columns}")
        
        # Use only common columns for analysis
        results_common = results_df[common_columns].copy()
        errors_common = errors_df[common_columns].copy()
        
        # Ensure consistent data types and clean data
        print(f"🔧 Cleaning and standardizing data types...")
        for col in common_columns:
            if col != 'DataSource':  # Skip the DataSource column we just added
                # Convert to string first to handle mixed types, then clean
                results_common[col] = results_common[col].astype(str).replace('nan', '').replace('None', '')
                errors_common[col] = errors_common[col].astype(str).replace('nan', '').replace('None', '')
        
        # Combine dataframes
        combined_df = pd.concat([results_common, errors_common], ignore_index=True)
        
        # Additional data cleaning for key columns
        print(f"🔧 Additional data cleaning...")
        if 'CampaignName' in combined_df.columns:
            combined_df['CampaignName'] = combined_df['CampaignName'].fillna('Unknown Campaign').astype(str)
        if 'AdGroups' in combined_df.columns:
            combined_df['AdGroups'] = combined_df['AdGroups'].fillna('Unknown Ad Group').astype(str)
        if 'Source' in combined_df.columns:
            combined_df['Source'] = combined_df['Source'].fillna('Unknown Source').astype(str)
        if 'AssetType' in combined_df.columns:
            combined_df['AssetType'] = combined_df['AssetType'].fillna('Unknown Asset Type').astype(str)
        if 'Asset' in combined_df.columns:
            combined_df['Asset'] = combined_df['Asset'].fillna('Unknown Asset').astype(str)
        
        print(f"✅ Combined data: {len(combined_df)} rows")
        
    except Exception as e:
        print(f"❌ Error combining dataframes: {e}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return None
    
    try:
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        print(f"🕐 Generated timestamp: {timestamp}")
        
        # Create comprehensive analysis results
        analysis_results = {}
        
        print(f"📊 Starting analysis sections...")
        
        # 1. Overall Summary
        print(f"📊 1. Calculating overall summary...")
        overall_stats = {
            'total_results': len(results_df),
            'total_errors': len(errors_df),
            'total_assets': len(combined_df),
            'success_rate': round((len(results_df) / len(combined_df) * 100), 2),
            'error_rate': round((len(errors_df) / len(combined_df) * 100), 2),
            'unique_sources': combined_df['Source'].nunique(),
            'unique_campaigns': combined_df['CampaignName'].nunique(),
            'unique_adgroups': combined_df['AdGroups'].nunique(),
            'unique_asset_types': combined_df['AssetType'].nunique()
        }
        analysis_results['overall'] = overall_stats
        print(f"✅ Overall summary completed")
        
        # 2. Analysis by Source (ALL sources)
        print(f"📊 2. Analyzing by source...")
        try:
            source_analysis = combined_df.groupby('Source').agg({
                'Asset': 'count',
                'DataSource': lambda x: (x == 'Results').sum()
            }).reset_index()
            
            source_analysis['Errors Count'] = combined_df.groupby('Source')['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
            source_analysis['Error Rate %'] = (source_analysis['Errors Count'] / source_analysis['Asset'] * 100).round(2)
            source_analysis = source_analysis.rename(columns={
                'Source': 'Source',
                'Asset': 'Total Assets',
                'DataSource': 'Results Count'
            })
            source_analysis = source_analysis.sort_values('Total Assets', ascending=False)
            analysis_results['source_analysis'] = source_analysis
            print(f"✅ Source analysis completed: {len(source_analysis)} sources")
        except Exception as e:
            print(f"❌ Error in source analysis: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            # Create empty DataFrame as fallback
            analysis_results['source_analysis'] = pd.DataFrame(columns=['Source', 'Total Assets', 'Results Count', 'Errors Count', 'Error Rate %'])
        
        # 3. Analysis by Asset Type (ALL asset types)
        print(f"📊 3. Analyzing by asset type...")
        try:
            asset_type_analysis = combined_df.groupby('AssetType').agg({
                'Asset': 'count',
                'DataSource': lambda x: (x == 'Results').sum()
            }).reset_index()
            
            asset_type_analysis['Errors Count'] = combined_df.groupby('AssetType')['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
            asset_type_analysis['Error Rate %'] = (asset_type_analysis['Errors Count'] / asset_type_analysis['Asset'] * 100).round(2)
            asset_type_analysis = asset_type_analysis.rename(columns={
                'AssetType': 'Asset Type',
                'Asset': 'Total Assets',
                'DataSource': 'Results Count'
            })
            asset_type_analysis = asset_type_analysis.sort_values('Total Assets', ascending=False)
            analysis_results['asset_type_analysis'] = asset_type_analysis
            print(f"✅ Asset type analysis completed: {len(asset_type_analysis)} asset types")
        except Exception as e:
            print(f"❌ Error in asset type analysis: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            # Create empty DataFrame as fallback
            analysis_results['asset_type_analysis'] = pd.DataFrame(columns=['Asset Type', 'Total Assets', 'Results Count', 'Errors Count', 'Error Rate %'])
        
        # 4. NEW: Source + Asset Type Combination Analysis (ALL combinations)
        print(f"📊 4. Analyzing source + asset type combinations...")
        try:
            source_asset_analysis = combined_df.groupby(['Source', 'AssetType']).agg({
                'Asset': 'count',
                'DataSource': lambda x: (x == 'Results').sum()
            }).reset_index()
            
            source_asset_analysis['Errors Count'] = combined_df.groupby(['Source', 'AssetType'])['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
            source_asset_analysis['Success Rate %'] = (source_asset_analysis['DataSource'] / source_asset_analysis['Asset'] * 100).round(2)
            source_asset_analysis['Error Rate %'] = (source_asset_analysis['Errors Count'] / source_asset_analysis['Asset'] * 100).round(2)
            source_asset_analysis = source_asset_analysis.rename(columns={
                'Source': 'Source',
                'AssetType': 'Asset Type',
                'Asset': 'Total Assets',
                'DataSource': 'Results Count'
            })
            source_asset_analysis = source_asset_analysis.sort_values('Total Assets', ascending=False)
            analysis_results['source_asset_analysis'] = source_asset_analysis
            print(f"✅ Source + asset type analysis completed: {len(source_asset_analysis)} combinations")
        except Exception as e:
            print(f"❌ Error in source + asset type analysis: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            # Create empty DataFrame as fallback
            analysis_results['source_asset_analysis'] = pd.DataFrame(columns=['Source', 'Asset Type', 'Total Assets', 'Results Count', 'Errors Count', 'Success Rate %', 'Error Rate %'])
        
        # 5. Analysis by Campaign (ALL campaigns)
        print(f"📊 5. Analyzing by campaign...")
        try:
            campaign_analysis = combined_df.groupby('CampaignName').agg({
                'Asset': 'count',
                'DataSource': lambda x: (x == 'Results').sum()
            }).reset_index()
            
            campaign_analysis['Errors Count'] = combined_df.groupby('CampaignName')['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
            campaign_analysis['Error Rate %'] = (campaign_analysis['Errors Count'] / campaign_analysis['Asset'] * 100).round(2)
            campaign_analysis = campaign_analysis.rename(columns={
                'CampaignName': 'Campaign Name',
                'Asset': 'Total Assets',
                'DataSource': 'Results Count'
            })
            campaign_analysis = campaign_analysis.sort_values('Total Assets', ascending=False)
            analysis_results['campaign_analysis'] = campaign_analysis
            print(f"✅ Campaign analysis completed: {len(campaign_analysis)} campaigns")
        except Exception as e:
            print(f"❌ Error in campaign analysis: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            # Create empty DataFrame as fallback
            analysis_results['campaign_analysis'] = pd.DataFrame(columns=['Campaign Name', 'Total Assets', 'Results Count', 'Errors Count', 'Error Rate %'])
        
        # 6. Analysis by Ad Group (ALL ad groups)
        print(f"📊 6. Analyzing by ad group...")
        try:
            adgroup_analysis = combined_df.groupby(['AdGroups', 'CampaignName']).agg({
                'Asset': 'count',
                'DataSource': lambda x: (x == 'Results').sum()
            }).reset_index()
            
            adgroup_analysis['Errors Count'] = combined_df.groupby(['AdGroups', 'CampaignName'])['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
            adgroup_analysis['Success Rate %'] = (adgroup_analysis['DataSource'] / adgroup_analysis['Asset'] * 100).round(2)
            adgroup_analysis = adgroup_analysis.rename(columns={
                'AdGroups': 'Ad Group',
                'CampaignName': 'Campaign Name',
                'Asset': 'Total Assets',
                'DataSource': 'Results Count'
            })
            adgroup_analysis = adgroup_analysis.sort_values('Total Assets', ascending=False)
            analysis_results['adgroup_analysis'] = adgroup_analysis
            print(f"✅ Ad group analysis completed: {len(adgroup_analysis)} ad groups")
        except Exception as e:
            print(f"❌ Error in ad group analysis: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            # Create empty DataFrame as fallback
            analysis_results['adgroup_analysis'] = pd.DataFrame(columns=['Ad Group', 'Campaign Name', 'Total Assets', 'Results Count', 'Errors Count', 'Success Rate %'])
        
        # 7. Complete Source + Campaign + Asset Type Analysis (ALL combinations)
        print(f"📊 7. Analyzing detailed combinations (Source + Campaign + Asset Type)...")
        try:
            detailed_analysis = combined_df.groupby(['Source', 'CampaignName', 'AssetType']).agg({
                'Asset': 'count',
                'DataSource': lambda x: (x == 'Results').sum()
            }).reset_index()
            
            detailed_analysis['Errors Count'] = combined_df.groupby(['Source', 'CampaignName', 'AssetType'])['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
            detailed_analysis['Success Rate %'] = (detailed_analysis['DataSource'] / detailed_analysis['Asset'] * 100).round(2)
            detailed_analysis = detailed_analysis.rename(columns={
                'Source': 'Source',
                'CampaignName': 'Campaign Name',
                'AssetType': 'Asset Type',
                'Asset': 'Total Assets',
                'DataSource': 'Results Count'
            })
            detailed_analysis = detailed_analysis.sort_values('Total Assets', ascending=False)
            analysis_results['detailed_analysis'] = detailed_analysis
            print(f"✅ Detailed analysis completed: {len(detailed_analysis)} combinations")
        except Exception as e:
            print(f"❌ Error in detailed analysis: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            # Create empty DataFrame as fallback
            analysis_results['detailed_analysis'] = pd.DataFrame(columns=['Source', 'Campaign Name', 'Asset Type', 'Total Assets', 'Results Count', 'Errors Count', 'Success Rate %'])
        
        # 7b. Complete Source + Campaign + AdGroup + Asset Type Analysis (ALL combinations with Ad Groups)
        print(f"📊 7b. Analyzing detailed ad group combinations...")
        try:
            detailed_adgroup_analysis = combined_df.groupby(['Source', 'CampaignName', 'AdGroups', 'AssetType']).agg({
                'Asset': 'count',
                'DataSource': lambda x: (x == 'Results').sum()
            }).reset_index()
            
            detailed_adgroup_analysis['Errors Count'] = combined_df.groupby(['Source', 'CampaignName', 'AdGroups', 'AssetType'])['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
            detailed_adgroup_analysis['Success Rate %'] = (detailed_adgroup_analysis['DataSource'] / detailed_adgroup_analysis['Asset'] * 100).round(2)
            detailed_adgroup_analysis = detailed_adgroup_analysis.rename(columns={
                'Source': 'Source',
                'CampaignName': 'Campaign Name',
                'AdGroups': 'Ad Group',
                'AssetType': 'Asset Type',
                'Asset': 'Total Assets',
                'DataSource': 'Results Count'
            })
            detailed_adgroup_analysis = detailed_adgroup_analysis.sort_values('Total Assets', ascending=False)
            analysis_results['detailed_adgroup_analysis'] = detailed_adgroup_analysis
            print(f"✅ Detailed ad group analysis completed: {len(detailed_adgroup_analysis)} combinations")
        except Exception as e:
            print(f"❌ Error in detailed ad group analysis: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            # Create empty DataFrame as fallback
            analysis_results['detailed_adgroup_analysis'] = pd.DataFrame(columns=['Source', 'Campaign Name', 'Ad Group', 'Asset Type', 'Total Assets', 'Results Count', 'Errors Count', 'Success Rate %'])
        
        # 8. Prompts Analysis (if prompts config exists)
        if prompts_config is not None:
            print(f"📊 8. Analyzing prompts performance...")
            prompts_analysis = analyze_prompts_performance(combined_df, prompts_config)
            analysis_results['prompts_analysis'] = prompts_analysis
            print(f"✅ Prompts analysis completed")
        else:
            print(f"⚠️ 8. Skipping prompts analysis (no prompts config)")
        
        # 9. Error Analysis (if errors exist)
        if len(errors_df) > 0:
            print(f"📊 9. Analyzing errors...")
            error_analysis = {}
            
            try:
                if 'ReasonForError' in errors_df.columns:
                    print(f"  📊 Analyzing error reasons...")
                    error_reasons = errors_df['ReasonForError'].value_counts().reset_index()
                    error_reasons.columns = ['Error Reason', 'Count']
                    error_reasons['Percentage'] = (error_reasons['Count'] / len(errors_df) * 100).round(2)
                    error_analysis['error_reasons'] = error_reasons
                    print(f"  ✅ Error reasons analysis: {len(error_reasons)} unique reasons")
            except Exception as e:
                print(f"  ❌ Error in error reasons analysis: {e}")
                error_analysis['error_reasons'] = pd.DataFrame(columns=['Error Reason', 'Count', 'Percentage'])
            
            try:
                # Error analysis by source
                print(f"  📊 Analyzing errors by source...")
                error_by_source = errors_df['Source'].value_counts().reset_index()
                error_by_source.columns = ['Source', 'Error Count']
                error_by_source['Percentage'] = (error_by_source['Error Count'] / len(errors_df) * 100).round(2)
                error_analysis['error_by_source'] = error_by_source
                print(f"  ✅ Errors by source: {len(error_by_source)} sources")
            except Exception as e:
                print(f"  ❌ Error in errors by source analysis: {e}")
                error_analysis['error_by_source'] = pd.DataFrame(columns=['Source', 'Error Count', 'Percentage'])
            
            try:
                # Error analysis by asset type
                print(f"  📊 Analyzing errors by asset type...")
                error_by_asset_type = errors_df['AssetType'].value_counts().reset_index()
                error_by_asset_type.columns = ['Asset Type', 'Error Count']
                error_by_asset_type['Percentage'] = (error_by_asset_type['Error Count'] / len(errors_df) * 100).round(2)
                error_analysis['error_by_asset_type'] = error_by_asset_type
                print(f"  ✅ Errors by asset type: {len(error_by_asset_type)} asset types")
            except Exception as e:
                print(f"  ❌ Error in errors by asset type analysis: {e}")
                error_analysis['error_by_asset_type'] = pd.DataFrame(columns=['Asset Type', 'Error Count', 'Percentage'])
            
            analysis_results['error_analysis'] = error_analysis
            print(f"✅ Error analysis completed")
        else:
            print(f"⚠️ 9. Skipping error analysis (no errors found)")
        
    except Exception as e:
        print(f"❌ Error during analysis calculations: {e}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return None
    
    # Save all analysis to files
    try:
        print(f"💾 Saving analysis results...")
        sections_dir = os.path.join(output_dir, f'complete_analysis_{timestamp}')
        os.makedirs(sections_dir, exist_ok=True)
        print(f"📁 Created analysis directory: {sections_dir}")
        
        # Save each analysis section as CSV
        print(f"💾 Saving source analysis...")
        try:
            analysis_results['source_analysis'].to_csv(os.path.join(sections_dir, 'source_analysis_complete.csv'), index=False)
        except Exception as e:
            print(f"❌ Error saving source analysis: {e}")
        
        print(f"💾 Saving asset type analysis...")
        try:
            analysis_results['asset_type_analysis'].to_csv(os.path.join(sections_dir, 'asset_type_analysis_complete.csv'), index=False)
        except Exception as e:
            print(f"❌ Error saving asset type analysis: {e}")
        
        print(f"💾 Saving source + asset combination analysis...")
        try:
            analysis_results['source_asset_analysis'].to_csv(os.path.join(sections_dir, 'source_asset_combination_analysis.csv'), index=False)
        except Exception as e:
            print(f"❌ Error saving source asset analysis: {e}")
        
        print(f"💾 Saving campaign analysis...")
        try:
            analysis_results['campaign_analysis'].to_csv(os.path.join(sections_dir, 'campaign_analysis_complete.csv'), index=False)
        except Exception as e:
            print(f"❌ Error saving campaign analysis: {e}")
        
        print(f"💾 Saving ad group analysis...")
        try:
            analysis_results['adgroup_analysis'].to_csv(os.path.join(sections_dir, 'adgroup_analysis_complete.csv'), index=False)
        except Exception as e:
            print(f"❌ Error saving ad group analysis: {e}")
        
        print(f"💾 Saving detailed combination analysis...")
        try:
            analysis_results['detailed_analysis'].to_csv(os.path.join(sections_dir, 'detailed_combination_analysis_complete.csv'), index=False)
        except Exception as e:
            print(f"❌ Error saving detailed analysis: {e}")
        
        try:
            analysis_results['detailed_adgroup_analysis'].to_csv(os.path.join(sections_dir, 'detailed_adgroup_analysis_complete.csv'), index=False)
        except Exception as e:
            print(f"❌ Error saving detailed ad group analysis: {e}")
        
        # Save prompts analysis if available
        if 'prompts_analysis' in analysis_results:
            print(f"💾 Saving prompts analysis...")
            prompts_dir = os.path.join(sections_dir, 'prompts_analysis')
            os.makedirs(prompts_dir, exist_ok=True)
            
            try:
                analysis_results['prompts_analysis']['prompt_performance'].to_csv(os.path.join(prompts_dir, 'prompt_performance.csv'), index=False)
            except Exception as e:
                print(f"❌ Error saving prompt performance: {e}")
            
            try:
                analysis_results['prompts_analysis']['adgroup_prompt_analysis'].to_csv(os.path.join(prompts_dir, 'adgroup_prompt_analysis.csv'), index=False)
            except Exception as e:
                print(f"❌ Error saving adgroup prompt analysis: {e}")
            
            try:
                analysis_results['prompts_analysis']['campaign_prompt_analysis'].to_csv(os.path.join(prompts_dir, 'campaign_prompt_analysis.csv'), index=False)
            except Exception as e:
                print(f"❌ Error saving campaign prompt analysis: {e}")
            
            # Save default assets analysis if available
            if 'default_assets_analysis' in analysis_results['prompts_analysis'] and len(analysis_results['prompts_analysis']['default_assets_analysis']) > 0:
                try:
                    analysis_results['prompts_analysis']['default_assets_analysis'].to_csv(os.path.join(prompts_dir, 'default_assets_analysis.csv'), index=False)
                except Exception as e:
                    print(f"❌ Error saving default assets analysis: {e}")
            print(f"✅ Prompts analysis saved")
        
        if 'error_analysis' in analysis_results:
            print(f"💾 Saving error analysis...")
            error_dir = os.path.join(sections_dir, 'error_analysis')
            os.makedirs(error_dir, exist_ok=True)
            
            if 'error_reasons' in analysis_results['error_analysis']:
                try:
                    analysis_results['error_analysis']['error_reasons'].to_csv(os.path.join(error_dir, 'error_reasons.csv'), index=False)
                except Exception as e:
                    print(f"❌ Error saving error reasons: {e}")
            
            try:
                analysis_results['error_analysis']['error_by_source'].to_csv(os.path.join(error_dir, 'errors_by_source.csv'), index=False)
            except Exception as e:
                print(f"❌ Error saving errors by source: {e}")
            
            try:
                analysis_results['error_analysis']['error_by_asset_type'].to_csv(os.path.join(error_dir, 'errors_by_asset_type.csv'), index=False)
            except Exception as e:
                print(f"❌ Error saving errors by asset type: {e}")
            
            print(f"✅ Error analysis saved")
        
        print(f"✅ Complete analysis saved to: {sections_dir}")
        
        # Create summary report inside the analysis directory
        print(f"📝 Creating summary report...")
        summary_output = os.path.join(sections_dir, 'analysis_summary.txt')
        with open(summary_output, 'w') as f:
            f.write(f"COMPLETE ADS OUTPUT ANALYSIS\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Source File: {os.path.basename(file_path)}\n")
            f.write(f"="*50 + "\n\n")
            f.write(f"OVERALL METRICS:\n")
            for key, value in overall_stats.items():
                f.write(f"- {key.replace('_', ' ').title()}: {value:,}\n")
            
            f.write(f"\nDATA COMPLETENESS:\n")
            f.write(f"- Total Sources Analyzed: {len(analysis_results['source_analysis'])}\n")
            f.write(f"- Total Campaigns Analyzed: {len(analysis_results['campaign_analysis'])}\n")
            f.write(f"- Total Ad Groups Analyzed: {len(analysis_results['adgroup_analysis'])}\n")
            f.write(f"- Total Source+Asset Type Combinations: {len(analysis_results['source_asset_analysis'])}\n")
            f.write(f"- Total Detailed Combinations: {len(analysis_results['detailed_analysis'])}\n")
            
            if 'prompts_analysis' in analysis_results:
                f.write(f"\nPROMPTS ANALYSIS:\n")
                prompts_data = analysis_results['prompts_analysis']
                if len(prompts_data['prompt_performance']) > 0:
                    f.write(f"- Prompts Analyzed: {len(prompts_data['prompt_performance']['Prompt Number'].unique())}\n")
                    f.write(f"- Ad Groups with Prompt Data: {len(prompts_data['adgroup_prompt_analysis'])}\n")
                    f.write(f"- Prompt Configurations Found: {len(prompts_data['prompt_configs'])}\n")
                else:
                    f.write(f"- No prompt data found in source names\n")
        
        print(f"✅ Complete summary saved to: {summary_output}")
        
    except Exception as e:
        print(f"❌ Error saving complete analysis: {e}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return None
    
    print(f"🎉 Analysis completed successfully!")
    return analysis_results, timestamp

if __name__ == "__main__":
    import sys
    
    print(f"🚀 Starting ads analysis script...")
    
    # Check if file path is provided as command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"📂 Using file from command line: {file_path}")
    else:
        # Default file path
        file_path = "Aniket 1023 Ad Groups__results.xlsx"
        print(f"📂 Looking for default file: {file_path}")
        
        # If default file doesn't exist, ask user for file path
        if not os.path.exists(file_path):
            print(f"❌ Default file not found: {file_path}")
            print(f"📂 Please provide the Excel file path:")
            print(f"   Usage: python ads_analysis_complete.py <path_to_excel_file>")
            print(f"   Example: python ads_analysis_complete.py \"C:\\path\\to\\your\\file.xlsx\"")
            
            # List any Excel files in current directory
            excel_files = [f for f in os.listdir('.') if f.endswith(('.xlsx', '.xls'))]
            if excel_files:
                print(f"\n📋 Excel files found in current directory:")
                for i, f in enumerate(excel_files, 1):
                    print(f"   {i}. {f}")
                print(f"\n💡 You can run: python ads_analysis_complete.py \"{excel_files[0]}\"")
            else:
                print(f"\n📋 No Excel files found in current directory.")
            
            sys.exit(1)
    
    print(f"📂 Target file: {file_path}")
    
    # Check if file exists
    if os.path.exists(file_path):
        print(f"✅ File found, starting analysis...")
        try:
            results, timestamp = analyze_ads_data_complete(file_path)
            if results:
                print(f"\n🎉 Complete analysis finished!")
                print(f"📊 No data limits applied - ALL records analyzed")
                print(f"📁 Results saved with timestamp: {timestamp}")
            else:
                print(f"\n❌ Analysis failed - check logs above for details")
        except Exception as e:
            print(f"\n❌ Unexpected error during analysis: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
    else:
        print(f"❌ File not found: {file_path}")
        print("Please ensure the Excel file exists and the path is correct.") 