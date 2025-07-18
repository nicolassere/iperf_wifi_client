# ===== services/heatmap_analyzer.py =====
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

class HeatmapAnalyzer:
    """Analiza datos históricos para generar mapas de calor y detectar conflictos."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(".")
        self.data_dir.mkdir(exist_ok=True)
        
    def load_historical_data(self, days: int = 7) -> List[Dict]:
        """Carga datos históricos de los últimos N días."""
        cutoff_date = datetime.now() - timedelta(days=days)
        all_data = []
        print(f"📂 Ruta absoluta de data_dir: {self.data_dir.resolve()}")

        for json_file in self.data_dir.glob("all_networks_test_*.json"):
            try:
                print(f"📄 Archivo detectado: {json_file}")
                with open(json_file, 'r') as f:
                    print(f"📄 Archivo detectado: {json_file}")
                    data = json.load(f)
                    # Filtrar por fecha
                    if isinstance(data, list):
                        for entry in data:
                            timestamp = datetime.fromisoformat(entry.get('timestamp', ''))
                            if timestamp >= cutoff_date:
                                all_data.append(entry)
                    else:
                        timestamp = datetime.fromisoformat(data.get('timestamp', ''))
                        if timestamp >= cutoff_date:
                            all_data.append(data)
            except Exception as e:
                print(f"Error cargando {json_file}: {e}")

        print(f"Cargados {len(all_data)} registros de datos históricos")

        return sorted(all_data, key=lambda x: x.get('timestamp', ''))
    
    def analyze_ap_performance(self, data: List[Dict]) -> Dict[str, Dict]:
        """Analiza el rendimiento de cada AP a lo largo del tiempo."""
        ap_stats = defaultdict(lambda: {
            'signal_readings': [],
            'ping_times': [],
            'download_speeds': [],
            'upload_speeds': [],
            'timestamps': [],
            'channels': [],
            'connection_attempts': 0,
            'successful_connections': 0,
            'bssid': None,
            'security': None
        })
        
        for entry in data:
            networks = entry.get('all_networks_tested', [])
            for network in networks:
                ssid = network.get('ssid', 'Unknown')
                bssid = network.get('network_info', {}).get('bssid', 'Unknown')
                
                # Usar BSSID como clave única (más preciso que SSID)
                key = f"{ssid} ({bssid})"
                
                ap_stats[key]['connection_attempts'] += 1
                ap_stats[key]['bssid'] = bssid
                ap_stats[key]['timestamps'].append(entry.get('timestamp'))
                
                # Información de red
                net_info = network.get('network_info', {})
                ap_stats[key]['signal_readings'].append(net_info.get('signal_percentage', 0))
                if net_info.get('channel'):
                    ap_stats[key]['channels'].append(net_info.get('channel'))
                if net_info.get('authentication'):
                    ap_stats[key]['security'] = net_info.get('authentication')
                
                # Si la conexión fue exitosa, agregar métricas de rendimiento
                if network.get('connection_successful', False):
                    ap_stats[key]['successful_connections'] += 1
                    
                    test_results = network.get('test_results', {})
                    
                    # Ping
                    ping_result = test_results.get('ping', {})
                    if 'error' not in ping_result and ping_result.get('avg_time'):
                        ap_stats[key]['ping_times'].append(ping_result['avg_time'])
                    
                    # Velocidad
                    speed_result = test_results.get('speedtest', {})
                    if 'error' not in speed_result:
                        download = speed_result.get('download', {}).get('bandwidth', 0)
                        upload = speed_result.get('upload', {}).get('bandwidth', 0)
                        if download > 0:
                            ap_stats[key]['download_speeds'].append(download / 1_000_000)
                        if upload > 0:
                            ap_stats[key]['upload_speeds'].append(upload / 1_000_000)
        
        # Calcular estadísticas resumidas
        for key, stats in ap_stats.items():
            stats['success_rate'] = (stats['successful_connections'] / stats['connection_attempts']) * 100
            stats['avg_signal'] = statistics.mean(stats['signal_readings']) if stats['signal_readings'] else 0
            stats['avg_ping'] = statistics.mean(stats['ping_times']) if stats['ping_times'] else None
            stats['avg_download'] = statistics.mean(stats['download_speeds']) if stats['download_speeds'] else None
            stats['avg_upload'] = statistics.mean(stats['upload_speeds']) if stats['upload_speeds'] else None
            stats['most_common_channel'] = statistics.mode(stats['channels']) if stats['channels'] else None
            
        return dict(ap_stats)
    
    def detect_channel_conflicts(self, data: List[Dict]) -> List[Dict]:
        """Detecta conflictos de canal entre APs."""
        conflicts = []
        
        # Obtener información actual de canales
        latest_entry = data[-1] if data else {}
        current_networks = latest_entry.get('all_networks_tested', [])
        
        # Agrupar por canal
        channels_map = defaultdict(list)
        for network in current_networks:
            net_info = network.get('network_info', {})
            channel = net_info.get('channel')
            if channel:
                channels_map[channel].append({
                    'ssid': network.get('ssid', 'Unknown'),
                    'bssid': net_info.get('bssid', 'Unknown'),
                    'signal': net_info.get('signal_percentage', 0),
                    'security': net_info.get('authentication', 'Unknown')
                })
        
        # Detectar conflictos
        for channel, aps in channels_map.items():
            if len(aps) > 1:
                # Calcular interferencia potencial
                total_signal = sum(ap['signal'] for ap in aps)
                conflict_severity = "ALTA" if total_signal > 150 else "MEDIA" if total_signal > 100 else "BAJA"
                
                conflicts.append({
                    'channel': channel,
                    'aps_count': len(aps),
                    'aps': aps,
                    'total_signal_strength': total_signal,
                    'conflict_severity': conflict_severity,
                    'recommendation': self._get_channel_recommendation(channel, aps)
                })
        
        return conflicts
    
    def _get_channel_recommendation(self, channel: int, aps: List[Dict]) -> str:
        """Genera recomendación para resolver conflicto de canal."""
        if channel in [1, 6, 11]:  # Canales principales 2.4GHz
            return f"Canal {channel} es óptimo para 2.4GHz, pero considera cambiar APs débiles a 5GHz"
        elif channel <= 14:  # Otros canales 2.4GHz
            return f"Canal {channel} puede causar interferencia. Considera canales 1, 6 o 11"
        else:  # 5GHz
            return f"Canal {channel} (5GHz) - Distribución aceptable, monitorear rendimiento"
    
    def generate_heatmap_data(self, ap_stats: Dict[str, Dict]) -> Dict:
        """Genera datos estructurados para visualización de heatmap."""
        heatmap_data = {
            'signal_quality': {},
            'performance': {},
            'reliability': {},
            'time_series': defaultdict(list)
        }
        
        for ap_name, stats in ap_stats.items():
            # Mapa de calor de calidad de señal
            heatmap_data['signal_quality'][ap_name] = {
                'avg_signal': stats['avg_signal'],
                'signal_stability': statistics.stdev(stats['signal_readings']) if len(stats['signal_readings']) > 1 else 0,
                'readings_count': len(stats['signal_readings'])
            }
            
            # Mapa de calor de rendimiento
            heatmap_data['performance'][ap_name] = {
                'avg_ping': stats['avg_ping'] or 999,
                'avg_download': stats['avg_download'] or 0,
                'avg_upload': stats['avg_upload'] or 0,
                'combined_score': self._calculate_performance_score(stats)
            }
            
            # Mapa de calor de confiabilidad
            heatmap_data['reliability'][ap_name] = {
                'success_rate': stats['success_rate'],
                'total_attempts': stats['connection_attempts'],
                'consistency': self._calculate_consistency_score(stats)
            }
            
            # Datos de series temporales
            for i, timestamp in enumerate(stats['timestamps']):
                heatmap_data['time_series'][ap_name].append({
                    'timestamp': timestamp,
                    'signal': stats['signal_readings'][i] if i < len(stats['signal_readings']) else 0,
                    'ping': stats['ping_times'][i] if i < len(stats['ping_times']) else None,
                    'download': stats['download_speeds'][i] if i < len(stats['download_speeds']) else None
                })
        
        return heatmap_data
    
    def _calculate_performance_score(self, stats: Dict) -> float:
        """Calcula un puntaje de rendimiento combinado (0-100)."""
        score = 0
        
        # Componente de ping (40% del puntaje)
        if stats['avg_ping']:
            ping_score = max(0, 100 - (stats['avg_ping'] - 10) * 2)  # 10ms = 100, 60ms = 0
            score += ping_score * 0.4
        
        # Componente de velocidad de descarga (40% del puntaje)
        if stats['avg_download']:
            download_score = min(100, (stats['avg_download'] / 100) * 100)  # 100Mbps = 100
            score += download_score * 0.4
        
        # Componente de confiabilidad (20% del puntaje)
        reliability_score = stats['success_rate']
        score += reliability_score * 0.2
        
        return round(score, 1)
    
    def _calculate_consistency_score(self, stats: Dict) -> float:
        """Calcula un puntaje de consistencia basado en variabilidad."""
        if not stats['signal_readings']:
            return 0
        
        # Menor variabilidad = mayor consistencia
        signal_cv = statistics.stdev(stats['signal_readings']) / statistics.mean(stats['signal_readings'])
        consistency = max(0, 100 - (signal_cv * 100))
        
        return round(consistency, 1)
    
    def create_visual_heatmap(self, heatmap_data: Dict, output_file: str = "wifi_heatmap.png"):
        """Crea visualización de mapa de calor."""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('WiFi Network Heatmap Analysis', fontsize=16, fontweight='bold')
        
        # Preparar datos para visualización
        ap_names = list(heatmap_data['signal_quality'].keys())
        
        # 1. Calidad de señal
        signal_data = [[heatmap_data['signal_quality'][ap]['avg_signal']] for ap in ap_names]
        sns.heatmap(signal_data, 
                   yticklabels=[ap.split('(')[0][:20] for ap in ap_names],
                   xticklabels=['Señal %'],
                   annot=True, 
                   fmt='.1f',
                   cmap='RdYlGn',
                   ax=axes[0,0])
        axes[0,0].set_title('Calidad de Señal Promedio')
        
        # 2. Rendimiento
        perf_data = [[heatmap_data['performance'][ap]['combined_score']] for ap in ap_names]
        sns.heatmap(perf_data,
                   yticklabels=[ap.split('(')[0][:20] for ap in ap_names],
                   xticklabels=['Score'],
                   annot=True,
                   fmt='.1f',
                   cmap='RdYlGn',
                   ax=axes[0,1])
        axes[0,1].set_title('Puntaje de Rendimiento')
        
        # 3. Confiabilidad
        rel_data = [[heatmap_data['reliability'][ap]['success_rate']] for ap in ap_names]
        sns.heatmap(rel_data,
                   yticklabels=[ap.split('(')[0][:20] for ap in ap_names],
                   xticklabels=['Éxito %'],
                   annot=True,
                   fmt='.1f',
                   cmap='RdYlGn',
                   ax=axes[1,0])
        axes[1,0].set_title('Tasa de Éxito de Conexión')
        
        # 4. Ping promedio
        ping_data = [[heatmap_data['performance'][ap]['avg_ping']] for ap in ap_names]
        sns.heatmap(ping_data,
                   yticklabels=[ap.split('(')[0][:20] for ap in ap_names],
                   xticklabels=['Ping ms'],
                   annot=True,
                   fmt='.1f',
                   cmap='RdYlGn_r',  # Invertido porque menor ping es mejor
                   ax=axes[1,1])
        axes[1,1].set_title('Latencia Promedio (ms)')
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_file
