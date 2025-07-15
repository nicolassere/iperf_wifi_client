
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import sys
from services.wifi_analyzer import WiFiAnalyzer
from services.network_tester import test_single_network
from services.network_tester import test_single_network
from services.wifi_interface import wifi_analyzer_mode, display_wifi_summary
from services.main_monitor import main_loop
from config.config import *



if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd == "analyzer":
            # Modo analizador interactivo
            wifi_analyzer_mode()
        elif cmd == "test" and len(sys.argv) >= 3:
            # Prueba de red específica
            ssid = sys.argv[2]
            password = sys.argv[3] if len(sys.argv) >= 4 else None
            duration = int(sys.argv[4]) if len(sys.argv) >= 5 else 60
            test_single_network(ssid, password, duration)
        elif cmd == "scan":
            # Escaneo simple
            analyzer = WiFiAnalyzer()
            display_wifi_summary(analyzer)
        else:
            print("Uso:")
            print("  python script.py analyzer        - Modo analizador interactivo")
            print("  python script.py scan           - Escaneo simple de redes")
            print("  python script.py test <ssid> [password] [duration] - Prueba red específica")
            print("  python script.py               - Monitoreo continuo (modo original)")
    else:
        # Modo original mejorado
        try:
            main_loop()
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoreo detenido por el usuario")
        except Exception as e:
            print(f"\n\n💥 Error fatal: {e}")