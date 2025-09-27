#!/usr/bin/env python3
"""
Production Ads Analysis Dashboard Launcher
Clean, production-ready interface with tabs and ad group focus
"""

import subprocess
import sys
import os

def main():
    print("🚀 Starting Production Ads Analysis Dashboard...")
    print("📊 Clean interface with tabs and ad group focus")
    print("🔍 Smart error categorization with clickable details")
    print("🎯 Production-ready code with fixed deprecation warnings")
    print("🔗 URL: http://localhost:8503")
    print("-" * 60)
    
    try:
        # Launch Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "ads_analysis_dashboard.py",
            "--server.port=8503",
            "--server.address=localhost",
            "--browser.gatherUsageStats=false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error launching dashboard: {e}")
        print("💡 Make sure Streamlit is installed: pip install streamlit")

if __name__ == "__main__":
    main() 