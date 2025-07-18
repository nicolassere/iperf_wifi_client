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

def precision_heatmap_mode():
    """Modo de mapeo de calor de precisión con ubicación GPS."""
    from services.enhanced_heatmap_analyzer import EnhancedWiFiHeatmapAnalyzer
    
    print("🎯 === MODO HEATMAP DE PRECISIÓN ===")
    print("Este modo recolecta mediciones WiFi con ubicación GPS precisa")
    print("para análisis de variación de señal por metro.")
    print()
    
    analyzer = EnhancedWiFiHeatmapAnalyzer()
    wifi_scanner = WiFiAnalyzer()
    
    while True:
        print("\n📋 === MENÚ HEATMAP DE PRECISIÓN ===")
        print("1. 📍 Recolectar medición en ubicación actual")
        print("2. 🗺️  Generar mapa de calor de precisión")
        print("3. 📊 Analizar variación de señal")
        print("4. 📂 Exportar datos de medición")
        print("5. 📥 Importar datos de medición")
        print("6. 🔄 Recolección automática (grid)")
        print("7. 📈 Ver estadísticas de medición")
        print("8. 🚪 Salir")
        
        choice = input("\nSeleccione una opción (1-8): ").strip()
        
        if choice == "1":
            # Recolectar medición manual
            print("\n📡 Escaneando redes WiFi...")
            try:
                networks = wifi_scanner.scan_networks()
                if not networks:
                    print("❌ No se encontraron redes WiFi")
                    continue
                
                print(f"✅ Encontradas {len(networks)} redes")
                
                # Convertir formato para compatibilidad
                converted_networks = []
                for network in networks:
                    converted_networks.append({
                        'ssid': network.get('ssid', 'Unknown'),
                        'bssid': network.get('bssid', 'Unknown'),
                        'signal_percentage': network.get('signal_percentage', 0),
                        'channel': network.get('channel', 0),
                        'frequency': network.get('frequency', 0),
                        'authentication': network.get('authentication', 'Unknown')
                    })
                
                measurement = analyzer.collect_measurement_at_location(converted_networks)
                print(f"✅ Medición recolectada exitosamente")
                
                # Mostrar resumen
                print(f"📍 Ubicación: {measurement['location'][0]:.6f}, {measurement['location'][1]:.6f}")
                print(f"📱 Redes detectadas: {len(measurement['networks'])}")
                
                # Mostrar las 3 redes más fuertes
                top_networks = sorted(
                    measurement['networks'].items(),
                    key=lambda x: x[1]['signal_strength'],
                    reverse=True
                )[:3]
                
                print("\n📶 Top 3 redes por señal:")
                for i, (net_name, net_data) in enumerate(top_networks, 1):
                    ssid = net_name.split('_')[0]
                    print(f"  {i}. {ssid}: {net_data['signal_strength']}%")
                
            except Exception as e:
                print(f"❌ Error recolectando medición: {e}")
        
        elif choice == "2":
            # Generar mapa de calor
            print("\n🗺️  Generando mapa de calor de precisión...")
            
            measurements = analyzer.location_service.measurement_points
            if not measurements:
                print("❌ No hay mediciones disponibles. Recolecte algunas primero.")
                continue
            
            # Mostrar redes disponibles
            all_networks = set()
            for measurement in measurements:
                wifi_data = measurement['wifi_data']
                for net_key in wifi_data.get('networks', {}):
                    ssid = net_key.split('_')[0]
                    all_networks.add(ssid)
            
            print(f"\n📡 Redes disponibles ({len(all_networks)}):")
            network_list = list(all_networks)
            for i, network in enumerate(network_list, 1):
                print(f"  {i}. {network}")
            
            try:
                selection = input(f"\nSeleccione red (1-{len(network_list)}) o escriba nombre: ").strip()
                
                if selection.isdigit() and 1 <= int(selection) <= len(network_list):
                    selected_network = network_list[int(selection) - 1]
                else:
                    selected_network = selection
                
                print(f"🎯 Generando mapa para: {selected_network}")
                
                heatmap_file = analyzer.create_precision_heatmap(selected_network)
                print(f"✅ Mapa generado: {heatmap_file}")
                
                # Mostrar estadísticas básicas
                network_measurements = []
                for measurement in measurements:
                    wifi_data = measurement['wifi_data']
                    for net_key, net_data in wifi_data.get('networks', {}).items():
                        if selected_network in net_key:
                            network_measurements.append(net_data['signal_strength'])
                
                if network_measurements:
                    print(f"\n📊 Estadísticas de {selected_network}:")
                    print(f"   Mediciones: {len(network_measurements)}")
                    print(f"   Señal min: {min(network_measurements)}%")
                    print(f"   Señal max: {max(network_measurements)}%")
                    print(f"   Señal prom: {sum(network_measurements)/len(network_measurements):.1f}%")
                
            except Exception as e:
                print(f"❌ Error generando mapa: {e}")
        
        elif choice == "3":
            # Analizar variación de señal
            print("\n📈 Analizando variación de señal...")
            
            measurements = analyzer.location_service.measurement_points
            if len(measurements) < 2:
                print("❌ Necesita al menos 2 mediciones para análisis")
                continue
            
            # Mostrar redes disponibles
            all_networks = set()
            for measurement in measurements:
                wifi_data = measurement['wifi_data']
                for net_key in wifi_data.get('networks', {}):
                    ssid = net_key.split('_')[0]
                    all_networks.add(ssid)
            
            print(f"\n📡 Redes disponibles:")
            network_list = list(all_networks)
            for i, network in enumerate(network_list, 1):
                print(f"  {i}. {network}")
            
            try:
                selection = input(f"\nSeleccione red (1-{len(network_list)}): ").strip()
                
                if selection.isdigit() and 1 <= int(selection) <= len(network_list):
                    selected_network = network_list[int(selection) - 1]
                    
                    analysis = analyzer.analyze_signal_variation(selected_network)
                    
                    if 'error' in analysis:
                        print(f"❌ {analysis['error']}")
                        continue
                    
                    print(f"\n📊 === ANÁLISIS DE VARIACIÓN: {selected_network} ===")
                    print(f"Mediciones totales: {analysis['total_measurements']}")
                    
                    stats = analysis['signal_stats']
                    print(f"\n📶 Estadísticas de señal:")
                    print(f"   Mínima: {stats['min']}%")
                    print(f"   Máxima: {stats['max']}%")
                    print(f"   Promedio: {stats['avg']:.1f}%")
                    print(f"   Desviación estándar: {stats['std_dev']:.1f}%")
                    print(f"   Rango: {stats['max'] - stats['min']}%")
                    
                    if 'avg_signal_gradient' in analysis:
                        print(f"\n📏 Gradiente de señal:")
                        print(f"   Promedio: {analysis['avg_signal_gradient']:.4f}% por metro")
                        
                        # Interpretación del gradiente
                        gradient = analysis['avg_signal_gradient']
                        if gradient > 2.0:
                            print("   🔴 Gradiente ALTO - Señal muy variable con la posición")
                        elif gradient > 1.0:
                            print("   🟡 Gradiente MEDIO - Señal moderadamente variable")
                        else:
                            print("   🟢 Gradiente BAJO - Señal relativamente estable")
                    
                    # Mostrar algunos ejemplos de variación
                    if analysis['distance_analysis']:
                        print(f"\n📏 Ejemplos de variación por distancia:")
                        for i, example in enumerate(analysis['distance_analysis'][:5]):
                            print(f"   {i+1}. {example['distance_meters']}m → {example['signal_difference']}% de diferencia")
                
            except Exception as e:
                print(f"❌ Error en análisis: {e}")
        
        elif choice == "4":
            # Exportar datos
            try:
                filename = input("Nombre del archivo (default: wifi_measurements.json): ").strip()
                if not filename:
                    filename = "wifi_measurements.json"
                
                export_path = analyzer.export_measurement_data(filename)
                print(f"✅ Datos exportados a: {export_path}")
                
                # Mostrar resumen
                count = len(analyzer.location_service.measurement_points)
                print(f"📊 Exportadas {count} mediciones")
                
            except Exception as e:
                print(f"❌ Error exportando: {e}")
        
        elif choice == "5":
            # Importar datos
            try:
                filename = input("Nombre del archivo a importar: ").strip()
                if not filename:
                    print("❌ Nombre de archivo requerido")
                    continue
                
                count = analyzer.import_measurement_data(filename)
                print(f"✅ Importadas {count} mediciones")
                
            except Exception as e:
                print(f"❌ Error importando: {e}")
        
        elif choice == "6":
            # Recolección automática en grid
            print("\n🔄 Recolección automática en grid")
            print("⚠️  Esta función requiere movimiento manual a cada punto")
            
            try:
                # Obtener ubicación actual como centro
                current_location = analyzer.location_service.get_current_location()
                if not current_location:
                    print("❌ No se pudo obtener ubicación actual")
                    continue
                
                grid_size = int(input("Tamaño de grid en metros (default: 5): ").strip() or "5")
                grid_points = int(input("Puntos por lado (default: 3): ").strip() or "3")
                
                grid_coords = analyzer.create_measurement_grid(current_location, grid_size, grid_points)
                
                print(f"\n📍 Grid generado: {len(grid_coords)} puntos")
                print(f"Centro: {current_location[0]:.6f}, {current_location[1]:.6f}")
                print(f"Área: {grid_size * grid_points}m x {grid_size * grid_points}m")
                
                print("\n🚶 Instrucciones:")
                print("1. Muévase a cada punto mostrado")
                print("2. Presione Enter para medir en cada ubicación")
                print("3. Presione 'q' para salir")
                
                for i, coord in enumerate(grid_coords, 1):
                    print(f"\n📍 Punto {i}/{len(grid_coords)}: {coord[0]:.6f}, {coord[1]:.6f}")
                    
                    user_input = input("Presione Enter para medir (o 'q' para salir): ").strip()
                    if user_input.lower() == 'q':
                        break
                    
                    # Simular que estamos en esa ubicación
                    # En implementación real, verificaría GPS actual
                    print("📡 Midiendo...")
                    networks = wifi_scanner.scan_networks()
                    
                    if networks:
                        # Forzar ubicación específica para el grid
                        original_method = analyzer.location_service.get_current_location
                        analyzer.location_service.get_current_location = lambda: coord
                        
                        converted_networks = []
                        for network in networks:
                            converted_networks.append({
                                'ssid': network.get('ssid', 'Unknown'),
                                'bssid': network.get('bssid', 'Unknown'),
                                'signal_percentage': network.get('signal_percentage', 0),
                                'channel': network.get('channel', 0),
                                'frequency': network.get('frequency', 0),
                                'authentication': network.get('authentication', 'Unknown')
                            })
                        
                        measurement = analyzer.collect_measurement_at_location(converted_networks)
                        
                        # Restaurar método original
                        analyzer.location_service.get_current_location = original_method
                        
                        print(f"✅ Medición {i} completada")
                    else:
                        print("❌ No se encontraron redes")
                
                print(f"\n✅ Recolección en grid completada")
                
            except Exception as e:
                print(f"❌ Error en recolección automática: {e}")
        
        elif choice == "7":
            # Ver estadísticas
            measurements = analyzer.location_service.measurement_points
            
            if not measurements:
                print("❌ No hay mediciones disponibles")
                continue
            
            print(f"\n📊 === ESTADÍSTICAS DE MEDICIÓN ===")
            print(f"Total de mediciones: {len(measurements)}")
            
            # Contar redes únicas
            all_networks = set()
            total_detections = 0
            
            for measurement in measurements:
                wifi_data = measurement['wifi_data']
                networks = wifi_data.get('networks', {})
                total_detections += len(networks)
                
                for net_key in networks:
                    ssid = net_key.split('_')[0]
                    all_networks.add(ssid)
            
            print(f"Redes únicas detectadas: {len(all_networks)}")
            print(f"Total de detecciones: {total_detections}")
            print(f"Promedio de redes por medición: {total_detections/len(measurements):.1f}")
            
            # Mostrar rango de fechas
            if measurements:
                timestamps = [m['timestamp'] for m in measurements]
                print(f"Período: {min(timestamps)} - {max(timestamps)}")
            
            # Mostrar área cubierta
            if len(measurements) > 1:
                lats = [m['location'][0] for m in measurements]
                lons = [m['location'][1] for m in measurements]
                
                lat_range = max(lats) - min(lats)
                lon_range = max(lons) - min(lons)
                
                # Convertir a metros aproximadamente
                lat_meters = lat_range * 111320  # grados a metros
                lon_meters = lon_range * 111320 * 0.64  # ajuste por latitud (aprox para Uruguay)
                
                print(f"\n📏 Área cubierta:")
                print(f"   Latitud: {lat_range:.6f}° ({lat_meters:.1f}m)")
                print(f"   Longitud: {lon_range:.6f}° ({lon_meters:.1f}m)")
            
            # Top 5 redes por detecciones
            network_counts = {}
            for measurement in measurements:
                wifi_data = measurement['wifi_data']
                for net_key in wifi_data.get('networks', {}):
                    ssid = net_key.split('_')[0]
                    network_counts[ssid] = network_counts.get(ssid, 0) + 1
            
            if network_counts:
                print(f"\n📶 Top 5 redes más detectadas:")
                top_networks = sorted(network_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                for i, (ssid, count) in enumerate(top_networks, 1):
                    percentage = (count / len(measurements)) * 100
                    print(f"   {i}. {ssid}: {count} detecciones ({percentage:.1f}%)")
        
        elif choice == "8":
            print("🚪 Saliendo del modo heatmap de precisión...")
            break
        
        else:
            print("❌ Opción inválida. Seleccione 1-8.")

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

        elif cmd == "precision":
            # NUEVO: Modo heatmap de precisión con GPS
            precision_heatmap_mode()

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
            print("  python main.py geomap [days]              - Mapa de calor geográfico")
            print("  python main.py precision                  - Heatmap de precisión con GPS")
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