
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import sys
from services.wifi_analyzer import WiFiAnalyzer
from services.network_tester import test_single_network
from services.network_tester import test_single_network
from services.wifi_interface import wifi_analyzer_mode, display_wifi_summary
from services.main_monitor import main_loop
from config.config import *



if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd == "analyzer":
            # Modo analizador interactivo
            wifi_analyzer_mode()
        elif cmd == "test" and len(sys.argv) >= 3:
            # Prueba de red específica
            ssid = sys.argv[2]
            password = sys.argv[3] if len(sys.argv) >= 4 else None
            duration = int(sys.argv[4]) if len(sys.argv) >= 5 else 60
            test_single_network(ssid, password, duration)
        elif cmd == "scan":
            # Escaneo simple
            analyzer = WiFiAnalyzer()
            display_wifi_summary(analyzer)

        elif cmd == "heatmap":
            # Nuevo modo: análisis de heatmap con reporte
            from services.heatmap_analyzer import HeatmapAnalyzer
            from services.report_generator import WiFiReportGenerator
            
            print("🗺️  Generando análisis de heatmap...")
            
            days = int(sys.argv[2]) if len(sys.argv) >= 3 else 7
            
            # Cargar datos
            heatmap_analyzer = HeatmapAnalyzer()
            report_generator = WiFiReportGenerator()
            
            historical_data = heatmap_analyzer.load_historical_data(days)
            
            if not historical_data:
                print("❌ No se encontraron datos históricos suficientes")
                sys.exit(1)
            
            # Analizar rendimiento
            ap_stats = heatmap_analyzer.analyze_ap_performance(historical_data)
            
            # Detectar conflictos
            conflicts = heatmap_analyzer.detect_channel_conflicts(historical_data)
            
            # Generar datos de heatmap
            heatmap_data = heatmap_analyzer.generate_heatmap_data(ap_stats)
            
            # Generar reportes
            print("📄 Generando reporte HTML...")
            html_report = report_generator.generate_heatmap_report(
                ap_stats, conflicts, heatmap_data
            )
            
            print("📄 Generando resumen JSON...")
            json_report = report_generator.generate_json_summary(ap_stats, conflicts)
            
            # Mostrar resultados en consola
            print(f"\n📊 === ANÁLISIS DE HEATMAP ({days} días) ===")
            print(f"Total de APs analizados: {len(ap_stats)}")
            print(f"Conflictos detectados: {len(conflicts)}")
            
            if conflicts:
                print(f"\n⚠️  === CONFLICTOS DE CANAL ===")
                for conflict in conflicts:
                    print(f"Canal {conflict['channel']}: {conflict['aps_count']} APs - Severidad {conflict['conflict_severity']}")
            
            print(f"\n📊 === TOP 5 REDES POR RENDIMIENTO ===")
            top_performers = sorted(
                [(name, stats) for name, stats in ap_stats.items() if stats['avg_download']],
                key=lambda x: x[1]['avg_download'],
                reverse=True
            )[:5]
            
            for name, stats in top_performers:
                print(f"{name.split('(')[0]}: {stats['avg_download']:.1f} Mbps, {stats['success_rate']:.1f}% éxito")
            
            print(f"\n📁 Reportes generados:")
            print(f"  HTML: {html_report}")
            print(f"  JSON: {json_report}")

        elif cmd == "geomap":
            # Nuevo modo: mapa de calor geográfico
            from services.heatmap_analyzer import HeatmapAnalyzer
            from services.geographic_heatmap import GeographicHeatmapGenerator
            
            print("🗺️  Generando mapa de calor geográfico...")
            
            days = int(sys.argv[2]) if len(sys.argv) >= 3 else 7
            
            # Cargar datos históricos
            heatmap_analyzer = HeatmapAnalyzer()
            geo_heatmap = GeographicHeatmapGenerator()
            
            historical_data = heatmap_analyzer.load_historical_data(days)
            
            if not historical_data:
                print("❌ No se encontraron datos históricos suficientes")
                sys.exit(1)
            
            # Analizar rendimiento
            ap_stats = heatmap_analyzer.analyze_ap_performance(historical_data)
            
            # Generar mapas geográficos
            signal_map = geo_heatmap.generate_signal_heatmap(ap_stats)
            speed_map = geo_heatmap.generate_performance_heatmap(ap_stats)
            
            print(f"\n🗺️  Mapas generados:")
            print(f"   📶 Señal: {signal_map}")
            print(f"   🚀 Velocidad: {speed_map}")
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
        else:
            print("Uso:")
            print("  python main.py analyzer                    - Modo analizador interactivo")
            print("  python main.py scan                       - Escaneo simple de redes")
            print("  python main.py test <ssid> [pass] [dur]   - Prueba red específica")
            print("  python main.py heatmap [days]             - Análisis de heatmap (def: 7 días)")
            print("  python main.py conflicts                  - Detectar conflictos de canal")
            print("  python main.py trends [days]              - Análisis de tendencias (def: 3 días)")
            print("  python main.py                           - Monitoreo continuo (modo original)")
            
    else:
        # Modo original mejorado
        try:
            main_loop()
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoreo detenido por el usuario")
        except Exception as e:
            print(f"\n\n💥 Error fatal: {e}")