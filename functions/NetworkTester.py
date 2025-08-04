from traitlets import default
import subprocess
import time
import json
import re
import statistics
import os
from config.config import Config


class NetworkTester:
    """Handles all network testing functionality."""
    
    def __init__(self):
        # Allow dynamic server configuration
        self.iperf_server = Config.IPERF_SERVER
    
    def set_iperf_server(self, server_ip: str):
        """Update the iperf server IP."""
        self.iperf_server = server_ip
        Config.IPERF_SERVER = server_ip
        print(f"✓ iPerf server set to: {server_ip}")
    
    @staticmethod
    def check_iperf_server():
        """Check if LOCAL iperf3 server is running."""
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
    
    @staticmethod
    def start_iperf_server():
        """Start LOCAL iperf3 server if not running."""
        if NetworkTester.check_iperf_server():
            print("✓ Local iperf3 server already running")
            return True
        
        try:
            print("Starting local iperf3 server...")
            subprocess.Popen(
                [Config.IPERF_PATH, "-s"], 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            time.sleep(2)
            return NetworkTester.check_iperf_server()
        except Exception as e:
            print(f"Error starting local iperf3 server: {e}")
            return False
    
    @staticmethod
    def run_ping(target=Config.PING_TARGET, count=Config.PING_COUNT):
        """Run ping test."""
        try:
            result = subprocess.run(
                ["ping", "-n", str(count), target], 
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            # Parse results
            ping_times = []
            packet_loss = "0%"
            
            for line in result.stdout.splitlines():
                if "tiempo=" in line or "time=" in line:
                    match = re.search(r'(?:tiempo|time)=(\d+)ms', line)
                    if match:
                        ping_times.append(int(match.group(1)))
                elif "perdidos" in line or "loss" in line:
                    match = re.search(r'\(([0-9]+)%', line)
                    if match:
                        packet_loss = f"{match.group(1)}%"
            
            if ping_times:
                return {
                    "success": True,
                    "avg_time": statistics.mean(ping_times),
                    "min_time": min(ping_times),
                    "max_time": max(ping_times),
                    "packet_loss": packet_loss,
                    "raw_times": ping_times
                }
            else:
                return {"success": False, "error": "No ping responses"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def run_speedtest(server_id=Config.SPEEDTEST_SERVER_ID):
        """Run speedtest."""
        try:
            result = subprocess.run(
                [Config.SPEEDTEST_PATH, "--server-id", str(server_id), "--format=json"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {
                    "success": True,
                    "download_mbps": data.get("download", {}).get("bandwidth", 0) / 1_000_000,
                    "upload_mbps": data.get("upload", {}).get("bandwidth", 0) / 1_000_000,
                    "ping_ms": data.get("ping", {}).get("latency", 0),
                    "server": data.get("server", {}).get("name", "Unknown"),
                    "raw_data": data
                }
            else:
                return {"success": False, "error": "Speedtest failed"}
                
        except FileNotFoundError:
            return {"success": False, "error": "speedtest.exe not found"}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid speedtest output"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_iperf_suite(self, duration=10):
            if not os.path.exists(Config.IPERF_PATH):
                return {"success": False, "error": "iperf3 not found", "tests": {}, "raw_output": []}

            results = {"success": True, "server": self.iperf_server, "tests": {}, "raw_output": []}

            def stream_process(cmd_list, desc):
                print(f"\n🔄 {desc}")
                print("-" * 50)
                proc = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                lines = []
                while True:
                    line = proc.stdout.readline()
                    if line == '' and proc.poll() is not None:
                        break
                    if line:
                        clean = line.strip()
                        print(f"   {clean}")
                        lines.append(line)
                try:
                    proc.wait(timeout=duration + 10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    print(f"   ⚠️ Timeout en {desc}")
                return lines

            def run_json(cmd_list):
                try:
                    proc = subprocess.run(
                        cmd_list,
                        capture_output=True,
                        text=True,
                        timeout=duration + 10
                    )
                    if proc.returncode == 0:
                        return json.loads(proc.stdout)
                    else:
                        stderr = proc.stderr.strip()
                        print(f"   ⚠️ Error en JSON command {' '.join(cmd_list)}: returncode {proc.returncode}, stderr: {stderr}")
                except subprocess.TimeoutExpired:
                    print(f"   ⚠️ Timeout en JSON command {' '.join(cmd_list)}")
                except json.JSONDecodeError:
                    print(f"   ⚠️ JSON inválido de {' '.join(cmd_list)}")
                return None

            try:
                print(f"\n🚀 EJECUTANDO SUITE ROBUSTA DE IPERF")
                print(f"   Servidor: {self.iperf_server}")
                print(f"   Duración: {duration} segundos por test")
                print("=" * 70)

                # 1. TCP FORWARD
                print("\n1. TCP FORWARD (cliente -> servidor)")
                tcp_fwd_lines = stream_process([
                    Config.IPERF_PATH, "-c", self.iperf_server, "-t", str(duration), "-i", "1"
                ], "TCP FORWARD (streaming)")
                results["raw_output"].extend(tcp_fwd_lines)
                tcp_fwd_json = run_json([
                    Config.IPERF_PATH, "-c", self.iperf_server, "-J", "-t", str(duration)
                ])
                if tcp_fwd_json:
                    dl_bps = tcp_fwd_json.get("end", {}).get("sum_received", {}).get("bits_per_second", 0)
                    ul_bps = tcp_fwd_json.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0)
                    results["tests"]["tcp_forward"] = {
                        "download_mbps": dl_bps / 1_000_000,
                        "upload_mbps": ul_bps / 1_000_000,
                        "download_gbps": dl_bps / 1_000_000_000,
                        "upload_gbps": ul_bps / 1_000_000_000
                    }

                # 2. TCP REVERSE
                print("\n2. TCP REVERSE (servidor -> cliente)")
                tcp_rev_lines = stream_process([
                    Config.IPERF_PATH, "-c", self.iperf_server, "-R", "-t", str(duration), "-i", "1"
                ], "TCP REVERSE (streaming)")
                results["raw_output"].extend(tcp_rev_lines)
                tcp_rev_json = run_json([
                    Config.IPERF_PATH, "-c", self.iperf_server, "-J", "-R", "-t", str(duration)
                ])
                if tcp_rev_json:
                    dl_bps = tcp_rev_json.get("end", {}).get("sum_received", {}).get("bits_per_second", 0)
                    ul_bps = tcp_rev_json.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0)
                    results["tests"]["tcp_reverse"] = {
                        "download_mbps": dl_bps / 1_000_000,
                        "upload_mbps": ul_bps / 1_000_000,
                        "download_gbps": dl_bps / 1_000_000_000,
                        "upload_gbps": ul_bps / 1_000_000_000
                    }

                # 3. UDP REVERSE 10 Mbps con degradación y fallback IPv4
                def run_udp_reverse_10mbps():
                    desc = "UDP REVERSE 10 Mbps (servidor -> cliente)"
                    target_rates = ["10M", "5M", "2M"]
                    last_error = None
                    for rate in target_rates:
                        print(f"\n3. {desc} intentando {rate}")
                        print("-" * 50)
                        # streaming (con -l para evitar fragmentación y forzar IPv4 si hay fallos después)
                        udp_rev_lines = stream_process([
                            Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-R", "-b", rate, "-t", str(duration), "-i", "1", "-l", "1400"
                        ], f"UDP REVERSE {rate} (streaming)")
                        results["raw_output"].extend(udp_rev_lines)

                        # JSON normal
                        udp_rev_json = run_json([
                            Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-R", "-b", rate, "-t", str(duration), "-J", "-l", "1400"
                        ])
                        if udp_rev_json is None:
                            # fallback IPv4
                            print(f"   ⚠️ fallo en modo por defecto para {rate}, reintentando con IPv4")
                            udp_rev_json = run_json([
                                Config.IPERF_PATH, "-4", "-c", self.iperf_server, "-u", "-R", "-b", rate, "-t", str(duration), "-J", "-l", "1400"
                            ])

                        if udp_rev_json:
                            sum_info = udp_rev_json.get("end", {}).get("sum", {})
                            actual_bps = sum_info.get("bits_per_second", 0)
                            results["tests"]["udp_reverse_10mbps"] = {
                                "target_mbps": float(rate.rstrip("M")),
                                "actual_mbps": actual_bps / 1_000_000,
                                "jitter_ms": sum_info.get("jitter_ms", 0),
                                "lost_packets": sum_info.get("lost_packets", 0),
                                "lost_percent": sum_info.get("lost_percent", 0),
                                "total_packets": sum_info.get("packets", 0),
                                "used_rate": rate,
                            }
                            print(f"   ✅ UDP REVERSE {rate} exitoso")
                            return
                        else:
                            last_error = f"Reverse UDP {rate} falló incluso con fallback IPv4"
                    # si todos fallan:
                    print(f"   ❌ {desc} falló en todos los niveles: {last_error}")
                    results["tests"]["udp_reverse_10mbps"] = {"error": "failed all retries", "details": last_error}

                run_udp_reverse_10mbps()

                # 4. UDP 10 Mbps STABILITY TEST con degradación y fallback IPv4
                def run_udp_stability_10mbps():
                    desc = "UDP 10 Mbps STABILITY TEST (cliente -> servidor)"
                    target_rates = ["10M", "5M", "1M"]
                    last_error = None
                    for rate in target_rates:
                        print(f"\n4. {desc} intentando {rate}")
                        print("-" * 50)
                        udp_5m_lines = stream_process([
                            Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-b", rate, "-t", str(duration), "-i", "1", "-l", "1400"
                        ], f"UDP {rate} STABILITY (streaming)")
                        results["raw_output"].extend(udp_5m_lines)

                        udp_5m_json = run_json([
                            Config.IPERF_PATH, "-c", self.iperf_server, "-u", "-b", rate, "-t", str(duration), "-J", "-l", "1400"
                        ])
                        if udp_5m_json is None:
                            print(f"   ⚠️ fallo en modo por defecto para {rate}, reintentando con IPv4")
                            udp_5m_json = run_json([
                                Config.IPERF_PATH, "-4", "-c", self.iperf_server, "-u", "-b", rate, "-t", str(duration), "-J", "-l", "1400"
                            ])

                        if udp_5m_json:
                            sum_info = udp_5m_json.get("end", {}).get("sum", {})
                            actual_bps = sum_info.get("bits_per_second", 0)
                            lost = sum_info.get("lost_percent", 0)
                            jitter = sum_info.get("jitter_ms", 0)
                            # calidad como antes
                            if lost < 0.1 and jitter < 2.0:
                                quality = "EXCELENTE"
                            elif lost < 0.5 and jitter < 5.0:
                                quality = "BUENA"
                            elif lost < 1.0:
                                quality = "ACEPTABLE"
                            else:
                                quality = "PROBLEMÁTICA"

                            results["tests"]["udp_5mbps"] = {
                                "target_mbps": float(rate.rstrip("M")),
                                "actual_mbps": actual_bps / 1_000_000,
                                "jitter_ms": jitter,
                                "lost_percent": lost,
                                "total_packets": sum_info.get("packets", 0),
                                "lost_packets": sum_info.get("lost_packets", 0),
                                "used_rate": rate,
                                "quality": quality,
                            }
                            print(f"   ✅ UDP {rate} STABILITY exitoso (calidad: {quality})")
                            return
                        else:
                            last_error = f"UDP stability {rate} falló incluso con fallback IPv4"
                    print(f"   ❌ {desc} falló en todos los niveles: {last_error}")
                    results["tests"]["udp_10mbps"] = {"error": "failed all retries", "details": last_error}

                run_udp_stability_10mbps()

                # verificación de tests críticos
                if "udp_10mbps" not in results["tests"]:
                    results["success"] = False
                    results["error"] = "UDP 10 Mbps stability no completado"

                if "udp_reverse_10mbps" not in results["tests"]:
                    results["success"] = False
                    results.setdefault("error", "");
                    if "UDP" not in results["error"]:
                        results["error"] += " | UDP reverse 10Mbps no completado"

                # resumen impreso (podés expandir según quieras)
                print("\n" + "=" * 70)
                print("🎯 RESUMEN FINAL DE CONECTIVIDAD")
                print("=" * 70)
                if "tcp_forward" in results["tests"]:
                    t = results["tests"]["tcp_forward"]
                    print(f"📊 TCP FORWARD: Download {t['download_mbps']:.1f} Mbps, Upload {t['upload_mbps']:.1f} Mbps")
                if "tcp_reverse" in results["tests"]:
                    t = results["tests"]["tcp_reverse"]
                    print(f"📊 TCP REVERSE: Download {t['download_mbps']:.1f} Mbps, Upload {t['upload_mbps']:.1f} Mbps")
                if "udp_reverse_10mbps" in results["tests"]:
                    u = results["tests"]["udp_reverse_10mbps"]
                    print(f"📊 UDP REVERSE 10Mbps: actual {u.get('actual_mbps', 0):.1f} Mbps, rate usada {u.get('used_rate')}")
                if "udp_10mbps" in results["tests"]:
                    u = results["tests"]["udp_10mbps"]
                    print(f"📊 UDP 10Mbps Stability: actual {u.get('actual_mbps', 0):.1f} Mbps, calidad {u.get('quality')}")

                print("=" * 70)
                return results

            except subprocess.TimeoutExpired:
                return {"success": False, "error": "iPerf test timeout", "tests": results.get("tests", {}), "raw_output": results.get("raw_output", [])}
            except json.JSONDecodeError:
                return {"success": False, "error": "Invalid iperf3 JSON output", "tests": results.get("tests", {}), "raw_output": results.get("raw_output", [])}
            except Exception as e:
                return {"success": False, "error": str(e), "tests": results.get("tests", {}), "raw_output": results.get("raw_output", [])}
        
    @staticmethod
    def run_traceroute(target=Config.PING_TARGET):
        """Run traceroute."""
        try:
            result = subprocess.run(
                ["tracert", "-w", "3000", "-h", "20", target],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            hops = []
            for line in result.stdout.splitlines():
                match = re.match(r'\s*(\d+)\s+(.+)', line)
                if match:
                    hop_num = int(match.group(1))
                    hop_info = match.group(2).strip()
                    hops.append({"hop": hop_num, "info": hop_info})
            
            return {
                "success": True,
                "hops": hops,
                "total_hops": len(hops),
                "raw_output": result.stdout
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Traceroute timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

