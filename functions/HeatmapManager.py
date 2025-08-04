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