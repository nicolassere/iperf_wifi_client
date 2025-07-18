import subprocess
import json
import time
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from config.config import *
import traceback


class WiFiAnalyzer:
    """Analizador WiFi para Windows usando netsh - Solo redes visibles."""
    
    def __init__(self):
        self.last_scan = 0
        self.cached_networks = []
        self.tested_networks = set()  # Para evitar reconectar constantemente
    
    def scan_networks(self, force_refresh=False) -> List[Dict]:
        """Escanea SOLO redes WiFi visibles actualmente."""
        current_time = time.time()
        
        # Usar caché si es reciente y no se fuerza refresh
        if not force_refresh and (current_time - self.last_scan) < 30:
            return self.cached_networks
        
        try:
            print("🔍 Escaneando redes WiFi visibles...")
            
            # Forzar refresh del perfil WiFi
            subprocess.run(["netsh", "wlan", "refresh"], 
                         capture_output=True, timeout=10)
            
            # Obtener SOLO redes visibles
            networks = self._get_all_visible_networks()
            
            # Obtener información de conexión actual
            current_info = self.get_current_connection_info()
            current_ssid = current_info.get("ssid", "")
            
            # Marcar red actual y verificar cuáles están guardadas
            for network in networks:
                if network.get('ssid') == current_ssid:
                    network.update(current_info)
                    network["is_current"] = True
                    network["status"] = "connected"
                else:
                    network["is_current"] = False
                    network["status"] = "available"
                
                # Verificar si está guardada
                network["is_saved"] = self._is_network_saved(network.get('ssid', ''))
            
            self.cached_networks = networks
            self.last_scan = current_time
            
            print(f"✓ Encontradas {len(networks)} redes visibles")
            return networks
            
        except Exception as e:
            print(f"❌ Error escaneando redes: {e}")
            return []
    
    def _get_all_visible_networks(self) -> List[Dict]:
        """Obtiene TODAS las redes visibles (no solo la conectada)."""
        networks = []
        
        try:
            # Comando para obtener todas las redes disponibles
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True,
                text=True,
                timeout=20,
                encoding='cp1252'
            )
            
            current_network = {}
            
            for line in result.stdout.splitlines():
                line = line.strip()
                
                # Detectar inicio de nueva red
                if line.startswith("SSID") and ":" in line:
                    # Guardar red anterior si existe
                    if current_network.get("ssid"):
                        networks.append(current_network.copy())
                    
                    # Iniciar nueva red
                    ssid = line.split(":", 1)[1].strip()
                    current_network = {
                        "ssid": ssid,
                        "is_current": False,
                        "is_saved": False,
                        "signal_strength": "N/A",
                        "signal_percentage": 0,
                        "channel": "N/A",
                        "radio_type": "N/A",
                        "authentication": "N/A",
                        "encryption": "N/A",
                        "bssid": "N/A",
                        "mac_address": "N/A",
                        "network_type": "N/A",
                        "is_connectable": True
                    }
                
                elif ":" in line and current_network.get("ssid"):
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    # Múltiples variaciones de nombres según idioma y codificación
                    if any(term in key for term in ["network type", "tipo de red"]):
                        current_network["network_type"] = value
                    elif any(term in key for term in ["authentication", "autenticación", "autenticacion", "autenticaci¢n"]):
                        current_network["authentication"] = value
                        # Determinar si es conectable
                        if "open" in value.lower() or "abierto" in value.lower():
                            current_network["is_open"] = True
                        else:
                            current_network["is_open"] = False
                    elif any(term in key for term in ["encryption", "cifrado", "cipher"]):
                        current_network["encryption"] = value
                    elif "bssid" in key:
                        current_network["bssid"] = value
                        current_network["mac_address"] = value
                    elif any(term in key for term in ["signal", "señal", "senal", "se¤al"]):
                        current_network["signal_strength"] = value
                        # Extraer porcentaje numérico
                        match = re.search(r'(\d+)%', value)
                        if match:
                            current_network["signal_percentage"] = int(match.group(1))
                        else:
                            # Si no tiene %, buscar solo números
                            match = re.search(r'(\d+)', value)
                            if match:
                                current_network["signal_percentage"] = int(match.group(1))
                    elif any(term in key for term in ["radio type", "tipo de radio"]):
                        current_network["radio_type"] = value
                    elif any(term in key for term in ["channel", "canal"]):
                        current_network["channel"] = value
            
            # Agregar última red
            if current_network.get("ssid"):
                networks.append(current_network)
            
            # Filtrar redes válidas y ordenar por señal
            valid_networks = []
            for network in networks:
                if network.get("ssid") and network.get("ssid") != "":
                    valid_networks.append(network)
            
            # Ordenar por señal (más fuerte primero)
            valid_networks.sort(key=lambda x: x.get("signal_percentage", 0), reverse=True)
            
            return valid_networks
            
        except Exception as e:
            print(f"❌ Error obteniendo redes visibles: {e}")
            return []
    
    def _is_network_saved(self, ssid: str) -> bool:
        """Verifica si una red está guardada en el sistema."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "profiles"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            for line in result.stdout.splitlines():
                if "All User Profile" in line or "Perfil de todos los usuarios" in line:
                    profile_name = line.split(":")[-1].strip()
                    if profile_name == ssid:
                        return True
            return False
            
        except Exception:
            return False
    
    def connect_to_all_available_networks(self) -> List[Dict]:
        """Conecta a TODAS las redes disponibles y prueba cada una."""
        networks = self.scan_networks(force_refresh=True)
        connection_results = []
        
        print(f"\n🔄 === PROBANDO TODAS LAS REDES DISPONIBLES ===")
        print(f"📡 Redes encontradas: {len(networks)}")
        
        for i, network in enumerate(networks, 1):
            ssid = network.get("ssid", "")
            if not ssid or ssid in self.tested_networks:
                continue
            
            print(f"\n🔗 [{i}/{len(networks)}] Probando: {ssid}")
            print(f"   📶 Señal: {network.get('signal_percentage', 0)}%")
            print(f"   🔐 Seguridad: {network.get('authentication', 'N/A')}")
            print(f"   📍 BSSID: {network.get('bssid', 'N/A')}")
            
            # Intentar conexión
            connection_result = self.test_network_connection(network)
            connection_results.append(connection_result)
            
            # Marcar como probada
            self.tested_networks.add(ssid)
            
            # Pequeña pausa entre conexiones
            time.sleep(2)
        
        return connection_results
    
    def test_network_connection(self, network: Dict) -> Dict:
        """Prueba la conexión a una red específica."""
        ssid = network.get("ssid", "")
        is_open = network.get("is_open", False)
        is_saved = network.get("is_saved", False)
        
        result = {
            "ssid": ssid,
            "network_info": network,
            "connection_attempted": True,
            "connection_successful": False,
            "connection_time": None,
            "test_results": {},
            "error": None
        }
        
        try:
            start_time = time.time()
            
            # Desconectar de red actual
            self.disconnect_current()
            time.sleep(1)
            
            # Intentar conexión
            if is_saved:
                # Red guardada - intentar conexión directa
                print(f"   💾 Red guardada - conectando...")
                connection_result = self.connect_to_network(ssid)
            elif is_open:
                # Red abierta - intentar conexión sin contraseña
                print(f"   🔓 Red abierta - conectando...")
                connection_result = self.connect_to_network(ssid)
            else:
                # Red protegida no guardada - marcar como no conectable
                print(f"   🔒 Red protegida sin credenciales - saltando...")
                result["connection_attempted"] = False
                result["error"] = "Red protegida sin credenciales guardadas"
                return result
            
            connection_time = time.time() - start_time
            result["connection_time"] = connection_time
            
            if connection_result.get("success", False):
                result["connection_successful"] = True
                print(f"   ✅ Conectado en {connection_time:.1f}s")
                
                # Realizar pruebas de red
                test_results = self.perform_network_tests()
                print(test_results)
                result["test_results"] = test_results
                
                # Mostrar resultados inmediatos
                if "ping" in test_results and "error" not in test_results["ping"]:
                    ping_avg = test_results["ping"].get("avg_time", 0)
                    print(f"   🏓 Ping: {ping_avg:.1f}ms")

                if "speedtest" in test_results and "error" not in test_results["speedtest"]:
                    download_val = test_results["speedtest"].get("download", {}).get("bandwidth", 0)
                    download = download_val / 1_000_000 if isinstance(download_val, (int, float)) else 0
                    
                    upload_val = test_results["speedtest"].get("upload", {}).get("bandwidth", 0)
                    upload = upload_val / 1_000_000 if isinstance(upload_val, (int, float)) else 0
                    
                    print(f"   🚀 Velocidad: {download:.1f}↓ / {upload:.1f}↑ Mbps")                
                            
                
            else:
                result["error"] = connection_result.get("error", "Error desconocido")
                print(f"   ❌ Falló: {result['error']}")
            
        except Exception as e:
            result["error"] = str(e)
            print(traceback.format_exc())

            print("ERROR ACA")
            print(f"   💥 Excepción: {e}")
        
        return result
    
    def perform_network_tests(self) -> Dict:
        """Realiza pruebas de red rápidas."""
        from services.network_tests import run_ping, run_speedtest
        
        return {
            "ping": run_ping(),
            "speedtest": run_speedtest(),
            "connection_info": self.get_current_connection_info()
        }
    
    def connect_to_network(self, ssid: str, password: str = None) -> Dict:
        """Intenta conectar a una red WiFi."""
        try:
            if password:
                # Conectar con contraseña
                result = subprocess.run(
                    ["netsh", "wlan", "connect", f"name={ssid}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                # Conectar sin contraseña (red abierta o guardada)
                result = subprocess.run(
                    ["netsh", "wlan", "connect", f"name={ssid}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            
            if result.returncode == 0:
                time.sleep(3)  # Esperar estabilización
                return {
                    "success": True,
                    "ssid": ssid,
                    "message": "Conexión exitosa"
                }
            else:
                return {
                    "success": False,
                    "ssid": ssid,
                    "error": result.stderr or "Error de conexión",
                    "message": "Falló la conexión"
                }
                
        except Exception as e:
            return {
                "success": False,
                "ssid": ssid,
                "error": str(e),
                "message": "Error de conexión"
            }
    
    def get_current_connection_info(self) -> Dict:
        """Obtiene información detallada de la conexión actual."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='cp1252'
            )
            
            info = {}
            for line in result.stdout.splitlines():
                line = line.strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if any(term in key for term in ["name", "nombre"]):
                        info["interface_name"] = value
                    elif any(term in key for term in ["description", "descripción", "descripcion", "descripci¢n"]):
                        info["adapter_description"] = value
                    elif "guid" in key:
                        info["guid"] = value
                    elif any(term in key for term in ["physical address", "dirección física", "direccion fisica", "direcci¢n f¡sica"]):
                        info["mac_address"] = value
                    elif any(term in key for term in ["state", "estado"]) and "hospedada" not in key:
                        info["connection_state"] = value
                    elif "ssid" in key and "bssid" not in key:
                        info["ssid"] = value
                    elif "bssid" in key:
                        info["bssid"] = value
                        info["ap_mac"] = value
                    elif any(term in key for term in ["network type", "tipo de red"]):
                        info["network_type"] = value
                    elif any(term in key for term in ["radio type", "tipo de radio"]):
                        info["radio_type"] = value
                    elif any(term in key for term in ["authentication", "autenticación", "autenticacion", "autenticaci¢n"]):
                        info["authentication"] = value
                    elif any(term in key for term in ["cipher", "cifrado"]):
                        info["encryption"] = value
                    elif any(term in key for term in ["connection mode", "modo de conexión", "modo de conexion", "modo de conexi¢n"]):
                        info["connection_mode"] = value
                    elif any(term in key for term in ["channel", "canal"]):
                        info["channel"] = value
                    elif any(term in key for term in ["receive rate", "velocidad de recepción", "velocidad de recepcion", "velocidad de recepci¢n"]):
                        info["receive_rate"] = value
                    elif any(term in key for term in ["transmit rate", "velocidad de transmisión", "velocidad de transmision", "velocidad de transmisi¢n"]):
                        info["transmit_rate"] = value
                    elif any(term in key for term in ["signal", "señal", "senal", "se¤al"]):
                        info["signal_strength"] = value
                        # Extraer porcentaje numérico
                        match = re.search(r'(\d+)%', value)
                        if match:
                            info["signal_percentage"] = int(match.group(1))
                        else:
                            # Si no tiene %, buscar solo números
                            match = re.search(r'(\d+)', value)
                            if match:
                                info["signal_percentage"] = int(match.group(1))
            
            return info
            
        except Exception as e:
            return {"error": f"Error obteniendo info de conexión: {str(e)}"}
    
    def disconnect_current(self) -> bool:
        """Desconecta de la red WiFi actual."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "disconnect"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def get_network_summary(self) -> Dict:
        """Obtiene resumen de redes VISIBLES."""
        networks = self.scan_networks()
        
        summary = {
            "total_networks": len(networks),
            "connected_networks": len([n for n in networks if n.get("is_current", False)]),
            "saved_networks": len([n for n in networks if n.get("is_saved", False)]),
            "open_networks": len([n for n in networks if n.get("is_open", False)]),
            "strongest_signal": max([n.get("signal_percentage", 0) for n in networks] + [0]),
            "networks": networks
        }
        
        return summary
    
    def get_detailed_scan_info(self) -> List[Dict]:
        """Obtiene información detallada de escaneo incluyendo canales y BSSID."""
        try:
            # Comando para obtener información detallada
            result = subprocess.run(
                ["netsh", "wlan", "show", "profiles"], 
                capture_output=True, text=True, encoding='utf-8'
            )
            
            # También obtener información de redes disponibles
            scan_result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, encoding='utf-8'
            )
            
            # Parsear y devolver información estructurada
            detailed_networks = []
            # Aquí iría la lógica de parsing específica para tu sistema
            # Esta es una implementación de ejemplo
            
            return detailed_networks
        except Exception as e:
            return {"error": f"Error en escaneo detallado: {e}"}

    def analyze_channel_distribution(self) -> Dict:
        """Analiza la distribución de canales en el entorno."""
        networks = self.get_detailed_scan_info()
        
        channel_analysis = {
            'channel_distribution': defaultdict(int),
            'band_distribution': {'2.4GHz': 0, '5GHz': 0},
            'congestion_score': 0,
            'recommendations': []
        }
        
        for network in networks:
            channel = network.get('channel')
            if channel:
                channel_analysis['channel_distribution'][channel] += 1
                
                # Clasificar por banda
                if channel <= 14:
                    channel_analysis['band_distribution']['2.4GHz'] += 1
                else:
                    channel_analysis['band_distribution']['5GHz'] += 1
        
        # Calcular puntuación de congestión
        total_networks = len(networks)
        if total_networks > 0:
            # Más redes en pocos canales = mayor congestión
            unique_channels = len(channel_analysis['channel_distribution'])
            channel_analysis['congestion_score'] = (total_networks / max(unique_channels, 1)) * 10
        
        return channel_analysis
        
        
        
    def reset_tested_networks(self):
            """Reinicia el conjunto de redes probadas."""
            self.tested_networks.clear()
            print("🔄 Lista de redes probadas reiniciada")