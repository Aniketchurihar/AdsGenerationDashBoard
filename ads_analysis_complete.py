import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import os
from datetime import datetime
import re

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
    
    # Filter for default assets (sources that don't contain "Model:" or "Prompt")
    default_assets_data = combined_df[
        (~combined_df['Source'].str.contains('Model:', na=False)) |
        (~combined_df['Source'].str.contains('Prompt', na=False))
    ].copy()
    
    if len(default_assets_data) == 0:
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
    default_analysis = default_analysis.sort_values(['Campaign Name', 'Ad Group', 'Asset Type'])
    
    return default_analysis

def analyze_prompts_performance(combined_df, prompts_config):
    """
    Analyze prompt performance based on per-prompt configuration variables from Prompts tab
    Each row in prompts_config represents a different prompt configuration
    """
    
    # Parse per-prompt configuration - each row is a different prompt
    prompt_configs = {}
    
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
    
    # Add prompt number to combined_df
    combined_df_with_prompt = combined_df.copy()
    combined_df_with_prompt['PromptNumber'] = combined_df_with_prompt['Source'].apply(parse_source_for_prompt_number)
    
    # Filter only rows with valid prompt numbers
    prompt_data = combined_df_with_prompt[combined_df_with_prompt['PromptNumber'].notna()].copy()
    
    if len(prompt_data) == 0:
        return {
            'prompt_configs': prompt_configs,
            'prompt_performance': pd.DataFrame(),
            'adgroup_prompt_analysis': pd.DataFrame(),
            'campaign_prompt_analysis': pd.DataFrame(),
            'default_assets_analysis': pd.DataFrame()
        }
    
    # Analysis by Ad Group and Prompt
    adgroup_prompt_analysis = prompt_data.groupby(['CampaignName', 'AdGroups', 'PromptNumber', 'AssetType']).agg({
        'Asset': 'count',
        'DataSource': lambda x: (x == 'Results').sum()
    }).reset_index()
    
    adgroup_prompt_analysis['Errors Count'] = prompt_data.groupby(['CampaignName', 'AdGroups', 'PromptNumber', 'AssetType'])['DataSource'].apply(lambda x: (x == 'Errors').sum()).values
    adgroup_prompt_analysis['Success Rate %'] = (adgroup_prompt_analysis['DataSource'] / adgroup_prompt_analysis['Asset'] * 100).round(2)
    

    
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
    
    # Apply the configuration
    config_values = adgroup_prompt_analysis.apply(get_prompt_specific_config, axis=1, result_type='expand')
    adgroup_prompt_analysis['Max_To_Generate'] = config_values[0]
    adgroup_prompt_analysis['Target_Assets'] = config_values[1]
    
    # Calculate gaps (actual - target)
    # Positive = over target, Negative = under target
    adgroup_prompt_analysis['Generation_Gap'] = adgroup_prompt_analysis['Asset'] - adgroup_prompt_analysis['Max_To_Generate']
    adgroup_prompt_analysis['Selection_Gap'] = adgroup_prompt_analysis['DataSource'] - adgroup_prompt_analysis['Target_Assets']
    
    adgroup_prompt_analysis = adgroup_prompt_analysis.rename(columns={
        'CampaignName': 'Campaign Name',
        'AdGroups': 'Ad Group',
        'PromptNumber': 'Prompt Number',
        'AssetType': 'Asset Type',
        'Asset': 'Total Generated',
        'DataSource': 'Results Assets'
    })
    
    # Sort by Campaign Name, Ad Group, Asset Type (Headlines first), then Prompt Number for better organization
    adgroup_prompt_analysis['Asset_Type_Order'] = adgroup_prompt_analysis['Asset Type'].apply(lambda x: 0 if 'Headline' in str(x) else 1)
    adgroup_prompt_analysis = adgroup_prompt_analysis.sort_values(['Campaign Name', 'Ad Group', 'Asset_Type_Order', 'Prompt Number'])
    adgroup_prompt_analysis = adgroup_prompt_analysis.drop(columns=['Asset_Type_Order'])
    
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
    
    config_values = prompt_performance.apply(get_prompt_config_values, axis=1, result_type='expand')
    prompt_performance['Expected_Per_AdGroup'] = config_values[0]
    prompt_performance['Target_Per_AdGroup'] = config_values[1]
    
    prompt_performance = prompt_performance.rename(columns={
        'PromptNumber': 'Prompt Number',
        'AssetType': 'Asset Type',
        'Asset': 'Total Generated',
        'DataSource': 'Results Assets'
    })
    
    # Sort by Prompt Number
    prompt_performance = prompt_performance.sort_values(['Prompt Number', 'Asset Type'])
    
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
    campaign_prompt_analysis = campaign_prompt_analysis.sort_values(['Campaign Name', 'Prompt Number', 'Asset Type'])
    
    # Default Assets Analysis
    default_assets_analysis = analyze_default_assets(combined_df)
    
    return {
        'prompt_configs': prompt_configs,
        'prompt_performance': prompt_performance,
        'adgroup_prompt_analysis': adgroup_prompt_analysis,
        'campaign_prompt_analysis': campaign_prompt_analysis,
        'default_assets_analysis': default_assets_analysis
    }

