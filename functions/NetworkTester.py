from traitlets import default
import subprocess
import time
import json
import re
import statistics
import os
from config.config import Config


class NetworkTester:
    """Handles all network testing functionality."""
    
    def __init__(self):
        # Allow dynamic server configuration
        self.iperf_server = Config.IPERF_SERVER
    
    def set_iperf_server(self, server_ip: str):
        """Update the iperf server IP."""
        self.iperf_server = server_ip
        Config.IPERF_SERVER = server_ip
        print(f"✓ iPerf server set to: {server_ip}")
    
    @staticmethod
    def get_client_network_info():
        """Obtener información de red del cliente - VERSIÓN ULTRA ROBUSTA UNIVERSAL."""
        client_info = {
            'client_ip': None,
            'gateway': None,
            'dns_servers': [],
            'interface_name': None,
            'subnet_mask': None,
            'timestamp': time.time()
        }
        
        def normalize_text(text):
            """Normalizar texto para manejar diferentes encodings y caracteres especiales."""
            # Reemplazar caracteres especiales comunes en diferentes encodings
            replacements = {
                '¢': 'ó', '¡': 'í', '†': 'é', '£': 'ú', 'š': 'á', 
                'Š': 'Á', '‚': 'é', 'ƒ': 'ó', '„': 'ü', '…': 'à',
                'scara': 'máscara', 'Direcci': 'Dirección', 
                'Configuraci': 'Configuración', 'descripci': 'descripción'
            }
            normalized = text
            for old, new in replacements.items():
                normalized = normalized.replace(old, new)
            return normalized.lower()
        
        def is_wifi_adapter_line(line):
            """Detectar si una línea corresponde a un adaptador WiFi."""
            line_lower = normalize_text(line)
            wifi_indicators = [
                'wireless', 'wi-fi', 'wifi', 'inalámbrica', 'inalambrica',
                '802.11', 'wlan', 'wireless lan', 'lan inalámbrica'
            ]
            adapter_indicators = ['adapter', 'adaptador']
            
            has_wifi = any(indicator in line_lower for indicator in wifi_indicators)
            has_adapter = any(indicator in line_lower for indicator in adapter_indicators)
            has_colon = ':' in line
            
            return has_wifi and has_adapter and has_colon
        
        def is_virtual_adapter(line):
            """Detectar si es un adaptador virtual que debemos ignorar."""
            line_lower = normalize_text(line)
            virtual_indicators = [
                'virtual', 'direct', 'hosted', 'microsoft', 'loopback',
                'tunnel', 'teredo', 'isatap', 'miniport', 'bluetooth'
            ]
            return any(indicator in line_lower for indicator in virtual_indicators)
        
        def extract_ipv4(text):
            """Extraer dirección IPv4 de un texto."""
            ipv4_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            match = re.search(ipv4_pattern, text)
            if match:
                ip = match.group(1)
                # Validar que sea una IP válida
                parts = ip.split('.')
                if all(0 <= int(part) <= 255 for part in parts):
                    return ip
            return None
        
        def is_private_ip(ip):
            """Verificar si es una IP privada válida."""
            if not ip:
                return False
            try:
                parts = [int(x) for x in ip.split('.')]
                # Rangos privados: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
                if parts[0] == 10:
                    return True
                elif parts[0] == 172 and 16 <= parts[1] <= 31:
                    return True
                elif parts[0] == 192 and parts[1] == 168:
                    return True
                # También aceptar algunas IPs públicas válidas
                elif parts[0] not in [0, 127, 255]:
                    return True
            except:
                pass
            return False
        
        try:
            print("🔧 NetworkTester: Iniciando análisis robusto de red...")
            
            # Método 1: ipconfig /all (principal)
            encodings = ['cp1252', 'utf-8', 'latin1', 'cp850']
            result = None
            
            for encoding in encodings:
                try:
                    result = subprocess.run(
                        ["ipconfig", "/all"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        encoding=encoding
                    )
                    if result.returncode == 0 and len(result.stdout) > 100:
                        print(f"   ✅ ipconfig exitoso con encoding: {encoding}")
                        break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            
            if not result or result.returncode != 0:
                print("   ⚠️ ipconfig /all falló, intentando método alternativo...")
                # Fallback a ipconfig simple
                try:
                    result = subprocess.run(
                        ["ipconfig"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        encoding='cp1252'
                    )
                except:
                    print("   ❌ Todos los métodos de ipconfig fallaron")
                    return client_info
            
            lines = result.stdout.splitlines()
            
            # Variables de estado
            current_interface = None
            in_wifi_section = False
            dhcp_servers = []
            potential_gateways = []
            wifi_adapters_found = []
            
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Detectar adaptador WiFi
                if is_wifi_adapter_line(line):
                    wifi_adapters_found.append(line)
                    
                    # Solo procesar si no es virtual
                    if not is_virtual_adapter(line):
                        current_interface = line
                        client_info['interface_name'] = current_interface
                        in_wifi_section = True
                        print(f"   🎯 Adaptador WiFi real: {current_interface[:60]}...")
                        continue
                    else:
                        print(f"   ⏭️  Adaptador virtual ignorado: {line[:50]}...")
                
                # Detectar fin de sección de adaptador
                elif (('adapter' in line.lower() or 'adaptador' in line.lower()) and 
                    ':' in line and in_wifi_section):
                    print(f"   📤 Fin de sección WiFi actual")
                    in_wifi_section = False
                    current_interface = None
                    continue
                
                # Procesar información dentro de la sección WiFi
                if in_wifi_section and current_interface and ':' in line:
                    try:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if not value:
                            continue
                        
                        key_norm = normalize_text(key)
                        value_norm = normalize_text(value)
                        
                        # IPv4 Address (múltiples patrones)
                        if any(pattern in key_norm for pattern in [
                            'ipv4', 'dirección ipv4', 'direccion ipv4', 'ip address'
                        ]):
                            ip = extract_ipv4(value)
                            if ip and is_private_ip(ip) and not client_info['client_ip']:
                                client_info['client_ip'] = ip
                                print(f"   ✅ IP encontrada: {ip}")
                        
                        # Subnet Mask (múltiples patrones y encodings)
                        elif any(pattern in key_norm for pattern in [
                            'subnet mask', 'máscara de subred', 'mascara de subred',
                            'subred', 'subnet', 'máscara', 'mascara'
                        ]):
                            mask = extract_ipv4(value)
                            if mask and not client_info['subnet_mask']:
                                client_info['subnet_mask'] = mask
                                print(f"   ✅ Máscara encontrada: {mask}")
                        
                        # Default Gateway (manejar IPv4 e IPv6)
                        elif any(pattern in key_norm for pattern in [
                            'default gateway', 'puerta de enlace predeterminada',
                            'puerta de enlace', 'gateway', 'enlace predeterminado'
                        ]):
                            # Priorizar IPv4 sobre IPv6
                            gateway_ipv4 = extract_ipv4(value)
                            if gateway_ipv4 and not client_info['gateway']:
                                client_info['gateway'] = gateway_ipv4
                                print(f"   ✅ Gateway IPv4: {gateway_ipv4}")
                            elif gateway_ipv4:
                                potential_gateways.append(gateway_ipv4)
                        
                        # DHCP Server (como fallback para gateway)
                        elif any(pattern in key_norm for pattern in [
                            'dhcp server', 'servidor dhcp', 'dhcp'
                        ]):
                            dhcp_ip = extract_ipv4(value)
                            if dhcp_ip:
                                dhcp_servers.append(dhcp_ip)
                                print(f"   📝 Servidor DHCP: {dhcp_ip}")
                        
                        # DNS Servers (solo IPv4)
                        elif any(pattern in key_norm for pattern in [
                            'dns servers', 'servidores dns', 'dns'
                        ]):
                            dns_ip = extract_ipv4(value)
                            if dns_ip and dns_ip not in client_info['dns_servers']:
                                client_info['dns_servers'].append(dns_ip)
                                print(f"   ✅ DNS encontrado: {dns_ip}")
                        
                    except ValueError:
                        continue
                    except Exception:
                        continue
            
            # Post-procesamiento: fallbacks inteligentes
            
            # Fallback para gateway
            if not client_info['gateway']:
                # Usar DHCP server como gateway
                if dhcp_servers:
                    client_info['gateway'] = dhcp_servers[0]
                # Usar gateway potencial
                elif potential_gateways:
                    client_info['gateway'] = potential_gateways[0]
                # Inferir gateway desde IP
                elif client_info['client_ip']:
                    try:
                        ip_parts = client_info['client_ip'].split('.')
                        gateway_guess = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.1"
                        client_info['gateway'] = gateway_guess
                    except:
                        pass
            
            # Método 2: route print (fallback adicional para gateway)
            if not client_info['gateway']:
                try:
                    print("   🔄 Buscando gateway con route print...")
                    route_result = subprocess.run(
                        ["route", "print", "0.0.0.0"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        encoding='cp1252'
                    )
                    
                    if route_result.returncode == 0:
                        for line in route_result.stdout.splitlines():
                            if "0.0.0.0" in line:
                                gateway = extract_ipv4(line)
                                if gateway and gateway != "0.0.0.0":
                                    client_info['gateway'] = gateway
                                    break
                except:
                    pass
            
            # Método 3: arp -a (último recurso)
            if not client_info['gateway'] and client_info['client_ip']:
                try:
                    print("   🔄 Buscando gateway con arp...")
                    arp_result = subprocess.run(
                        ["arp", "-a"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        encoding='cp1252'
                    )
                    
                    if arp_result.returncode == 0:
                        for line in arp_result.stdout.splitlines():
                            gateway = extract_ipv4(line)
                            if gateway and gateway.endswith('.1'):
                                client_info['gateway'] = gateway
                                print(f"   ✅ Gateway desde ARP: {gateway}")
                                break
                except:
                    pass
            
            # Resumen final
            print(f"   📊 RESUMEN FINAL:")
            print(f"      🖥️  Adaptadores WiFi encontrados: {len(wifi_adapters_found)}")
            print(f"      📱 Interfaz seleccionada: {client_info['interface_name'][:50] if client_info['interface_name'] else 'Ninguna'}...")
            print(f"      🌐 IP: {client_info['client_ip'] or 'No encontrada'}")
            print(f"      🚪 Gateway: {client_info['gateway'] or 'No encontrado'}")
            print(f"      🎭 Máscara: {client_info['subnet_mask'] or 'No encontrada'}")
            print(f"      🔍 DNS: {len(client_info['dns_servers'])} servidor(es)")
            
            # Evaluación de éxito
            if client_info['client_ip'] and client_info['gateway']:
                print(f"   ✅ NetworkTester: Información completa obtenida exitosamente")
            elif client_info['client_ip']:
                print(f"   ⚠️ NetworkTester: IP obtenida, gateway incompleto")
            else:
                print(f"   ❌ NetworkTester: Información insuficiente obtenida")
            
            return client_info
        
        except subprocess.TimeoutExpired:
            print("   ❌ NetworkTester: Timeout en comandos de red")
            return client_info
        except Exception as e:
            print(f"   ❌ NetworkTester: Error inesperado: {e}")
            return client_info
    @staticmethod
    def check_iperf_server():
        """Check if LOCAL iperf3 server is running."""
        try:
            result = subprocess.run(
                ["netstat", "-an"], 
                capture_output=True, 
                text=True,
                timeout=10
            )
            return ":5201" in result.stdout
        except:
            return False
    
    @staticmethod
    def start_iperf_server():
        """Start LOCAL iperf3 server if not running."""
        if NetworkTester.check_iperf_server():
            print("✓ Local iperf3 server already running")
            return True
        
        try:
            print("Starting local iperf3 server...")
            subprocess.Popen(
                [Config.IPERF_PATH, "-s"], 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            time.sleep(2)
            return NetworkTester.check_iperf_server()
        except Exception as e:
            print(f"Error starting local iperf3 server: {e}")
            return False
    
    @staticmethod
    def run_ping(target=Config.PING_TARGET, count=Config.PING_COUNT):
        """Run ping test."""
        try:
            result = subprocess.run(
                ["ping", "-n", str(count), target], 
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            # Parse results
            ping_times = []
            packet_loss = "0%"
            
            for line in result.stdout.splitlines():
                if "tiempo=" in line or "time=" in line:
                    match = re.search(r'(?:tiempo|time)=(\d+)ms', line)
                    if match:
                        ping_times.append(int(match.group(1)))
                elif "perdidos" in line or "loss" in line:
                    match = re.search(r'\(([0-9]+)%', line)
                    if match:
                        packet_loss = f"{match.group(1)}%"
            
            if ping_times:
                return {
                    "success": True,
                    "avg_time": statistics.mean(ping_times),
                    "min_time": min(ping_times),
                    "max_time": max(ping_times),
                    "packet_loss": packet_loss,
                    "raw_times": ping_times
                }
            else:
                return {"success": False, "error": "No ping responses"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def run_speedtest(server_id=Config.SPEEDTEST_SERVER_ID):
        """Run speedtest."""
        try:
            result = subprocess.run(
                [Config.SPEEDTEST_PATH, "--server-id", str(server_id), "--format=json"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {
                    "success": True,
                    "download_mbps": data.get("download", {}).get("bandwidth", 0) / 1_000_000,
                    "upload_mbps": data.get("upload", {}).get("bandwidth", 0) / 1_000_000,
                    "ping_ms": data.get("ping", {}).get("latency", 0),
                    "server": data.get("server", {}).get("name", "Unknown"),
                    "raw_data": data
                }
            else:
                return {"success": False, "error": "Speedtest failed"}
                
        except FileNotFoundError:
            return {"success": False, "error": "speedtest.exe not found"}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid speedtest output"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_iperf_suite(self, duration=10):
        """Suite completa de tests iPerf con múltiples tests UDP."""
        if not os.path.exists(Config.IPERF_PATH):
            return {"success": False, "error": "iperf3 not found", "tests": {}, "raw_output": []}

        results = {"success": True, "server": self.iperf_server, "tests": {}, "raw_output": []}

        def stream_process(cmd_list, desc):
            print(f"\n🔄 {desc}")
            print("-" * 50)
            proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            lines = []
            while True:
                line = proc.stdout.readline()
                if line == '' and proc.poll() is not None:
                    break
                if line:
                    clean = line.strip()
                    print(f"   {clean}")
                    lines.append(line)
            try:
                proc.wait(timeout=duration + 10)
            except subprocess.TimeoutExpired:
                proc.kill()
                print(f"   ⚠️ Timeout en {desc}")
            return lines

        def run_json(cmd_list):
            try:
                proc = subprocess.run(
                    cmd_list,
                    capture_output=True,
                    text=True,
                    timeout=duration + 10
                )
                if proc.returncode == 0:
                    return json.loads(proc.stdout)
                else:
                    stderr = proc.stderr.strip()
                    print(f"   ⚠️ Error en JSON command {' '.join(cmd_list)}: returncode {proc.returncode}, stderr: {stderr}")
            except subprocess.TimeoutExpired:
                print(f"   ⚠️ Timeout en JSON command {' '.join(cmd_list)}")
            except json.JSONDecodeError:
                print(f"   ⚠️ JSON inválido de {' '.join(cmd_list)}")
            return None

        # Obtener información de red del cliente
        client_info = self.get_client_network_info()
        results['client_network_info'] = client_info
        
        print(f"\n📋 INFO DE RED DEL CLIENTE:")
        print(f"   IP Cliente: {client_info.get('client_ip', 'N/A')}")
        print(f"   Gateway: {client_info.get('gateway', 'N/A')}")
        print(f"   Interfaz: {client_info.get('interface_name', 'N/A')}")

        try:
            print(f"\n🚀 EJECUTANDO SUITE COMPLETA DE IPERF")
            print(f"   Servidor: {self.iperf_server}")
            print(f"   Duración: {duration} segundos por test")
            print("=" * 70)

            # 1. TCP FORWARD
            print("\n1. TCP FORWARD (cliente -> servidor)")
            tcp_fwd_lines = stream_process([
                Config.IPERF_PATH, "-c", self.iperf_server, "-t", str(duration), "-i", "1"
            ], "TCP FORWARD (streaming)")
            results["raw_output"].extend(tcp_fwd_lines)
            tcp_fwd_json = run_json([
                Config.IPERF_PATH, "-c", self.iperf_server, "-J", "-t", str(duration)
            ])
            if tcp_fwd_json:
                dl_bps = tcp_fwd_json.get("end", {}).get("sum_received", {}).get("bits_per_second", 0)
                ul_bps = tcp_fwd_json.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0)
                results["tests"]["tcp_forward"] = {
                    "download_mbps": dl_bps / 1_000_000,
                    "upload_mbps": ul_bps / 1_000_000,
                    "download_gbps": dl_bps / 1_000_000_000,
                    "upload_gbps": ul_bps / 1_000_000_000
                }

            # 2. TCP REVERSE
            print("\n2. TCP REVERSE (servidor -> cliente)")
            tcp_rev_lines = stream_process([
                Config.IPERF_PATH, "-c", self.iperf_server, "-R", "-t", str(duration), "-i", "1"
            ], "TCP REVERSE (streaming)")
            results["raw_output"].extend(tcp_rev_lines)
            tcp_rev_json = run_json([
                Config.IPERF_PATH, "-c", self.iperf_server, "-J", "-R", "-t", str(duration)
            ])
            if tcp_rev_json:
                dl_bps = tcp_rev_json.get("end", {}).get("sum_received", {}).get("bits_per_second", 0)
                ul_bps = tcp_rev_json.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0)
                results["tests"]["tcp_reverse"] = {
                    "download_mbps": dl_bps / 1_000_000,
                    "upload_mbps": ul_bps / 1_000_000,
                    "download_gbps": dl_bps / 1_000_000_000,
                    "upload_gbps": ul_bps / 1_000_000_000
                }

            # 3. MÚLTIPLES TESTS UDP FORWARD (NUEVO)
            udp_forward_rates = ["1M", "5M", "10M"]
            print(f"\n3. UDP FORWARD TESTS (cliente -> servidor)")
            results["tests"]["udp_forward_tests"] = {}
            
            for rate in udp_forward_rates:
                print(f"\n   3.{udp_forward_rates.index(rate)+1}. UDP FORWARD {rate}")
                print("-" * 40)
                
                # Streaming
                udp_fwd_lines = stream_process([
                    Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-b", rate, 
                    "-t", str(duration), "-i", "1", "-l", "1400"
                ], f"UDP FORWARD {rate} (streaming)")
                results["raw_output"].extend(udp_fwd_lines)
                
                # JSON
                udp_fwd_json = run_json([
                    Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-b", rate, 
                    "-t", str(duration), "-J", "-l", "1400"
                ])
                
                if udp_fwd_json is None:
                    # Fallback IPv4
                    print(f"   ⚠️ Reintentando UDP FORWARD {rate} con IPv4")
                    udp_fwd_json = run_json([
                        Config.IPERF_PATH, "-4", "-c", self.iperf_server, "-u", "-b", rate,
                        "-t", str(duration), "-J", "-l", "1400"
                    ])
                
                if udp_fwd_json:
                    sum_info = udp_fwd_json.get("end", {}).get("sum", {})
                    actual_bps = sum_info.get("bits_per_second", 0)
                    lost = sum_info.get("lost_percent", 0)
                    jitter = sum_info.get("jitter_ms", 0)
                    
                    # Calcular calidad
                    if lost < 0.1 and jitter < 2.0:
                        quality = "EXCELENTE"
                    elif lost < 0.5 and jitter < 5.0:
                        quality = "BUENA"
                    elif lost < 1.0:
                        quality = "ACEPTABLE"
                    else:
                        quality = "PROBLEMÁTICA"
                    
                    results["tests"]["udp_forward_tests"][f"udp_forward_{rate}"] = {
                        "target_mbps": float(rate.rstrip("M")),
                        "actual_mbps": actual_bps / 1_000_000,
                        "jitter_ms": jitter,
                        "lost_percent": lost,
                        "total_packets": sum_info.get("packets", 0),
                        "lost_packets": sum_info.get("lost_packets", 0),
                        "quality": quality,
                    }
                    print(f"   ✅ UDP FORWARD {rate}: {actual_bps/1_000_000:.1f} Mbps, {lost:.2f}% loss, calidad: {quality}")
                else:
                    results["tests"]["udp_forward_tests"][f"udp_forward_{rate}"] = {
                        "error": f"Failed UDP forward test {rate}"
                    }

            # 4. MÚLTIPLES TESTS UDP REVERSE (MEJORADO)
            udp_reverse_rates = ["1M", "5M", "10M"]
            print(f"\n4. UDP REVERSE TESTS (servidor -> cliente)")
            results["tests"]["udp_reverse_tests"] = {}
            
            for rate in udp_reverse_rates:
                print(f"\n   4.{udp_reverse_rates.index(rate)+1}. UDP REVERSE {rate}")
                print("-" * 40)
                
                # Streaming
                udp_rev_lines = stream_process([
                    Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-R", "-b", rate,
                    "-t", str(duration), "-i", "1", "-l", "1400"
                ], f"UDP REVERSE {rate} (streaming)")
                results["raw_output"].extend(udp_rev_lines)
                
                # JSON
                udp_rev_json = run_json([
                    Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-R", "-b", rate,
                    "-t", str(duration), "-J", "-l", "1400"
                ])
                
                if udp_rev_json is None:
                    # Fallback IPv4
                    print(f"   ⚠️ Reintentando UDP REVERSE {rate} con IPv4")
                    udp_rev_json = run_json([
                        Config.IPERF_PATH, "-4", "-c", self.iperf_server, "-u", "-R", "-b", rate,
                        "-t", str(duration), "-J", "-l", "1400"
                    ])
                
                if udp_rev_json:
                    sum_info = udp_rev_json.get("end", {}).get("sum", {})
                    actual_bps = sum_info.get("bits_per_second", 0)
                    lost = sum_info.get("lost_percent", 0)
                    jitter = sum_info.get("jitter_ms", 0)
                    
                    # Calcular calidad
                    if lost < 0.1 and jitter < 2.0:
                        quality = "EXCELENTE"
                    elif lost < 0.5 and jitter < 5.0:
                        quality = "BUENA"
                    elif lost < 1.0:
                        quality = "ACEPTABLE"
                    else:
                        quality = "PROBLEMÁTICA"
                    
                    results["tests"]["udp_reverse_tests"][f"udp_reverse_{rate}"] = {
                        "target_mbps": float(rate.rstrip("M")),
                        "actual_mbps": actual_bps / 1_000_000,
                        "jitter_ms": jitter,
                        "lost_percent": lost,
                        "total_packets": sum_info.get("packets", 0),
                        "lost_packets": sum_info.get("lost_packets", 0),
                        "quality": quality,
                    }
                    print(f"   ✅ UDP REVERSE {rate}: {actual_bps/1_000_000:.1f} Mbps, {lost:.2f}% loss, calidad: {quality}")
                else:
                    results["tests"]["udp_reverse_tests"][f"udp_reverse_{rate}"] = {
                        "error": f"Failed UDP reverse test {rate}"
                    }

           

            # Resumen final
            print("\n" + "=" * 70)
            print("🎯 RESUMEN FINAL DE CONECTIVIDAD")
            print("=" * 70)
            if "tcp_forward" in results["tests"]:
                t = results["tests"]["tcp_forward"]
                print(f"📊 TCP FORWARD: Download {t['download_mbps']:.1f} Mbps, Upload {t['upload_mbps']:.1f} Mbps")
            if "tcp_reverse" in results["tests"]:
                t = results["tests"]["tcp_reverse"]
                print(f"📊 TCP REVERSE: Download {t['download_mbps']:.1f} Mbps, Upload {t['upload_mbps']:.1f} Mbps")
            
            # Resumen UDP Forward
            if "udp_forward_tests" in results["tests"]:
                print(f"📊 UDP FORWARD TESTS:")
                for test_name, test_data in results["tests"]["udp_forward_tests"].items():
                    if "error" not in test_data:
                        rate = test_name.split("_")[-1]
                        print(f"   {rate}: {test_data['actual_mbps']:.1f} Mbps ({test_data['quality']})")
            
            # Resumen UDP Reverse  
            if "udp_reverse_tests" in results["tests"]:
                print(f"📊 UDP REVERSE TESTS:")
                for test_name, test_data in results["tests"]["udp_reverse_tests"].items():
                    if "error" not in test_data:
                        rate = test_name.split("_")[-1]
                        print(f"   {rate}: {test_data['actual_mbps']:.1f} Mbps ({test_data['quality']})")

            print("=" * 70)
            return results

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "iPerf test timeout", "tests": results.get("tests", {}), "raw_output": results.get("raw_output", [])}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid iperf3 JSON output", "tests": results.get("tests", {}), "raw_output": results.get("raw_output", [])}
        except Exception as e:
            return {"success": False, "error": str(e), "tests": results.get("tests", {}), "raw_output": results.get("raw_output", [])}
        
    @staticmethod
    def run_traceroute(target=Config.PING_TARGET):
        """Run traceroute."""
        try:
            result = subprocess.run(
                ["tracert", "-w", "3000", "-h", "20", target],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            hops = []
            for line in result.stdout.splitlines():
                match = re.match(r'\s*(\d+)\s+(.+)', line)
                if match:
                    hop_num = int(match.group(1))
                    hop_info = match.group(2).strip()
                    hops.append({"hop": hop_num, "info": hop_info})
            
            return {
                "success": True,
                "hops": hops,
                "total_hops": len(hops),
                "raw_output": result.stdout
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Traceroute timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}