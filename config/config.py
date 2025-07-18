# CONFIGURACIÓN
IPERF_PATH = "C:\\iperf3\\iperf3.exe\\iperf3.exe"  # Ruta al ejecutable de iperf3
IPERF_SERVER = "127.0.0.1"           # Servidor local para pruebas
INTERVAL_MINUTES = 0.1
WIFI_SCAN_INTERVAL = 2  # Intervalos entre escaneos WiFi (minutos)


# Configuración de Heatmap
HEATMAP_ENABLED = True
HEATMAP_ANALYSIS_INTERVAL = 10  # Cada cuántas iteraciones hacer análisis automático
HEATMAP_HISTORY_DAYS = 7  # Días de historia para análisis completo
HEATMAP_MIN_SIGNAL_THRESHOLD = 30  # Señal mínima para considerar AP
HEATMAP_CONFLICT_THRESHOLD = 2  # Mínimo de APs para considerar conflicto

# Configuración de alertas
ALERT_LOW_PERFORMANCE_THRESHOLD = 70  # % de éxito mínimo
ALERT_HIGH_PING_THRESHOLD = 100  # ms máximo aceptable
ALERT_LOW_SPEED_THRESHOLD = 10  # Mbps mínimo aceptable

# Configuración de visualización
VISUALIZATION_ENABLED = True
VISUALIZATION_DPI = 300
VISUALIZATION_STYLE = 'seaborn'  # estilo de matplotlib
