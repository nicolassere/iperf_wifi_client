import subprocess
import time
import re
from datetime import datetime
from typing import List, Dict
from collections import defaultdict
from config.config import Config




class WiFiScanner:
    """Enhanced WiFi scanner with connection capabilities and SSID filtering."""
    
    def __init__(self):
        self.last_scan = 0
        self.cached_networks = []
        self.tested_networks = set()
        # NUEVO: Cache de APs por SSID+BSSID
        self.ap_cache = {}  # Key: "SSID_BSSID", Value: AP data
    
    def scan_networks(self, force_refresh=False) -> List[Dict]:
        """
        Scan WiFi networks - VERSIÓN MEJORADA CON FILTRADO POR SSID
        Funciona con español/inglés y filtra solo SSIDs monitoreados
        """
        try:
            print("🔄 Escaneando redes WiFi...")
            
            # Mostrar qué SSIDs estamos monitoreando
            if hasattr(Config, 'MONITORED_SSIDS') and Config.MONITORED_SSIDS:
                print(f"📋 Monitoreando SSIDs: {', '.join(Config.MONITORED_SSIDS)}")
            else:
                print(f"📋 Monitoreando TODAS las redes")
            
            # Force refresh - comando correcto
            try:
                subprocess.run(["netsh", "wlan", "refresh", "hostednetwork"], 
                            capture_output=True, timeout=10)
            except:
                # Fallback si no funciona el refresh
                pass
            
            time.sleep(1)
            
            # FORZAR mode=bssid para obtener BSSID (crítico para múltiples APs)
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True,
                text=True,
                timeout=20,
                encoding='cp1252'
            )
            
            print(f"✅ Comando netsh ejecutado, código: {result.returncode}")
            
            if result.returncode != 0:
                print(f"⚠️ Error con mode=bssid, probando comando básico...")
                # Fallback a comando básico
                result = subprocess.run(
                    ["netsh", "wlan", "show", "networks"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    encoding='cp1252'
                )
                
                if result.returncode != 0:
                    print(f"❌ Error en netsh: {result.stderr}")
                    return []
                else:
                    print("⚠️ Usando comando básico - no se obtendrán BSSIDs individuales")
            
            # Debug: mostrar primeras líneas
            lines = result.stdout.splitlines()
            print(f"📋 Procesando {len(lines)} líneas de salida...")
            
            # Mostrar algunas líneas para debug (solo si es desarrollo)
            if hasattr(Config, 'DEBUG_MODE') and Config.DEBUG_MODE:
                print("🔍 Primeras líneas de netsh:")
                for i, line in enumerate(lines[:10]):
                    if line.strip():
                        print(f"   {i:2d}: '{line.strip()}'")
            
            networks = []
            current_network = {}
            
            for line_num, line in enumerate(lines):
                line = line.strip()
                
                # DETECTAR INICIO DE NUEVA RED
                # Patrones: "SSID 1 : NombreRed" o "SSID : NombreRed"
                if re.match(r'^SSID\s*\d*\s*:', line, re.IGNORECASE):
                    # Guardar red anterior si existe y es relevante
                    if self._should_save_network(current_network):
                        # Calcular métricas adicionales
                        self._calculate_signal_metrics(current_network)
                        current_network["is_saved"] = self._is_network_saved(current_network["ssid"])
                        # Generar clave única AP
                        ap_key = f"{current_network['ssid']}_{current_network['bssid']}"
                        current_network["ap_key"] = ap_key
                        self.ap_cache[ap_key] = current_network.copy()
                        networks.append(current_network.copy())
                        
                        print(f"   ✅ AP guardado: '{current_network['ssid']}' ({current_network['bssid'][-8:] if current_network['bssid'] != 'Unknown' else 'No-BSSID'}) - {current_network.get('signal_percentage', 0)}% - Canal {current_network.get('channel', 0)}")
                    
                    # Extraer SSID
                    ssid_match = re.search(r'SSID\s*\d*\s*:\s*(.*)$', line, re.IGNORECASE)
                    if ssid_match:
                        ssid_name = ssid_match.group(1).strip()
                        # Si SSID está vacío, crear nombre
                        if not ssid_name:
                            ssid_name = f"Hidden_Network_{len(networks)+1}"
                    else:
                        ssid_name = f"Unknown_Network_{len(networks)+1}"
                    
                    # Inicializar nueva red
                    current_network = {
                        "ssid": ssid_name,
                        "bssid": "Unknown", 
                        "signal_percentage": 0,
                        "signal_dbm": None,
                        "noise_dbm": None,
                        "snr_db": None,
                        "signal_quality": "Unknown",
                        "channel": 0,
                        "channel_width": "Unknown",
                        "band": "Unknown", 
                        "authentication": "Unknown",
                        "encryption": "Unknown",
                        "phy_type": "Unknown",
                        "max_rate_mbps": None,
                        "is_open": False,
                        "is_saved": False,
                        "timestamp": datetime.now().isoformat(),
                        "ap_key": None
                    }
                    
                    # Solo mostrar debug si es una red que monitoreamos
                    if self._should_monitor_ssid(ssid_name):
                        print(f"   🎯 SSID monitoreado encontrado: '{ssid_name}'")
                    
                    continue
                
                # PROCESAR ATRIBUTOS DE LA RED ACTUAL
                if current_network.get("ssid") and ":" in line:
                    try:
                        key, value = line.split(":", 1)
                        key = key.strip().lower()
                        value = value.strip()
                        
                        # BSSID (MAC address del AP) - CRÍTICO
                        if "bssid" in key:
                            current_network["bssid"] = value
                            if self._should_monitor_ssid(current_network["ssid"]):
                                print(f"     📍 BSSID: {value}")
                        
                        # SEÑAL - Manejo robusto
                        elif any(term in key for term in ["señal", "signal", "senal", "se¤al"]):
                            current_network["signal_strength"] = value
                            # Buscar porcentaje
                            percentage_match = re.search(r'(\d+)%', value)
                            if percentage_match:
                                signal_pct = int(percentage_match.group(1))
                                current_network["signal_percentage"] = signal_pct
                                current_network["signal_dbm"] = self._percentage_to_dbm(signal_pct)
                                if self._should_monitor_ssid(current_network["ssid"]):
                                    print(f"     📶 Señal: {signal_pct}% ({current_network['signal_dbm']:.1f} dBm)")
                            else:
                                # Buscar solo números sin %
                                number_match = re.search(r'(\d+)', value)
                                if number_match:
                                    signal_pct = int(number_match.group(1))
                                    current_network["signal_percentage"] = signal_pct
                                    current_network["signal_dbm"] = self._percentage_to_dbm(signal_pct)
                                    if self._should_monitor_ssid(current_network["ssid"]):
                                        print(f"     📶 Señal: {signal_pct}% (estimado)")
                        
                        # CANAL
                        elif any(term in key for term in ["canal", "channel"]):
                            channel_match = re.search(r'(\d+)', value)
                            if channel_match:
                                channel_num = int(channel_match.group(1))
                                current_network["channel"] = channel_num
                                # Determinar banda
                                if channel_num <= 14:
                                    current_network["band"] = "2.4GHz"
                                else:
                                    current_network["band"] = "5GHz"
                                if self._should_monitor_ssid(current_network["ssid"]):
                                    print(f"     📡 Canal: {channel_num} ({current_network['band']})")
                        
                        # AUTENTICACIÓN - Manejo español/inglés
                        elif any(term in key for term in ["autenticación", "authentication", "autenticacion", "autenticaci¢n"]):
                            current_network["authentication"] = value
                            # Detectar redes abiertas
                            if any(open_term in value.lower() for open_term in ["abierta", "open", "ninguna", "none"]):
                                current_network["is_open"] = True
                            if self._should_monitor_ssid(current_network["ssid"]):
                                print(f"     🔐 Autenticación: {value}")
                        
                        # CIFRADO - Manejo español/inglés  
                        elif any(term in key for term in ["cifrado", "encryption", "cipher"]):
                            current_network["encryption"] = value
                            if self._should_monitor_ssid(current_network["ssid"]):
                                print(f"     🔒 Cifrado: {value}")
                        
                        # TIPO DE RADIO
                        elif any(term in key for term in ["tipo de radio", "radio type", "tipo radio"]):
                            current_network["phy_type"] = value
                            # Determinar capacidades
                            if "802.11ax" in value or "wifi 6" in value.lower():
                                current_network["channel_width"] = "20/40/80/160 MHz"
                                current_network["max_rate_mbps"] = 1200
                            elif "802.11ac" in value or "wifi 5" in value.lower():
                                current_network["channel_width"] = "20/40/80 MHz"
                                current_network["max_rate_mbps"] = 866
                            elif "802.11n" in value or "wifi 4" in value.lower():
                                current_network["channel_width"] = "20/40 MHz"
                                current_network["max_rate_mbps"] = 300
                            elif "802.11g" in value:
                                current_network["channel_width"] = "20 MHz"
                                current_network["max_rate_mbps"] = 54
                            elif "802.11a" in value:
                                current_network["channel_width"] = "20 MHz"
                                current_network["max_rate_mbps"] = 54
                            if self._should_monitor_ssid(current_network["ssid"]):
                                print(f"     📻 Tipo: {value}")
                        
                        # TIPO DE RED (Infraestructura/Ad-hoc)
                        elif any(term in key for term in ["tipo de red", "network type", "tipo red"]):
                            current_network["network_type"] = value
                            if self._should_monitor_ssid(current_network["ssid"]):
                                print(f"     🏗️ Tipo de red: {value}")
                    
                    except ValueError:
                        # Línea mal formateada, ignorar
                        continue
                    except Exception as e:
                        if hasattr(Config, 'DEBUG_MODE') and Config.DEBUG_MODE:
                            print(f"     ⚠️ Error procesando línea '{line}': {e}")
                        continue
            
            # Guardar última red si existe y es relevante
            if self._should_save_network(current_network):
                self._calculate_signal_metrics(current_network)
                current_network["is_saved"] = self._is_network_saved(current_network["ssid"])
                ap_key = f"{current_network['ssid']}_{current_network['bssid']}"
                current_network["ap_key"] = ap_key
                self.ap_cache[ap_key] = current_network.copy()
                networks.append(current_network)
                print(f"   ✅ Último AP guardado: '{current_network['ssid']}' ({current_network['bssid'][-8:] if current_network['bssid'] != 'Unknown' else 'No-BSSID'}) - {current_network.get('signal_percentage', 0)}%")
            
            # ESTADÍSTICAS FINALES
            print(f"\n🎯 RESUMEN DE ESCANEO:")
            print(f"   📊 Total líneas procesadas: {len(lines)}")
            print(f"   📡 APs monitoreados encontrados: {len(networks)}")
            
            if networks:
                print(f"   📋 Detalle de APs:")
                ssid_counts = {}
                for net in networks:
                    ssid = net['ssid']
                    ssid_counts[ssid] = ssid_counts.get(ssid, 0) + 1
                    
                    signal_info = f"{net['signal_percentage']}%" if net['signal_percentage'] > 0 else "0%"
                    channel_info = f"Ch{net['channel']}" if net['channel'] > 0 else "Ch?"
                    bssid_short = net['bssid'][-8:] if net['bssid'] != "Unknown" else "No-BSSID"
                    
                    print(f"      📶 {net['ssid']} ({bssid_short}) - {signal_info} - {channel_info} - {net['band']} - {net['authentication']}")
                
                # Mostrar conteo por SSID
                if len(ssid_counts) > 1 or any(count > 1 for count in ssid_counts.values()):
                    print(f"   📊 APs por SSID:")
                    for ssid, count in ssid_counts.items():
                        print(f"      {ssid}: {count} AP(s)")
                        
            else:
                print("   ❌ No se encontraron APs de los SSIDs monitoreados")
                if hasattr(Config, 'MONITORED_SSIDS') and Config.MONITORED_SSIDS:
                    print(f"   🔍 Verificar que estos SSIDs estén activos: {Config.MONITORED_SSIDS}")
                else:
                    print("   🔍 Verificar conectividad WiFi y permisos")
            
            self.cached_networks = networks
            return networks
            
        except subprocess.TimeoutExpired:
            print("❌ Timeout ejecutando netsh wlan")
            return []
        except Exception as e:
            print(f"💥 Error inesperado en scan_networks: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _should_monitor_ssid(self, ssid: str) -> bool:
        """Verificar si un SSID debe ser monitoreado."""
        if not hasattr(Config, 'MONITORED_SSIDS'):
            return True  # Si no hay configuración, monitorear todo
        
        if hasattr(Config, 'MONITOR_ALL_NETWORKS') and Config.MONITOR_ALL_NETWORKS:
            return True
        
        if not Config.MONITORED_SSIDS:
            return True  # Lista vacía = monitorear todo
        
        return ssid in Config.MONITORED_SSIDS
    
    def _should_save_network(self, network: dict) -> bool:
        """Verificar si una red completa debe ser guardada."""
        if not network.get("ssid") or network["ssid"].startswith(("Hidden_Network_", "Unknown_Network_")):
            return False
        
        # Advertir si no tiene BSSID pero permitir guardado
        if network.get("bssid") == "Unknown":
            if self._should_monitor_ssid(network["ssid"]):
                print(f"   ⚠️ Red {network['ssid']} sin BSSID - múltiples APs no se distinguirán")
        
        return self._should_monitor_ssid(network["ssid"])
    
    def _percentage_to_dbm(self, percentage: int) -> float:
        """Convert signal percentage to dBm with better accuracy."""
        # More accurate conversion based on common WiFi adapter mappings
        if percentage >= 100:
            return -30
        elif percentage >= 90:
            return -30 - (100 - percentage) * 0.5
        elif percentage >= 75:
            return -35 - (90 - percentage) * 1.0
        elif percentage >= 50:
            return -50 - (75 - percentage) * 0.6
        elif percentage >= 25:
            return -65 - (50 - percentage) * 0.6
        elif percentage >= 10:
            return -80 - (25 - percentage) * 0.7
        else:
            return -90 - (10 - percentage) * 1.0
    
    def _calculate_signal_metrics(self, network: Dict):
        """Calculate SNR and signal quality metrics."""
        if network["signal_dbm"] is not None:
            # Estimate noise floor based on band
            if network["band"] == "2.4GHz":
                network["noise_dbm"] = -95  # Typical noise floor for 2.4GHz
            else:
                network["noise_dbm"] = -100  # Typical noise floor for 5GHz
            
            # Calculate SNR
            network["snr_db"] = network["signal_dbm"] - network["noise_dbm"]
            
            # Determine signal quality based on SNR
            if network["snr_db"] >= 40:
                network["signal_quality"] = "Excellent"
            elif network["snr_db"] >= 30:
                network["signal_quality"] = "Very Good"
            elif network["snr_db"] >= 20:
                network["signal_quality"] = "Good"
            elif network["snr_db"] >= 15:
                network["signal_quality"] = "Fair"
            else:
                network["signal_quality"] = "Poor"
    
    def display_network_details(self, network: Dict):
        """Display detailed network information."""
        print(f"\n📡 {network['ssid']} ({network['bssid']})")
        print(f"   Signal: {network['signal_percentage']}% ({network.get('signal_dbm', 'N/A'):.1f} dBm)")
        print(f"   Channel: {network['channel']} ({network['band']})")
        print(f"   Width: {network['channel_width']}")
        print(f"   SNR: {network.get('snr_db', 'N/A'):.1f} dB")
        print(f"   Auth: {network['authentication']}")
        print(f"   Encryption: {network['encryption']}")
        print(f"   PHY: {network['phy_type']}")
        if network.get('ap_key'):
            print(f"   AP Key: {network['ap_key']}")
    
    def _is_network_saved(self, ssid: str) -> bool:
        """Check if a network profile exists."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "profiles"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return ssid in result.stdout
        except:
            return False
    
    def connect_to_network(self, ssid: str, password: str = None) -> Dict:
        """Connect to a WiFi network."""
        try:
            # Disconnect first
            subprocess.run(["netsh", "wlan", "disconnect"], capture_output=True, timeout=10)
            time.sleep(2)
            
            # Connect
            result = subprocess.run(
                ["netsh", "wlan", "connect", f"name={ssid}"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                time.sleep(5)  # Wait for connection
                return {"success": True, "message": "Connected successfully"}
            else:
                return {"success": False, "error": result.stderr or "Connection failed"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_current_connection_info(self) -> Dict:
        """Get detailed information about current connection."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='cp1252'
            )
            
            info = {}
            lines = result.stdout.splitlines()
            
            # Check if we have any content
            if not lines or len(result.stdout.strip()) < 50:
                return {"error": "No WiFi connection detected"}
            
            for line in lines:
                line = line.strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if any(term in key for term in ["name", "nombre"]) and "ssid" not in key:
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
                    elif any(term in key for term in ["ap bssid", "bssid"]):
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
                        # Extraer solo el número del canal
                        match = re.search(r'(\d+)', value)
                        if match:
                            info["channel"] = match.group(1)
                            info["channel_raw"] = value
                    elif any(term in key for term in ["receive rate", "velocidad de recepción", "velocidad de recepcion", "velocidad de recepci¢n"]):
                        info["receive_rate"] = value
                    elif any(term in key for term in ["transmit rate", "velocidad de transmisión", "velocidad de transmision", "velocidad de transmisi¢n"]):
                        info["transmit_rate"] = value
                    elif any(term in key for term in ["signal", "señal", "senal", "se¤al"]):
                        info["signal_strength"] = value
                        # Extract numeric percentage
                        match = re.search(r'(\d+)%', value)
                        if match:
                            info["signal_percentage"] = int(match.group(1))
                            # Calcular dBm
                            info["signal_dbm"] = self._percentage_to_dbm(info["signal_percentage"])
                        else:
                            # If no %, look for numbers only
                            match = re.search(r'(\d+)', value)
                            if match:
                                info["signal_percentage"] = int(match.group(1))
                                info["signal_dbm"] = self._percentage_to_dbm(info["signal_percentage"])
            
            # Check if we got valid connection info
            if 'ssid' not in info:
                return {"error": "No active WiFi connection found"}
            
            return info
            
        except Exception as e:
            return {"error": f"Error getting connection info: {str(e)}"}