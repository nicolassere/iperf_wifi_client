import time
from datetime import datetime
from config.config import *
from services.wifi_analyzer import WiFiAnalyzer
from services.utils import save_result
from services.iperf_manager import diagnose_iperf3, start_iperf_server, run_iperf_external
from services.network_tests import run_ping, run_traceroute, run_speedtest
from services.wifi_interface import display_wifi_summary 

def main_loop():
    """Bucle principal de monitoreo - CONECTA A TODAS LAS REDES DISPONIBLES."""
    print("=== Monitor de Red - Prueba TODAS las Redes Disponibles ===")
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
        print(f"\n{'='*60}")
        print(f"🔄 ITERACIÓN #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Reiniciar lista de redes probadas cada cierto tiempo
        if iteration % 5 == 0:  # Cada 5 iteraciones
            analyzer.reset_tested_networks()
        
        # CONECTAR Y PROBAR TODAS LAS REDES DISPONIBLES
        print(f"\n🌐 === FASE 1: ESCANEO Y CONEXIÓN A TODAS LAS REDES ===")
        all_network_results = analyzer.connect_to_all_available_networks()
        
        # Generar resumen de conexiones
        successful_connections = [r for r in all_network_results if r.get("connection_successful", False)]
        failed_connections = [r for r in all_network_results if not r.get("connection_successful", False)]
        
        print(f"\n📊 === RESUMEN DE CONEXIONES ===")
        print(f"✅ Conexiones exitosas: {len(successful_connections)}")
        print(f"❌ Conexiones fallidas: {len(failed_connections)}")
        print(f"⏭️ Redes saltadas: {len([r for r in all_network_results if not r.get('connection_attempted', True)])}")
        
        # Mostrar mejores conexiones
        if successful_connections:
            print(f"\n🏆 === MEJORES CONEXIONES ===")
            # Ordenar por velocidad de ping (menor es mejor)
            successful_connections.sort(key=lambda x: x.get("test_results", {}).get("ping", {}).get("avg_time", 999))
            
            for i, conn in enumerate(successful_connections[:5], 1):  # Top 5
                ssid = conn.get("ssid", "Desconocida")
                print(conn)
                signal = conn.get("network_info", {}).get("signal_percentage", 0)
                ping_results = conn.get("test_results", {}).get("ping", {})
                speed_results = conn.get("test_results", {}).get("speedtest", {})                
                print(f"🥇 {i}. {ssid} ({signal}% señal)")

                if "error" in ping_results or "error" in speed_results:
                    print("HUBO ERROR ACA")
                
                if "error" not in ping_results:
                    print(f"   🏓 Ping: {ping_results.get('avg_time', 0):.1f}ms")


                if "error" not in speed_results:       
                    download_val = speed_results.get("download", {}).get("bandwidth", 0)
                    download = download_val / 1_000_000 if isinstance(download_val, (int, float)) else 0
                    
                    upload_val = speed_results.get("upload", {}).get("bandwidth", 0)
                    upload = upload_val / 1_000_000 if isinstance(upload_val, (int, float)) else 0
                    print(f"   🚀 Velocidad: {download:.1f}↓ / {upload:.1f}↑ Mbps")
                else: 
                    print("Error en speedtest en main monitor")
        
        # FASE 2: PRUEBAS ADICIONALES EN LA MEJOR RED
        print(f"\n🎯 === FASE 2: PRUEBAS ADICIONALES ===")
        
        # Volver a conectar a la mejor red para pruebas adicionales
        if successful_connections:
            best_network = successful_connections[0]
            best_ssid = best_network.get("ssid", "")
            
            print(f"🔗 Reconectando a la mejor red: {best_ssid}")
            connection_result = analyzer.connect_to_network(best_ssid)
            
            if connection_result.get("success", False):
                print(f"✅ Conectado a {best_ssid} para pruebas adicionales")
                
                # Obtener información detallada
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
                
                # Ejecutar pruebas adicionales
                additional_tests = {
                    "ping": run_ping(),
                    "traceroute": run_traceroute(),
                    "speedtest": run_speedtest(),
                    "iperf3": run_iperf_external()
                }
                
                # Mostrar resultados de pruebas adicionales
                print(f"\n🧪 === RESULTADOS PRUEBAS ADICIONALES ===")
                
                if "error" not in additional_tests["ping"]:
                    print(f"🏓 Ping: {additional_tests['ping']['avg_time']:.1f}ms promedio, {additional_tests['ping']['packet_loss']} pérdida")
                
                if "error" not in additional_tests["speedtest"]:
                    download_val = additional_tests["speedtest"].get("download", {}).get("bandwidth", 0)
                    download = download_val / 1_000_000 if isinstance(download_val, (int, float)) else 0
                    upload_val = additional_tests["speedtest"].get("upload", {}).get("bandwidth", 0)
                    upload = upload_val / 1_000_000 if isinstance(upload_val, (int, float)) else 0
                    print(f"   🚀 Velocidad: {download:.1f}↓ / {upload:.1f}↑ Mbps")
                  
                    print(f"🚀 Velocidad: {download:.1f} Mbps ↓ / {upload:.1f} Mbps ↑")
                
                if "error" not in additional_tests["iperf3"]:
                    try:
                        throughput = additional_tests["iperf3"]["end"]["sum_received"]["bits_per_second"] / 1_000_000
                        print(f"⚡ iperf3: {throughput:.1f} Mbps")
                    except:
                        print("⚡ iperf3: datos recibidos")
                
                # Compilar resultado completo
                result = {
                    "iteration": iteration,
                    "timestamp": datetime.now().isoformat(),
                    "all_networks_tested": all_network_results,
                    "successful_connections": len(successful_connections),
                    "failed_connections": len(failed_connections),
                    "best_network": best_network,
                    "current_wifi": current_wifi,
                    "wifi_summary": wifi_summary,
                    "additional_tests": additional_tests
                }
                
            else:
                print(f"❌ No se pudo reconectar a {best_ssid}")
                result = {
                    "iteration": iteration,
                    "timestamp": datetime.now().isoformat(),
                    "all_networks_tested": all_network_results,
                    "successful_connections": len(successful_connections),
                    "failed_connections": len(failed_connections),
                    "error": "No se pudo reconectar a la mejor red"
                }
        
        else:
            print("❌ No se pudo conectar a ninguna red")
            result = {
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
                "all_networks_tested": all_network_results,
                "successful_connections": 0,
                "failed_connections": len(failed_connections),
                "error": "No se pudo conectar a ninguna red"
            }
        
        # Mostrar errores
        error_count = 0
        for network_result in all_network_results:
            if network_result.get("error"):
                error_count += 1
                if error_count <= 3:  # Mostrar solo los primeros 3 errores
                    print(f"❌ {network_result.get('ssid', 'Desconocida')}: {network_result['error']}")
        
        if error_count > 3:
            print(f"❌ ... y {error_count - 3} errores más")
        
        # Resumen de redes detectadas
        wifi_summary = analyzer.get_network_summary()
        print(f"\n📡 === RESUMEN REDES DETECTADAS ===")
        print(f"📊 Total detectadas: {wifi_summary['total_networks']}")
        print(f"🔓 Redes abiertas: {wifi_summary['open_networks']}")
        print(f"💾 Redes guardadas: {wifi_summary['saved_networks']}")
        print(f"📶 Señal máxima: {wifi_summary['strongest_signal']}%")
        
        # Mostrar top 3 redes
        for i, network in enumerate(wifi_summary['networks'][:3], 1):
            status = "🟢" if network.get('is_current') else "🔓" if network.get('is_open') else "🔒"
            print(f"  {status} {i}. {network.get('ssid', 'Sin nombre')} - {network.get('signal_percentage', 0)}%")
        
        # Guardar resultado
        save_result(result, f"all_networks_test_{datetime.now().strftime('%Y%m%d')}.json")
        print(f"\n💾 Resultado guardado")
        
        # Esperar siguiente iteración
        print(f"\n⏰ Esperando {INTERVAL_MINUTES} minutos para próxima iteración...")
        print(f"{'='*60}")
        time.sleep(INTERVAL_MINUTES * 60)