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
    IPERF_SERVER = "127.0.0.1"
    
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

class NetworkTester:
    """Handles all network testing functionality."""
    
    @staticmethod
    def check_iperf_server():
        """Check if iperf3 server is running."""
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
        """Start iperf3 server if not running."""
        if NetworkTester.check_iperf_server():
            print("✓ iperf3 server already running")
            return True
        
        try:
            print("Starting iperf3 server...")
            subprocess.Popen(
                [Config.IPERF_PATH, "-s"], 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            time.sleep(2)
            return NetworkTester.check_iperf_server()
        except Exception as e:
            print(f"Error starting iperf3 server: {e}")
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
    
    @staticmethod
    def run_iperf(server=Config.IPERF_SERVER, duration=10):
        """Run iperf3 test."""
        if not os.path.exists(Config.IPERF_PATH):
            return {"success": False, "error": "iperf3 not found"}
        
        if not NetworkTester.check_iperf_server():
            return {"success": False, "error": "No iperf3 server running"}
        
        try:
            result = subprocess.run(
                [Config.IPERF_PATH, "-c", server, "-J", "-t", str(duration)],
                capture_output=True,
                text=True,
                timeout=duration + 10
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                throughput = data.get("end", {}).get("sum_received", {}).get("bits_per_second", 0)
                
                return {
                    "success": True,
                    "throughput_mbps": throughput / 1_000_000,
                    "duration": duration,
                    "raw_data": data
                }
            else:
                return {"success": False, "error": f"iperf3 failed: {result.stderr}"}
                
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid iperf3 output"}
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
    """Enhanced WiFi scanner with connection capabilities."""
    
    def __init__(self):
        self.last_scan = 0
        self.cached_networks = []
        self.tested_networks = set()
    
    def scan_networks(self, force_refresh=False) -> List[Dict]:
        """Scan all visible WiFi networks."""
        current_time = time.time()
        
        if not force_refresh and (current_time - self.last_scan) < 30:
            return self.cached_networks
        
        try:
            # Force refresh
            subprocess.run(["netsh", "wlan", "refresh"], capture_output=True, timeout=10)
            
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True,
                text=True,
                timeout=20,
                encoding='cp1252'
            )
            
            networks = []
            current_network = {}
            
            for line in result.stdout.splitlines():
                line = line.strip()
                
                if line.startswith("SSID") and ":" in line:
                    if current_network.get("ssid"):
                        networks.append(current_network.copy())
                    
                    ssid = line.split(":", 1)[1].strip()
                    current_network = {
                        "ssid": ssid,
                        "bssid": "Unknown",
                        "signal_percentage": 0,
                        "channel": 0,
                        "authentication": "Unknown",
                        "is_open": False,
                        "is_saved": False,
                        "timestamp": datetime.now().isoformat()
                    }
                
                elif ":" in line and current_network.get("ssid"):
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if "bssid" in key:
                        current_network["bssid"] = value
                    elif any(term in key for term in ["signal", "señal", "senal", "se¤al"]):
                        current_network["signal_strength"] = value
                        # Extraer porcentaje numérico
                        match = re.search(r'(\d+)%', value)
                        if match:
                            current_network["signal_percentage"] = int(match.group(1))
                    

                    elif any(term in key for term in ["channel", "canal"]):
                        match = re.search(r'(\d+)', value)
                        if match:
                            current_network["channel"] = int(match.group(1))
                    elif any(term in key for term in ["authentication", "autenticación"]):
                        current_network["authentication"] = value
                        if "open" in value.lower() or "abierto" in value.lower():
                            current_network["is_open"] = True
            
            if current_network.get("ssid"):
                networks.append(current_network)
            
            # Check which networks are saved
            for network in networks:
                network["is_saved"] = self._is_network_saved(network["ssid"])
            
            self.cached_networks = networks
            self.last_scan = current_time
            
            return networks
            
        except Exception as e:
            print(f"Error scanning networks: {e}")
            return []
    
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
    
    def collect_measurement_with_tests(self, x: float, y: float, room: str = "", run_tests: bool = True):
        """Collect WiFi measurements and optionally run network tests."""
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
                    'signal': network['signal_strength'],
                    'channel': network['channel'],
                    'authentication': network['authentication']
                }
                measurement['networks'].append(net_data)
                
                # Store in AP-specific data
                ap_key = f"{network['ssid']}_{network['bssid']}"
                print(f"  📡 {network['ssid']} ({network['bssid']}) - Signal: {network['signal_percentage']}%")
                self.ap_data[ap_key].append({
                    'location': {'x': x, 'y': y},
                    'signal': network['signal_strength'],
                    'timestamp': datetime.now().isoformat()
                })
        
        # Run network tests if connected
        if run_tests:
            current_conn = self.scanner.get_current_connection_info()
            if 'ssid' in current_conn:
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
                
                # iPerf test (if server available)
                if self.tester.check_iperf_server():
                    iperf_result = self.tester.run_iperf()
                    if iperf_result['success']:
                        measurement['tests']['iperf'] = iperf_result
                        print(f"    iPerf: {iperf_result['throughput_mbps']:.1f} Mbps")
        
        self.measurements.append(measurement)
        self.save_data()
        
        print(f"📍 Measurement collected at ({x:.1f}, {y:.1f}) - {len(networks)} networks")
        return measurement
    
    def test_all_networks(self, x: float, y: float, room: str = ""):
        """Test all available networks at a location."""
        networks = self.scanner.scan_networks(force_refresh=True)
        connectable = [n for n in networks if n['is_open'] or n['is_saved']]
        
        print(f"\n🔄 Testing {len(connectable)} connectable networks at ({x:.1f}, {y:.1f})")
        
        results = []
        for network in connectable:
            ssid = network['ssid']

                
            print(f"\n🔗 Testing: {ssid}")
            print(f"   Signal: {network['signal_percentage']}%")
            
            # Connect
            conn_result = self.scanner.connect_to_network(ssid)
            if not conn_result['success']:
                print(f"   ❌ Connection failed: {conn_result['error']}")
                continue
            
            # Run tests
            test_result = {
                'location': {'x': x, 'y': y},
                'room': room,
                'network': network,
                'timestamp': datetime.now().isoformat(),
                'tests': {}
            }
            
            # Ping
            ping = self.tester.run_ping()
            if ping['success']:
                test_result['tests']['ping'] = ping
                print(f"   Ping: {ping['avg_time']:.1f}ms")
            
            # Speed (quick test)
            if network['signal_percentage'] > 40:  # Only test decent signals
                speed = self.tester.run_speedtest()
                if speed['success']:
                    test_result['tests']['speedtest'] = speed
                    print(f"   Speed: {speed['download_mbps']:.1f}↓/{speed['upload_mbps']:.1f}↑ Mbps")
            
            results.append(test_result)
            self.scanner.tested_networks.add(ssid)

            
            # Store results
            ap_key = f"{network['ssid']}_{network['bssid']}"
            self.network_test_results[ap_key].append(test_result)
             # Store in AP-specific data
            self.ap_data[ap_key].append({
                    'location': {'x': x, 'y': y},
                    'signal': network['signal_strength'],
                    'timestamp': datetime.now().isoformat()
                })
        
        self.save_data()
        return results
    
    def create_ap_heatmap(self, ap_key: str, include_performance: bool = True):
        """Create heatmap for specific AP with optional performance overlay."""
        if ap_key not in self.ap_data:
            print(f"No data found for AP: {ap_key}")
            return None
        
        data = self.ap_data[ap_key]
        data = self._normalize_signal_data(data)  


        if len(data) < 3:
            print(data)
            print(f"Insufficient data points for {ap_key}")
            return None
        
        # Create figure
        fig, axes = plt.subplots(1, 2 if include_performance else 1, figsize=(20 if include_performance else 12, 8))
        if not include_performance:
            axes = [axes]
        
        # Signal strength heatmap
        self._create_signal_heatmap(axes[0], data, ap_key)
        
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
    
    def _normalize_signal_data(self, data: List[Dict]) -> List[Dict]:
        """Convierte '99%' en 99.0 (float) dentro del campo 'signal'."""
        for entry in data:
            signal = entry.get("signal", "")
            if isinstance(signal, str) and signal.endswith("%"):
                try:
                    entry["signal"] = float(signal.strip('%'))
                except ValueError:
                    entry["signal"] = None
            elif isinstance(signal, (int, float)):
                entry["signal"] = float(signal)
            else:
                entry["signal"] = None
        return [d for d in data if d["signal"] is not None]

    
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
        """
        Interpolación suave usando griddata, ideal para visualizar datos reales.
        """
        # Usamos griddata con el método 'cubic' para una interpolación suave.
        # Esto crea una superficie continua y diferenciable que pasa por tus puntos.
        # Es perfecto para representar un campo como la señal WiFi.
        grid = griddata(points, values, (xx, yy), method='cubic')

        # El método 'cubic' puede generar valores fuera del rango original (ej. > 100 o < 0)
        # en los bordes de la interpolación. Los "recortamos" para mantenerlos en el rango 0-100.
        grid = np.clip(grid, 0, 100)
        
        # griddata puede dejar 'NaN' (Not a Number) en áreas fuera del alcance de tus puntos.
        # Rellenamos esos huecos usando una interpolación 'nearest' para que no haya vacíos.
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
            if len(data) < 3:
                continue
            
            points = np.array([(d['location']['x'], d['location']['y']) for d in data])
            values = np.array([d['signal'] for d in data])
            
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
            if len(data) < 3:
                continue
            
            points = np.array([(d['location']['x'], d['location']['y']) for d in data])
            values = np.array([d['signal'] for d in data])
            
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
            if len(usage_list) < 3:
                continue
            
            points = np.array([(u['location']['x'], u['location']['y']) for u in usage_list])
            values = np.array([len(usage_list) for _ in usage_list])
            
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

