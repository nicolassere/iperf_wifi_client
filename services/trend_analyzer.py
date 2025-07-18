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