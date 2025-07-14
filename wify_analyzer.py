# wifi_analyzer.py
"""
Analizador WiFi para Windows usando netsh
"""

import subprocess
import time
import re
from typing import List, Dict, Optional
from config import NETSH_TIMEOUT


class WiFiAnalyzer:
    """Analizador WiFi para Windows usando netsh."""
    
    def __init__(self):
        self.last_scan = 0
        self.cached_networks = []
    
    def scan_networks(self, force_refresh=False) -> List[Dict]:
        """Escanea redes WiFi disponibles."""
        current_time = time.time()
        
        # Usar caché si es reciente y no se fuerza refresh
        if not force_refresh and (current_time - self.last_scan) < 30:
            return self.cached_networks
        
        try:
            print("🔍 Escaneando redes WiFi...")
            
            # Forzar refresh del perfil WiFi
            subprocess.run(["netsh", "wlan", "refresh"], 
                         capture_output=True, timeout=10)
            
            # Obtener redes disponibles
            networks = self._parse_available_networks()
            self.cached_networks = networks
            self.last_scan = current_time
            
            print(f"✓ Encontradas {len(networks)} redes")
            return networks
            
        except Exception as e:
            print(f"❌ Error escaneando redes: {e}")
            return []
    
    def _parse_available_networks(self) -> List[Dict]:
        """Parsea la salida de netsh para obtener información de redes."""
        networks = []
        
        try:
            # Obtener perfiles guardados
            result = subprocess.run(
                ["netsh", "wlan", "show", "profiles"],
                capture_output=True,
                text=True,
                timeout=NETSH_TIMEOUT
            )
            
            # Obtener información de la conexión actual
            current_info = self.get_current_connection_info()
            current_ssid = current_info.get("ssid", "")
            
            # Parsear perfiles guardados
            saved_profiles = []
            for line in result.stdout.splitlines():
                if "All User Profile" in line or "Perfil de todos los usuarios" in line:
                    profile_name = line.split(":")[-1].strip()
                    if profile_name:
                        saved_profiles.append(profile_name)
            
            # Obtener detalles de cada perfil guardado
            for profile_name in saved_profiles:
                network_info = self._get_network_details(profile_name)
                if network_info:
                    if profile_name == current_ssid:
                        network_info.update(current_info)
                        network_info["is_current"] = True
                        network_info["status"] = "connected"
                    else:
                        network_info["is_current"] = False
                        network_info["status"] = "saved"
                    
                    networks.append(network_info)
            
            # Obtener redes disponibles (no solo guardadas)
            visible_networks = self._get_all_visible_networks()
            
            # Combinar información
            for visible in visible_networks:
                existing = next((n for n in networks if n.get('ssid') == visible.get('ssid')), None)
                if not existing:
                    visible["is_saved"] = False
                    visible["status"] = "available"
                    networks.append(visible)
                else:
                    existing.update({k: v for k, v in visible.items() if v and k not in ['is_saved', 'status']})
            
        except Exception as e:
            print(f"❌ Error parseando redes: {e}")
        
        return networks
    
    def _get_all_visible_networks(self) -> List[Dict]:
        """Obtiene TODAS las redes visibles."""
        networks = []
        
        try:
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
                
                if line.startswith("SSID") and ":" in line:
                    if current_network.get("ssid"):
                        networks.append(current_network.copy())
                    
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
                        "network_type": "N/A"
                    }
                
                elif ":" in line and current_network.get("ssid"):
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if any(term in key for term in ["network type", "tipo de red"]):
                        current_network["network_type"] = value
                    elif any(term in key for term in ["authentication", "autenticación", "autenticacion", "autenticaci¢n"]):
                        current_network["authentication"] = value
                    elif any(term in key for term in ["encryption", "cifrado", "cipher"]):
                        current_network["encryption"] = value
                    elif "bssid" in key:
                        current_network["bssid"] = value
                        current_network["mac_address"] = value
                    elif any(term in key for term in ["signal", "señal", "senal", "se¤al"]):
                        current_network["signal_strength"] = value
                        match = re.search(r'(\d+)%', value)
                        if match:
                            current_network["signal_percentage"] = int(match.group(1))
                        else:
                            match = re.search(r'(\d+)', value)
                            if match:
                                current_network["signal_percentage"] = int(match.group(1))
                    elif any(term in key for term in ["radio type", "tipo de radio"]):
                        current_network["radio_type"] = value
                    elif any(term in key for term in ["channel", "canal"]):
                        current_network["channel"] = value
            
            if current_network.get("ssid"):
                networks.append(current_network)
            
        except Exception as e:
            print(f"❌ Error obteniendo redes visibles: {e}")
        
        return networks
    
    def _get_network_details(self, profile_name: str) -> Optional[Dict]:
        """Obtiene detalles de una red específica."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "profile", profile_name, "key=clear"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            network_info = {
                "ssid": profile_name,
                "is_saved": True,
                "status": "saved"
            }
            
            for line in result.stdout.splitlines():
                line = line.strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if "authentication" in key or "autenticación" in key:
                        network_info["authentication"] = value
                    elif "cipher" in key or "cifrado" in key:
                        network_info["encryption"] = value
                    elif "security key" in key or "clave de seguridad" in key:
                        network_info["security_type"] = value
                    elif "key content" in key or "contenido de la clave" in key:
                        network_info["has_password"] = bool(value and value != "")
            
            return network_info
            
        except Exception as e:
            print(f"❌ Error obteniendo detalles de {profile_name}: {e}")
            return None
    
    def connect_to_network(self, ssid: str, password: str = None) -> Dict:
        """Intenta conectar a una red WiFi."""
        try:
            print(f"🔗 Intentando conectar a: {ssid}")
            
            result = subprocess.run(
                ["netsh", "wlan", "connect", f"name={ssid}"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"✅ Conectado exitosamente a {ssid}")
                time.sleep(3)
                return {
                    "success": True,
                    "ssid": ssid,
                    "message": "Conexión exitosa",
                    "details": self.get_current_connection_info()
                }
            else:
                print(f"❌ Error conectando a {ssid}: {result.stderr}")
                return {
                    "success": False,
                    "ssid": ssid,
                    "error": result.stderr,
                    "message": "Falló la conexión"
                }
                
        except Exception as e:
            print(f"❌ Excepción conectando a {ssid}: {e}")
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
                        match = re.search(r'(\d+)%', value)
                        if match:
                            info["signal_percentage"] = int(match.group(1))
                        else:
                            match = re.search(r'(\d+)', value)
                            if match:
                                info["signal_percentage"] = int(match.group(1))
            
            return info
            
        except Exception as e:
            print(f"❌ Error obteniendo info de conexión: {e}")
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
        """Obtiene resumen de todas las redes."""
        networks = self.scan_networks()
        
        summary = {
            "total_networks": len(networks),
            "connected_networks": len([n for n in networks if n.get("is_current", False)]),
            "saved_networks": len([n for n in networks if n.get("is_saved", False)]),
            "open_networks": len([n for n in networks if n.get("authentication", "").lower() in ["open", "abierto"]]),
            "strongest_signal": max([n.get("signal_percentage", 0) for n in networks] + [0]),
            "networks": networks
        }
        
        return summary