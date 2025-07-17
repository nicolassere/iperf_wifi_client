import time
from datetime import datetime
from services.wifi_analyzer import WiFiAnalyzer
from config.config import *

def display_wifi_summary(analyzer: WiFiAnalyzer):
    """Muestra resumen de WiFi solo de redes visibles."""
    summary = analyzer.get_network_summary()
    
    # Filtrar solo las redes visibles (que tienen signal_strength distinto de "N/A")
    visible_networks = [
        net for net in summary['networks'] 
        if net.get('signal_strength') != "N/A"
    ]
    
    print(f"\n📊 === RESUMEN WIFI (Solo redes visibles) ===")
    print(f"📡 Redes visibles: {len(visible_networks)}")
    print(f"🔗 Redes conectadas: {summary['connected_networks']}")
    print(f"💾 Redes guardadas: {summary['saved_networks']}")
    print(f"🔓 Redes abiertas: {summary['open_networks']}")
    print(f"📶 Señal más fuerte: {summary['strongest_signal']}%")
    
    print(f"\n📱 === REDES DETECTADAS (VISIBLES) ===")
    for i, network in enumerate(visible_networks[:10], 1):  # Mostrar máximo 10
        status_icon = "🟢" if network.get('is_current') else "🔵" if network.get('is_saved') else "⚪"
        
        print(f"{status_icon} {i}. {network.get('ssid', 'Sin nombre')}")
        print(f"   📍 MAC: {network.get('bssid', 'N/A')}")
        print(f"   📶 Señal: {network.get('signal_strength')} ({network.get('signal_percentage', 0)}%)")
        print(f"   🔐 Seguridad: {network.get('authentication', 'N/A')} | {network.get('encryption', 'N/A')}")
        print(f"   📻 Canal: {network.get('channel', 'N/A')} | Tipo: {network.get('radio_type', 'N/A')}")
        if network.get('is_current'):
            print(f"   🔗 Estado: CONECTADA")
        elif network.get('is_saved'):
            print(f"   💾 Estado: GUARDADA")
        print()

 

def wifi_analyzer_mode():
    """Modo analizador WiFi interactivo."""
    analyzer = WiFiAnalyzer()
    
    print("🔍 === MODO ANALIZADOR WIFI ===")
    print("Comandos disponibles:")
    print("  scan - Escanear redes")
    print("  show - Mostrar resumen")
    print("  connect <ssid> [password] - Conectar a red")
    print("  disconnect - Desconectar")
    print("  current - Info de conexión actual")
    print("  monitor - Monitoreo continuo")
    print("  exit - Salir")
    print()
    
    while True:
        try:
            command = input("WiFi> ").strip().split()
            if not command:
                continue
                
            cmd = command[0].lower()
            
            if cmd == "exit":
                break
            elif cmd == "scan":
                analyzer.scan_networks(force_refresh=True)
                display_wifi_summary(analyzer)
            elif cmd == "show":
                display_wifi_summary(analyzer)
            elif cmd == "current":
                info = analyzer.get_current_connection_info()
                if "error" in info:
                    print(f"❌ {info['error']}")
                else:
                    print(f"🔗 Red actual: {info.get('ssid', 'Sin conexión')}")
                    print(f"📍 MAC AP: {info.get('bssid', 'N/A')}")
                    print(f"📶 Señal: {info.get('signal_strength', 'N/A')}")
                    print(f"🔐 Seguridad: {info.get('authentication', 'N/A')}")
                    print(f"📻 Canal: {info.get('channel', 'N/A')}")
            elif cmd == "disconnect":
                if analyzer.disconnect_current():
                    print("✅ Desconectado exitosamente")
                else:
                    print("❌ Error al desconectar")
            elif cmd == "connect":
                if len(command) >= 2:
                    ssid = command[1]
                    password = command[2] if len(command) >= 3 else None
                    result = analyzer.connect_to_network(ssid, password)
                    if result['success']:
                        print(f"✅ {result['message']}")
                    else:
                        print(f"❌ {result['message']}: {result.get('error', '')}")
                else:
                    print("❌ Uso: connect <ssid> [password]")
            elif cmd == "monitor":
                print("📊 Iniciando monitoreo continuo... (Ctrl+C para detener)")
                try:
                    while True:
                        display_wifi_summary(analyzer)
                        time.sleep(30)  # Actualizar cada 30 segundos
                except KeyboardInterrupt:
                    print("\n⏹️ Monitoreo detenido")
            else:
                print(f"❌ Comando desconocido: {cmd}")
                
        except KeyboardInterrupt:
            print("\n👋 Saliendo del analizador WiFi...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")