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
                        <td>{stats['avg_ping']:.1f}</td>
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