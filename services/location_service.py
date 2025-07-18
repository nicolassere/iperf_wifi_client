import json
import requests
from typing import Dict, Tuple, Optional
from datetime import datetime

class LocationService:
    """Servicio para obtener coordenadas GPS."""
    
    def __init__(self):
        self.location_cache = {}
        self.load_location_cache()
    
    def get_current_location(self) -> Optional[Tuple[float, float]]:
        """Obtiene ubicación actual usando diferentes métodos."""
        try:
            # Método 1: API de geolocalización por IP
            response = requests.get("http://ip-api.com/json/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return (float(data['lat']), float(data['lon']))
        except:
            pass
        
        # Método 2: Coordenadas manuales (fallback)
        return self.get_manual_location()
    
    def get_manual_location(self) -> Optional[Tuple[float, float]]:
        """Solicita coordenadas manuales al usuario."""
        try:
            print("\n📍 Ingresa tu ubicación actual:")
            lat = float(input("Latitud (ej: -34.9011): "))
            lon = float(input("Longitud (ej: -56.1645): "))
            return (lat, lon)
        except:
            return None
    
    def save_ap_location(self, bssid: str, ssid: str, location: Tuple[float, float]):
        """Guarda ubicación de un AP."""
        self.location_cache[bssid] = {
            'ssid': ssid,
            'lat': location[0],
            'lon': location[1],
            'timestamp': datetime.now().isoformat()
        }
        self.save_location_cache()
    
    def get_ap_location(self, bssid: str) -> Optional[Tuple[float, float]]:
        """Obtiene ubicación guardada de un AP."""
        if bssid in self.location_cache:
            data = self.location_cache[bssid]
            return (data['lat'], data['lon'])
        return None
    
    def load_location_cache(self):
        """Carga caché de ubicaciones."""
        try:
            with open("data/ap_locations.json", "r") as f:
                self.location_cache = json.load(f)
        except:
            self.location_cache = {}
    
    def save_location_cache(self):
        """Guarda caché de ubicaciones."""
        try:
            with open("data/ap_locations.json", "w") as f:
                json.dump(self.location_cache, f, indent=2)
        except Exception as e:
            print(f"Error guardando ubicaciones: {e}")
