import time
from datetime import datetime
from services.wifi_analyzer import WiFiAnalyzer
from services.network_tests import run_ping, run_speedtest
from services.utils import save_result

def test_single_network(ssid: str, password: str = None, test_duration: int = 60):
    """Prueba una red específica durante un tiempo determinado."""
    print(f"🧪 === PRUEBA DE RED: {ssid} ===")
    
    analyzer = WiFiAnalyzer()
    
    # Conectar a la red
    print("🔗 Conectando a la red...")
    connection_result = analyzer.connect_to_network(ssid, password)
    
    if not connection_result['success']:
        print(f"❌ No se pudo conectar: {connection_result['message']}")
        return
    
    print(f"✅ Conectado exitosamente a {ssid}")
    
    # Obtener información detallada
    current_info = analyzer.get_current_connection_info()
    print(f"\n📊 Información de conexión:")
    print(f"📍 MAC AP: {current_info.get('bssid', 'N/A')}")
    print(f"📶 Señal: {current_info.get('signal_strength', 'N/A')}")
    print(f"📻 Canal: {current_info.get('channel', 'N/A')}")
    print(f"🔐 Seguridad: {current_info.get('authentication', 'N/A')}")
    print(f"⚡ Velocidades: RX {current_info.get('receive_rate', 'N/A')} | TX {current_info.get('transmit_rate', 'N/A')}")
    
    # Ejecutar pruebas
    print(f"\n🧪 Ejecutando pruebas durante {test_duration} segundos...")
    
    start_time = time.time()
    test_results = []
    
    while time.time() - start_time < test_duration:
        print(f"🔄 Prueba {len(test_results) + 1}...")
        
        # Ping test
        ping_result = run_ping()
        
        # Speedtest (cada 3 pruebas para no sobrecargar)
        speedtest_result = None
        if len(test_results) % 3 == 0:
            speedtest_result = run_speedtest()
        
        # Información WiFi actualizada
        wifi_info = analyzer.get_current_connection_info()
        
        test_result = {
            "timestamp": datetime.now().isoformat(),
            "ping": ping_result,
            "speedtest": speedtest_result,
            "wifi_info": wifi_info
        }
        
        test_results.append(test_result)
        
        # Mostrar resultados inmediatos
        if "error" not in ping_result:
            print(f"  🏓 Ping: {ping_result['avg_time']:.1f}ms")
        
        if speedtest_result and "error" not in speedtest_result:
            download = speedtest_result.get("download", 0) / 1_000_000
            upload = speedtest_result.get("upload", 0) / 1_000_000
            print(f"  🚀 Velocidad: {download:.1f} Mbps ↓ / {upload:.1f} Mbps ↑")
        
        time.sleep(10)  # Esperar 10 segundos entre pruebas
    
    # Generar resumen final
    print(f"\n📈 === RESUMEN DE PRUEBAS ===")
    
    # Estadísticas de ping
    ping_times = [r['ping']['avg_time'] for r in test_results if 'error' not in r['ping']]
    if ping_times:
        print(f"🏓 Ping promedio: {sum(ping_times)/len(ping_times):.1f}ms")
        print(f"🏓 Ping mínimo: {min(ping_times):.1f}ms")
        print(f"🏓 Ping máximo: {max(ping_times):.1f}ms")
    
    # Estadísticas de velocidad
    speed_tests = [r['speedtest'] for r in test_results if r['speedtest'] and 'error' not in r['speedtest']]
    if speed_tests:
        downloads = [s['download']/1_000_000 for s in speed_tests]
        uploads = [s['upload']/1_000_000 for s in speed_tests]
        print(f"🚀 Velocidad promedio: {sum(downloads)/len(downloads):.1f} Mbps ↓ / {sum(uploads)/len(uploads):.1f} Mbps ↑")
    
    # Guardar resultados completos
    final_result = {
        "test_type": "single_network",
        "ssid": ssid,
        "duration": test_duration,
        "connection_info": current_info,
        "test_results": test_results,
        "summary": {
            "total_tests": len(test_results),
            "avg_ping": sum(ping_times)/len(ping_times) if ping_times else 0,
            "speed_tests": len(speed_tests)
        }
    }
    
    save_result(final_result, f"single_network_test_{ssid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    print(f"💾 Resultados guardados")