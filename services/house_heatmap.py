
import statistics
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from pathlib import Path
import subprocess
import re
from scipy.interpolate import griddata
import threading
import time

class SimpleHouseLocationService:
    """Servicio de ubicación simple para interiores de casa."""
    
    def __init__(self, house_width: float = 15, house_length: float = 20):
        self.house_width = house_width  # ancho en metros
        self.house_length = house_length  # largo en metros
        self.measurement_points = []
        self.rooms = {}  # Para definir habitaciones
        
    def define_room(self, room_name: str, x_start: float, y_start: float, 
                   width: float, length: float):
        """Define una habitación en el plano de la casa."""
        self.rooms[room_name] = {
            'x_start': x_start,
            'y_start': y_start,
            'width': width,
            'length': length,
            'center': (x_start + width/2, y_start + length/2)
        }
        print(f"🏠 Habitación '{room_name}' definida: {width}x{length}m")
    
    def get_room_coordinates(self, room_name: str, x_meters: float, y_meters: float) -> Tuple[float, float]:
        """Convierte posición en metros a coordenadas de la casa."""
        # Validar que esté dentro de los límites
        x_meters = max(0, min(x_meters, self.house_width))
        y_meters = max(0, min(y_meters, self.house_length))
        return (x_meters, y_meters)
    
    def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """Calcula distancia entre dos puntos en metros."""
        x1, y1 = coord1
        x2, y2 = coord2
        return ((x2 - x1)**2 + (y2 - y1)**2)**0.5
    
    def save_measurement_point(self, location: Tuple[float, float], wifi_data: Dict, room: str = ""):
        """Guarda un punto de medición con ubicación y datos WiFi."""
        measurement = {
            'timestamp': datetime.now().isoformat(),
            'room': room,
            'location': location,
            'position_meters': location,
            'wifi_data': wifi_data,
            'measurement_id': len(self.measurement_points)
        }
        self.measurement_points.append(measurement)
        return measurement['measurement_id']
    
    def get_nearby_measurements(self, location: Tuple[float, float], radius_meters: float = 2) -> List[Dict]:
        """Obtiene mediciones cercanas dentro del radio especificado."""
        nearby = []
        for measurement in self.measurement_points:
            distance = self.calculate_distance(location, measurement['location'])
            if distance <= radius_meters:
                measurement['distance'] = distance
                nearby.append(measurement)
        return nearby


