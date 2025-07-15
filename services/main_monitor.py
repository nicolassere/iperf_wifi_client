import time
from datetime import datetime
from config.config import *
from services.wifi_analyzer import WiFiAnalyzer
from services.utils import save_result
from services.iperf_manager import diagnose_iperf3, start_iperf_server, run_iperf_external
from services.network_tests import run_ping, run_traceroute, run_speedtest
from services.wifi_interface import display_wifi_summary 

def main_loop():
    """Bucle principal de monitoreo mejorado con análisis WiFi."""
    print("=== Monitor de Red con Analizador WiFi ===")
    print(f"Intervalo: {INTERVAL_MINUTES} minutos")
    print(f"Servidor iperf3: {IPERF_SERVER}")
    
    # Inicializar analizador WiFi
    analyzer = WiFiAnalyzer()
    
    # Realizar diagnóstico inicial
    diagnose_iperf3()
    
    # Verificar/iniciar servidor iperf3
    if IPERF_SERVER == "127.0.0.1":
        start_iperf_server()
    
    # Mostrar resumen WiFi inicial
    display_wifi_summary(analyzer)
    
    iteration = 0
    while True:
        iteration += 1
        print(f"\n--- Prueba #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        # Obtener información WiFi detallada
        current_wifi = analyzer.get_current_connection_info()
        wifi_summary = analyzer.get_network_summary()
        
        # Mostrar información de conexión actual
        if "error" not in current_wifi:
            print(f"📶 Red: {current_wifi.get('ssid', 'desconocida')}")
            print(f"📍 MAC AP: {current_wifi.get('bssid', 'N/A')}")
            print(f"📊 Señal: {current_wifi.get('signal_strength', 'N/A')} ({current_wifi.get('signal_percentage', 0)}%)")
            print(f"📻 Canal: {current_wifi.get('channel', 'N/A')} | {current_wifi.get('radio_type', 'N/A')}")
            print(f"🔐 Seguridad: {current_wifi.get('authentication', 'N/A')} | {current_wifi.get('encryption', 'N/A')}")
            print(f"⚡ Velocidad: RX {current_wifi.get('receive_rate', 'N/A')} | TX {current_wifi.get('transmit_rate', 'N/A')}")
        else:
            print(f"📶 WiFi: {current_wifi.get('error', 'Sin conexión')}")
        
        # Ejecutar todas las pruebas
        result = {
            "iteration": iteration,
            "current_wifi": current_wifi,
            "wifi_summary": wifi_summary,
            "ping": run_ping(),
            "traceroute": run_traceroute(),
            "speedtest": run_speedtest(),
            "iperf3": run_iperf_external()
        }
        
        # Mostrar resumen de pruebas
        if "error" not in result["ping"]:
            print(f"🏓 Ping: {result['ping']['avg_time']:.1f}ms promedio, {result['ping']['packet_loss']} pérdida")
        
        if "error" not in result["speedtest"]:
            download = result["speedtest"].get("download", 0) / 1_000_000
            upload = result["speedtest"].get("upload", 0) / 1_000_000
            print(f"🚀 Velocidad: {download:.1f} Mbps ↓ / {upload:.1f} Mbps ↑")
        
        if "error" not in result["iperf3"]:
            try:
                throughput = result["iperf3"]["end"]["sum_received"]["bits_per_second"] / 1_000_000
                print(f"⚡ iperf3: {throughput:.1f} Mbps")
            except:
                print("⚡ iperf3: datos recibidos")
        
        # Mostrar errores
        for test, data in result.items():
            if test not in ["iteration", "current_wifi", "wifi_summary"] and isinstance(data, dict) and "error" in data:
                print(f"❌ {test}: {data['error']}")
        
        # Resumen de redes detectadas cada cierto tiempo
        if iteration % 3 == 0:  # Cada 3 iteraciones
            print(f"\n📡 Redes detectadas: {wifi_summary['total_networks']} (Señal máx: {wifi_summary['strongest_signal']}%)")
            for network in wifi_summary['networks'][:3]:  # Top 3
                status = "🟢" if network.get('is_current') else "🔵" if network.get('is_saved') else "⚪"
                print(f"  {status} {network.get('ssid', 'Sin nombre')} - {network.get('signal_percentage', 0)}%")
        
        # Guardar resultado
        save_result(result)
        print("💾 Resultado guardado")
        
        # Escanear redes cada cierto tiempo
        if iteration % WIFI_SCAN_INTERVAL == 0:
            print("🔍 Actualizando escaneo de redes WiFi...")
            analyzer.scan_networks(force_refresh=True)
        
        # Esperar siguiente iteración
        print(f"⏰ Esperando {INTERVAL_MINUTES} minutos...")
        time.sleep(INTERVAL_MINUTES * 60)