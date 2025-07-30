#!/usr/bin/env python3
"""
Integrated WiFi Analysis System with Persistent Heatmaps
Includes: WiFi scanning, network testing (ping, speedtest, iperf), and heatmap generation
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import re
import time
import os
from collections import defaultdict
import statistics
from scipy.interpolate import Rbf
from scipy.interpolate import griddata
import numpy as np


# Configuration
class Config:
    # Paths
    IPERF_PATH = "C:\\iperf3\\iperf3.exe\\iperf3.exe"
    SPEEDTEST_PATH = "C:\\Users\\Usuario\\speedtest.exe"
    IPERF_SERVER = "iperf.he.net"  # Default public server
    
    # House dimensions
    HOUSE_WIDTH = 15
    HOUSE_LENGTH = 20
    
    # Data storage
    DATA_DIR = Path("heatmap_data")
    
    # Test settings
    PING_TARGET = "8.8.8.8"
    PING_COUNT = 4
    SPEEDTEST_SERVER_ID = 40741  # ANTEL
    
    # Heatmap settings
    GRID_RESOLUTION = 0.5
    HEATMAP_DPI = 300
    MEASUREMENT_INTERVAL = 30

    # FILTRADO DE REDES - SOLO MONITOREAR ESTOS SSIDs
    MONITORED_SSIDS = [
        "Pumita",           
        "Puma",              
        
    ]
    
    # Si está vacío, monitorea TODAS las redes
    MONITOR_ALL_NETWORKS = True  # Cambiar a True para monitorear todo


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
        """Run comprehensive iPerf test suite with REAL-TIME output."""
        if not os.path.exists(Config.IPERF_PATH):
            return {"success": False, "error": "iperf3 not found"}
        
        results = {
            "success": True,
            "server": self.iperf_server,
            "tests": {},
            "raw_output": []
        }
        
        try:
            print(f"\n🚀 EJECUTANDO SUITE COMPLETA DE IPERF")
            print(f"   Servidor: {self.iperf_server}")
            print(f"   Duración: {duration} segundos por test")
            print("="*70)
            
            # 1. TCP TEST CON SALIDA EN TIEMPO REAL
            print(f"\n🔄 1. TCP THROUGHPUT TEST")
            print("-"*50)
            
            process = subprocess.Popen(
                [Config.IPERF_PATH, "-c", self.iperf_server, "-t", str(duration), "-i", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            tcp_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Mostrar línea en tiempo real
                    clean_line = output.strip()
                    print(f"   {clean_line}")
                    tcp_lines.append(output)
            
            process.wait(timeout=duration + 10)
            results["raw_output"].extend(tcp_lines)
            
            # Obtener datos JSON para procesamiento
            json_process = subprocess.run(
                [Config.IPERF_PATH, "-c", self.iperf_server, "-J", "-t", str(duration)],
                capture_output=True,
                text=True,
                timeout=duration + 10
            )
            
            if json_process.returncode == 0:
                tcp_data = json.loads(json_process.stdout)
                
                download_bps = tcp_data.get("end", {}).get("sum_received", {}).get("bits_per_second", 0)
                upload_bps = tcp_data.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0)
                
                results["tests"]["tcp"] = {
                    "download_mbps": download_bps / 1_000_000,
                    "upload_mbps": upload_bps / 1_000_000,
                    "download_gbps": download_bps / 1_000_000_000,
                    "upload_gbps": upload_bps / 1_000_000_000
                }
                
                print("-"*50)
                print(f"✅ TCP RESUMEN:")
                print(f"   Download: {results['tests']['tcp']['download_mbps']:.1f} Mbps ({results['tests']['tcp']['download_gbps']:.2f} Gbps)")
                print(f"   Upload:   {results['tests']['tcp']['upload_mbps']:.1f} Mbps ({results['tests']['tcp']['upload_gbps']:.2f} Gbps)")
                
                # 2. UDP TEST SOLO SI TCP FUE EXITOSO
                if download_bps > 0:
                    target_bps = min(download_bps, 1_000_000_000)  # Máximo 1 Gbps para UDP
                    target_mbps = target_bps / 1_000_000
                    
                    print(f"\n🔄 2. UDP QUALITY TEST")
                    print(f"   Target: {target_mbps:.0f} Mbps")
                    print("-"*50)
                    
                    udp_process = subprocess.Popen(
                        [Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-b", str(target_bps), 
                        "-t", str(duration), "-i", "1"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    
                    udp_lines = []
                    while True:
                        output = udp_process.stdout.readline()
                        if output == '' and udp_process.poll() is not None:
                            break
                        if output:
                            clean_line = output.strip()
                            print(f"   {clean_line}")
                            udp_lines.append(output)
                    
                    udp_process.wait(timeout=duration + 10)
                    results["raw_output"].extend(udp_lines)
                    
                    # Obtener datos JSON para UDP
                    udp_json_process = subprocess.run(
                        [Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-b", str(target_bps), 
                        "-t", str(duration), "-J"],
                        capture_output=True,
                        text=True,
                        timeout=duration + 10
                    )
                    
                    if udp_json_process.returncode == 0:
                        udp_data = json.loads(udp_json_process.stdout)
                        
                        results["tests"]["udp"] = {
                            "target_mbps": target_mbps,
                            "actual_mbps": udp_data.get("end", {}).get("sum", {}).get("bits_per_second", 0) / 1_000_000,
                            "jitter_ms": udp_data.get("end", {}).get("sum", {}).get("jitter_ms", 0),
                            "lost_packets": udp_data.get("end", {}).get("sum", {}).get("lost_packets", 0),
                            "lost_percent": udp_data.get("end", {}).get("sum", {}).get("lost_percent", 0),
                            "total_packets": udp_data.get("end", {}).get("sum", {}).get("packets", 0)
                        }
                        
                        print("-"*50)
                        print(f"✅ UDP RESUMEN:")
                        print(f"   Throughput:  {results['tests']['udp']['actual_mbps']:.1f} Mbps (target: {target_mbps:.0f})")
                        print(f"   Jitter:      {results['tests']['udp']['jitter_ms']:.2f} ms")
                        print(f"   Packet Loss: {results['tests']['udp']['lost_percent']:.1f}% ({results['tests']['udp']['lost_packets']}/{results['tests']['udp']['total_packets']})")
                        
                        # Evaluación de calidad
                        if results['tests']['udp']['lost_percent'] < 1.0 and results['tests']['udp']['jitter_ms'] < 5.0:
                            quality = "EXCELENTE"
                        elif results['tests']['udp']['lost_percent'] < 3.0 and results['tests']['udp']['jitter_ms'] < 10.0:
                            quality = "BUENA"
                        elif results['tests']['udp']['lost_percent'] < 5.0:
                            quality = "ACEPTABLE"
                        else:
                            quality = "PROBLEMÁTICA"
                        
                        print(f"   Calidad:     {quality}")
            
            # 3. RESUMEN FINAL
            print("\n" + "="*70)
            print("🎯 RESUMEN FINAL DE CONECTIVIDAD")
            print("="*70)
            
            if "tcp" in results["tests"]:
                tcp = results["tests"]["tcp"]
                print(f"📊 TCP Performance:")
                print(f"   • Download: {tcp['download_gbps']:.2f} Gbps ({tcp['download_mbps']:.0f} Mbps)")
                print(f"   • Upload:   {tcp['upload_gbps']:.2f} Gbps ({tcp['upload_mbps']:.0f} Mbps)")
            
            if "udp" in results["tests"]:
                udp = results["tests"]["udp"]
                print(f"📊 UDP Quality:")
                print(f"   • Jitter:      {udp['jitter_ms']:.2f} ms")
                print(f"   • Packet Loss: {udp['lost_percent']:.1f}%")
            
            print("="*70)
            
            return results
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "iPerf test timeout"}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid iperf3 JSON output"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
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

class HeatmapManager:
    """Manages persistent heatmaps with network testing."""
    
    def __init__(self, house_width=Config.HOUSE_WIDTH, house_length=Config.HOUSE_LENGTH):
        self.house_width = house_width
        self.house_length = house_length
        self.data_dir = Config.DATA_DIR
        self.data_dir.mkdir(exist_ok=True)
        
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
        
        networks = self.scanner.scan_networks(force_refresh=True)
        
        measurement = {
            'id': measurement_id,
            'timestamp': datetime.now().isoformat(),
            'location': None,  # Will be mapped later
            'networks': [],
            'tests': {}
        }
        
        print(f"\n📍 MEASUREMENT ID: {measurement_id}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
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
                
                # Mostrar más información
            signal_dbm_str = f"({network['signal_dbm']:.1f} dBm)" if network.get('signal_dbm') is not None else ""
            print(f"  📡 {network['ssid']} {network['bssid']} - {network['signal_percentage']}% - Ch{network['channel']} {signal_dbm_str} - {network.get('signal_quality', 'Unknown')}")
                    # Run network tests if connected
        if run_tests:
            current_conn = self.scanner.get_current_connection_info()
            if 'ssid' in current_conn and 'error' not in current_conn:
                print(f"\n  Running network tests on {current_conn['ssid']}...")
                
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
            
        self.measurements.append(measurement)
        self.save_data()
        
        print(f"\n✅ Measurement ID {measurement_id} saved successfully!")
        print("   Remember to note this ID on your floor plan!")
        
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
        
        # Create base measurement
        measurement = {
            'id': measurement_id,
            'timestamp': datetime.now().isoformat(),
            'location': None,  # Will be mapped later
            'networks': [],
            'tests': {},
            'all_network_tests': []  # Store tests for all networks
        }
        
        # Store all visible networks info
        for network in networks:
            if network['bssid'] != "Unknown":
                net_data = {
                    'ssid': network['ssid'],
                    'bssid': network['bssid'],
                    'signal': network['signal_percentage'],
                    'signal_dbm': network.get('signal_dbm'),  # Añadir
                    'snr_db': network.get('snr_db'),         # Añadir
                    'signal_quality': network.get('signal_quality'),  # Añadir
                    'channel': network['channel'],
                    'band': network.get('band'),             # Añadir
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
                    measurement['tests']['iperf_suite'] = iperf_result
                else:
                    print(f"    ✗ iPerf: {iperf_result['error']}")
            
            measurement['all_network_tests'].append(network_test)
            self.scanner.tested_networks.add(ssid)
        
        # Save measurement
        self.measurements.append(measurement)
        self.save_data()
        
        print(f"\n✅ Network testing completed for ID {measurement_id}")
        print(f"   Tested {len(measurement['all_network_tests'])} networks")
        
        return measurement
    
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
                        
                        # Add to AP data for heatmap (THIS IS THE KEY ADDITION)
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
        
        # Create figure
        fig, axes = plt.subplots(1, 2 if include_performance else 1, figsize=(20 if include_performance else 12, 8))
        if not include_performance:
            axes = [axes]
        
        # Signal strength heatmap
        self._create_signal_heatmap(axes[0], data_with_coords, ap_key)
        
        # Performance heatmap if available
        if include_performance and ap_key in self.network_test_results:
            self._create_performance_heatmap(axes[1], self.network_test_results[ap_key], ap_key)
        
        # Save
        output_file = self.data_dir / f"heatmap_{ap_key.replace(':', '-')}.png"
        plt.tight_layout()
        plt.savefig(output_file, dpi=Config.HEATMAP_DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Heatmap saved: {output_file}")
        return str(output_file)
    
    def _create_signal_heatmap(self, ax, data, title):
        """Create signal strength heatmap."""
        # Grid
        x_grid = np.arange(0, self.house_width, Config.GRID_RESOLUTION)
        y_grid = np.arange(0, self.house_length, Config.GRID_RESOLUTION)
        xx, yy = np.meshgrid(x_grid, y_grid)
        
        # Interpolate
        points = np.array([(d['location']['x'], d['location']['y']) for d in data])
        values = np.array([d['signal'] for d in data])
        
        grid_signal = self._interpolate_grid(xx, yy, points, values)
        
        # Plot
        im = ax.contourf(xx, yy, grid_signal, levels=20, cmap='RdYlGn', alpha=0.8, vmin=0, vmax=100)
        
        # Rooms
        for room_name, room in self.rooms.items():
            rect = patches.Rectangle(
                (room['x'], room['y']), room['width'], room['height'],
                linewidth=2, edgecolor='black', facecolor='none'
            )
            ax.add_patch(rect)
            ax.text(room['x'] + room['width']/2, room['y'] + room['height']/2,
                   room_name, ha='center', va='center', fontsize=10, weight='bold')
        
        # Measurement points
        ax.scatter(points[:, 0], points[:, 1], c='blue', s=50, edgecolor='white', linewidth=2, zorder=5)
        
        # Format
        ax.set_xlim(0, self.house_width)
        ax.set_ylim(0, self.house_length)
        ax.set_xlabel('X (meters)')
        ax.set_ylabel('Y (meters)')
        ax.set_title(f'Signal Strength: {title.split("_")[0]}', fontsize=14, weight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        
        # Colorbar
        plt.colorbar(im, ax=ax, label='Signal %')
    
    def _create_performance_heatmap(self, ax, test_results, title):
        """Create performance heatmap based on test results."""
        if not test_results:
            ax.text(0.5, 0.5, 'No performance data available', 
                   transform=ax.transAxes, ha='center', va='center', fontsize=16)
            return
        
        # Extract performance data
        perf_data = []
        for result in test_results:
            loc = result['location']
            tests = result.get('tests', {})
            
            # Calculate performance score
            score = 0
            if 'ping' in tests and tests['ping']['success']:
                # Lower ping is better
                ping_score = max(0, 100 - tests['ping']['avg_time'])
                score += ping_score * 0.3
            
            if 'speedtest' in tests and tests['speedtest']['success']:
                # Higher speed is better
                speed_score = min(100, tests['speedtest']['download_mbps'])
                score += speed_score * 0.7
            
            if score > 0:
                perf_data.append({
                    'location': loc,
                    'score': score
                })
        
        if not perf_data:
            ax.text(0.5, 0.5, 'No performance tests completed', 
                   transform=ax.transAxes, ha='center', va='center', fontsize=16)
            return
        
        # Grid
        x_grid = np.arange(0, self.house_width, Config.GRID_RESOLUTION)
        y_grid = np.arange(0, self.house_length, Config.GRID_RESOLUTION)
        xx, yy = np.meshgrid(x_grid, y_grid)
        
        # Interpolate
        points = np.array([(d['location']['x'], d['location']['y']) for d in perf_data])
        values = np.array([d['score'] for d in perf_data])
        
        grid_perf = self._interpolate_grid(xx, yy, points, values)
        
        # Plot
        im = ax.contourf(xx, yy, grid_perf, levels=20, cmap='RdYlGn', alpha=0.8, vmin=0, vmax=100)
        
        # Rooms
        for room_name, room in self.rooms.items():
            rect = patches.Rectangle(
                (room['x'], room['y']), room['width'], room['height'],
                linewidth=2, edgecolor='black', facecolor='none'
            )
            ax.add_patch(rect)
        
        # Test points
        ax.scatter(points[:, 0], points[:, 1], c='red', s=100, marker='*', edgecolor='white', linewidth=2, zorder=5)
        
        # Format
        ax.set_xlim(0, self.house_width)
        ax.set_ylim(0, self.house_length)
        ax.set_xlabel('X (meters)')
        ax.set_ylabel('Y (meters)')
        ax.set_title(f'Network Performance: {title.split("_")[0]}', fontsize=14, weight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        
        # Colorbar
        plt.colorbar(im, ax=ax, label='Performance Score')
    
    def _interpolate_grid(self, xx, yy, points, values):
        """Smooth interpolation using griddata."""
        # Use griddata with cubic method for smooth interpolation
        grid = griddata(points, values, (xx, yy), method='cubic')
        
        # Clip values to valid range
        grid = np.clip(grid, 0, 100)
        
        # Fill NaN values with nearest neighbor
        nan_mask = np.isnan(grid)
        if np.any(nan_mask):
            grid[nan_mask] = griddata(points, values, (xx[nan_mask], yy[nan_mask]), method='nearest')
        
        return grid
    
    def create_composite_heatmap(self):
        """Create comprehensive composite heatmap."""
        if not self.ap_data:
            print("No AP data available")
            return None
        
        # Create figure with 4 subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # 1. Maximum signal strength
        self._create_max_signal_heatmap(ax1)
        
        # 2. AP density
        self._create_ap_density_heatmap(ax2)
        
        # 3. Best performing AP
        self._create_best_performance_heatmap(ax3)
        
        # 4. Channel distribution
        self._create_channel_distribution_map(ax4)
        
        # Save
        output_file = self.data_dir / "composite_heatmap.png"
        plt.tight_layout()
        plt.savefig(output_file, dpi=Config.HEATMAP_DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Composite heatmap saved: {output_file}")
        return str(output_file)
    
    def _create_max_signal_heatmap(self, ax):
        """Create maximum signal strength heatmap."""
        x_grid = np.arange(0, self.house_width, Config.GRID_RESOLUTION)
        y_grid = np.arange(0, self.house_length, Config.GRID_RESOLUTION)
        xx, yy = np.meshgrid(x_grid, y_grid)
        
        grid_max_signal = np.zeros_like(xx)
        
        for ap_key, data in self.ap_data.items():
            # Filter data with coordinates
            data_with_coords = [d for d in data if d.get('location') is not None]
            if len(data_with_coords) < 3:
                continue
            
            points = np.array([(d['location']['x'], d['location']['y']) for d in data_with_coords])
            values = np.array([d['signal'] for d in data_with_coords])
            
            grid_signal = self._interpolate_grid(xx, yy, points, values)
            grid_max_signal = np.maximum(grid_max_signal, grid_signal)
        
        im = ax.contourf(xx, yy, grid_max_signal, levels=20, cmap='RdYlGn', alpha=0.8, vmin=0, vmax=100)
        
        # Draw rooms
        for room_name, room in self.rooms.items():
            rect = patches.Rectangle(
                (room['x'], room['y']), room['width'], room['height'],
                linewidth=2, edgecolor='black', facecolor='none'
            )
            ax.add_patch(rect)
        
        ax.set_xlim(0, self.house_width)
        ax.set_ylim(0, self.house_length)
        ax.set_xlabel('X (meters)')
        ax.set_ylabel('Y (meters)')
        ax.set_title('Maximum WiFi Signal Strength', fontsize=14, weight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        plt.colorbar(im, ax=ax, label='Signal %')
    
    def _create_ap_density_heatmap(self, ax):
        """Create AP density heatmap."""
        x_grid = np.arange(0, self.house_width, Config.GRID_RESOLUTION)
        y_grid = np.arange(0, self.house_length, Config.GRID_RESOLUTION)
        xx, yy = np.meshgrid(x_grid, y_grid)
        
        grid_ap_count = np.zeros_like(xx)
        
        for ap_key, data in self.ap_data.items():
            # Filter data with coordinates
            data_with_coords = [d for d in data if d.get('location') is not None]
            if len(data_with_coords) < 3:
                continue
            
            points = np.array([(d['location']['x'], d['location']['y']) for d in data_with_coords])
            values = np.array([d['signal'] for d in data_with_coords])
            
            grid_signal = self._interpolate_grid(xx, yy, points, values)
            grid_ap_count += (grid_signal > 20).astype(int)
        
        im = ax.contourf(xx, yy, grid_ap_count, levels=10, cmap='YlOrRd', alpha=0.8)
        
        # Draw rooms
        for room_name, room in self.rooms.items():
            rect = patches.Rectangle(
                (room['x'], room['y']), room['width'], room['height'],
                linewidth=2, edgecolor='black', facecolor='none'
            )
            ax.add_patch(rect)
        
        ax.set_xlim(0, self.house_width)
        ax.set_ylim(0, self.house_length)
        ax.set_xlabel('X (meters)')
        ax.set_ylabel('Y (meters)')
        ax.set_title('WiFi AP Density', fontsize=14, weight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        plt.colorbar(im, ax=ax, label='Number of APs')
    
    def _create_best_performance_heatmap(self, ax):
        """Create heatmap showing best performing AP at each location."""
        x_grid = np.arange(0, self.house_width, Config.GRID_RESOLUTION)
        y_grid = np.arange(0, self.house_length, Config.GRID_RESOLUTION)
        xx, yy = np.meshgrid(x_grid, y_grid)
        
        # Calculate performance scores for each AP
        grid_best_score = np.zeros_like(xx)
        grid_best_ap = np.empty_like(xx, dtype=object)
        
        for ap_key in self.ap_data.keys():
            if ap_key not in self.network_test_results:
                continue
            
            test_results = self.network_test_results[ap_key]
            if not test_results:
                continue
            
            # Calculate average performance
            perf_scores = []
            for result in test_results:
                tests = result.get('tests', {})
                score = 0
                
                if 'ping' in tests and tests['ping']['success']:
                    score += max(0, 100 - tests['ping']['avg_time']) * 0.3
                
                if 'speedtest' in tests and tests['speedtest']['success']:
                    score += min(100, tests['speedtest']['download_mbps']) * 0.7
                
                if score > 0:
                    perf_scores.append(score)
            
            if perf_scores:
                avg_score = np.mean(perf_scores)
                
                # Update grid with best performer
                for i in range(xx.shape[0]):
                    for j in range(xx.shape[1]):
                        if avg_score > grid_best_score[i, j]:
                            grid_best_score[i, j] = avg_score
                            grid_best_ap[i, j] = ap_key.split('_')[0]
        
        im = ax.contourf(xx, yy, grid_best_score, levels=20, cmap='RdYlGn', alpha=0.8, vmin=0, vmax=100)
        
        # Draw rooms
        for room_name, room in self.rooms.items():
            rect = patches.Rectangle(
                (room['x'], room['y']), room['width'], room['height'],
                linewidth=2, edgecolor='black', facecolor='none'
            )
            ax.add_patch(rect)
        
        ax.set_xlim(0, self.house_width)
        ax.set_ylim(0, self.house_length)
        ax.set_xlabel('X (meters)')
        ax.set_ylabel('Y (meters)')
        ax.set_title('Best Performance Score', fontsize=14, weight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        plt.colorbar(im, ax=ax, label='Performance Score')
    
    def _create_channel_distribution_map(self, ax):
        """Create channel conflict visualization."""
        # Analyze channel usage
        channel_usage = defaultdict(list)
        
        for measurement in self.measurements:
            for network in measurement['networks']:
                channel = network.get('channel', 0)
                if channel > 0:
                    channel_usage[channel].append({
                        'location': measurement['location'],
                        'signal': network['signal'],
                        'ssid': network['ssid']
                    })
        
        # Find most congested channels
        congested_channels = sorted(channel_usage.items(), 
                                  key=lambda x: len(x[1]), 
                                  reverse=True)[:3]
        
        # Visualize congestion
        x_grid = np.arange(0, self.house_width, Config.GRID_RESOLUTION)
        y_grid = np.arange(0, self.house_length, Config.GRID_RESOLUTION)
        xx, yy = np.meshgrid(x_grid, y_grid)
        
        grid_congestion = np.zeros_like(xx)
        
        for channel, usage_list in congested_channels:
            # Filter usage with locations
            usage_with_coords = [u for u in usage_list if u['location'] is not None]
            if len(usage_with_coords) < 3:
                continue
            
            points = np.array([(u['location']['x'], u['location']['y']) for u in usage_with_coords])
            values = np.array([len(usage_list) for _ in usage_with_coords])
            
            grid_channel = self._interpolate_grid(xx, yy, points, values)
            grid_congestion += grid_channel
        
        im = ax.contourf(xx, yy, grid_congestion, levels=10, cmap='Reds', alpha=0.8)
        
        # Draw rooms
        for room_name, room in self.rooms.items():
            rect = patches.Rectangle(
                (room['x'], room['y']), room['width'], room['height'],
                linewidth=2, edgecolor='black', facecolor='none'
            )
            ax.add_patch(rect)
        
        # Add text showing top channels
        text = "Top Channels:\n"
        for ch, usage in congested_channels[:5]:
            text += f"Ch {ch}: {len(usage)} APs\n"
        
        ax.text(0.02, 0.98, text, transform=ax.transAxes, 
               verticalalignment='top', fontsize=10,
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        ax.set_xlim(0, self.house_width)
        ax.set_ylim(0, self.house_length)
        ax.set_xlabel('X (meters)')
        ax.set_ylabel('Y (meters)')
        ax.set_title('Channel Congestion', fontsize=14, weight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        plt.colorbar(im, ax=ax, label='Congestion Level')
    
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
    
    def get_statistics(self):
        """Get comprehensive statistics."""
        stats = {
            'total_measurements': len(self.measurements),
            'total_aps': len(self.ap_data),
            'tested_networks': len(self.network_test_results),
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
            
            # Add test results if available
            if ap_key in self.network_test_results:
                test_results = self.network_test_results[ap_key]
                ap_stats['tests_performed'] = len(test_results)
                
                # Calculate average test results
                ping_times = []
                download_speeds = []
                upload_speeds = []
                
                for result in test_results:
                    tests = result.get('tests', {})
                    
                    if 'ping' in tests and tests['ping']['success']:
                        ping_times.append(tests['ping']['avg_time'])
                        stats['test_summary']['total_ping_tests'] += 1
                    
                    if 'speedtest' in tests and tests['speedtest']['success']:
                        download_speeds.append(tests['speedtest']['download_mbps'])
                        upload_speeds.append(tests['speedtest']['upload_mbps'])
                        stats['test_summary']['total_speed_tests'] += 1
                    
                    if 'iperf' in tests and tests['iperf']['success']:
                        stats['test_summary']['avg_throughput'].append(tests['iperf']['throughput_mbps'])
                        stats['test_summary']['total_iperf_tests'] += 1
                
                if ping_times:
                    ap_stats['avg_ping'] = np.mean(ping_times)
                    stats['test_summary']['avg_ping'].extend(ping_times)
                
                if download_speeds:
                    ap_stats['avg_download'] = np.mean(download_speeds)
                    ap_stats['avg_upload'] = np.mean(upload_speeds)
                    stats['test_summary']['avg_download'].extend(download_speeds)
                    stats['test_summary']['avg_upload'].extend(upload_speeds)
            
            stats['ap_details'].append(ap_stats)
        
        # Sort by average signal
        stats['ap_details'].sort(key=lambda x: x['avg_signal'], reverse=True)
        
        # Calculate test summary averages
        if stats['test_summary']['avg_ping']:
            stats['test_summary']['avg_ping'] = np.mean(stats['test_summary']['avg_ping'])
        else:
            stats['test_summary']['avg_ping'] = None
            
        if stats['test_summary']['avg_download']:
            stats['test_summary']['avg_download'] = np.mean(stats['test_summary']['avg_download'])
            stats['test_summary']['avg_upload'] = np.mean(stats['test_summary']['avg_upload'])
        else:
            stats['test_summary']['avg_download'] = None
            stats['test_summary']['avg_upload'] = None
            
        if stats['test_summary']['avg_throughput']:
            stats['test_summary']['avg_throughput'] = np.mean(stats['test_summary']['avg_throughput'])
        else:
            stats['test_summary']['avg_throughput'] = None
        
        return stats
    
    def show_current_snr(manager):
        """Mostrar SNR de la conexión actual."""
        scanner = manager.scanner
        current = scanner.get_current_connection_snr()
        
        if 'error' not in current and 'ssid' in current:
            print(f"\n📡 CONEXIÓN ACTUAL - {current.get('ssid', 'Unknown')}")
            print(f"   Signal: {current.get('signal_percentage', 'N/A')}% ({current.get('signal_dbm', 'N/A'):.1f} dBm)")
            print(f"   SNR: {current.get('snr_db', 'N/A'):.1f} dB")
            print(f"   Calidad: {current.get('signal_quality', 'Unknown')}")
            print(f"   Ruido estimado: {current.get('noise_dbm', 'N/A')} dBm")
        else:
            print("No conectado a WiFi")

class EthernetTester:
    """Tester para conexiones cableadas Gigabit."""
    
    @staticmethod
    def get_ethernet_interfaces():
        """Obtener interfaces Ethernet disponibles."""
        try:
            result = subprocess.run(
                ["netsh", "interface", "show", "interface"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            ethernet_interfaces = []
            for line in result.stdout.splitlines():
                if "ethernet" in line.lower() or "local" in line.lower():
                    # Parse interface info
                    parts = line.split()
                    if len(parts) >= 4 and ("conectado" in line.lower() or "connected" in line.lower()):
                        ethernet_interfaces.append({
                            "name": " ".join(parts[3:]),
                            "status": "connected",
                            "type": "ethernet"
                        })
            
            return ethernet_interfaces
            
        except Exception as e:
            print(f"Error getting ethernet interfaces: {e}")
            return []
    
    @staticmethod
    def test_ethernet_speed(interface_name="Ethernet", server="iperf.he.net", duration=10):
        """Test de velocidad en conexión cableada."""
        print(f"\n🌐 TESTING ETHERNET CONNECTION: {interface_name}")
        print("=" * 60)
        
        # Información de la interfaz
        try:
            result = subprocess.run(
                ["netsh", "interface", "ip", "show", "config", interface_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("📋 Interface Information:")
                for line in result.stdout.splitlines()[:10]:
                    if line.strip():
                        print(f"   {line.strip()}")
            
        except Exception as e:
            print(f"⚠️ Could not get interface info: {e}")
        
        # Test de velocidad con iPerf
        print(f"\n🚀 Running Gigabit Speed Test...")
        print(f"   Server: {server}")
        print(f"   Duration: {duration} seconds")
        print("   " + "="*50)
        
        try:
            # TCP test con salida en tiempo real
            process = subprocess.Popen(
                ["C:\\iperf3\\iperf3.exe\\iperf3.exe", "-c", server, "-t", str(duration), "-i", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            tcp_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(f"   {output.strip()}")
                    tcp_lines.append(output)
            
            process.wait(timeout=duration + 10)
            
            # Test UDP a 1 Gbps
            print(f"\n🔄 Running UDP Test at 1 Gbps...")
            print("   " + "="*50)
            
            udp_process = subprocess.Popen(
                ["C:\\iperf3\\iperf3.exe\\iperf3.exe", "-c", server, "-u", "-b", "1G", "-t", str(duration), "-i", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            while True:
                output = udp_process.stdout.readline()
                if output == '' and udp_process.poll() is not None:
                    break
                if output:
                    print(f"   {output.strip()}")
            
            udp_process.wait(timeout=duration + 10)
            
            return {"success": True, "raw_output": "".join(tcp_lines)}
            
        except Exception as e:
            print(f"❌ Error durante test Ethernet: {e}")
            return {"success": False, "error": str(e)}




# Main execution function
def main():
    """Main entry point for the integrated system."""
    print("🏠 INTEGRATED WIFI ANALYSIS & HEATMAP SYSTEM")
    print("=" * 60)
    
    # Initialize manager
    manager = HeatmapManager()
    
    # Configure iPerf server
    print("\n📡 IPERF SERVER CONFIGURATION")
    print("Default server: iperf.he.net (public server)")
    custom_server = input("Enter iPerf server IP (press Enter for default): ").strip()
    if custom_server:
        manager.tester.set_iperf_server(custom_server)
    else:
        print("✓ Using default public server: iperf.he.net")
    
    # Ask about local server only if needed
    if custom_server == "127.0.0.1" or custom_server == "localhost":
        if not manager.tester.check_iperf_server():
            print("\n⚠️  Local iPerf3 server not running.")
            if input("Start local iPerf3 server? (y/n): ").lower() == 'y':
                manager.tester.start_iperf_server()
    
    # Setup rooms if needed
    if not manager.rooms:
        print("\nNo rooms defined. Using default layout...")
        manager.setup_default_layout()
        manager.save_data()
    
    # Main menu
    while True:
        print("\n" + "="*60)
        print("MAIN MENU")
        print("="*60)
        print("1. Collect measurement by ID (field mode)")
        print("2. Collect measurement with coordinates")
        print("3. Map IDs to coordinates")
        print("4. Test all networks by ID (field mode)")
        print("5. Auto-collect measurements")
        print("6. Generate individual AP heatmaps")
        print("7. Generate composite heatmap")
        print("8. View statistics")
        print("9. Continuous monitoring")
        print("10. Network diagnostics")
        print("11. Change iPerf server")
        print("12. Ethernet Test")
        print("0. Exit")
        print("="*60)
        
        choice = input("Select option: ").strip()
        
        if choice == "0":
            print("Goodbye!")
            break
            
        elif choice == "1":
            # Field mode - use ID

                manager.collect_measurement_by_id()
                
        elif choice == "2":
            # Original mode with coordinates
            try:
                coords = input("Enter x,y coordinates (e.g., 5.5,3.2): ").strip()
                x, y = map(float, coords.split(','))
                manager.collect_measurement_with_tests(x, y)
            except Exception as e:
                print(f"Error: {e}")
                
        elif choice == "3":
            # Map IDs to coordinates
            manager.batch_map_coordinates()
                
        elif choice == "4":
            # Test all networks by ID
                manager.test_all_networks_by_id()
                
        elif choice == "5":
            auto_collect(manager)
            
        elif choice == "6":
            for ap_key in manager.ap_data.keys():
                try:
                    manager.create_ap_heatmap(ap_key)
                except Exception as e:
                    print(f"Error creating heatmap for {ap_key}: {e}")
            
        elif choice == "7":
            manager.create_composite_heatmap()
            
        elif choice == "8":
            show_statistics(manager)
            
        elif choice == "9":
            continuous_monitoring(manager)
            
        elif choice == "10":
            network_diagnostics(manager)
            
        elif choice == "11":
            new_server = input("Enter new iPerf server IP: ").strip()
            if new_server:
                manager.tester.set_iperf_server(new_server)
        
        elif choice =="12":
            ethernet_diagnostics()


def ethernet_diagnostics():
    """Diagnósticos de red cableada."""
    print("\n🌐 ETHERNET DIAGNOSTICS")
    print("-" * 40)
    
    # Encontrar interfaces Ethernet
    interfaces = EthernetTester.get_ethernet_interfaces()
    
    if not interfaces:
        print("❌ No se encontraron interfaces Ethernet conectadas")
        return
    
    print("📋 Interfaces Ethernet encontradas:")
    for i, iface in enumerate(interfaces):
        print(f"   {i+1}. {iface['name']} ({iface['status']})")
    
    # Seleccionar interfaz
    if len(interfaces) == 1:
        selected = interfaces[0]
        print(f"\n✅ Usando interfaz: {selected['name']}")
    else:
        try:
            choice = int(input(f"\nSeleccionar interfaz (1-{len(interfaces)}): ")) - 1
            selected = interfaces[choice]
        except:
            print("❌ Selección inválida")
            return
    
    # Ejecutar test
    server = input("Servidor iPerf (Enter para iperf.he.net): ").strip() or "iperf.he.net"
    duration = int(input("Duración en segundos (Enter para 10): ").strip() or "10")
    
    EthernetTester.test_ethernet_speed(selected['name'], server, duration)

def auto_collect(manager):
    """Automated measurement collection."""
    try:
        num = int(input("Number of measurements: "))
        interval = float(input("Interval (seconds): ") or 30)
        run_tests = input("Run network tests? (y/n): ").lower() == 'y'
        
        print(f"\nCollecting {num} measurements...")
        for i in range(num):
            x = np.random.uniform(0, manager.house_width)
            y = np.random.uniform(0, manager.house_length)
            
            print(f"\n[{i+1}/{num}] Position: ({x:.1f}, {y:.1f})")
            manager.collect_measurement_with_tests(x, y, run_tests=run_tests)
            
            if i < num - 1:
                time.sleep(interval)
                
    except KeyboardInterrupt:
        print("\nStopped by user")


def continuous_monitoring(manager):
    """Continuous monitoring mode."""
    print("\nCONTINUOUS MONITORING MODE")
    print("Choose mode:")
    print("1. Random positions (original)")
    print("2. Fixed ID increments (field mode)")
    
    mode = input("Select mode (1 or 2): ").strip()
    
    if mode == "2":
        # Field mode with IDs
        print("\n- Measurements with auto-incrementing IDs")
        print("- Remember to map IDs to coordinates later")
        print("\nPress Ctrl+C to stop")
        
        measurement_count = 0
        
        try:
            while True:
                manager.collect_measurement_by_id(run_tests=False)
                measurement_count += 1
                
                # Periodic network test
                if measurement_count % 10 == 0:
                    print("\n🔄 Running network test...")
                    current_conn = manager.scanner.get_current_connection_info()
                    if 'ssid' in current_conn and 'error' not in current_conn:
                        # Run basic test
                        ping = manager.tester.run_ping()
                        if ping['success']:
                            print(f"✓ Ping: {ping['avg_time']:.1f}ms")
                
                time.sleep(30)
                
        except KeyboardInterrupt:
            print(f"\nMonitoring stopped. Total measurements: {measurement_count}")
            print("Remember to map IDs to coordinates using option 3!")
    
    else:
        # Original mode
        print("\n- Measurements every 30 seconds at random positions")
        print("- Test all networks every 5 minutes")
        print("- Update heatmaps every 10 minutes")
        print("\nPress Ctrl+C to stop")
        
        measurement_count = 0
        last_test_time = time.time()
        last_heatmap_time = time.time()
        
        try:
            while True:
                # Random position
                x = np.random.uniform(0, manager.house_width)
                y = np.random.uniform(0, manager.house_length)
                
                # Basic measurement
                manager.collect_measurement_with_tests(x, y, run_tests=False)
                measurement_count += 1
                
                # Test all networks every 5 minutes
                if time.time() - last_test_time > 300:
                    print("\n🔄 Testing all networks...")
                    manager.test_all_networks(x, y)
                    last_test_time = time.time()
                
                # Update heatmaps every 10 minutes
                if time.time() - last_heatmap_time > 600:
                    print("\n📊 Updating heatmaps...")
                    manager.create_composite_heatmap()
                    last_heatmap_time = time.time()
                
                time.sleep(30)
                
        except KeyboardInterrupt:
            print(f"\nMonitoring stopped. Total measurements: {measurement_count}")


def network_diagnostics(manager):
    """Run network diagnostics."""
    print("\nNETWORK DIAGNOSTICS")
    print("-" * 40)
    
    # Current connection
    current = manager.scanner.get_current_connection_info()
    
    if 'error' in current:
        print(f"⚠️  {current['error']}")
        print("\nPossible issues:")
        print("- Not connected to WiFi")
        print("- Need to run as Administrator")
        print("- WiFi adapter disabled")
        return
    
    if 'ssid' in current:
        print(f"Connected to: {current['ssid']}")
        print(f"Signal: {current.get('signal_percentage', 'N/A')}%")
        print(f"Channel: {current.get('channel', 'N/A')}")
        
        print("\nRunning tests...")
        
        # Ping
        ping = manager.tester.run_ping()
        if ping['success']:
            print(f"✓ Ping: {ping['avg_time']:.1f}ms (min: {ping['min_time']}, max: {ping['max_time']})")
        else:
            print(f"✗ Ping: {ping['error']}")
        
        # Traceroute
        if input("\nRun traceroute? (y/n): ").lower() == 'y':
            trace = manager.tester.run_traceroute()
            if trace['success']:
                print(f"✓ Traceroute: {trace['total_hops']} hops")
                for hop in trace['hops'][:10]:  # Show first 10 hops
                    print(f"   {hop['hop']}: {hop['info']}")
            else:
                print(f"✗ Traceroute: {trace['error']}")
        
        # Speedtest
        if input("\nRun speedtest? (y/n): ").lower() == 'y':
            speed = manager.tester.run_speedtest()
            if speed['success']:
                print(f"✓ Speedtest:")
                print(f"   Download: {speed['download_mbps']:.1f} Mbps")
                print(f"   Upload: {speed['upload_mbps']:.1f} Mbps")
                print(f"   Ping: {speed['ping_ms']:.1f} ms")
                print(f"   Server: {speed['server']}")
            else:
                print(f"✗ Speedtest: {speed['error']}")
        
        # iPerf
        if input("    Run iPerf test suite? (y/n): ").lower() == 'y':
            iperf_result = manager.tester.run_iperf_suite()
            if iperf_result['success']:
                print(f"✓ iPerf Test Suite:")
                print(f"   Throughput: {iperf_result['throughput_mbps']:.1f} Mbps")
                print(f"   Jitter: {iperf_result['jitter_ms']:.2f} ms")
                print(f"   Loss: {iperf_result['loss_percentage']:.2f}%")
            else:
                print(f"    ✗ iPerf: {iperf_result['error']}")


def show_statistics(manager):
    """Display comprehensive statistics."""
    stats = manager.get_statistics()
    
    print("\n" + "="*70)
    print("SYSTEM STATISTICS")
    print("="*70)
    print(f"Total measurements: {stats['total_measurements']}")
    print(f"Total APs tracked: {stats['total_aps']}")
    print(f"Networks tested: {stats['tested_networks']}")
    
    print("\n📊 TEST SUMMARY:")
    print(f"Ping tests: {stats['test_summary']['total_ping_tests']}")
    if stats['test_summary']['avg_ping']:
        print(f"  Average: {stats['test_summary']['avg_ping']:.1f} ms")
    
    print(f"Speed tests: {stats['test_summary']['total_speed_tests']}")
    if stats['test_summary']['avg_download']:
        print(f"  Avg Download: {stats['test_summary']['avg_download']:.1f} Mbps")
        print(f"  Avg Upload: {stats['test_summary']['avg_upload']:.1f} Mbps")
    
    print(f"iPerf tests: {stats['test_summary']['total_iperf_tests']}")
    if stats['test_summary']['avg_throughput']:
        print(f"  Avg Throughput: {stats['test_summary']['avg_throughput']:.1f} Mbps")
    
    print("\n📡 TOP ACCESS POINTS:")
    print("-"*70)
    print(f"{'SSID':<25} {'BSSID':<20} {'Avg Signal':<12} {'Tests':<8} {'Avg Ping':<10}")
    print("-"*70)
    
    for ap in stats['ap_details'][:10]:
        ssid = ap['name'][:24]
        bssid = ap['bssid'][:19]
        avg_ping = f"{ap.get('avg_ping', 0):.1f} ms" if 'avg_ping' in ap else "N/A"
        tests = ap.get('tests_performed', 0)
        
        print(f"{ssid:<25} {bssid:<20} {ap['avg_signal']:>10.1f}% {tests:>8} {avg_ping:>10}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()