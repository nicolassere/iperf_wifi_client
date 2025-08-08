import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy.interpolate import griddata
from collections import defaultdict
from datetime import datetime
from functions.WifiScanner import WiFiScanner
from functions.NetworkTester import NetworkTester
from config.config import Config
import json
import subprocess
import re
import time


class HeatmapManager:
    """Manages persistent heatmaps with network testing and individual file storage."""
    
    def __init__(self, house_width=Config.HOUSE_WIDTH, house_length=Config.HOUSE_LENGTH):
        self.house_width = house_width
        self.house_length = house_length
        self.data_dir = Config.DATA_DIR
        self.data_dir.mkdir(exist_ok=True)
        
        # Crear subdirectorios para archivos individuales
        self.individual_measurements_dir = self.data_dir / "individual_measurements"
        self.individual_measurements_dir.mkdir(exist_ok=True)
        
        self.ap_details_dir = self.data_dir / "ap_details"
        self.ap_details_dir.mkdir(exist_ok=True)
        
        self.scanner = WiFiScanner()
        self.tester = NetworkTester()
        self.rooms = {}
        self.measurements = []
        self.ap_data = defaultdict(list)
        self.network_test_results = defaultdict(list)
        
        # New: ID to coordinates mapping
        self.id_mapping = {}
        self.next_measurement_id = 1
        
        # Load existing data
        self.load_data()
    
    def get_current_client_ip_info(self):
        """Obtener información detallada de IP del cliente actual - VERSIÓN MEJORADA."""
        client_info = {
            'client_ip': None,
            'gateway': None,
            'dns_servers': [],
            'interface_name': None,
            'subnet_mask': None,
            'timestamp': time.time()
        }
        
        try:
            print("🔍 Obteniendo información de red del cliente...")
            
            # Usar el método del NetworkTester que ya está implementado
            network_tester_info = self.tester.get_client_network_info()
            
            # Si el NetworkTester tiene la info, usarla
            if network_tester_info.get('client_ip'):
                client_info.update(network_tester_info)
                print(f"   ✅ Info obtenida via NetworkTester:")
                print(f"      📍 IP Cliente: {client_info.get('client_ip', 'N/A')}")
                print(f"      🚪 Gateway: {client_info.get('gateway', 'N/A')}")
                print(f"      📡 Interfaz: {client_info.get('interface_name', 'N/A')}")
                return client_info
            
            # Fallback: intentar obtener manualmente
            print("   ⚠️ NetworkTester no devolvió info, intentando método manual...")
            
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                timeout=15,
                encoding='cp1252'
            )
            
            if result.returncode != 0:
                print(f"   ❌ Error ejecutando ipconfig: {result.stderr}")
                return client_info
            
            current_interface = None
            in_wifi_section = False
            
            for line in result.stdout.splitlines():
                line = line.strip()
                
                # Detectar inicio de sección WiFi
                if "Wireless LAN adapter" in line or "Adaptador de LAN inalámbrica" in line:
                    if "Wi-Fi 2" in line or "WiFi 2" in line:
                        current_interface = line
                        client_info['interface_name'] = current_interface
                        in_wifi_section = True
                        print(f"      📡 Interfaz WiFi encontrada: {current_interface}")
                        continue
                elif "adapter" in line.lower() or "adaptador" in line.lower():
                    # Nueva sección de adaptador, salir de WiFi
                    in_wifi_section = False
                    continue
                
                # Solo procesar si estamos en la sección WiFi correcta
                if in_wifi_section and ":" in line:
                    try:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # IPv4 Address
                        if ("IPv4" in key or "Dirección IPv4" in key) and value:
                            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', value)
                            if ip_match:
                                client_info['client_ip'] = ip_match.group(1)
                                print(f"      📍 IP Cliente: {client_info['client_ip']}")
                        
                        # Subnet Mask
                        elif ("Subnet Mask" in key or "Máscara de subred" in key) and value:
                            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', value)
                            if ip_match:
                                client_info['subnet_mask'] = ip_match.group(1)
                                print(f"      🌐 Máscara: {client_info['subnet_mask']}")
                        
                        # Default Gateway
                        elif ("Default Gateway" in key or "Puerta de enlace predeterminada" in key) and value:
                            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', value)
                            if ip_match:
                                client_info['gateway'] = ip_match.group(1)
                                print(f"      🚪 Gateway: {client_info['gateway']}")
                        
                        # DNS Servers
                        elif ("DNS Servers" in key or "Servidores DNS" in key) and value:
                            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', value)
                            if ip_match:
                                client_info['dns_servers'].append(ip_match.group(1))
                                print(f"      🔍 DNS: {ip_match.group(1)}")
                    
                    except ValueError:
                        continue
            
            # Verificar que obtuvimos la información básica
            if not client_info['client_ip']:
                print("   ⚠️ No se pudo obtener IP del cliente")
            if not client_info['gateway']:
                print("   ⚠️ No se pudo obtener gateway")
            
            return client_info
            
        except subprocess.TimeoutExpired:
            print("   ❌ Timeout ejecutando ipconfig")
            return client_info
        except Exception as e:
            print(f"   ❌ Error obteniendo info de red del cliente: {e}")
            return client_info
    
    def save_individual_measurement(self, measurement):
        """Guardar medición individual en archivo separado."""
        try:
            timestamp = measurement.get('timestamp', datetime.now().isoformat())
            measurement_id = measurement.get('id', f"manual_{int(datetime.now().timestamp())}")
            
            # Crear nombre de archivo único
            filename = f"measurement_{measurement_id}_{timestamp.replace(':', '-').replace('.', '_')}.json"
            filepath = self.individual_measurements_dir / filename
            
            # Verificar si ya tiene client_network_info, si no, obtenerla
            if 'client_network_info' not in measurement or not measurement['client_network_info'].get('client_ip'):
                print("   🔄 Obteniendo información de cliente para el archivo...")
                client_info = self.get_current_client_ip_info()
                measurement['client_network_info'] = client_info
            else:
                client_info = measurement['client_network_info']
            
            # Agregar resumen de APs para fácil lectura
            measurement['ap_summary'] = {
                'total_aps_found': len(measurement.get('networks', [])),
                'strongest_ap': None,
                'client_ip': client_info.get('client_ip', 'N/A'),
                'gateway': client_info.get('gateway', 'N/A'),
                'ap_list': []
            }
            
            # Procesar información de APs
            if measurement.get('networks'):
                # Encontrar AP más fuerte
                strongest = max(measurement['networks'], key=lambda x: x.get('signal', 0))
                measurement['ap_summary']['strongest_ap'] = {
                    'ssid': strongest.get('ssid'),
                    'bssid': strongest.get('bssid'),
                    'signal': strongest.get('signal'),
                    'signal_dbm': strongest.get('signal_dbm'),
                    'channel': strongest.get('channel'),
                    'band': strongest.get('band')
                }
                
                # Lista resumida de todos los APs
                for network in measurement['networks']:
                    ap_info = {
                        'ssid': network.get('ssid'),
                        'bssid': network.get('bssid'),
                        'signal_percentage': network.get('signal', 0),
                        'signal_dbm': network.get('signal_dbm'),
                        'snr_db': network.get('snr_db'),
                        'channel': network.get('channel'),
                        'band': network.get('band'),
                        'signal_quality': network.get('signal_quality'),
                        'authentication': network.get('authentication')
                    }
                    measurement['ap_summary']['ap_list'].append(ap_info)
                
                # Ordenar por señal
                measurement['ap_summary']['ap_list'].sort(
                    key=lambda x: x.get('signal_percentage', 0), reverse=True
                )
            
            # Guardar archivo individual
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(measurement, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Medición individual guardada: {filename}")
            print(f"   📍 Cliente IP: {measurement['ap_summary']['client_ip']}")
            print(f"   🚪 Gateway: {measurement['ap_summary']['gateway']}")
            
            # También crear archivo de resumen legible
            summary_filename = f"summary_{measurement_id}_{timestamp.replace(':', '-').replace('.', '_')}.txt"
            summary_filepath = self.individual_measurements_dir / summary_filename
            self.create_measurement_summary_file(measurement, summary_filepath)
            
            return str(filepath)
            
        except Exception as e:
            print(f"❌ Error guardando medición individual: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_measurement_summary_file(self, measurement, filepath):
        """Crear archivo de resumen legible de la medición."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("RESUMEN DE MEDICIÓN WIFI\n")
                f.write("=" * 80 + "\n\n")
                
                # Información básica
                f.write(f"ID de Medición: {measurement.get('id', 'N/A')}\n")
                f.write(f"Timestamp: {measurement.get('timestamp', 'N/A')}\n")
                
                location = measurement.get('location')
                if location:
                    f.write(f"Ubicación: ({location.get('x', 'N/A')}, {location.get('y', 'N/A')})\n")
                else:
                    f.write("Ubicación: No mapeada aún\n")
                
                # Información de red del cliente
                client_info = measurement.get('client_network_info', {})
                f.write(f"\nINFORMACIÓN DE RED DEL CLIENTE:\n")
                f.write(f"IP Cliente: {client_info.get('client_ip', 'N/A')}\n")
                f.write(f"Gateway: {client_info.get('gateway', 'N/A')}\n")
                f.write(f"Máscara de subred: {client_info.get('subnet_mask', 'N/A')}\n")
                if client_info.get('dns_servers'):
                    f.write(f"DNS: {', '.join(client_info.get('dns_servers', []))}\n")
                f.write(f"Interfaz: {client_info.get('interface_name', 'N/A')}\n")
                
                # Resumen de APs
                ap_summary = measurement.get('ap_summary', {})
                f.write(f"\nRESUMEN DE ACCESS POINTS:\n")
                f.write(f"Total APs encontrados: {ap_summary.get('total_aps_found', 0)}\n")
                
                strongest = ap_summary.get('strongest_ap')
                if strongest:
                    f.write(f"AP más fuerte: {strongest.get('ssid')} ({strongest.get('signal', 0)}%)\n")
                    f.write(f"  BSSID: {strongest.get('bssid', 'N/A')}\n")
                    f.write(f"  Señal: {strongest.get('signal_dbm', 'N/A')} dBm\n")
                    f.write(f"  Canal: {strongest.get('channel', 'N/A')} ({strongest.get('band', 'N/A')})\n")
                
                f.write(f"\nDETALLE DE TODOS LOS APs:\n")
                f.write("-" * 80 + "\n")
                f.write(f"{'SSID':<25} {'BSSID':<18} {'Señal':<8} {'dBm':<8} {'SNR':<8} {'Canal':<8} {'Banda':<8} {'Calidad':<12}\n")
                f.write("-" * 80 + "\n")
                
                for ap in ap_summary.get('ap_list', []):
                    ssid = (ap.get('ssid', 'N/A'))[:24]
                    bssid = (ap.get('bssid', 'N/A'))[:17]
                    signal = f"{ap.get('signal_percentage', 0)}%"
                    dbm = f"{ap.get('signal_dbm', 0):.1f}" if ap.get('signal_dbm') else "N/A"
                    snr = f"{ap.get('snr_db', 0):.1f}" if ap.get('snr_db') else "N/A"
                    channel = str(ap.get('channel', 'N/A'))
                    band = (ap.get('band', 'N/A'))[:7]
                    quality = (ap.get('signal_quality', 'N/A'))[:11]
                    
                    f.write(f"{ssid:<25} {bssid:<18} {signal:<8} {dbm:<8} {snr:<8} {channel:<8} {band:<8} {quality:<12}\n")
                
                # Tests de red si existen
                if measurement.get('tests'):
                    f.write(f"\nRESULTADOS DE TESTS DE RED:\n")
                    f.write("-" * 40 + "\n")
                    
                    tests = measurement['tests']
                    if 'ping' in tests and tests['ping'].get('success'):
                        ping = tests['ping']
                        f.write(f"Ping: {ping.get('avg_time', 'N/A'):.1f} ms (promedio)\n")
                        f.write(f"  Min: {ping.get('min_time', 'N/A')} ms, Max: {ping.get('max_time', 'N/A')} ms\n")
                        f.write(f"  Pérdida de paquetes: {ping.get('packet_loss', 'N/A')}\n")
                    
                    if 'speedtest' in tests and tests['speedtest'].get('success'):
                        speed = tests['speedtest']
                        f.write(f"Speedtest:\n")
                        f.write(f"  Download: {speed.get('download_mbps', 'N/A'):.1f} Mbps\n")
                        f.write(f"  Upload: {speed.get('upload_mbps', 'N/A'):.1f} Mbps\n")
                        f.write(f"  Ping: {speed.get('ping_ms', 'N/A'):.1f} ms\n")
                        f.write(f"  Servidor: {speed.get('server', 'N/A')}\n")
                    
                    if 'iperf_suite' in tests and tests['iperf_suite'].get('success'):
                        iperf = tests['iperf_suite']
                        f.write(f"iPerf Suite:\n")
                        f.write(f"  Servidor: {iperf.get('server', 'N/A')}\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write("FIN DEL RESUMEN\n")
                f.write("=" * 80 + "\n")
            
            print(f"📄 Resumen legible guardado: {filepath.name}")
            
        except Exception as e:
            print(f"❌ Error creando resumen: {e}")
    
    def save_ap_details(self, measurement):
        """Guardar detalles específicos de cada AP en archivos separados."""
        try:
            networks = measurement.get('networks', [])
            timestamp = measurement.get('timestamp', datetime.now().isoformat())
            measurement_id = measurement.get('id', 'unknown')
            location = measurement.get('location')
            client_info = measurement.get('client_network_info', {})
            
            for network in networks:
                ssid = network.get('ssid', 'unknown')
                bssid = network.get('bssid', 'unknown')
                
                # Crear archivo para cada AP
                ap_filename = f"AP_{ssid}_{bssid.replace(':', '')}_{timestamp.replace(':', '-').replace('.', '_')}.json"
                ap_filepath = self.ap_details_dir / ap_filename
                
                ap_record = {
                    'measurement_id': measurement_id,
                    'timestamp': timestamp,
                    'location': location,
                    'client_network_info': client_info,
                    'ap_details': network,
                    'measurement_context': {
                        'total_aps_in_scan': len(networks),
                        'strongest_signal_in_scan': max([n.get('signal', 0) for n in networks]) if networks else 0,
                        'ap_rank_by_signal': sorted(networks, key=lambda x: x.get('signal', 0), reverse=True).index(network) + 1 if network in networks else 0
                    }
                }
                
                # Si este AP ya tiene archivo, actualizar
                if ap_filepath.exists():
                    try:
                        with open(ap_filepath, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                        
                        # Convertir a lista de mediciones si no lo es ya
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                        
                        existing_data.append(ap_record)
                        
                        with open(ap_filepath, 'w', encoding='utf-8') as f:
                            json.dump(existing_data, f, indent=2, ensure_ascii=False)
                            
                    except Exception:
                        # Si hay error leyendo archivo existente, sobrescribir
                        with open(ap_filepath, 'w', encoding='utf-8') as f:
                            json.dump([ap_record], f, indent=2, ensure_ascii=False)
                else:
                    # Archivo nuevo
                    with open(ap_filepath, 'w', encoding='utf-8') as f:
                        json.dump([ap_record], f, indent=2, ensure_ascii=False)
                
                print(f"📡 AP guardado: {ssid} ({network.get('signal', 0)}%) -> {ap_filename}")
                
        except Exception as e:
            print(f"❌ Error guardando detalles de AP: {e}")
    
    def define_room(self, name: str, x: float, y: float, width: float, height: float):
        """Define a room in the house layout."""
        self.rooms[name] = {'x': x, 'y': y, 'width': width, 'height': height}
        print(f"Room '{name}' defined: {width}x{height}m at ({x}, {y})")
    
    def setup_default_layout(self):
        """Setup default house layout."""
        self.define_room("living_room", 0, 0, 6, 8)
        self.define_room("kitchen", 6, 0, 4, 5)
        self.define_room("bedroom1", 0, 8, 5, 6)
        self.define_room("bedroom2", 5, 8, 5, 6)
        self.define_room("bathroom", 10, 0, 3, 4)
        self.define_room("hallway", 5, 5, 5, 3)
    
    def collect_measurement_by_id(self, measurement_id: int = None, run_tests: bool = True):
        """Collect WiFi measurements using ID system for field work."""
        if measurement_id is None:
            measurement_id = self.next_measurement_id
            self.next_measurement_id += 1
        
        print(f"\n📍 MEASUREMENT ID: {measurement_id}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
        
        
        # Escanear redes
        networks = self.scanner.scan_networks(force_refresh=True)
        
        measurement = {
            'id': measurement_id,
            'timestamp': datetime.now().isoformat(),
            'location': None,  # Will be mapped later
            'networks': [],
            'tests': {},
            'client_network_info': None  # AGREGAR AQUÍ DIRECTAMENTE
        }
        
        print(f"   Networks found: {len(networks)}")
        
        # Store network data
        for network in networks:
            if network['bssid'] != "Unknown":
                net_data = {
                    'ssid': network['ssid'],
                    'bssid': network['bssid'],
                    'signal': network['signal_percentage'],
                    'signal_dbm': network.get('signal_dbm'),  
                    'snr_db': network.get('snr_db'),         
                    'signal_quality': network.get('signal_quality'),  
                    'channel': network['channel'],
                    'band': network.get('band'),             
                    'authentication': network['authentication']
                }
                measurement['networks'].append(net_data)
                
                # Mostrar información mejorada
                signal_dbm_str = f"({network['signal_dbm']:.1f} dBm)" if network.get('signal_dbm') is not None else ""
                snr_str = f"SNR: {network.get('snr_db', 'N/A'):.1f} dB" if network.get('snr_db') is not None else ""
                print(f"  📡 {network['ssid']} {network['bssid']} - {network['signal_percentage']}% - Ch{network['channel']} {signal_dbm_str} - {snr_str} - {network.get('signal_quality', 'Unknown')}")
        
        # Run network tests if connected
        if run_tests:
            current_conn = self.scanner.get_current_connection_info()
            if 'ssid' in current_conn and 'error' not in current_conn:
                print(f"\n  Running network tests on {current_conn['ssid']}...")
                client_info = self.get_current_client_ip_info()
                measurement['client_network_info'] = client_info
                
                # Ping test
                ping_result = self.tester.run_ping()
                if ping_result['success']:
                    measurement['tests']['ping'] = ping_result
                    print(f"    ✓ Ping: {ping_result['avg_time']:.1f}ms")
                
                # Speedtest (optional - takes time)
                if input("    Run speedtest? (y/n): ").lower() == 'y':
                    speed_result = self.tester.run_speedtest()
                    if speed_result['success']:
                        measurement['tests']['speedtest'] = speed_result
                        print(f"    ✓ Speed: {speed_result['download_mbps']:.1f}↓/{speed_result['upload_mbps']:.1f}↑ Mbps")
                
                # iPerf test
                if input("    Run iPerf test suite? (y/n): ").lower() == 'y':
                    iperf_result = self.tester.run_iperf_suite()
                    if iperf_result['success']:
                        measurement['tests']['iperf_suite'] = iperf_result
                    else:
                        print(f"    ✗ iPerf: {iperf_result['error']}")
            else:
                print(f"  ⚠️  No WiFi connection detected - skipping network tests")
        
        # Guardar archivos individuales ANTES de agregar a la lista principal
        individual_file = self.save_individual_measurement(measurement)
        self.save_ap_details(measurement)
        
        # Agregar a datos principales
        self.measurements.append(measurement)
        self.save_data()
        
        print(f"\n✅ Measurement ID {measurement_id} saved successfully!")
        print("   Remember to note this ID on your floor plan!")
        print(f"   Individual file: {individual_file}")
        
        return measurement
    
    def map_id_to_coordinates(self, measurement_id: int, x: float, y: float):
        """Map a measurement ID to coordinates after field work."""
        self.id_mapping[measurement_id] = {'x': x, 'y': y}
        
        # Update the measurement with coordinates
        for measurement in self.measurements:
            if measurement.get('id') == measurement_id:
                measurement['location'] = {'x': x, 'y': y}
                
                # Also update AP data
                for network in measurement['networks']:
                    ap_key = f"{network['ssid']}_{network['bssid']}"
                    self.ap_data[ap_key].append({
                        'location': {'x': x, 'y': y},
                        'signal': network['signal'],
                        'timestamp': measurement['timestamp']
                    })
                
                # Re-guardar archivo individual con coordenadas actualizadas
                self.save_individual_measurement(measurement)
                
                break
        
        self.save_data()
        print(f"✓ Measurement ID {measurement_id} mapped to coordinates ({x}, {y})")
    
    def batch_map_coordinates(self):
        """Interactive batch mapping of IDs to coordinates."""
        unmapped = [m for m in self.measurements if m.get('location') is None and 'id' in m]
        
        if not unmapped:
            print("No unmapped measurements found!")
            return
        
        print(f"\n🗺️  COORDINATE MAPPING")
        print(f"   Found {len(unmapped)} unmapped measurements")
        print("   Enter coordinates for each ID (or 'skip' to skip)")
        
        for measurement in unmapped:
            print(f"\n   ID {measurement['id']} - {measurement['timestamp']}")
            
            # Mostrar información de cliente y APs para ayudar a identificar
            client_info = measurement.get('client_network_info', {})
            if client_info.get('client_ip'):
                print(f"   Cliente IP: {client_info['client_ip']}")
                print(f"   Gateway: {client_info.get('gateway', 'N/A')}")
            
            ap_summary = measurement.get('ap_summary', {})
            strongest = ap_summary.get('strongest_ap')
            if strongest:
                print(f"   AP más fuerte: {strongest.get('ssid')} ({strongest.get('signal', 0)}%)")
            
            # Check if it's a network test or regular measurement
            if 'all_network_tests' in measurement:
                print(f"   Type: Network Test")
                print(f"   Networks tested: {len(measurement['all_network_tests'])}")
                if measurement['all_network_tests']:
                    print("   Tested networks:")
                    for test in measurement['all_network_tests'][:5]:  # Show first 5
                        print(f"     - {test['ssid']} ({test['signal']}%)")
            else:
                print(f"   Type: Regular Measurement")
                print(f"   Networks found: {len(measurement['networks'])}")
                if measurement['networks']:
                    print(f"   Strongest: {measurement['networks'][0]['ssid']} ({measurement['networks'][0]['signal']}%)")
            
            coords = input("   Enter x,y coordinates (e.g., 5.5,3.2): ").strip()
            
            if coords.lower() == 'skip':
                continue
            
            try:
                x, y = map(float, coords.split(','))
                
                # Use appropriate mapping function
                if 'all_network_tests' in measurement:
                    self.map_network_test_id_to_coordinates(measurement['id'], x, y)
                else:
                    self.map_id_to_coordinates(measurement['id'], x, y)
            except:
                print("   Invalid format, skipping...")
    
    # Métodos de heatmap simplificados (agregar según necesites)
    def save_data(self):
        """Save all data to disk."""
        data = {
            'house_dimensions': {'width': self.house_width, 'length': self.house_length},
            'rooms': self.rooms,
            'measurements': self.measurements,
            'ap_data': {k: v for k, v in self.ap_data.items()},
            'network_test_results': {k: v for k, v in self.network_test_results.items()},
            'id_mapping': self.id_mapping,
            'next_measurement_id': self.next_measurement_id,
            'last_updated': datetime.now().isoformat()
        }
        
        file_path = self.data_dir / "heatmap_data.json"
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Data saved ({len(self.measurements)} measurements, {len(self.ap_data)} APs)")
    
    def load_data(self):
        """Load data from disk."""
        file_path = self.data_dir / "heatmap_data.json"
        
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                self.house_width = data['house_dimensions']['width']
                self.house_length = data['house_dimensions']['length']
                self.rooms = data['rooms']
                self.measurements = data['measurements']
                self.ap_data = defaultdict(list, data['ap_data'])
                self.network_test_results = defaultdict(list, data.get('network_test_results', {}))
                self.id_mapping = data.get('id_mapping', {})
                self.next_measurement_id = data.get('next_measurement_id', 1)
                
                print(f"📂 Loaded: {len(self.measurements)} measurements, {len(self.ap_data)} APs")
            except Exception as e:
                print(f"Error loading data: {e}")
    
    def collect_measurement_with_tests(self, x: float, y: float, room: str = "", run_tests: bool = True):
        """Original method - collect WiFi measurements with coordinates."""
        networks = self.scanner.scan_networks(force_refresh=True)
        
        measurement = {
            'timestamp': datetime.now().isoformat(),
            'location': {'x': x, 'y': y},
            'room': room,
            'networks': [],
            'tests': {}
        }
        
        # Store network data
        for network in networks:
            if network['bssid'] != "Unknown":
                net_data = {
                    'ssid': network['ssid'],
                    'bssid': network['bssid'],
                    'signal': network['signal_percentage'],
                    'channel': network['channel'],
                    'authentication': network['authentication']
                }
                measurement['networks'].append(net_data)
                
                # Store in AP-specific data
                ap_key = f"{network['ssid']}_{network['bssid']}"
                print(f"  📡 {network['ssid']} ({network['bssid']}) - Signal: {network['signal_percentage']}%")
                self.ap_data[ap_key].append({
                    'location': {'x': x, 'y': y},
                    'signal': network['signal_percentage'],
                    'timestamp': datetime.now().isoformat()
                })
        
        # Run network tests if connected
        if run_tests:
            current_conn = self.scanner.get_current_connection_info()
            if 'ssid' in current_conn and 'error' not in current_conn:
                print(f"  Running network tests on {current_conn['ssid']}...")
                
                # Ping test
                ping_result = self.tester.run_ping()
                if ping_result['success']:
                    measurement['tests']['ping'] = ping_result
                    print(f"    Ping: {ping_result['avg_time']:.1f}ms")
                
                # Speedtest (optional - takes time)
                if input("    Run speedtest? (y/n): ").lower() == 'y':
                    speed_result = self.tester.run_speedtest()
                    if speed_result['success']:
                        measurement['tests']['speedtest'] = speed_result
                        print(f"    Speed: {speed_result['download_mbps']:.1f}↓/{speed_result['upload_mbps']:.1f}↑ Mbps")
                
                # iPerf test
                if input("    Run iPerf test suite? (y/n): ").lower() == 'y':
                    iperf_result = self.tester.run_iperf_suite()
                    if iperf_result['success']:
                        measurement['tests']['iperf_suite'] = iperf_result
                    else:
                        print(f"    ✗ iPerf: {iperf_result['error']}")
        
        # Guardar archivos individuales
        self.save_individual_measurement(measurement)
        self.save_ap_details(measurement)
        
        self.measurements.append(measurement)
        self.save_data()
        
        print(f"📍 Measurement collected at ({x:.1f}, {y:.1f}) - {len(networks)} networks")
        return measurement
    
    def test_all_networks_by_id(self, measurement_id: int = None):
        """Test all available networks at a location using ID system."""
        if measurement_id is None:
            measurement_id = self.next_measurement_id
            self.next_measurement_id += 1
        
        networks = self.scanner.scan_networks(force_refresh=True)
        connectable = [n for n in networks if n['is_open'] or n['is_saved']]
        
        print(f"\n🔄 TESTING ALL NETWORKS - ID: {measurement_id}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"   Found {len(connectable)} connectable networks")
        print("   Remember to note this ID on your floor plan!")
        
        # Obtener información de cliente
        
        # Create base measurement
        measurement = {
            'id': measurement_id,
            'timestamp': datetime.now().isoformat(),
            'location': None,  # Will be mapped later
            'networks': [],
            'tests': {},
            'all_network_tests': [],  # Store tests for all networks
            'client_network_info': None
        }
        
        # Store all visible networks info
        for network in networks:
            if network['bssid'] != "Unknown":
                net_data = {
                    'ssid': network['ssid'],
                    'bssid': network['bssid'],
                    'signal': network['signal_percentage'],
                    'signal_dbm': network.get('signal_dbm'),
                    'snr_db': network.get('snr_db'),
                    'signal_quality': network.get('signal_quality'),
                    'channel': network['channel'],
                    'band': network.get('band'),
                    'authentication': network['authentication']
                }
                measurement['networks'].append(net_data)
        
        # Test each connectable network
        for network in connectable:
            ssid = network['ssid']
            print(f"  📡 {network['ssid']} - Signal: {network['signal_percentage']}% "
                  f"({network.get('signal_dbm', 'N/A'):.1f} dBm) "
                  f"SNR: {network.get('snr_db', 'N/A'):.1f} dB "
                  f"[{network.get('signal_quality', 'Unknown')}]")
            
            # Connect
            conn_result = self.scanner.connect_to_network(ssid)
            if not conn_result['success']:
                print(f"   ❌ Connection failed: {conn_result['error']}")
                continue
            client_info = self.get_current_client_ip_info()
            measurement['client_network_info'] = client_info

            
            # Run tests
            network_test = {
                'ssid': ssid,
                'bssid': network['bssid'],
                'signal': network['signal_percentage'],
                'timestamp': datetime.now().isoformat(),
                'tests': {}
            }
            
            # Ping
            ping = self.tester.run_ping()
            if ping['success']:
                network_test['tests']['ping'] = ping
                print(f"   ✓ Ping: {ping['avg_time']:.1f}ms")
            
            # Speed test for decent signals
            if network['signal_percentage'] > 40:
                if input("   Run speedtest? (y/n): ").lower() == 'y':
                    speed = self.tester.run_speedtest()
                    if speed['success']:
                        network_test['tests']['speedtest'] = speed
                        print(f"   ✓ Speed: {speed['download_mbps']:.1f}↓/{speed['upload_mbps']:.1f}↑ Mbps")
            
            # iPerf test
            if input("    Run iPerf test suite? (y/n): ").lower() == 'y':
                iperf_result = self.tester.run_iperf_suite()
                if iperf_result['success']:
                    network_test['tests']['iperf_suite'] = iperf_result
                else:
                    print(f"    ✗ iPerf: {iperf_result['error']}")
            
            measurement['all_network_tests'].append(network_test)
            self.scanner.tested_networks.add(ssid)
        
        # Guardar archivos individuales
        self.save_individual_measurement(measurement)
        self.save_ap_details(measurement)
        
        # Save measurement
        self.measurements.append(measurement)
        self.save_data()
        
        print(f"\n✅ Network testing completed for ID {measurement_id}")
        print(f"   Tested {len(measurement['all_network_tests'])} networks")
        
        return measurement
    
    # Agregar estos métodos a la clase HeatmapManager en HeatmapManager.py

    def scan_wifi_only(self, measurement_id: int = None):
        """Solo escanear WiFi sin tests."""
        if measurement_id is None:
            measurement_id = self.next_measurement_id
            self.next_measurement_id += 1
        
        print(f"\n📍 MEDICIÓN ID: {measurement_id}")
        print(f"⏰ Hora: {datetime.now().strftime('%H:%M:%S')}")
        
        # Escanear redes
        networks = self.scanner.scan_networks(force_refresh=True)
        
        measurement = {
            'id': measurement_id,
            'timestamp': datetime.now().isoformat(),
            'location': None,
            'networks': [],
            'tests': {},  # Vacío - sin tests
            'client_network_info': self.get_current_client_ip_info(),
            'test_type': 'wifi_only'
        }
        
        print(f"📊 Redes encontradas: {len(networks)}")
        
        # Guardar info de redes
        for network in networks:
            if network['bssid'] != "Unknown":
                net_data = {
                    'ssid': network['ssid'],
                    'bssid': network['bssid'],
                    'signal': network['signal_percentage'],
                    'signal_dbm': network.get('signal_dbm'),
                    'snr_db': network.get('snr_db'),
                    'signal_quality': network.get('signal_quality'),
                    'channel': network['channel'],
                    'band': network.get('band'),
                    'authentication': network['authentication']
                }
                measurement['networks'].append(net_data)
                print(f"  📡 {network['ssid']} - {network['signal_percentage']}% - Ch{network['channel']}")
        
        # Guardar
        self.save_individual_measurement(measurement)
        self.save_ap_details(measurement)
        self.measurements.append(measurement)
        self.save_data()
        
        print(f"✅ Escaneo WiFi completado - ID: {measurement_id}")
        return measurement

    def run_speedtest_only(self):
        """Solo ejecutar SpeedTest."""
        current = self.scanner.get_current_connection_info()
        if 'error' in current or 'ssid' not in current:
            print("❌ No hay conexión WiFi para SpeedTest")
            return None
        
        print(f"📶 Conectado a: {current['ssid']} ({current.get('signal_percentage', 'N/A')}%)")
        print("\n🚀 Ejecutando SpeedTest...")
        
        result = self.tester.run_speedtest()
        if result['success']:
            print(f"✅ Download: {result['download_mbps']:.1f} Mbps")
            print(f"✅ Upload: {result['upload_mbps']:.1f} Mbps")
            print(f"✅ Ping: {result['ping_ms']:.1f} ms")
            print(f"✅ Servidor: {result['server']}")
        else:
            print(f"❌ Error: {result['error']}")
        
        return result

    def run_iperf_only(self):
        """Solo ejecutar iPerf."""
        current = self.scanner.get_current_connection_info()
        if 'error' in current or 'ssid' not in current:
            print("❌ No hay conexión WiFi para iPerf")
            return None
        
        print(f"📶 Conectado a: {current['ssid']} ({current.get('signal_percentage', 'N/A')}%)")
        print(f"🌐 Servidor iPerf: {self.tester.iperf_server}")
        
        result = self.tester.run_iperf_suite()
        if result['success']:
            print("✅ iPerf completado")
        else:
            print(f"❌ Error: {result['error']}")
        
        return result

    def wifi_and_speedtest(self):
        """WiFi scan + SpeedTest."""
        # Primero WiFi
        measurement = self.scan_wifi_only()
        
        # Luego SpeedTest
        speed_result = self.run_speedtest_only()
        if speed_result and speed_result['success']:
            measurement['tests']['speedtest'] = speed_result
            measurement['test_type'] = 'wifi_speedtest'
            
            # Actualizar guardado
            self.save_individual_measurement(measurement)
            self.save_data()
        
        return measurement

    def wifi_and_iperf(self):
        """WiFi scan + iPerf."""
        # Primero WiFi
        measurement = self.scan_wifi_only()
        
        
        # Luego iPerf
        iperf_result = self.run_iperf_only()
        if iperf_result and iperf_result['success']:
            measurement['tests']['iperf_suite'] = iperf_result
            measurement['test_type'] = 'wifi_iperf'
            
            # Actualizar guardado
            self.save_individual_measurement(measurement)
            self.save_data()
        
        return measurement

    def iperf_and_speedtest(self):
        """iPerf + SpeedTest (sin WiFi scan)."""
        current = self.scanner.get_current_connection_info()
        if 'error' in current or 'ssid' not in current:
            print("❌ Se requiere conexión WiFi")
            return None
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'connection': current,
            'tests': {}
        }
        
        # SpeedTest
        speed = self.run_speedtest_only()
        if speed and speed['success']:
            results['tests']['speedtest'] = speed
        

        
        iperf = self.run_iperf_only()
        if iperf and iperf['success']:
            results['tests']['iperf_suite'] = iperf
        
        # Guardar como medición especial
        if results['tests']:
            measurement = {
                'id': f"tests_{int(time.time())}",
                'timestamp': results['timestamp'],
                'test_type': 'iperf_speedtest',
                'connection_info': current,
                'client_network_info': self.get_current_client_ip_info(),
                'tests': results['tests']
            }
            self.save_individual_measurement(measurement)
        
        return results

    def map_network_test_id_to_coordinates(self, measurement_id: int, x: float, y: float):
        """Map a network test ID to coordinates and update all related data."""
        self.id_mapping[measurement_id] = {'x': x, 'y': y}
        
        # Find and update the measurement
        for measurement in self.measurements:
            if measurement.get('id') == measurement_id:
                measurement['location'] = {'x': x, 'y': y}
                
                # Update AP data for all networks found
                for network in measurement['networks']:
                    ap_key = f"{network['ssid']}_{network['bssid']}"
                    self.ap_data[ap_key].append({
                        'location': {'x': x, 'y': y},
                        'signal': network['signal'],
                        'timestamp': measurement['timestamp']
                    })
                
                # Update network test results if this was a network test
                if 'all_network_tests' in measurement:
                    for test in measurement['all_network_tests']:
                        ap_key = f"{test['ssid']}_{test['bssid']}"
                        
                        # Add to AP data for heatmap
                        self.ap_data[ap_key].append({
                            'location': {'x': x, 'y': y},
                            'signal': test['signal'],
                            'timestamp': test['timestamp']
                        })
                        
                        # Also add to network test results for performance data
                        test_result = {
                            'location': {'x': x, 'y': y},
                            'network': {
                                'ssid': test['ssid'],
                                'bssid': test['bssid'],
                                'signal_percentage': test['signal']
                            },
                            'timestamp': test['timestamp'],
                            'tests': test['tests']
                        }
                        self.network_test_results[ap_key].append(test_result)
                
                # Re-guardar archivo individual con coordenadas
                self.save_individual_measurement(measurement)
                
                break
        
        self.save_data()
        print(f"✓ Network test ID {measurement_id} mapped to coordinates ({x}, {y})")
    
    def create_ap_heatmap(self, ap_key: str, include_performance: bool = True):
        """Create heatmap for specific AP with optional performance overlay."""
        if ap_key not in self.ap_data:
            print(f"No data found for AP: {ap_key}")
            return None
        
        data = self.ap_data[ap_key]
        
        # Filter out data without locations
        data_with_coords = [d for d in data if d.get('location') is not None]
        
        if len(data_with_coords) < 3:
            print(f"Insufficient data points with coordinates for {ap_key} ({len(data_with_coords)} points)")
            return None
        
        print(f"✅ Heatmap would be created for {ap_key} with {len(data_with_coords)} points")
        return f"heatmap_{ap_key.replace(':', '-')}.png"
    
    def create_composite_heatmap(self):
        """Create comprehensive composite heatmap."""
        if not self.ap_data:
            print("No AP data available")
            return None
        
        print(f"✅ Composite heatmap would be created with {len(self.ap_data)} APs")
        return "composite_heatmap.png"
    
    def show_current_snr(self):
        """Mostrar SNR de la conexión actual."""
        current = self.scanner.get_current_connection_info()
        
        if 'error' not in current and 'ssid' in current:
            print(f"\n📡 CONEXIÓN ACTUAL - {current.get('ssid', 'Unknown')}")
            print(f"   Signal: {current.get('signal_percentage', 'N/A')}% ({current.get('signal_dbm', 'N/A'):.1f} dBm)")
            
            # Calcular SNR si no está disponible
            if current.get('signal_dbm') and not current.get('snr_db'):
                # Estimar ruido basado en banda
                if current.get('channel', 0) <= 14:
                    noise_floor = -95  # 2.4GHz
                else:
                    noise_floor = -100  # 5GHz
                
                snr = current['signal_dbm'] - noise_floor
                print(f"   SNR: {snr:.1f} dB (estimado)")
                print(f"   Ruido estimado: {noise_floor} dBm")
            else:
                print(f"   SNR: {current.get('snr_db', 'N/A'):.1f} dB")
                print(f"   Ruido estimado: {current.get('noise_dbm', 'N/A')} dBm")
                
            # Calidad de señal
            signal_quality = current.get('signal_quality', 'Unknown')
            print(f"   Calidad: {signal_quality}")
        else:
            print("No conectado a WiFi")
    
    def get_statistics(self):
        """Get comprehensive statistics."""
        stats = {
            'total_measurements': len(self.measurements),
            'total_aps': len(self.ap_data),
            'tested_networks': len(self.network_test_results),
            'individual_files': len(list(self.individual_measurements_dir.glob("*.json"))),
            'ap_detail_files': len(list(self.ap_details_dir.glob("*.json"))),
            'ap_details': [],
            'test_summary': {
                'total_ping_tests': 0,
                'avg_ping': [],
                'total_speed_tests': 0,
                'avg_download': [],
                'avg_upload': [],
                'total_iperf_tests': 0,
                'avg_throughput': []
            }
        }
        
        # AP statistics
        for ap_key, data in self.ap_data.items():
            ap_stats = {
                'name': ap_key.split('_')[0],
                'bssid': ap_key.split('_')[1] if '_' in ap_key else 'Unknown',
                'measurements': len(data),
                'avg_signal': np.mean([d['signal'] for d in data]) if data else 0,
                'max_signal': max([d['signal'] for d in data]) if data else 0,
                'min_signal': min([d['signal'] for d in data]) if data else 0
            }
            stats['ap_details'].append(ap_stats)
        
        # Sort by average signal
        stats['ap_details'].sort(key=lambda x: x['avg_signal'], reverse=True)
        
        return stats