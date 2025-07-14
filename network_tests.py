# network_tests.py
"""
Funciones para ejecutar pruebas de red (ping, traceroute, speedtest, iperf3)
"""

import subprocess
import json
import os
import time
from config import (
    IPERF_PATH, IPERF_SERVER, PING_TIMEOUT, TRACEROUTE_TIMEOUT,
    SPEEDTEST_TIMEOUT, IPERF_TIMEOUT
)


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


def run_ping(target="8.8.8.8", count=4):
    """Ejecuta ping y extrae métricas básicas."""
    try:
        result = subprocess.run(
            ["ping", "-n", str(count), target], 
            capture_output=True, 
            text=True,
            timeout=PING_TIMEOUT
        )
        
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
            timeout=TRACEROUTE_TIMEOUT
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "Traceroute timeout después de 60 segundos"
    except Exception as e:
        return f"Error en traceroute: {str(e)}"


def run_speedtest():
    """Ejecuta speedtest-cli si está disponible."""
    try:
        # Verificar si speedtest-cli está disponible
        subprocess.run(["speedtest-cli", "--version"], 
                      capture_output=True, 
                      text=True, 
                      timeout=5)
        
        result = subprocess.run(
            ["speedtest-cli", "--json"], 
            capture_output=True, 
            text=True,
            timeout=SPEEDTEST_TIMEOUT
        )
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"error": "speedtest-cli falló", "stderr": result.stderr}
            
    except subprocess.TimeoutExpired:
        return {"error": "Speedtest timeout después de 2 minutos"}
    except FileNotFoundError:
        return {"error": "speedtest-cli no está instalado"}
    except json.JSONDecodeError:
        return {"error": "No se pudo parsear el JSON de speedtest-cli"}
    except Exception as e:
        return {"error": f"Error en speedtest: {str(e)}"}


def run_iperf_external(path=IPERF_PATH, server_ip=IPERF_SERVER):
    """Ejecuta iperf3 con manejo de errores mejorado."""
    
    if not os.path.exists(path):
        return {"error": f"iperf3 no encontrado en {path}"}
    
    if not check_iperf_server():
        return {"error": "No hay servidor iperf3 corriendo en el puerto 5201"}
    
    try:
        methods = [
            {
                "args": f'"{path}" -c {server_ip} -J -t 10',
                "shell": True,
                "cwd": os.path.dirname(path)
            },
            {
                "args": [path, "-c", server_ip, "-J", "-t", "10"],
                "shell": False,
                "cwd": os.path.dirname(path)
            },
            {
                "args": ["iperf3.exe", "-c", server_ip, "-J", "-t", "10"],
                "shell": False,
                "cwd": os.path.dirname(path)
            }
        ]
        
        for i, method in enumerate(methods):
            try:
                print(f"  Intentando método {i+1}/3...")
                result = subprocess.run(
                    method["args"],
                    capture_output=True,
                    text=True,
                    timeout=IPERF_TIMEOUT,
                    shell=method["shell"],
                    cwd=method["cwd"],
                    creationflags=subprocess.CREATE_NO_WINDOW if not method["shell"] else 0
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    print(f"  ✓ Método {i+1} exitoso")
                    return json.loads(result.stdout)
                else:
                    print(f"  ✗ Método {i+1} falló: código {result.returncode}")
                    if i == len(methods) - 1:
                        return {
                            "error": f"Todos los métodos fallaron. Último error: código {result.returncode}",
                            "stderr": result.stderr,
                            "stdout": result.stdout
                        }
                    
            except json.JSONDecodeError:
                print(f"  ✗ Método {i+1}: Error parseando JSON")
                if i == len(methods) - 1:
                    return {
                        "error": "No se pudo parsear JSON de iperf3",
                        "raw_output": result.stdout
                    }
                continue
            except Exception as e:
                print(f"  ✗ Método {i+1}: {str(e)}")
                if i == len(methods) - 1:
                    return {"error": f"Error ejecutando iperf3: {str(e)}"}
                continue
        
    except subprocess.TimeoutExpired:
        return {"error": "iperf3 timeout después de 30 segundos"}
    except Exception as e:
        return {"error": f"Error general ejecutando iperf3: {str(e)}"}


def start_iperf_server(path=IPERF_PATH):
    """Inicia servidor iperf3 si no está corriendo."""
    if check_iperf_server():
        print("✓ Servidor iperf3 ya está corriendo")
        return True
    
    try:
        print("Iniciando servidor iperf3...")
        subprocess.Popen([path, "-s"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(2)
        
        if check_iperf_server():
            print("✓ Servidor iperf3 iniciado correctamente")
            return True
        else:
            print("✗ No se pudo iniciar el servidor iperf3")
            return False
            
    except Exception as e:
        print(f"✗ Error iniciando servidor iperf3: {e}")
        return False


def diagnose_iperf3():
    """Diagnóstico completo de iperf3."""
    print("\n=== DIAGNÓSTICO IPERF3 ===")
    
    # 1. Verificar archivo
    print(f"1. Verificando archivo: {IPERF_PATH}")
    if os.path.exists(IPERF_PATH):
        print(f"   ✓ Archivo existe")
        print(f"   ✓ Tamaño: {os.path.getsize(IPERF_PATH)} bytes")
    else:
        print(f"   ✗ Archivo NO existe")
        return
    
    # 2. Verificar permisos
    print(f"2. Verificando permisos")
    if os.access(IPERF_PATH, os.X_OK):
        print(f"   ✓ Permisos de ejecución OK")
    else:
        print(f"   ✗ Sin permisos de ejecución")
    
    # 3. Verificar servidor
    print(f"3. Verificando servidor en {IPERF_SERVER}:5201")
    if check_iperf_server():
        print(f"   ✓ Servidor corriendo")
    else:
        print(f"   ✗ Servidor NO corriendo")
        print(f"   → Iniciando servidor...")
        if start_iperf_server():
            print(f"   ✓ Servidor iniciado")
        else:
            print(f"   ✗ No se pudo iniciar servidor")
    
    # 4. Prueba directa
    print(f"4. Prueba directa sin JSON")
    try:
        result = subprocess.run(
            [IPERF_PATH, "-c", IPERF_SERVER, "-t", "3"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=os.path.dirname(IPERF_PATH)
        )
        if result.returncode == 0:
            print(f"   ✓ Prueba directa exitosa")
            print(f"   ✓ Salida: {len(result.stdout)} caracteres")
        else:
            print(f"   ✗ Prueba directa falló: código {result.returncode}")
            print(f"   ✗ STDERR: {result.stderr}")
            print(f"   ✗ STDOUT: {result.stdout}")
    except Exception as e:
        print(f"   ✗ Excepción: {e}")
    
    # 5. Prueba con JSON
    print(f"5. Prueba con JSON")
    try:
        result = subprocess.run(
            [IPERF_PATH, "-c", IPERF_SERVER, "-J", "-t", "3"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=os.path.dirname(IPERF_PATH)
        )
        if result.returncode == 0:
            print(f"   ✓ Prueba JSON exitosa")
            try:
                data = json.loads(result.stdout)
                print(f"   ✓ JSON válido: {len(data)} campos")
            except:
                print(f"   ✗ JSON inválido")
                print(f"   → Primeras 200 chars: {result.stdout[:200]}")
        else:
            print(f"   ✗ Prueba JSON falló: código {result.returncode}")
            print(f"   ✗ STDERR: {result.stderr}")
    except Exception as e:
        print(f"   ✗ Excepción: {e}")
    
    print("=== FIN DIAGNÓSTICO ===\n")