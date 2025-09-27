# 📊 Ads Analysis Dashboard

A comprehensive Streamlit-based dashboard for analyzing advertising campaign performance, focusing on asset generation success rates and error categorization.

## 🚀 Features

- **Performance Overview**: Key metrics and success rates across campaigns
- **Source Analysis**: Performance breakdown by generation source and prompts
- **Campaign & Ad Group Analysis**: Detailed performance insights with filtering
- **Interactive Error Analysis**: Smart error categorization with drill-down capabilities
- **Asset Traceability**: Track individual assets from generation to review

## 📋 Requirements

### Data Format

Your Excel file must contain two tabs:

- **Results Tab**: Successful asset generation data
- **Errors Tab**: Failed asset generation data with error reasons

### Required Columns

Both tabs must include:

- `AccountID`, `CampaignName`, `AdGroups`, `AssetType`, `Asset`, `Source`, `ErrorFromAdsGeneration`

Errors tab additionally requires:

- `ReasonForError`

## 🛠️ Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd ads-analysis-dashboard
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the dashboard:

```bash
python launch_dashboard.py
```

4. Open your browser to `http://localhost:8503`

## 📊 Dashboard Tabs

### 🏠 Complete Overview

- Key performance metrics
- Source performance matrix
- Top campaigns and error insights
- Quick action items

### 🎯 Source Details

- Source performance analysis with model/prompt filtering
- Asset type distribution
- Success vs error breakdown

### 📊 Campaign Details

- Campaign performance metrics
- Source and asset type analysis
- Detailed campaign breakdown

### 👥 Ad Group Details

- Ad group performance with filtering
- Default asset analysis
- Ad groups needing attention

### 🔍 Ads Generation Error Vs Ads Review

- Error source comparison (Generation vs Review)
- Clubbed error analysis with asset drill-down
- Error reduction suggestions

### ❌ Error Categories

- Categorized error analysis
- Clickable error details showing affected assets
- Source-based error breakdown

### 📥 Downloads

- Export analysis results as CSV files
- Timestamped file downloads

## 🔧 Key Features

### Smart Error Clubbing

Similar errors are automatically grouped together:

- `Asset contains forbidden phrase: instantly` + `Asset contains forbidden phrase: advice` → `Asset contains forbidden phrase: X`
- `Headline7 must be unique` + `Headline12 must be unique` → `Headline X must be unique`

### Interactive Asset Drill-down

Click on any error to see:

- Specific assets affected
- Campaign and ad group context
- Source attribution
- Generation vs Review classification

### Source Intelligence

Automatically parses source names to extract:

- Model information (e.g., GPT-4o)
- Prompt numbers for consistent ordering
- Clean display names for better UX

## 📁 Project Structure

```
├── ads_analysis_dashboard.py    # Main Streamlit dashboard
├── ads_analysis_complete.py     # Core analysis engine
├── launch_dashboard.py          # Dashboard launcher
├── requirements.txt             # Python dependencies
├── README.md                   # This file
└── .gitignore                  # Git ignore rules
```

## 🎯 Output

The dashboard generates timestamped analysis folders in `output/` containing:

- CSV exports of all analysis results
- Summary text files with key insights
- Organized by analysis timestamp

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues or questions, please create an issue in the GitHub repository.
