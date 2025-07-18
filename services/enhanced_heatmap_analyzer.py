import folium
import json
import statistics
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from folium.plugins import HeatMap
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from pathlib import Path
import math

class PreciseLocationService:
    """Service for precise GPS location tracking with meter-level accuracy."""
    
    def __init__(self):
        self.location_cache = {}
        self.ap_locations = {}
        self.measurement_points = []
        
    def get_current_location(self, method='gps') -> Optional[Tuple[float, float]]:
        """Get current precise location using multiple methods."""
        try:
            # In a real implementation, you would use GPS libraries like:
            # - gpsd for Linux
            # - CoreLocation for iOS
            # - Android Location Services
            
            # For now, we'll simulate high-precision GPS
            # You should replace this with actual GPS code
            import random
            
            # Simulate movement within a small area (few meters precision)
            base_lat = -34.9011  # Montevideo base
            base_lon = -56.1645
            
            # Add small random variations (±0.0001 degrees ≈ ±11 meters)
            lat_offset = random.uniform(-0.0001, 0.0001)
            lon_offset = random.uniform(-0.0001, 0.0001)
            
            return (base_lat + lat_offset, base_lon + lon_offset)
            
        except Exception as e:
            print(f"Error getting location: {e}")
            return None
    
    def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """Calculate distance between two coordinates in meters."""
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        
        # Haversine formula for precise distance calculation
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def save_measurement_point(self, location: Tuple[float, float], wifi_data: Dict):
        """Save a measurement point with location and WiFi data."""
        measurement = {
            'timestamp': datetime.now().isoformat(),
            'location': location,
            'wifi_data': wifi_data,
            'measurement_id': len(self.measurement_points)
        }
        self.measurement_points.append(measurement)
        return measurement['measurement_id']
    
    def get_nearby_measurements(self, location: Tuple[float, float], radius_meters: float = 10) -> List[Dict]:
        """Get all measurements within a specified radius."""
        nearby = []
        for measurement in self.measurement_points:
            distance = self.calculate_distance(location, measurement['location'])
            if distance <= radius_meters:
                measurement['distance'] = distance
                nearby.append(measurement)
        return nearby