class LiveHeatmapGrid:
    """Grilla de heatmap que se actualiza automáticamente por habitación."""
    
    def __init__(self, analyzer, grid_resolution: float = 0.5, update_interval: float = 2.0):
        self.analyzer = analyzer
        self.grid_resolution = grid_resolution  # Resolución de la grilla en metros
        self.update_interval = update_interval  # Intervalo de actualización en segundos
        self.room_grids = {}  # Grillas por habitación
        self.room_heatmaps = {}  # Heatmaps por habitación
        self.is_updating = False
        self.selected_network = None
        
        # Figura principal
        self.fig = None
        self.axes = {}
        
    def initialize_room_grids(self):
        """Inicializa las grillas para cada habitación."""
        for room_name, room_info in self.analyzer.location_service.rooms.items():
            # Crear grilla para la habitación
            x_points = int(room_info['width'] / self.grid_resolution) + 1
            y_points = int(room_info['length'] / self.grid_resolution) + 1
            
            # Coordenadas de la grilla
            x_grid = np.linspace(room_info['x_start'], 
                               room_info['x_start'] + room_info['width'], 
                               x_points)
            y_grid = np.linspace(room_info['y_start'], 
                               room_info['y_start'] + room_info['length'], 
                               y_points)
            
            self.room_grids[room_name] = {
                'x_grid': x_grid,
                'y_grid': y_grid,
                'x_mesh': np.meshgrid(x_grid, y_grid)[0],
                'y_mesh': np.meshgrid(x_grid, y_grid)[1],
                'signal_grid': np.zeros((y_points, x_points)),
                'measurement_count': np.zeros((y_points, x_points)),
                'last_update': None
            }
            
        print(f"📊 Grillas inicializadas para {len(self.room_grids)} habitaciones")
        print(f"   Resolución: {self.grid_resolution}m")
    
    def setup_live_display(self, network_name: str):
        """Configura la visualización en vivo."""
        self.selected_network = network_name
        
        # Calcular layout de subplots
        num_rooms = len(self.analyzer.location_service.rooms)
        cols = min(3, num_rooms)
        rows = (num_rooms + cols - 1) // cols
        
        # Crear figura con subplots
        self.fig, axes_array = plt.subplots(rows, cols, figsize=(5*cols, 4*rows))
        
        # Manejar el caso de un solo subplot
        if num_rooms == 1:
            axes_array = [axes_array]
        elif rows == 1:
            axes_array = [axes_array] if num_rooms == 1 else axes_array
        else:
            axes_array = axes_array.flatten()
        
        # Configurar cada subplot para una habitación
        for i, (room_name, room_info) in enumerate(self.analyzer.location_service.rooms.items()):
            if i < len(axes_array):
                ax = axes_array[i]
                self.axes[room_name] = ax
                
                # Configurar el eje
                ax.set_xlim(room_info['x_start'], room_info['x_start'] + room_info['width'])
                ax.set_ylim(room_info['y_start'], room_info['y_start'] + room_info['length'])
                ax.set_title(f'{room_name} - {network_name}')
                ax.set_xlabel('X (metros)')
                ax.set_ylabel('Y (metros)')
                ax.grid(True, alpha=0.3)
                ax.set_aspect('equal')
        
        # Ocultar subplots no utilizados
        for i in range(num_rooms, len(axes_array)):
            axes_array[i].set_visible(False)
        
        plt.tight_layout()
        plt.ion()  # Modo interactivo
        plt.show()
        
        print(f"🖥️  Display en vivo configurado para red: {network_name}")
    
    def update_room_grid(self, room_name: str, x_pos: float, y_pos: float, signal_strength: float):
        """Actualiza la grilla de una habitación específica con nueva medición."""
        if room_name not in self.room_grids:
            print(f"⚠️  Habitación '{room_name}' no encontrada en grillas")
            return
        
        grid_data = self.room_grids[room_name]
        room_info = self.analyzer.location_service.rooms[room_name]
        
        # Convertir posición global a posición relativa en la habitación
        rel_x = x_pos - room_info['x_start']
        rel_y = y_pos - room_info['y_start']
        
        # Encontrar el punto de grilla más cercano
        x_idx = int(np.round(rel_x / self.grid_resolution))
        y_idx = int(np.round(rel_y / self.grid_resolution))
        
        # Verificar límites
        if (0 <= x_idx < grid_data['signal_grid'].shape[1] and 
            0 <= y_idx < grid_data['signal_grid'].shape[0]):
            
            # Actualizar grilla con promedio ponderado
            current_count = grid_data['measurement_count'][y_idx, x_idx]
            current_signal = grid_data['signal_grid'][y_idx, x_idx]
            
            # Promedio incremental
            new_count = current_count + 1
            new_signal = (current_signal * current_count + signal_strength) / new_count
            
            grid_data['signal_grid'][y_idx, x_idx] = new_signal
            grid_data['measurement_count'][y_idx, x_idx] = new_count
            grid_data['last_update'] = datetime.now()
            
            print(f"📍 Grilla actualizada: {room_name} ({x_idx}, {y_idx}) = {new_signal:.1f}%")
    
    def interpolate_room_heatmap(self, room_name: str):
        """Interpola los datos de la grilla para crear un heatmap suave."""
        if room_name not in self.room_grids:
            return None
        
        grid_data = self.room_grids[room_name]
        room_info = self.analyzer.location_service.rooms[room_name]
        
        # Obtener puntos con mediciones
        measured_points = []
        measured_signals = []
        
        for i in range(grid_data['signal_grid'].shape[0]):
            for j in range(grid_data['signal_grid'].shape[1]):
                if grid_data['measurement_count'][i, j] > 0:
                    # Convertir índices a coordenadas globales
                    x_global = room_info['x_start'] + j * self.grid_resolution
                    y_global = room_info['y_start'] + i * self.grid_resolution
                    
                    measured_points.append((x_global, y_global))
                    measured_signals.append(grid_data['signal_grid'][i, j])
        
        if len(measured_points) < 3:
            return None  # Necesitamos al menos 3 puntos para interpolación
        
        # Crear grilla densa para interpolación
        x_dense = np.linspace(room_info['x_start'], 
                             room_info['x_start'] + room_info['width'], 
                             int(room_info['width'] / 0.2) + 1)
        y_dense = np.linspace(room_info['y_start'], 
                             room_info['y_start'] + room_info['length'], 
                             int(room_info['length'] / 0.2) + 1)
        
        x_mesh, y_mesh = np.meshgrid(x_dense, y_dense)
        
        # Interpolación
        try:
            z_interpolated = griddata(measured_points, measured_signals, 
                                    (x_mesh, y_mesh), method='cubic', fill_value=0)
            return x_mesh, y_mesh, z_interpolated
        except:
            # Fallback a interpolación lineal
            z_interpolated = griddata(measured_points, measured_signals, 
                                    (x_mesh, y_mesh), method='linear', fill_value=0)
            return x_mesh, y_mesh, z_interpolated
    
    def update_display(self):
        """Actualiza la visualización de todos los heatmaps con mejoras visuales."""
        if not self.fig or not self.selected_network:
            return
        
        for room_name, ax in self.axes.items():
            ax.clear()
            
            room_info = self.analyzer.location_service.rooms[room_name]
            grid_data = self.room_grids[room_name]
            
            # Configurar el eje con estilo mejorado
            ax.set_xlim(room_info['x_start'] - 0.2, room_info['x_start'] + room_info['width'] + 0.2)
            ax.set_ylim(room_info['y_start'] - 0.2, room_info['y_start'] + room_info['length'] + 0.2)
            
            # Título con información de calidad
            total_measurements = int(np.sum(grid_data['measurement_count']))
            coverage = (np.count_nonzero(grid_data['measurement_count']) / grid_data['signal_grid'].size) * 100
            ax.set_title(f'{room_name.upper()} - {self.selected_network}\n{total_measurements} mediciones | {coverage:.1f}% cobertura', 
                        fontsize=11, fontweight='bold')
            
            ax.set_xlabel('X (metros)', fontsize=9)
            ax.set_ylabel('Y (metros)', fontsize=9)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_aspect('equal')
            
            # Dibujar contorno de la habitación con estilo
            rect = patches.Rectangle(
                (room_info['x_start'], room_info['y_start']),
                room_info['width'], room_info['length'],
                linewidth=3, edgecolor='navy', facecolor='lightgray', alpha=0.1
            )
            ax.add_patch(rect)
            
            # Interpolar y mostrar heatmap
            interpolation_result = self.interpolate_room_heatmap(room_name)
            if interpolation_result:
                x_mesh, y_mesh, z_interpolated = interpolation_result
                
                # Crear heatmap con más niveles para suavidad
                contour = ax.contourf(x_mesh, y_mesh, z_interpolated, 
                                    levels=30, alpha=0.8, cmap='RdYlGn', 
                                    vmin=0, vmax=100)
                
                # Agregar líneas de contorno para mejor definición
                contour_lines = ax.contour(x_mesh, y_mesh, z_interpolated, 
                                         levels=[25, 50, 75], colors='black', 
                                         alpha=0.4, linewidths=0.8)
                ax.clabel(contour_lines, inline=True, fontsize=8, fmt='%d%%')
                
                # Agregar puntos de medición con tamaño variable
                for i in range(grid_data['signal_grid'].shape[0]):
                    for j in range(grid_data['signal_grid'].shape[1]):
                        if grid_data['measurement_count'][i, j] > 0:
                            x_pos = room_info['x_start'] + j * self.grid_resolution
                            y_pos = room_info['y_start'] + i * self.grid_resolution
                            signal = grid_data['signal_grid'][i, j]
                            count = grid_data['measurement_count'][i, j]
                            
                            # Tamaño del punto basado en número de mediciones
                            point_size = 80 + (count * 20)  # Más mediciones = puntos más grandes
                            
                            scatter = ax.scatter(x_pos, y_pos, c=signal, s=point_size, 
                                               cmap='RdYlGn', edgecolors='black', 
                                               linewidths=1.5, vmin=0, vmax=100, zorder=5)
                            
                            # Etiqueta de señal con mejor formato
                            label_color = 'white' if signal < 50 else 'black'
                            ax.annotate(f'{signal:.0f}%\n({int(count)})', (x_pos, y_pos), 
                                      ha='center', va='center', fontsize=7, 
                                      fontweight='bold', color=label_color,
                                      bbox=dict(boxstyle='round,pad=0.3', 
                                              facecolor='white', alpha=0.9, edgecolor='gray'))
                
                # Agregar barra de color solo en el primer subplot
                if room_name == list(self.axes.keys())[0]:
                    cbar = plt.colorbar(contour, ax=ax, shrink=0.8, aspect=20)
                    cbar.set_label('Intensidad WiFi (%)', rotation=270, labelpad=15, fontsize=9)
            
            else:
                # Si no hay suficientes datos para interpolación, mostrar solo puntos
                for i in range(grid_data['signal_grid'].shape[0]):
                    for j in range(grid_data['signal_grid'].shape[1]):
                        if grid_data['measurement_count'][i, j] > 0:
                            x_pos = room_info['x_start'] + j * self.grid_resolution
                            y_pos = room_info['y_start'] + i * self.grid_resolution
                            signal = grid_data['signal_grid'][i, j]
                            
                            ax.scatter(x_pos, y_pos, c=signal, s=150, cmap='RdYlGn',
                                     edgecolors='black', linewidths=2, vmin=0, vmax=100)
                            
                            ax.annotate(f'{signal:.0f}%', (x_pos, y_pos), 
                                      xytext=(0, 20), textcoords='offset points',
                                      ha='center', fontsize=9, fontweight='bold',
                                      bbox=dict(boxstyle='round,pad=0.3', 
                                              facecolor='yellow', alpha=0.8))
                
                # Mensaje de información
                ax.text(0.5, 0.5, 'Necesita más mediciones\npara interpolación', 
                       transform=ax.transAxes, ha='center', va='center',
                       fontsize=10, style='italic', color='red',
                       bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
            
            # Panel de información mejorado
            last_update = grid_data.get('last_update')
            if last_update:
                time_diff = datetime.now() - last_update
                time_str = f"{time_diff.seconds}s" if time_diff.seconds < 60 else f"{time_diff.seconds//60}m"
            else:
                time_str = "N/A"
            
            # Calcular calidad de señal promedio
            measured_signals = []
            for i in range(grid_data['signal_grid'].shape[0]):
                for j in range(grid_data['signal_grid'].shape[1]):
                    if grid_data['measurement_count'][i, j] > 0:
                        measured_signals.append(grid_data['signal_grid'][i, j])
            
            avg_quality = statistics.mean(measured_signals) if measured_signals else 0
            quality_color = 'green' if avg_quality > 70 else 'orange' if avg_quality > 40 else 'red'
            
            info_text = f"📊 Mediciones: {total_measurements}\n⚡ Promedio: {avg_quality:.1f}%\n🕒 Última: {time_str}"
            
            ax.text(0.02, 0.98, info_text, transform=ax.transAxes, 
                   verticalalignment='top', fontsize=8,
                   bbox=dict(boxstyle='round,pad=0.4', facecolor=quality_color, 
                           alpha=0.7, edgecolor='black', linewidth=1))
        
        # Título general de la figura
        self.fig.suptitle(f'🏠 Mapa de Calor WiFi en Tiempo Real - {self.selected_network}', 
                         fontsize=14, fontweight='bold', y=0.95)
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.90)
        plt.draw()
        plt.pause(0.1)
    
    def start_auto_update(self):
        """Inicia la actualización automática del display."""
        self.is_updating = True
        
        def update_loop():
            while self.is_updating:
                try:
                    self.update_display()
                    time.sleep(self.update_interval)
                except Exception as e:
                    print(f"⚠️  Error en actualización automática: {e}")
                    time.sleep(self.update_interval)
        
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
        print(f"🔄 Actualización automática iniciada (cada {self.update_interval}s)")
    
    def stop_auto_update(self):
        """Detiene la actualización automática."""
        self.is_updating = False
        print("⏹️  Actualización automática detenida")
    
    def add_measurement_to_grid(self, x_pos: float, y_pos: float, room_name: str, 
                               wifi_data: Dict, network_filter: str = None):
        """Agrega una nueva medición a la grilla correspondiente."""
        # Filtrar por red específica si se especifica
        target_network = network_filter or self.selected_network
        if not target_network:
            return
        
        # Buscar la red en los datos WiFi
        signal_strength = None
        for net_key, net_data in wifi_data.get('networks', {}).items():
            if target_network in net_key:
                signal_strength = net_data.get('signal_strength', 0)
                break
        
        if signal_strength is not None:
            self.update_room_grid(room_name, x_pos, y_pos, signal_strength)
            print(f"📊 Medición agregada a grilla: {room_name} - {signal_strength:.1f}%")
    
    def get_room_statistics(self, room_name: str) -> Dict:
        """Obtiene estadísticas de una habitación específica."""
        if room_name not in self.room_grids:
            return {}
        
        grid_data = self.room_grids[room_name]
        measured_signals = []
        
        for i in range(grid_data['signal_grid'].shape[0]):
            for j in range(grid_data['signal_grid'].shape[1]):
                if grid_data['measurement_count'][i, j] > 0:
                    measured_signals.append(grid_data['signal_grid'][i, j])
        
        if not measured_signals:
            return {'error': 'No hay mediciones en esta habitación'}
        
        return {
            'room_name': room_name,
            'total_measurements': len(measured_signals),
            'avg_signal': statistics.mean(measured_signals),
            'min_signal': min(measured_signals),
            'max_signal': max(measured_signals),
            'std_dev': statistics.stdev(measured_signals) if len(measured_signals) > 1 else 0,
            'coverage_percentage': (len(measured_signals) / (grid_data['signal_grid'].shape[0] * grid_data['signal_grid'].shape[1])) * 100
        }


