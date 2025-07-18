import folium
import numpy as np
from folium.plugins import HeatMap
from typing import Dict, List, Tuple
from services.location_service import LocationService

class GeographicHeatmapGenerator:
    """Genera mapas de calor geográficos reales."""
    
    def __init__(self):
        self.location_service = LocationService()
    
    def generate_signal_heatmap(self, ap_stats: Dict, center_location: Tuple[float, float] = None) -> str:
        """Genera mapa de calor de intensidad de señal."""
        
        if not center_location:
            center_location = (-34.9011, -56.1645)  # Montevideo por defecto
        
        # Crear mapa base
        m = folium.Map(location=center_location, zoom_start=15)
        
        # Datos para el heatmap
        heat_data = []
        markers_data = []
        
        for ap_key, stats in ap_stats.items():
            bssid = stats.get('bssid', 'Unknown')
            location = self.location_service.get_ap_location(bssid)
            
            if location:
                lat, lon = location
                signal_strength = stats.get('avg_signal', 0)
                
                # Agregar punto al heatmap (lat, lon, peso)
                heat_data.append([lat, lon, signal_strength])
                
                # Agregar marcador con info
                ssid = ap_key.split('(')[0]
                popup_text = f"""
                <b>{ssid}</b><br>
                Señal: {signal_strength:.1f}%<br>
                Ping: {stats.get('avg_ping', 'N/A')} ms<br>
                Descarga: {stats.get('avg_download', 'N/A')} Mbps<br>
                Éxito: {stats.get('success_rate', 0):.1f}%
                """
                
                # Color según rendimiento
                color = self._get_performance_color(stats)
                
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=8,
                    popup=popup_text,
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.7
                ).add_to(m)
        
        # Agregar capa de heatmap
        if heat_data:
            HeatMap(heat_data, 
                   radius=50, 
                   blur=30,
                   gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(m)
        
        # Guardar mapa
        output_file = "reports/wifi_geographic_heatmap.html"
        m.save(output_file)
        
        return output_file
    
    def generate_performance_heatmap(self, ap_stats: Dict, center_location: Tuple[float, float] = None) -> str:
        """Genera mapa de calor de rendimiento de velocidad."""
        
        if not center_location:
            center_location = (-34.9011, -56.1645)
        
        m = folium.Map(location=center_location, zoom_start=15)
        
        heat_data = []
        
        for ap_key, stats in ap_stats.items():
            bssid = stats.get('bssid', 'Unknown')
            location = self.location_service.get_ap_location(bssid)
            
            if location and stats.get('avg_download'):
                lat, lon = location
                download_speed = stats.get('avg_download', 0)
                
                # Normalizar velocidad para heatmap (0-100)
                normalized_speed = min(100, (download_speed / 100) * 100)
                heat_data.append([lat, lon, normalized_speed])
        
        # Agregar heatmap de velocidad
        if heat_data:
            HeatMap(heat_data, 
                   radius=40, 
                   blur=25,
                   gradient={0.0: 'red', 0.5: 'orange', 1.0: 'green'}).add_to(m)
        
        output_file = "reports/wifi_speed_heatmap.html"
        m.save(output_file)
        
        return output_file
    
    def _get_performance_color(self, stats: Dict) -> str:
        """Determina color según rendimiento."""
        score = stats.get('avg_download', 0)
        
        if score >= 50:
            return 'green'
        elif score >= 20:
            return 'orange'
        else:
            return 'red'
    
    def update_ap_locations(self, networks: List[Dict]):
        """Actualiza ubicaciones de APs detectados."""
        current_location = self.location_service.get_current_location()
        
        if not current_location:
            print("⚠️  No se pudo obtener ubicación actual")
            return
        
        for network in networks:
            bssid = network.get('bssid', 'Unknown')
            ssid = network.get('ssid', 'Unknown')
            
            if bssid != 'Unknown' and not self.location_service.get_ap_location(bssid):
                # Guardar ubicación actual para este AP
                self.location_service.save_ap_location(bssid, ssid, current_location)
                print(f"📍 Ubicación guardada para {ssid} ({bssid})")