def analyze_ads_data_complete(file_path, output_dir="output"):
    """
    Complete analysis of ads data - NO LIMITS on data size
    Includes all combinations including Asset Type + Source analysis
    """
    
    print(f"Loading data from: {file_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read the Excel file
    try:
        # Read all tabs
        results_df = pd.read_excel(file_path, sheet_name='Results')
        errors_df = pd.read_excel(file_path, sheet_name='Errors')
        
        # Try to read Prompts tab (optional)
        prompts_config = None
        try:
            prompts_config = pd.read_excel(file_path, sheet_name='Prompts')
            print(f"Prompts tab: {len(prompts_config)} rows")
        except Exception as prompts_e:
            print(f"Prompts tab not found or error reading: {prompts_e}")
        
        print(f"Results tab: {len(results_df)} rows")
        print(f"Errors tab: {len(errors_df)} rows")
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None
    
    # Combine both dataframes for comprehensive analysis
    results_df['DataSource'] = 'Results'
    errors_df['DataSource'] = 'Errors'
    
    # Get common columns between both dataframes
    common_columns = list(set(results_df.columns) & set(errors_df.columns))
    print(f"Common columns: {len(common_columns)}")
    
    # Use only common columns for analysis
    results_common = results_df[common_columns].copy()
    errors_common = errors_df[common_columns].copy()
    
    # Combine dataframes
    combined_df = pd.concat([results_common, errors_common], ignore_index=True)
    
    print(f"Combined data: {len(combined_df)} rows")
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create comprehensive analysis results
    analysis_results = {}
    
    # 1. Overall Summary
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
    
    # 2. Analysis by Source (ALL sources)
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
    
    # 3. Analysis by Asset Type (ALL asset types)
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
    
    # 4. NEW: Source + Asset Type Combination Analysis (ALL combinations)
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
    
    # 5. Analysis by Campaign (ALL campaigns)
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
    
    # 6. Analysis by Ad Group (ALL ad groups)
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
    
    # 7. Complete Source + Campaign + Asset Type Analysis (ALL combinations)
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
    
    # 7b. Complete Source + Campaign + AdGroup + Asset Type Analysis (ALL combinations with Ad Groups)
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
    
    # 8. Prompts Analysis (if prompts config exists)
    if prompts_config is not None:
        prompts_analysis = analyze_prompts_performance(combined_df, prompts_config)
        analysis_results['prompts_analysis'] = prompts_analysis
    
    # 9. Error Analysis (if errors exist)
    if len(errors_df) > 0:
        error_analysis = {}
        
        if 'ReasonForError' in errors_df.columns:
            error_reasons = errors_df['ReasonForError'].value_counts().reset_index()
            error_reasons.columns = ['Error Reason', 'Count']
            error_reasons['Percentage'] = (error_reasons['Count'] / len(errors_df) * 100).round(2)
            error_analysis['error_reasons'] = error_reasons
        
        # Error analysis by source
        error_by_source = errors_df['Source'].value_counts().reset_index()
        error_by_source.columns = ['Source', 'Error Count']
        error_by_source['Percentage'] = (error_by_source['Error Count'] / len(errors_df) * 100).round(2)
        error_analysis['error_by_source'] = error_by_source
        
        # Error analysis by asset type
        error_by_asset_type = errors_df['AssetType'].value_counts().reset_index()
        error_by_asset_type.columns = ['Asset Type', 'Error Count']
        error_by_asset_type['Percentage'] = (error_by_asset_type['Error Count'] / len(errors_df) * 100).round(2)
        error_analysis['error_by_asset_type'] = error_by_asset_type
        
        analysis_results['error_analysis'] = error_analysis
    
    # Save all analysis to files
    try:
        sections_dir = os.path.join(output_dir, f'complete_analysis_{timestamp}')
        os.makedirs(sections_dir, exist_ok=True)
        
        # Save each analysis section as CSV
        analysis_results['source_analysis'].to_csv(os.path.join(sections_dir, 'source_analysis_complete.csv'), index=False)
        analysis_results['asset_type_analysis'].to_csv(os.path.join(sections_dir, 'asset_type_analysis_complete.csv'), index=False)
        analysis_results['source_asset_analysis'].to_csv(os.path.join(sections_dir, 'source_asset_combination_analysis.csv'), index=False)
        analysis_results['campaign_analysis'].to_csv(os.path.join(sections_dir, 'campaign_analysis_complete.csv'), index=False)
        analysis_results['adgroup_analysis'].to_csv(os.path.join(sections_dir, 'adgroup_analysis_complete.csv'), index=False)
        analysis_results['detailed_analysis'].to_csv(os.path.join(sections_dir, 'detailed_combination_analysis_complete.csv'), index=False)
        
        # Save prompts analysis if available
        if 'prompts_analysis' in analysis_results:
            prompts_dir = os.path.join(sections_dir, 'prompts_analysis')
            os.makedirs(prompts_dir, exist_ok=True)
            
            analysis_results['prompts_analysis']['prompt_performance'].to_csv(os.path.join(prompts_dir, 'prompt_performance.csv'), index=False)
            analysis_results['prompts_analysis']['adgroup_prompt_analysis'].to_csv(os.path.join(prompts_dir, 'adgroup_prompt_analysis.csv'), index=False)
            analysis_results['prompts_analysis']['campaign_prompt_analysis'].to_csv(os.path.join(prompts_dir, 'campaign_prompt_analysis.csv'), index=False)
            
            # Save default assets analysis if available
            if 'default_assets_analysis' in analysis_results['prompts_analysis'] and len(analysis_results['prompts_analysis']['default_assets_analysis']) > 0:
                analysis_results['prompts_analysis']['default_assets_analysis'].to_csv(os.path.join(prompts_dir, 'default_assets_analysis.csv'), index=False)
        
        if 'error_analysis' in analysis_results:
            error_dir = os.path.join(sections_dir, 'error_analysis')
            os.makedirs(error_dir, exist_ok=True)
            
            if 'error_reasons' in analysis_results['error_analysis']:
                analysis_results['error_analysis']['error_reasons'].to_csv(os.path.join(error_dir, 'error_reasons.csv'), index=False)
            analysis_results['error_analysis']['error_by_source'].to_csv(os.path.join(error_dir, 'errors_by_source.csv'), index=False)
            analysis_results['error_analysis']['error_by_asset_type'].to_csv(os.path.join(error_dir, 'errors_by_asset_type.csv'), index=False)
        
        print(f"✅ Complete analysis saved to: {sections_dir}")
        
        # Create summary report inside the analysis directory
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
        return None
    
    return analysis_results, timestamp

if __name__ == "__main__":
    # File path
    file_path = "Aniket 1023 Ad Groups__results.xlsx"
    
    # Check if file exists
    if os.path.exists(file_path):
        results, timestamp = analyze_ads_data_complete(file_path)
        if results:
            print(f"\n🎉 Complete analysis finished!")
            print(f"📊 No data limits applied - ALL records analyzed")
            print(f"📁 Results saved with timestamp: {timestamp}")
    else:
        print(f"❌ File not found: {file_path}")
        print("Please ensure the Excel file is in the current directory.") 