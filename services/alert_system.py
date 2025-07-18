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