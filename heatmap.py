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
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
    def load_historical_data(self, days: int = 7) -> List[Dict]:
        """Carga datos históricos de los últimos N días."""
        cutoff_date = datetime.now() - timedelta(days=days)
        all_data = []
        
        for json_file in self.data_dir.glob("all_networks_test_*.json"):
            try:
                with open(json_file, 'r') as f:
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

# ===== services/wifi_analyzer.py (MODIFICACIONES) =====
# Agregar estos métodos a la clase WiFiAnalyzer existente:

def get_detailed_scan_info(self) -> List[Dict]:
    """Obtiene información detallada de escaneo incluyendo canales y BSSID."""
    try:
        # Comando para obtener información detallada
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"], 
            capture_output=True, text=True, encoding='utf-8'
        )
        
        # También obtener información de redes disponibles
        scan_result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        # Parsear y devolver información estructurada
        detailed_networks = []
        # Aquí iría la lógica de parsing específica para tu sistema
        # Esta es una implementación de ejemplo
        
        return detailed_networks
    except Exception as e:
        return {"error": f"Error en escaneo detallado: {e}"}

def analyze_channel_distribution(self) -> Dict:
    """Analiza la distribución de canales en el entorno."""
    networks = self.get_detailed_scan_info()
    
    channel_analysis = {
        'channel_distribution': defaultdict(int),
        'band_distribution': {'2.4GHz': 0, '5GHz': 0},
        'congestion_score': 0,
        'recommendations': []
    }
    
    for network in networks:
        channel = network.get('channel')
        if channel:
            channel_analysis['channel_distribution'][channel] += 1
            
            # Clasificar por banda
            if channel <= 14:
                channel_analysis['band_distribution']['2.4GHz'] += 1
            else:
                channel_analysis['band_distribution']['5GHz'] += 1
    
    # Calcular puntuación de congestión
    total_networks = len(networks)
    if total_networks > 0:
        # Más redes en pocos canales = mayor congestión
        unique_channels = len(channel_analysis['channel_distribution'])
        channel_analysis['congestion_score'] = (total_networks / max(unique_channels, 1)) * 10
    
    return channel_analysis

# ===== services/report_generator.py =====
import json
from datetime import datetime
from typing import Dict, List
from pathlib import Path

