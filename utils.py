# utils.py
"""
Funciones utilitarias para el sistema de monitoreo
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict
from wifi_analyzer import WiFiAnalyzer
from config import DEFAULT_OUTPUT_FILE


def save_result(result_dict: Dict, output_path: str = DEFAULT_OUTPUT_FILE):
    """Guarda resultado con timestamp."""
    result_dict["timestamp"] = datetime.now().isoformat()
    
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []
        
        data.append(result_dict)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    except Exception as e:
        print(f"✗ Error guardando resultado: {e}")


def display_wifi_summary(analyzer: WiFiAnalyzer):
    """Muestra resumen de WiFi de forma amigable."""
    summary = analyzer.get_network_summary()
    
    print(f"\n📊 === RESUMEN WIFI ===")
    print(f"📡 Redes totales: {summary['total_networks']}")
    print(f"🔗 Redes conectadas: {summary['connected_networks']}")
    print(f"💾 Redes guardadas: {summary['saved_networks']}")
    print(f"🔓 Redes abiertas: {summary['open_networks']}")
    print(f"📶 Señal más fuerte: {summary['strongest_signal']}%")
    
    print(f"\n📱 === REDES DETECTADAS ===")
    for i, network in enumerate(summary['networks'][:10], 1):
        status_icon = "🟢" if network.get('is_current') else "🔵" if network.get('is_saved') else "⚪"
        
        print(f"{status_icon} {i}. {network.get('ssid', 'Sin nombre')}")
        print(f"   📍 MAC: {network.get('bssid', 'N/A')}")
        print(f"   📶 Señal: {network.get('signal_strength', 'N/A')} ({network.get