# Main execution function
def main():
    """Main entry point for the integrated system."""
    print("🏠 INTEGRATED WIFI ANALYSIS & HEATMAP SYSTEM")
    print("=" * 60)
    
    # Initialize manager
    manager = HeatmapManager()
    
    # Check for iperf server
    if not manager.tester.check_iperf_server():
        print("\n⚠️  iPerf3 server not running.")
        if input("Start iPerf3 server? (y/n): ").lower() == 'y':
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
        print("1. Collect measurement with tests")
        print("2. Test all networks at location")
        print("3. Auto-collect measurements")
        print("4. Generate individual AP heatmaps")
        print("5. Generate composite heatmap")
        print("6. View statistics")
        print("7. Continuous monitoring")
        print("8. Network diagnostics")
        print("0. Exit")
        print("="*60)
        
        choice = input("Select option: ").strip()
        
        if choice == "0":
            print("Goodbye!")
            break
            
        elif choice == "1":
            try:
                coords = input("Enter x,y coordinates (e.g., 5.5,3.2): ").strip()
                x, y = map(float, coords.split(','))
                manager.collect_measurement_with_tests(x, y)
            except Exception as e:
                print(f"Error: {e}")
                
        elif choice == "2":
            try:
                coords = input("Enter x,y coordinates (e.g., 5.5,3.2): ").strip()
                x, y = map(float, coords.split(','))
                manager.test_all_networks(x, y)
            except Exception as e:
                print(f"Error: {e}")
                
        elif choice == "3":
            auto_collect(manager)
            
        elif choice == "4":
            for ap_key in manager.ap_data.keys():
                try:
                    manager.create_ap_heatmap(ap_key)
                except Exception as e:
                    print(f"Error creating heatmap for {ap_key}: {e}")
            
        elif choice == "5":
            manager.create_composite_heatmap()
            
        elif choice == "6":
            show_statistics(manager)
            
        elif choice == "7":
            continuous_monitoring(manager)
            
        elif choice == "8":
            network_diagnostics(manager)

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
    print("- Measurements every 30 seconds")
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
        if manager.tester.check_iperf_server():
            if input("\nRun iPerf test? (y/n): ").lower() == 'y':
                iperf = manager.tester.run_iperf()
                if iperf['success']:
                    print(f"✓ iPerf: {iperf['throughput_mbps']:.1f} Mbps")
                else:
                    print(f"✗ iPerf: {iperf['error']}")
    else:
        print("Not connected to any WiFi network")

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