#!/usr/bin/env python3
"""
Main script to run the integrated WiFi analysis and heatmap system
"""

# Import the integrated system
from integrated_wifi_system import main, Config

# Optional: Override configuration here
# Config.IPERF_PATH = "C:\\path\\to\\iperf3.exe"
# Config.SPEEDTEST_PATH = "C:\\path\\to\\speedtest.exe"
# Config.HOUSE_WIDTH = 20
# Config.HOUSE_LENGTH = 15

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║     INTEGRATED WIFI ANALYSIS & HEATMAP SYSTEM v2.0           ║
    ║                                                              ║
    ║  Features:                                                   ║
    ║  • WiFi scanning and signal strength mapping                 ║
    ║  • Network performance testing (ping, speedtest, iperf)      ║
    ║  • Persistent data storage                                   ║
    ║  • Individual AP heatmaps                                    ║
    ║  • Composite heatmaps (signal, performance, congestion)      ║
    ║  • Continuous monitoring mode                                ║
    ║                                                              ║
    ║  All data is saved in: heatmap_data/                        ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Run the main system
    main()