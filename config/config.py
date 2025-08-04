import os
from pathlib import Path


class Config:
    # Paths
    IPERF_PATH = "C:\\iperf3\\iperf3.exe\\iperf3.exe"
    SPEEDTEST_PATH = "C:\\Users\\Usuario\\speedtest.exe"
    IPERF_SERVER = "179.26.51.71" 

    # House dimensions
    HOUSE_WIDTH = 15
    HOUSE_LENGTH = 20

    # Data storage
    DATA_DIR = Path("heatmap_data")

    # Test settings
    PING_TARGET = "8.8.8.8"
    PING_COUNT = 4
    SPEEDTEST_SERVER_ID = 40741  # ANTEL

    # Heatmap settings
    GRID_RESOLUTION = 0.5
    HEATMAP_DPI = 300
    MEASUREMENT_INTERVAL = 30

    # FILTRADO DE REDES - SOLO MONITOREAR ESTOS SSIDs
    MONITORED_SSIDS = [
        "Pumita",           
        "Puma",              
        
    ]

    # Si está vacío, monitorea TODAS las redes
    MONITOR_ALL_NETWORKS = True  # Cambiar a True para monitorear todo

