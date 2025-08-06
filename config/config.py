import os
from pathlib import Path


class Config:
    # Paths
    IPERF_PATH = "C:\\iperf3\\iperf3.exe\\iperf3.exe"
    SPEEDTEST_PATH = "C:\\Users\\Usuario\\speedtest.exe"
    IPERF_SERVER = "167.62.110.20" 

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
    MONITOR_ALL_NETWORKS = False  # Cambiar a True para monitorear todo
    
    # NUEVAS CONFIGURACIONES
    
    # UDP Test configurations
    UDP_FORWARD_RATES = ["1M", "5M", "10M", "25M", "50M"]  # Velocidades para tests UDP forward
    UDP_REVERSE_RATES = ["1M", "5M", "10M", "25M", "50M"]  # Velocidades para tests UDP reverse
    UDP_PACKET_SIZE = 1400  # Tamaño de paquete UDP para evitar fragmentación
    
    # File organization
    SAVE_INDIVIDUAL_FILES = True  # Guardar cada medición en archivo separado
    SAVE_AP_DETAILS = True        # Guardar detalles por AP
    SAVE_SUMMARY_FILES = True     # Crear archivos de resumen .txt legibles
    
    # Network info collection
    COLLECT_CLIENT_INFO = True    # Recopilar información de red del cliente
    SHOW_ADVANCED_METRICS = True  # Mostrar SNR, calidad de señal, etc.
    
    # Debug options
    DEBUG_MODE = False            # Mostrar información de debug detallada
    VERBOSE_SCANNING = True       # Mostrar detalles durante escaneo
    
    # Performance thresholds
    SIGNAL_QUALITY_THRESHOLDS = {
        "excellent": 40,  # SNR >= 40 dB
        "very_good": 30,  # SNR >= 30 dB  
        "good": 20,       # SNR >= 20 dB
        "fair": 15,       # SNR >= 15 dB
        # < 15 dB = poor
    }
    
    # UDP Quality thresholds
    UDP_QUALITY_THRESHOLDS = {
        "excellent": {"loss": 0.1, "jitter": 2.0},    # < 0.1% loss, < 2ms jitter
        "good": {"loss": 0.5, "jitter": 5.0},         # < 0.5% loss, < 5ms jitter
        "acceptable": {"loss": 1.0, "jitter": 10.0},  # < 1.0% loss, < 10ms jitter
        # >= 1.0% loss = problematic
    }
    
    # Noise floor estimates (dBm)
    NOISE_FLOOR = {
        "2.4GHz": -95,  # Typical noise floor for 2.4GHz
        "5GHz": -100,   # Typical noise floor for 5GHz
        "6GHz": -100    # Typical noise floor for 6GHz (WiFi 6E)
    }