class EnhancedWiFiHeatmapAnalyzer:
    """Analizador de heatmap WiFi mejorado con grilla en vivo."""
    
    def __init__(self, data_dir: str = "data", house_width: float = 15, house_length: float = 20):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.location_service = SimpleHouseLocationService(house_width, house_length)
        # self.wifi_scanner = WiFiAnalyzer()  # Comentado porque no tenemos la implementación
        self.house_layout = {}
        self.live_grid = None
        
    def setup_house_layout(self):
        """Configura el layout básico de la casa."""
        # Definir habitaciones ejemplo - PERSONALIZA ESTO SEGÚN TU CASA
        self.location_service.define_room("sala", 0, 0, 6, 8)
        self.location_service.define_room("cocina", 6, 0, 4, 5)
        self.location_service.define_room("dormitorio1", 0, 8, 5, 6)
        self.location_service.define_room("dormitorio2", 5, 8, 5, 6)
        self.location_service.define_room("baño", 10, 0, 3, 4)
        
        print("🏠 Layout de casa configurado")
        print(f"   Dimensiones: {self.location_service.house_width}x{self.location_service.house_length}m")
    
    def initialize_live_grid(self, network_name: str, grid_resolution: float = 0.5, update_interval: float = 2.0):
        """Inicializa la grilla en vivo para una red específica."""
        self.live_grid = LiveHeatmapGrid(self, grid_resolution, update_interval)
        self.live_grid.initialize_room_grids()
        self.live_grid.setup_live_display(network_name)
        self.live_grid.start_auto_update()
        
        print(f"🎯 Grilla en vivo inicializada para: {network_name}")
        return self.live_grid
    
    def collect_measurement_at_location(self, x_pos: float, y_pos: float, 
        room_name: str = "", wifi_networks: List[Dict] = None) -> Dict:
        """Colecta medición WiFi en ubicación específica y actualiza grilla."""
        
        # Datos de ejemplo si no se proporcionan redes WiFi reales
        if wifi_networks is None:
            # Simulación de escaneo WiFi
            wifi_networks = [
                {'ssid': 'MiWiFi_Principal', 'bssid': '00:11:22:33:44:55', 
                 'signal_percentage': np.random.randint(20, 100), 'frequency': 2437, 'channel': 6},
                {'ssid': 'WiFi_Vecino', 'bssid': '00:11:22:33:44:66', 
                 'signal_percentage': np.random.randint(10, 60), 'frequency': 2412, 'channel': 1}
            ]
        
        # Obtener coordenadas
        location = self.location_service.get_room_coordinates(room_name, x_pos, y_pos)
        
        # Procesar datos WiFi
        processed_data = {
            'timestamp': datetime.now().isoformat(),
            'room': room_name,
            'location': location,
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
        
        # Guardar medición
        measurement_id = self.location_service.save_measurement_point(location, processed_data, room_name)
        
        # Actualizar grilla en vivo si está activa
        if self.live_grid:
            self.live_grid.add_measurement_to_grid(x_pos, y_pos, room_name, processed_data)
        
        print(f"📍 Medición {measurement_id} guardada en {room_name} ({x_pos}m, {y_pos}m)")
        print(f"   Encontradas {len(wifi_networks)} redes")
        
        return processed_data
    
    def simulate_measurement_sequence(self, network_name: str, num_points: int = 20):
        """Simula una secuencia de mediciones para demostración."""
        if not self.live_grid:
            print("⚠️  Inicia primero la grilla en vivo")
            return
        
        print(f"🎮 Iniciando simulación de {num_points} mediciones...")
        print("   Las mediciones aparecerán automáticamente en el heatmap")
        
        rooms = list(self.location_service.rooms.keys())
        
        for i in range(num_points):
            # Seleccionar habitación aleatoria
            room = np.random.choice(rooms)
            room_info = self.location_service.rooms[room]
            
            # Generar posición aleatoria dentro de la habitación
            x_pos = room_info['x_start'] + np.random.random() * room_info['width']
            y_pos = room_info['y_start'] + np.random.random() * room_info['length']
            
            # Simular medición con señal variable según distancia del centro
            center_x = room_info['x_start'] + room_info['width'] / 2
            center_y = room_info['y_start'] + room_info['length'] / 2
            
            # Calcular distancia del centro (simulando router en el centro)
            distance_from_center = ((x_pos - center_x)**2 + (y_pos - center_y)**2)**0.5
            max_distance = ((room_info['width']**2 + room_info['length']**2)**0.5) / 2
            
            # Señal más fuerte cerca del centro
            base_signal = 100 - (distance_from_center / max_distance * 60)
            noise = np.random.normal(0, 10)  # Añadir ruido
            signal_strength = max(10, min(100, base_signal + noise))
            
            # Crear datos WiFi simulados
            wifi_data = {
                'networks': {
                    f'{network_name}_00:11:22:33:44:55': {
                        'signal_strength': signal_strength,
                        'frequency': 2437,
                        'channel': 6
                    }
                }
            }
            
            # Agregar medición
            self.collect_measurement_at_location(x_pos, y_pos, room, [])
            self.live_grid.add_measurement_to_grid(x_pos, y_pos, room, wifi_data, network_name)
            
            print(f"   📍 Punto {i+1}: {room} ({x_pos:.1f}, {y_pos:.1f}) = {signal_strength:.1f}%")
            
            # Pausa para ver la actualización
            time.sleep(1.5)
        
        print("✅ Simulación completada!")
    
    def export_grid_data(self, filename: str = "grid_heatmap_data.json"):
        """Exporta los datos de la grilla a un archivo JSON."""
        if not self.live_grid:
            print("⚠️  No hay grilla activa para exportar")
            return
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'network_name': self.live_grid.selected_network,
            'grid_resolution': self.live_grid.grid_resolution,
            'house_dimensions': {
                'width': self.location_service.house_width,
                'length': self.location_service.house_length
            },
            'rooms': self.location_service.rooms,
            'room_grids': {}
        }
        
        # Exportar datos de grilla por habitación
        for room_name, grid_data in self.live_grid.room_grids.items():
            export_data['room_grids'][room_name] = {
                'signal_grid': grid_data['signal_grid'].tolist(),
                'measurement_count': grid_data['measurement_count'].tolist(),
                'last_update': grid_data['last_update'].isoformat() if grid_data['last_update'] else None,
                'statistics': self.live_grid.get_room_statistics(room_name)
            }
        
        file_path = self.data_dir / filename
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"📁 Datos de grilla exportados a: {file_path}")
        return str(file_path)
    
    def generate_coverage_report(self) -> str:
        """Genera un reporte detallado de cobertura WiFi."""
        if not self.live_grid:
            return "No hay grilla activa"
        
        report = []
        report.append("📋 === REPORTE DE COBERTURA WIFI ===")
        report.append(f"🕒 Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"📡 Red: {self.live_grid.selected_network}")
        report.append(f"🏠 Casa: {self.location_service.house_width}x{self.location_service.house_length}m")
        report.append("")
        
        total_measurements = 0
        total_coverage = 0
        room_count = 0
        
        for room_name in self.location_service.rooms.keys():
            stats = self.live_grid.get_room_statistics(room_name)
            if 'error' not in stats:
                room_count += 1
                total_measurements += stats['total_measurements']
                total_coverage += stats['coverage_percentage']
                
                # Clasificar calidad
                avg_signal = stats['avg_signal']
                if avg_signal >= 80:
                    quality = "🟢 EXCELENTE"
                elif avg_signal >= 60:
                    quality = "🟡 BUENA"
                elif avg_signal >= 40:
                    quality = "🟠 REGULAR"
                else:
                    quality = "🔴 POBRE"
                
                report.append(f"🏠 {room_name.upper()}")
                report.append(f"   Calidad: {quality} ({avg_signal:.1f}%)")
                report.append(f"   Mediciones: {stats['total_measurements']}")
                report.append(f"   Rango: {stats['min_signal']:.1f}% - {stats['max_signal']:.1f}%")
                report.append(f"   Cobertura: {stats['coverage_percentage']:.1f}%")
                report.append("")
        
        # Resumen general
        if room_count > 0:
            avg_coverage = total_coverage / room_count
            report.append("📊 === RESUMEN GENERAL ===")
            report.append(f"🔢 Total mediciones: {total_measurements}")
            report.append(f"📍 Cobertura promedio: {avg_coverage:.1f}%")
            report.append(f"🏠 Habitaciones analizadas: {room_count}")
            
            # Recomendaciones
            report.append("")
            report.append("💡 === RECOMENDACIONES ===")
            if avg_coverage < 30:
                report.append("⚠️  Cobertura baja - Necesita más mediciones")
            elif avg_coverage < 60:
                report.append("📈 Cobertura moderada - Considere más puntos")
            else:
                report.append("✅ Cobertura buena para análisis")
        
        return "\n".join(report)


# Función principal mejorada
def setup_and_run_enhanced_heatmap():
    """Función principal mejorada con grilla en vivo."""
    
    print("🏠 === ANALIZADOR DE HEATMAP WIFI CON GRILLA EN VIVO ===")
    
    # Configuración inicial
    width = float(input("Ancho de tu casa en metros (default: 15): ") or 15)
    length = float(input("Largo de tu casa en metros (default: 20): ") or 20)
    
    analyzer = EnhancedWiFiHeatmapAnalyzer(house_width=width, house_length=length)
    analyzer.setup_house_layout()
    
    # Menú principal
    while True:
        print("\n" + "="*60)
        print("OPCIONES DISPONIBLES:")
        print("1. Inicializar grilla en vivo")
        print("2. Medición manual (actualiza grilla automáticamente)")
        print("3. Detener grilla en vivo")
        print("4. Estadísticas por habitación")
        print("5. Configurar nueva habitación")
        print("0. Salir")
        print("="*60)
        
        choice = input("Selecciona opción: ").strip()
        
        if choice == '1':
            # Inicializar grilla en vivo
            network = input("Nombre de la red WiFi para monitorear: ")
            resolution = float(input("Resolución de grilla en metros (default: 0.5): ") or 0.5)
            update_interval = float(input("Intervalo de actualización en segundos (default: 2): ") or 2.0)
            
            try:
                analyzer.initialize_live_grid(network, resolution, update_interval)
                print("✅ Grilla en vivo iniciada! La ventana se actualizará automáticamente.")
            except Exception as e:
                print(f"❌ Error iniciando grilla: {e}")
        
        elif choice == '2':
            # Medición manual
            if not analyzer.live_grid:
                print("⚠️  Inicia primero la grilla en vivo (opción 1)")
                continue
                
            try:
                x = float(input("Posición X (metros): "))
                y = float(input("Posición Y (metros): "))
                room = input("Habitación: ")
                
                # Verificar que la habitación existe
                if room not in analyzer.location_service.rooms:
                    print(f"⚠️  Habitación '{room}' no definida. Habitaciones disponibles: {list(analyzer.location_service.rooms.keys())}")
                    continue
                
                analyzer.collect_measurement_at_location(x, y, room)
                print("✅ Medición agregada! El heatmap se actualizará automáticamente.")
                
            except Exception as e:
                print(f"❌ Error: {e}")
        
        elif choice == '3':
            # Detener grilla en vivo
            analyzer.stop_live_grid()
        
        elif choice == '4':
            # Estadísticas por habitación
            if not analyzer.live_grid:
                print("⚠️  No hay grilla activa")
                continue
            
            for room_name in analyzer.location_service.rooms.keys():
                stats = analyzer.live_grid.get_room_statistics(room_name)
                if 'error' not in stats:
                    print(f"\n📊 {room_name.upper()}:")
                    print(f"   Mediciones: {stats['total_measurements']}")
                    print(f"   Señal promedio: {stats['avg_signal']:.1f}%")
                    print(f"   Rango: {stats['min_signal']:.1f}% - {stats['max_signal']:.1f}%")
                    print(f"   Cobertura: {stats['coverage_percentage']:.1f}%")
                else:
                    print(f"\n📊 {room_name.upper()}: Sin mediciones")
        
        elif choice == '5':
            # Configurar nueva habitación
            try:
                name = input("Nombre de la habitación: ")
                x_start = float(input("Posición X inicial (metros): "))
                y_start = float(input("Posición Y inicial (metros): "))
                width = float(input("Ancho (metros): "))
                length = float(input("Largo (metros): "))
                
                analyzer.location_service.define_room(name, x_start, y_start, width, length)
                
                # Reinicializar grillas si están activas
                if analyzer.live_grid:
                    analyzer.live_grid.initialize_room_grids()
                    print("✅ Grillas actualizadas con nueva habitación")
                
            except Exception as e:
                print(f"❌ Error configurando habitación: {e}")
        
        elif choice == '0':
            if analyzer.live_grid:
                analyzer.stop_live_grid()
            break
        
        else:
            print("❌ Opción no válida")

if __name__ == "__main__":
    setup_and_run_enhanced_heatmap()