class EnhancedWiFiHeatmapAnalyzer:
    """Enhanced WiFi heatmap analyzer with precise location tracking."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.location_service = PreciseLocationService()
        self.measurement_grid = {}
        
    def collect_measurement_at_location(self, wifi_networks: List[Dict]) -> Dict:
        """Collect WiFi measurement at current precise location."""
        current_location = self.location_service.get_current_location()
        if not current_location:
            raise Exception("Could not get current location")
        
        # Process WiFi data
        processed_data = {
            'timestamp': datetime.now().isoformat(),
            'location': current_location,
            'networks': {}
        }
        
        for network in wifi_networks:
            ssid = network.get('ssid', 'Unknown')
            bssid = network.get('bssid', 'Unknown')
            
            network_data = {
                'signal_strength': network.get('signal_percentage', 0),
                'frequency': network.get('frequency', 0),
                'channel': network.get('channel', 0),
                'security': network.get('authentication', 'Unknown'),
                'bssid': bssid
            }
            
            processed_data['networks'][f"{ssid}_{bssid}"] = network_data
        
        # Save measurement
        measurement_id = self.location_service.save_measurement_point(current_location, processed_data)
        
        print(f"📍 Measurement {measurement_id} saved at {current_location}")
        print(f"   Found {len(wifi_networks)} networks")
        
        return processed_data
    
    def create_precision_heatmap(self, network_name: str, output_file: str = "precision_heatmap.html") -> str:
        """Create a high-precision heatmap for a specific network."""
        measurements = self.location_service.measurement_points
        
        if not measurements:
            raise Exception("No measurements available. Collect some data first!")
        
        # Filter measurements for the specific network
        network_measurements = []
        for measurement in measurements:
            wifi_data = measurement['wifi_data']
            for net_key, net_data in wifi_data.get('networks', {}).items():
                if network_name in net_key:
                    network_measurements.append({
                        'location': measurement['location'],
                        'signal': net_data['signal_strength'],
                        'timestamp': measurement['timestamp']
                    })
        
        if not network_measurements:
            raise Exception(f"No measurements found for network: {network_name}")
        
        # Calculate center location
        center_lat = sum(m['location'][0] for m in network_measurements) / len(network_measurements)
        center_lon = sum(m['location'][1] for m in network_measurements) / len(network_measurements)
        
        # Create high-precision map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=20,  # Maximum zoom for precision
            tiles='OpenStreetMap'
        )
        
        # Add satellite imagery for better reference
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google Satellite',
            name='Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Prepare heatmap data
        heat_data = []
        for measurement in network_measurements:
            lat, lon = measurement['location']
            signal = measurement['signal']
            # Normalize signal strength for better visualization
            normalized_signal = signal / 100.0
            heat_data.append([lat, lon, normalized_signal])
        
        # Add heatmap layer
        HeatMap(
            heat_data,
            radius=15,  # Smaller radius for precision
            blur=10,    # Less blur for sharper definition
            gradient={
                0.0: 'red',
                0.3: 'orange', 
                0.6: 'yellow',
                0.8: 'lightgreen',
                1.0: 'green'
            },
            min_opacity=0.4,
            max_zoom=20
        ).add_to(m)
        
        # Add measurement points as markers
        for i, measurement in enumerate(network_measurements):
            lat, lon = measurement['location']
            signal = measurement['signal']
            
            # Color based on signal strength
            if signal >= 80:
                color = 'green'
            elif signal >= 60:
                color = 'orange'
            else:
                color = 'red'
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=8,
                popup=f"""
                <b>Measurement {i+1}</b><br>
                Network: {network_name}<br>
                Signal: {signal}%<br>
                Time: {measurement['timestamp'][:19]}<br>
                Location: {lat:.6f}, {lon:.6f}
                """,
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.8
            ).add_to(m)
        
        # Add measurement path
        if len(network_measurements) > 1:
            path_coords = [m['location'] for m in network_measurements]
            folium.PolyLine(
                locations=path_coords,
                color='blue',
                weight=2,
                opacity=0.7,
                popup="Measurement Path"
            ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Save map
        full_path = self.data_dir / output_file
        m.save(str(full_path))
        
        print(f"🗺️  Precision heatmap saved to: {full_path}")
        print(f"   Network: {network_name}")
        print(f"   Measurements: {len(network_measurements)}")
        
        return str(full_path)
    
    def analyze_signal_variation(self, network_name: str) -> Dict:
        """Analyze how signal varies with location changes."""
        measurements = self.location_service.measurement_points
        
        # Filter for specific network
        network_data = []
        for measurement in measurements:
            wifi_data = measurement['wifi_data']
            for net_key, net_data in wifi_data.get('networks', {}).items():
                if network_name in net_key:
                    network_data.append({
                        'location': measurement['location'],
                        'signal': net_data['signal_strength'],
                        'timestamp': measurement['timestamp']
                    })
        
        if len(network_data) < 2:
            return {"error": "Need at least 2 measurements for analysis"}
        
        # Calculate signal variations
        analysis = {
            'network_name': network_name,
            'total_measurements': len(network_data),
            'signal_stats': {
                'min': min(d['signal'] for d in network_data),
                'max': max(d['signal'] for d in network_data),
                'avg': statistics.mean(d['signal'] for d in network_data),
                'std_dev': statistics.stdev(d['signal'] for d in network_data) if len(network_data) > 1 else 0
            },
            'distance_analysis': [],
            'signal_gradient': []
        }
        
        # Analyze signal vs distance
        for i in range(len(network_data) - 1):
            for j in range(i + 1, len(network_data)):
                point1 = network_data[i]
                point2 = network_data[j]
                
                distance = self.location_service.calculate_distance(
                    point1['location'], point2['location']
                )
                
                signal_diff = abs(point1['signal'] - point2['signal'])
                
                if distance > 0:
                    gradient = signal_diff / distance  # Signal change per meter
                    analysis['distance_analysis'].append({
                        'distance_meters': round(distance, 2),
                        'signal_difference': round(signal_diff, 2),
                        'gradient_per_meter': round(gradient, 4)
                    })
        
        # Calculate average gradient
        if analysis['distance_analysis']:
            avg_gradient = statistics.mean(d['gradient_per_meter'] for d in analysis['distance_analysis'])
            analysis['avg_signal_gradient'] = round(avg_gradient, 4)
        
        return analysis
    
    def create_measurement_grid(self, center_location: Tuple[float, float], 
                              grid_size_meters: int = 5, grid_points: int = 10) -> List[Tuple[float, float]]:
        """Create a grid of measurement points for systematic coverage."""
        lat_center, lon_center = center_location
        
        # Convert meters to degrees (approximate)
        lat_per_meter = 1 / 111320  # degrees latitude per meter
        lon_per_meter = 1 / (111320 * math.cos(math.radians(lat_center)))  # degrees longitude per meter
        
        grid_coords = []
        half_points = grid_points // 2
        
        for i in range(-half_points, half_points + 1):
            for j in range(-half_points, half_points + 1):
                lat_offset = i * grid_size_meters * lat_per_meter
                lon_offset = j * grid_size_meters * lon_per_meter
                
                new_lat = lat_center + lat_offset
                new_lon = lon_center + lon_offset
                
                grid_coords.append((new_lat, new_lon))
        
        return grid_coords
    
    def export_measurement_data(self, filename: str = "wifi_measurements.json"):
        """Export all measurement data to JSON file."""
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'total_measurements': len(self.location_service.measurement_points),
            'measurements': self.location_service.measurement_points
        }
        
        file_path = self.data_dir / filename
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"📊 Measurement data exported to: {file_path}")
        return str(file_path)
    
    def import_measurement_data(self, filename: str):
        """Import measurement data from JSON file."""
        file_path = self.data_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        self.location_service.measurement_points = data.get('measurements', [])
        
        print(f"📥 Imported {len(self.location_service.measurement_points)} measurements")
        return len(self.location_service.measurement_points)

# Usage Example
if __name__ == "__main__":
    # Create analyzer instance
    analyzer = EnhancedWiFiHeatmapAnalyzer()
    
    # Example: Simulate collecting measurements
    print("🔍 Starting WiFi heatmap collection...")
    
    # Simulate WiFi networks data (replace with actual WiFi scanning)
    sample_networks = [
        {
            'ssid': 'MyWiFi_5G',
            'bssid': 'AA:BB:CC:DD:EE:FF',
            'signal_percentage': 85,
            'channel': 36,
            'frequency': 5180,
            'authentication': 'WPA2'
        },
        {
            'ssid': 'NeighborWiFi',
            'bssid': 'FF:EE:DD:CC:BB:AA',
            'signal_percentage': 45,
            'channel': 6,
            'frequency': 2437,
            'authentication': 'WPA2'
        }
    ]
    
    # Collect measurements at different locations
    # In practice, you would move around and call this function
    for i in range(10):
        try:
            measurement = analyzer.collect_measurement_at_location(sample_networks)
            print(f"✅ Collected measurement {i+1}")
        except Exception as e:
            print(f"❌ Error collecting measurement {i+1}: {e}")
    
    # Create precision heatmap
    try:
        heatmap_file = analyzer.create_precision_heatmap('MyWiFi_5G')
        print(f"🎯 Precision heatmap created: {heatmap_file}")
    except Exception as e:
        print(f"❌ Error creating heatmap: {e}")
    
    # Analyze signal variation
    try:
        analysis = analyzer.analyze_signal_variation('MyWiFi_5G')
        print(f"📈 Signal variation analysis:")
        print(f"   Signal range: {analysis['signal_stats']['min']}% - {analysis['signal_stats']['max']}%")
        print(f"   Average signal: {analysis['signal_stats']['avg']:.1f}%")
        print(f"   Standard deviation: {analysis['signal_stats']['std_dev']:.1f}%")
        if 'avg_signal_gradient' in analysis:
            print(f"   Average gradient: {analysis['avg_signal_gradient']:.4f}% per meter")
    except Exception as e:
        print(f"❌ Error analyzing signal variation: {e}")
    
    # Export data
    try:
        export_file = analyzer.export_measurement_data()
        print(f"💾 Data exported to: {export_file}")
    except Exception as e:
        print(f"❌ Error exporting data: {e}")