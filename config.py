# config.py
"""
Configuración del sistema de monitoreo de red
"""

# Configuración de iperf3
IPERF_PATH = "C:\\iperf3\\iperf3.exe\\iperf3.exe"  # Ruta al ejecutable de iperf3
IPERF_SERVER = "127.0.0.1"  # Servidor local para pruebas

# Configuración de intervalos
INTERVAL_MINUTES = 5  # Intervalo principal de monitoreo
WIFI_SCAN_INTERVAL = 2  # Intervalos entre escaneos WiFi (iteraciones)

# Configuración de archivos de salida
DEFAULT_OUTPUT_FILE = "test_results.json"

# Configuración de timeouts
PING_TIMEOUT = 30
TRACEROUTE_TIMEOUT = 60
SPEEDTEST_TIMEOUT = 120
IPERF_TIMEOUT = 30
NETSH_TIMEOUT = 15

# Configuración de caché WiFi
WIFI_CACHE_SECONDS = 30