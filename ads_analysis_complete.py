import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import os
from datetime import datetime

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
        # Read both tabs
        results_df = pd.read_excel(file_path, sheet_name='Results')
        errors_df = pd.read_excel(file_path, sheet_name='Errors')
        
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
    
    # 8. Error Analysis (if errors exist)
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