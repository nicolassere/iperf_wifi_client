import subprocess
import json
import time
import os
from datetime import datetime
from services.wifi_analyzer import WiFiAnalyzer


# Funciones prueba de red
def check_iperf_server():
    """Verifica si hay un servidor iperf3 corriendo."""
    try:
        result = subprocess.run(
            ["netstat", "-an"], 
            capture_output=True, 
            text=True,
            timeout=10
        )
        return ":5201" in result.stdout
    except:
        return False

def get_wifi_info():
    """Obtiene info de la red WiFi usando netsh (función original mejorada)."""
    analyzer = WiFiAnalyzer()
    current_info = analyzer.get_current_connection_info()
    
    if "error" in current_info:
        return current_info
    
    return current_info

def run_ping(target="8.8.8.8", count=4):
    """Ejecuta ping y extrae métricas básicas."""
    try:
        result = subprocess.run(
            ["ping", "-n", str(count), target], 
            capture_output=True, 
            text=True,
            timeout=30
        )
        
        # Extraer métricas básicas del ping
        lines = result.stdout.splitlines()
        ping_times = []
        packet_loss = "0%"
        
        for line in lines:
            if "tiempo=" in line:
                try:
                    time_part = line.split("tiempo=")[1].split("ms")[0]
                    ping_times.append(int(time_part))
                except:
                    pass
            elif "perdidos" in line:
                try:
                    packet_loss = line.split("(")[1].split(")")[0]
                except:
                    pass
        
        return {
            "raw_output": result.stdout,
            "avg_time": sum(ping_times) / len(ping_times) if ping_times else 0,
            "min_time": min(ping_times) if ping_times else 0,
            "max_time": max(ping_times) if ping_times else 0,
            "packet_loss": packet_loss
        }
    except Exception as e:
        return {"error": f"Error en ping: {str(e)}"}

def run_traceroute(target="8.8.8.8"):
    """Ejecuta traceroute con timeout."""
    try:
        result = subprocess.run(
            ["tracert", target], 
            capture_output=True, 
            text=True,
            timeout=60
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "Traceroute timeout después de 60 segundos"
    except Exception as e:
        return f"Error en traceroute: {str(e)}"

def run_speedtest(server_id=40741):
    """Ejecuta speedtest contra un servidor específico (ej. ANTEL)."""
    speedtest_path = "C:\\Users\\Usuario\\speedtest.exe"  

    try:
        # Verificar si speedtest.exe está disponible
        subprocess.run(
            [speedtest_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Ejecutar speedtest contra el servidor especificado
        result = subprocess.run(
            [speedtest_path, "--server-id", str(server_id), "--format=json"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
                try:
                    print("entro aca")
                    parsed = json.loads(result.stdout)
                    return parsed
                except json.JSONDecodeError:
                    return {
                        "error": "No se pudo parsear el JSON de speedtest",
                        "raw_output": result.stdout
                    }
        else:
            print("entro aca 2")
            return {"error": "speedtest falló", "stderr": result.stderr}

    except subprocess.TimeoutExpired:
        return {"error": "Speedtest timeout después de 2 minutos"}
    except FileNotFoundError:
        return {"error": "speedtest.exe no está instalado o la ruta es incorrecta"}
    except json.JSONDecodeError:
        return {"error": "No se pudo parsear el JSON de speedtest"}
    except Exception as e:
        return {"error": f"Error en speedtest: {str(e)}"}