class WiFiReportGenerator:
    """Genera reportes detallados de análisis WiFi."""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_heatmap_report(self, 
                               ap_stats: Dict, 
                               conflicts: List[Dict], 
                               heatmap_data: Dict,
                               output_file: str = None) -> str:
        """Genera reporte completo de análisis de heatmap."""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not output_file:
            output_file = self.output_dir / f"wifi_heatmap_report_{timestamp}.html"
        
        # Preparar datos para el reporte
        top_performers = sorted(
            [(name, stats) for name, stats in ap_stats.items() if stats['avg_download']],
            key=lambda x: x[1]['avg_download'],
            reverse=True
        )[:5]
        
        most_reliable = sorted(
            [(name, stats) for name, stats in ap_stats.items()],
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )[:5]
        
        # Generar HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>WiFi Heatmap Analysis Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
                .conflict-high {{ background-color: #ffebee; }}
                .conflict-medium {{ background-color: #fff3e0; }}
                .conflict-low {{ background-color: #e8f5e8; }}
                .ap-name {{ font-weight: bold; color: #1976d2; }}
                .metric {{ display: inline-block; margin: 5px 10px; }}
                .warning {{ color: #d32f2f; font-weight: bold; }}
                .success {{ color: #388e3c; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 WiFi Network Heatmap Analysis Report</h1>
                <p>Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Total de APs analizados: {len(ap_stats)}</p>
            </div>
            
            <div class="section">
                <h2>🏆 Top 5 Redes por Rendimiento</h2>
                <table>
                    <tr>
                        <th>Red</th>
                        <th>Descarga (Mbps)</th>
                        <th>Ping (ms)</th>
                        <th>Éxito (%)</th>
                        <th>Puntaje</th>
                    </tr>
        """
        
        for name, stats in top_performers:
            html_content += f"""
                    <tr>
                        <td class="ap-name">{name.split('(')[0]}</td>
                        <td>{stats['avg_download']:.1f}</td>
                        <td>{stats['avg_ping']:.1f if stats['avg_ping'] else 'N/A'}</td>
                        <td>{stats['success_rate']:.1f}</td>
                        <td>{heatmap_data['performance'][name]['combined_score']}</td>
                    </tr>
            """
        
        html_content += """
                </table>
            </div>
            
            <div class="section">
                <h2>🔒 Redes Más Confiables</h2>
                <table>
                    <tr>
                        <th>Red</th>
                        <th>Tasa de Éxito</th>
                        <th>Intentos Totales</th>
                        <th>Señal Promedio</th>
                        <th>Consistencia</th>
                    </tr>
        """
        
        for name, stats in most_reliable:
            html_content += f"""
                    <tr>
                        <td class="ap-name">{name.split('(')[0]}</td>
                        <td>{stats['success_rate']:.1f}%</td>
                        <td>{stats['connection_attempts']}</td>
                        <td>{stats['avg_signal']:.1f}%</td>
                        <td>{heatmap_data['reliability'][name]['consistency']:.1f}%</td>
                    </tr>
            """
        
        html_content += """
                </table>
            </div>
        """
        
        # Sección de conflictos
        if conflicts:
            html_content += """
            <div class="section">
                <h2>⚠️ Conflictos de Canal Detectados</h2>
            """
            
            for conflict in conflicts:
                severity_class = f"conflict-{conflict['conflict_severity'].lower()}"
                html_content += f"""
                <div class="section {severity_class}">
                    <h3>Canal {conflict['channel']} - Severidad: {conflict['conflict_severity']}</h3>
                    <p><strong>APs en conflicto:</strong> {conflict['aps_count']}</p>
                    <p><strong>Fuerza de señal total:</strong> {conflict['total_signal_strength']}%</p>
                    <p><strong>Recomendación:</strong> {conflict['recommendation']}</p>
                    <ul>
                """
                
                for ap in conflict['aps']:
                    html_content += f"""
                        <li>{ap['ssid']} - {ap['signal']}% señal ({ap['security']})</li>
                    """
                
                html_content += """
                    </ul>
                </div>
                """
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        # Guardar archivo
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(output_file)
    
    def generate_json_summary(self, ap_stats: Dict, conflicts: List[Dict]) -> str:
        """Genera resumen en formato JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"wifi_summary_{timestamp}.json"
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_aps": len(ap_stats),
            "conflicts": len(conflicts),
            "top_performers": [
                {
                    "name": name,
                    "download_speed": stats['avg_download'],
                    "ping": stats['avg_ping'],
                    "success_rate": stats['success_rate']
                }
                for name, stats in sorted(ap_stats.items(), 
                                        key=lambda x: x[1]['avg_download'] or 0, 
                                        reverse=True)[:5]
            ],
            "channel_conflicts": conflicts,
            "recommendations": self._generate_recommendations(ap_stats, conflicts)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return str(output_file)
    
    def _generate_recommendations(self, ap_stats: Dict, conflicts: List[Dict]) -> List[str]:
        """Genera recomendaciones basadas en el análisis."""
        recommendations = []
        
        # Recomendaciones por conflictos
        high_conflict_channels = [c['channel'] for c in conflicts if c['conflict_severity'] == 'ALTA']
        if high_conflict_channels:
            recommendations.append(f"Evitar canales con alta congestión: {', '.join(map(str, high_conflict_channels))}")
        
        # Recomendaciones por rendimiento
        poor_performers = [name for name, stats in ap_stats.items() if stats['success_rate'] < 50]
        if poor_performers:
            recommendations.append(f"Investigar problemas de conectividad en {len(poor_performers)} APs con baja confiabilidad")
        
        # Recomendaciones generales
        if len(conflicts) > 3:
            recommendations.append("Considerar redistribución de canales para reducir interferencia")
        
        return recommendations

# ===== main.py (MODIFICACIONES) =====
# Agregar estas líneas al final del archivo main.py:

elif cmd == "heatmap":
    # Nuevo modo: análisis de heatmap
    from services.heatmap_analyzer import HeatmapAnalyzer
    from services.report_generator import WiFiReportGenerator
    
    print("🗺️  Generando análisis de heatmap...")
    
    # Configurar días de análisis
    days = int(sys.argv[2]) if len(sys.argv) >= 3 else 7
    
    # Inicializar analizadores
    heatmap_analyzer = HeatmapAnalyzer()
    report_generator = WiFiReportGenerator()
    
    # Cargar y analizar datos
    print(f"📊 Cargando datos de los últimos {days} días...")
    historical_data = heatmap_analyzer.load_historical_data(days)
    
    if not historical_data:
        print("❌ No se encontraron datos históricos")
        sys.exit(1)
    
    print(f"✅ Cargados {len(historical_data)} registros")
    
    # Analizar rendimiento de APs
    print("🔍 Analizando rendimiento de APs...")
    ap_stats = heatmap_analyzer.analyze_ap_performance(historical_data)
    
    # Detectar conflictos de canal
    print("⚠️  Detectando conflictos de canal...")
    conflicts = heatmap_analyzer.detect_channel_conflicts(historical_data)
    
    # Generar datos de heatmap
    print("🎨 Generando datos de heatmap...")
    heatmap_data = heatmap_analyzer.generate_heatmap_data(ap_stats)
    
    # Crear visualización
    print("📊 Creando visualización...")
    heatmap_file = heatmap_analyzer.create_visual_heatmap(heatmap_data)
    
    # Generar reportes
    print("📄 Generando reportes...")
    html_report = report_generator.generate_heatmap_report(ap_stats, conflicts, heatmap_data)
    json_summary = report_generator.generate_json_summary(ap_stats, conflicts)
    
    # Mostrar resumen en consola
    print("\n" + "="*60)
    print("📊 RESUMEN DEL ANÁLISIS DE HEATMAP")
    print("="*60)
    
    print(f"📈 Total de APs analizados: {len(ap_stats)}")
    print(f"⚠️  Conflictos de canal detectados: {len(conflicts)}")
    
    if conflicts:
        print(f"\n🚨 CONFLICTOS DE CANAL:")
        for conflict in conflicts:
            print(f"  • Canal {conflict['channel']}: {conflict['aps_count']} APs - Severidad {conflict['conflict_severity']}")
    
    # Top 3 mejores redes
    top_networks = sorted(
        [(name, stats) for name, stats in ap_stats.items() if stats['avg_download']],
        key=lambda x: x[1]['avg_download'],
        reverse=True
    )[:3]
    
    if top_networks:
        print(f"\n🏆 TOP 3 REDES POR VELOCIDAD:")
        for i, (name, stats) in enumerate(top_networks, 1):
            print(f"  {i}. {name.split('(')[0][:30]} - {stats['avg_download']:.1f} Mbps")
    
    print(f"\n📊 Archivos generados:")
    print(f"  • Heatmap visual: {heatmap_file}")
    print(f"  • Reporte HTML: {html_report}")
    print(f"  • Resumen JSON: {json_summary}")
    
elif cmd == "conflicts":
    # Nuevo modo: solo detección de conflictos
    from services.heatmap_analyzer import HeatmapAnalyzer
    
    print("⚠️  Detectando conflictos de canal...")
    
    heatmap_analyzer = HeatmapAnalyzer()
    historical_data = heatmap_analyzer.load_historical_data(1)  # Solo último día
    
    if historical_data:
        conflicts = heatmap_analyzer.detect_channel_conflicts(historical_data)
        
        if conflicts:
            print(f"\n🚨 CONFLICTOS DETECTADOS ({len(conflicts)}):")
            for conflict in conflicts:
                print(f"\n📡 Canal {conflict['channel']} - Severidad: {conflict['conflict_severity']}")
                print(f"   APs en conflicto: {conflict['aps_count']}")
                print(f"   Fuerza total: {conflict['total_signal_strength']}%")
                print(f"   Recomendación: {conflict['recommendation']}")
                for ap in conflict['aps']:
                    print(f"     • {ap['ssid']} ({ap['signal']}% señal)")
        else:
            print("✅ No se detectaron conflictos de canal")
    else:
        print("❌ No se encontraron datos para analizar")

# ===== services/main_monitor.py (MODIFICACIONES) =====
# Agregar estas líneas al final de main_loop(), después de save_result():

        # NUEVO: Análisis de heatmap automático cada 10 iteraciones
        if iteration % 10 == 0:
            print(f"\n🗺️  === ANÁLISIS DE HEATMAP AUTOMÁTICO ===")
            try:
                from services.heatmap_analyzer import HeatmapAnalyzer
                
                heatmap_analyzer = HeatmapAnalyzer()
                
                # Cargar datos recientes
                recent_data = heatmap_analyzer.load_historical_data(1)
                
                if recent_data:
                    # Detectar conflictos de canal
                    conflicts = heatmap_analyzer.detect_channel_conflicts(recent_data)
                    
                    if conflicts:
                        print(f"⚠️  Conflictos detectados: {len(conflicts)}")
                        for conflict in conflicts[:3]:  # Mostrar solo los 3 más importantes
                            print(f"   🚨 Canal {conflict['channel']}: {conflict['aps_count']} APs - {conflict['conflict_severity']}")
                    else:
                        print("✅ No se detectaron conflictos de canal")
                    
                    # Análisis rápido de rendimiento
                    ap_stats = heatmap_analyzer.analyze_ap_performance(recent_data)
                    
                    # Mostrar tendencias
                    declining_aps = []
                    for name, stats in ap_stats.items():
                        if stats['success_rate'] < 70 and stats['connection_attempts'] > 2:
                            declining_aps.append((name, stats['success_rate']))
                    
                    if declining_aps:
                        print(f"📉 APs con rendimiento declinante: {len(declining_aps)}")
                        for name, rate in declining_aps[:3]:
                            print(f"   ⚠️  {name.split('(')[0][:25]}: {rate:.1f}% éxito")
                    
                else:
                    print("❌ No hay datos suficientes para análisis")
                    
            except Exception as e:
                print(f"❌ Error en análisis de heatmap: {e}")

# ===== config/config.py (MODIFICACIONES) =====
# Agregar estas configuraciones al archivo config.py:

# Configuración de Heatmap
HEATMAP_ENABLED = True
HEATMAP_ANALYSIS_INTERVAL = 10  # Cada cuántas iteraciones hacer análisis automático
HEATMAP_HISTORY_DAYS = 7  # Días de historia para análisis completo
HEATMAP_MIN_SIGNAL_THRESHOLD = 30  # Señal mínima para considerar AP
HEATMAP_CONFLICT_THRESHOLD = 2  # Mínimo de APs para considerar conflicto

# Configuración de alertas
ALERT_LOW_PERFORMANCE_THRESHOLD = 70  # % de éxito mínimo
ALERT_HIGH_PING_THRESHOLD = 100  # ms máximo aceptable
ALERT_LOW_SPEED_THRESHOLD = 10  # Mbps mínimo aceptable

# Configuración de visualización
VISUALIZATION_ENABLED = True
VISUALIZATION_DPI = 300
VISUALIZATION_STYLE = 'seaborn'  # estilo de matplotlib

# ===== services/alert_system.py =====
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict
import json
from pathlib import Path

class AlertSystem:
    """Sistema de alertas para problemas de red detectados."""
    
    def __init__(self, config_file: str = "config/alerts.json"):
        self.config_file = Path(config_file)
        self.load_config()
        self.alert_history = []
    
    def load_config(self):
        """Carga configuración de alertas."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "email_enabled": False,
                "email_smtp_server": "smtp.gmail.com",
                "email_port": 587,
                "email_username": "",
                "email_password": "",
                "email_recipients": [],
                "console_alerts": True,
                "log_alerts": True,
                "alert_cooldown": 300  # 5 minutos entre alertas del mismo tipo
            }
    
    def check_performance_alerts(self, ap_stats: Dict[str, Dict]) -> List[Dict]:
        """Verifica alertas de rendimiento."""
        alerts = []
        
        for ap_name, stats in ap_stats.items():
            # Alerta por baja tasa de éxito
            if stats['success_rate'] < ALERT_LOW_PERFORMANCE_THRESHOLD:
                alerts.append({
                    'type': 'LOW_SUCCESS_RATE',
                    'severity': 'HIGH' if stats['success_rate'] < 50 else 'MEDIUM',
                    'ap_name': ap_name,
                    'value': stats['success_rate'],
                    'threshold': ALERT_LOW_PERFORMANCE_THRESHOLD,
                    'message': f"Baja tasa de éxito en {ap_name.split('(')[0]}: {stats['success_rate']:.1f}%"
                })
            
            # Alerta por alta latencia
            if stats['avg_ping'] and stats['avg_ping'] > ALERT_HIGH_PING_THRESHOLD:
                alerts.append({
                    'type': 'HIGH_PING',
                    'severity': 'MEDIUM',
                    'ap_name': ap_name,
                    'value': stats['avg_ping'],
                    'threshold': ALERT_HIGH_PING_THRESHOLD,
                    'message': f"Alta latencia en {ap_name.split('(')[0]}: {stats['avg_ping']:.1f}ms"
                })
            
            # Alerta por baja velocidad
            if stats['avg_download'] and stats['avg_download'] < ALERT_LOW_SPEED_THRESHOLD:
                alerts.append({
                    'type': 'LOW_SPEED',
                    'severity': 'MEDIUM',
                    'ap_name': ap_name,
                    'value': stats['avg_download'],
                    'threshold': ALERT_LOW_SPEED_THRESHOLD,
                    'message': f"Baja velocidad en {ap_name.split('(')[0]}: {stats['avg_download']:.1f}Mbps"
                })
        
        return alerts
    
    def check_channel_conflict_alerts(self, conflicts: List[Dict]) -> List[Dict]:
        """Verifica alertas de conflictos de canal."""
        alerts = []
        
        for conflict in conflicts:
            if conflict['conflict_severity'] == 'ALTA':
                alerts.append({
                    'type': 'CHANNEL_CONFLICT',
                    'severity': 'HIGH',
                    'channel': conflict['channel'],
                    'aps_count': conflict['aps_count'],
                    'message': f"Conflicto ALTO en canal {conflict['channel']}: {conflict['aps_count']} APs"
                })
        
        return alerts
    
    def process_alerts(self, alerts: List[Dict]):
        """Procesa y envía alertas."""
        if not alerts:
            return
        
        # Filtrar alertas por cooldown
        new_alerts = self._filter_by_cooldown(alerts)
        
        if not new_alerts:
            return
        
        # Enviar alertas
        if self.config['console_alerts']:
            self._send_console_alerts(new_alerts)
        
        if self.config['log_alerts']:
            self._log_alerts(new_alerts)
        
        if self.config['email_enabled']:
            self._send_email_alerts(new_alerts)
        
        # Actualizar historial
        self.alert_history.extend(new_alerts)
    
    def _filter_by_cooldown(self, alerts: List[Dict]) -> List[Dict]:
        """Filtra alertas por período de cooldown."""
        current_time = datetime.now()
        filtered_alerts = []
        
        for alert in alerts:
            alert_key = f"{alert['type']}_{alert.get('ap_name', alert.get('channel', 'general'))}"
            
            # Buscar alerta reciente del mismo tipo
            recent_alert = None
            for hist_alert in reversed(self.alert_history):
                if hist_alert.get('key') == alert_key:
                    recent_alert = hist_alert
                    break
            
            if recent_alert:
                time_diff = (current_time - datetime.fromisoformat(recent_alert['timestamp'])).total_seconds()
                if time_diff < self.config['alert_cooldown']:
                    continue  # Saltar por cooldown
            
            alert['key'] = alert_key
            alert['timestamp'] = current_time.isoformat()
            filtered_alerts.append(alert)
        
        return filtered_alerts
    
    def _send_console_alerts(self, alerts: List[Dict]):
        """Muestra alertas en consola."""
        print(f"\n🚨 === ALERTAS DEL SISTEMA ({len(alerts)}) ===")
        
        for alert in alerts:
            severity_icon = "🔴" if alert['severity'] == 'HIGH' else "🟡"
            print(f"{severity_icon} {alert['message']}")
    
    def _log_alerts(self, alerts: List[Dict]):
        """Guarda alertas en archivo de log."""
        log_file = Path("logs/alerts.log")
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            for alert in alerts:
                f.write(f"{alert['timestamp']} - {alert['severity']} - {alert['message']}\n")
    
    def _send_email_alerts(self, alerts: List[Dict]):
        """Envía alertas por email."""
        if not self.config['email_recipients']:
            return
        
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.config['email_username']
            msg['To'] = ', '.join(self.config['email_recipients'])
            msg['Subject'] = f"WiFi Monitor - {len(alerts)} Alertas Detectadas"
            
            # Cuerpo del mensaje
            body = f"""
            Alertas del Sistema WiFi Monitor
            Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Alertas detectadas:
            """
            
            for alert in alerts:
                body += f"\n• {alert['severity']}: {alert['message']}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Enviar email
            server = smtplib.SMTP(self.config['email_smtp_server'], self.config['email_port'])
            server.starttls()
            server.login(self.config['email_username'], self.config['email_password'])
            server.send_message(msg)
            server.quit()
            
            print(f"📧 Alertas enviadas por email a {len(self.config['email_recipients'])} destinatarios")
            
        except Exception as e:
            print(f"❌ Error enviando alertas por email: {e}")

# ===== services/trend_analyzer.py =====
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from collections import defaultdict

class TrendAnalyzer:
    """Analiza tendencias en el rendimiento de la red."""
    
    def __init__(self):
        self.trend_data = defaultdict(list)
    
    def analyze_performance_trends(self, historical_data: List[Dict]) -> Dict:
        """Analiza tendencias de rendimiento a lo largo del tiempo."""
        if len(historical_data) < 5:
            return {"error": "Datos insuficientes para análisis de tendencias"}
        
        # Organizar datos por AP
        ap_timeline = defaultdict(list)
        
        for entry in historical_data:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            networks = entry.get('all_networks_tested', [])
            
            for network in networks:
                ssid = network.get('ssid', 'Unknown')
                bssid = network.get('network_info', {}).get('bssid', 'Unknown')
                ap_key = f"{ssid}_{bssid}"
                
                if network.get('connection_successful', False):
                    test_results = network.get('test_results', {})
                    
                    ap_timeline[ap_key].append({
                        'timestamp': timestamp,
                        'signal': network.get('network_info', {}).get('signal_percentage', 0),
                        'ping': test_results.get('ping', {}).get('avg_time'),
                        'download': test_results.get('speedtest', {}).get('download', {}).get('bandwidth', 0) / 1_000_000 if test_results.get('speedtest', {}).get('download') else None,
                        'success': 1
                    })
        
        # Calcular tendencias
        trends = {}
        for ap_key, timeline in ap_timeline.items():
            if len(timeline) >= 3:
                trends[ap_key] = self._calculate_trend_metrics(timeline)
        
        return {
            'trends_by_ap': trends,
            'overall_trend': self._calculate_overall_trend(trends),
            'predictions': self._generate_predictions(trends)
        }
    
    def _calculate_trend_metrics(self, timeline: List[Dict]) -> Dict:
        """Calcula métricas de tendencia para un AP específico."""
        # Ordenar por timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        # Extraer series temporales
        timestamps = [item['timestamp'] for item in timeline]
        signals = [item['signal'] for item in timeline if item['signal'] > 0]
        pings = [item['ping'] for item in timeline if item['ping'] is not None]
        downloads = [item['download'] for item in timeline if item['download'] is not None]
        
        trends = {}
        
        # Tendencia de señal
        if len(signals) >= 3:
            trends['signal_trend'] = self._calculate_linear_trend(signals)
        
        # Tendencia de ping
        if len(pings) >= 3:
            trends['ping_trend'] = self._calculate_linear_trend(pings)
        
        # Tendencia de velocidad
        if len(downloads) >= 3:
            trends['download_trend'] = self._calculate_linear_trend(downloads)
        
        # Estabilidad general
        trends['stability_score'] = self._calculate_stability_score(timeline)
        
        return trends
    
    def _calculate_linear_trend(self, values: List[float]) -> Dict:
        """Calcula tendencia lineal simple."""
        if len(values) < 2:
            return {'slope': 0, 'direction': 'stable'}
        
        x = np.arange(len(values))
        y = np.array(values)
        
        # Regresión lineal simple
        slope = np.polyfit(x, y, 1)[0]
        
        # Determinar dirección
        if abs(slope) < 0.1:
            direction = 'stable'
        elif slope > 0:
            direction = 'improving'
        else:
            direction = 'declining'
        
        return {
            'slope': slope,
            'direction': direction,
            'magnitude': abs(slope),
            'confidence': self._calculate_trend_confidence(x, y, slope)
        }
    
    def _calculate_trend_confidence(self, x: np.ndarray, y: np.ndarray, slope: float) -> float:
        """Calcula confianza en la tendencia."""
        if len(x) < 3:
            return 0.0
        
        # Calcular R²
        predicted = slope * x + np.mean(y)
        ss_res = np.sum((y - predicted) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        
        if ss_tot == 0:
            return 0.0
        
        r_squared = 1 - (ss_res / ss_tot)
        return max(0.0, min(1.0, r_squared))
    
    def _calculate_stability_score(self, timeline: List[Dict]) -> float:
        """Calcula puntuación de estabilidad."""
        if len(timeline) < 3:
            return 0.0
        
        # Calcular variabilidad de métricas clave
        signals = [item['signal'] for item in timeline if item['signal'] > 0]
        pings = [item['ping'] for item in timeline if item['ping'] is not None]
        
        stability_score = 100.0
        
        # Penalizar alta variabilidad
        if signals:
            signal_cv = np.std(signals) / np.mean(signals) if np.mean(signals) > 0 else 0
            stability_score -= signal_cv * 20
        
        if pings:
            ping_cv = np.std(pings) / np.mean(pings) if np.mean(pings) > 0 else 0
            stability_score -= ping_cv * 30
        
        return max(0.0, min(100.0, stability_score))
    
    def _calculate_overall_trend(self, trends: Dict) -> Dict:
        """Calcula tendencia general del sistema."""
        if not trends:
            return {'status': 'no_data'}
        
        improving_count = 0
        declining_count = 0
        stable_count = 0
        
        for ap_trends in trends.values():
            for metric in ['signal_trend', 'ping_trend', 'download_trend']:
                if metric in ap_trends:
                    direction = ap_trends[metric]['direction']
                    if direction == 'improving':
                        improving_count += 1
                    elif direction == 'declining':
                        declining_count += 1
                    else:
                        stable_count += 1
        
        total_metrics = improving_count + declining_count + stable_count
        
        if total_metrics == 0:
            return {'status': 'no_data'}
        
        return {
            'status': 'calculated',
            'improving_percentage': (improving_count / total_metrics) * 100,
            'declining_percentage': (declining_count / total_metrics) * 100,
            'stable_percentage': (stable_count / total_metrics) * 100,
            'overall_direction': self._determine_overall_direction(improving_count, declining_count, stable_count)
        }
    
    def _determine_overall_direction(self, improving: int, declining: int, stable: int) -> str:
        """Determina dirección general del sistema."""
        if improving > declining * 1.5:
            return 'improving'
        elif declining > improving * 1.5:
            return 'declining'
        else:
            return 'stable'
    
    def _generate_predictions(self, trends: Dict) -> Dict:
        """Genera predicciones basadas en tendencias."""
        predictions = {}
        
        for ap_key, ap_trends in trends.items():
            ap_predictions = {}
            
            # Predicción de señal
            if 'signal_trend' in ap_trends:
                trend = ap_trends['signal_trend']
                if trend['direction'] == 'declining' and trend['confidence'] > 0.7:
                    ap_predictions['signal_warning'] = "Señal en declive, posible problema de conexión"
            
            # Predicción de rendimiento
            if 'download_trend' in ap_trends:
                trend = ap_trends['download_trend']
                if trend['direction'] == 'declining' and trend['confidence'] > 0.6:
                    ap_predictions['performance_warning'] = "Velocidad en declive, posible congestión"
            
            # Predicción de estabilidad
            stability = ap_trends.get('stability_score', 100)
            if stability < 60:
                ap_predictions['stability_warning'] = "Conexión inestable, considerar investigación"
            
            if ap_predictions:
                predictions[ap_key] = ap_predictions
        
        return predictions

# ===== Uso en main.py (COMANDO ADICIONAL) =====
elif cmd == "trends":
    # Nuevo modo: análisis de tendencias
    from services.heatmap_analyzer import HeatmapAnalyzer
    from services.trend_analyzer import TrendAnalyzer
    from services.alert_system import AlertSystem
    
    print("📈 Analizando tendencias de rendimiento...")
    
    days = int(sys.argv[2]) if len(sys.argv) >= 3 else 3
    
    # Cargar datos
    heatmap_analyzer = HeatmapAnalyzer()
    trend_analyzer = TrendAnalyzer()
    alert_system = AlertSystem()
    
    historical_data = heatmap_analyzer.load_historical_data(days)
    
    if not historical_data:
        print("❌ No se encontraron datos históricos suficientes")
        sys.exit(1)
    
    # Analizar tendencias
    trend_analysis = trend_analyzer.analyze_performance_trends(historical_data)
    
    if 'error' in trend_analysis:
        print(f"❌ {trend_analysis['error']}")
        sys.exit(1)
    
    # Mostrar resultados
    print(f"\n📊 === ANÁLISIS DE TENDENCIAS ({days} días) ===")
    
    overall = trend_analysis['overall_trend']
    if overall['status'] == 'calculated':
        print(f"📈 Tendencia general: {overall['overall_direction'].upper()}")
        print(f"   Mejorando: {overall['improving_percentage']:.1f}%")
        print(f"   Declinando: {overall['declining_percentage']:.1f}%")
        print(f"   Estable: {overall['stable_percentage']:.1f}%")
    
    # Mostrar predicciones
    predictions = trend_analysis['predictions']
    if predictions:
        print(f"\n🔮 === PREDICCIONES Y ALERTAS ===")
        for ap_key, pred in predictions.items():
            ap_name = ap_key.split('_')[0]
            print(f"\n⚠️  {ap_name}:")
            for warning_type, warning_msg in pred.items():
                print(f"   • {warning_msg}")
    
    # Análisis de rendimiento para alertas
    ap_stats = heatmap_analyzer.analyze_ap_performance(historical_data)
    performance_alerts = alert_system.check_performance_alerts(ap_stats)
    
    if performance_alerts:
        alert_system.process_alerts(performance_alerts)
    
    print(f"\n✅ Análisis de tendencias completado")

# ===== Instrucciones de uso actualizadas =====
print("Uso:")
print("  python main.py analyzer                    - Modo analizador interactivo")
print("  python main.py scan                       - Escaneo simple de redes")
print("  python main.py test <ssid> [pass] [dur]   - Prueba red específica")
print("  python main.py heatmap [days]             - Análisis de heatmap (def: 7 días)")
print("  python main.py conflicts                  - Detectar conflictos de canal")
print("  python main.py trends [days]              - Análisis de tendencias (def: 3 días)")
print("  python main.py                           - Monitoreo continuo (modo original)")

# ===== requirements.txt (DEPENDENCIAS ADICIONALES) =====
"""
matplotlib>=3.5.0
seaborn>=0.11.0
numpy>=1.21.0
pandas>=1.3.0
"""