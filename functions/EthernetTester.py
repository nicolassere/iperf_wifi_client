import subprocess

class EthernetTester:
    """Tester para conexiones cableadas Gigabit."""
    
    @staticmethod
    def get_ethernet_interfaces():
        """Obtener interfaces Ethernet disponibles."""
        try:
            result = subprocess.run(
                ["netsh", "interface", "show", "interface"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            ethernet_interfaces = []
            for line in result.stdout.splitlines():
                if "ethernet" in line.lower() or "local" in line.lower():
                    # Parse interface info
                    parts = line.split()
                    if len(parts) >= 4 and ("conectado" in line.lower() or "connected" in line.lower()):
                        ethernet_interfaces.append({
                            "name": " ".join(parts[3:]),
                            "status": "connected",
                            "type": "ethernet"
                        })
            
            return ethernet_interfaces
            
        except Exception as e:
            print(f"Error getting ethernet interfaces: {e}")
            return []
    
    @staticmethod
    def test_ethernet_speed(interface_name="Ethernet", server="iperf.he.net", duration=10):
        """Test de velocidad en conexión cableada."""
        print(f"\n🌐 TESTING ETHERNET CONNECTION: {interface_name}")
        print("=" * 60)
        
        # Información de la interfaz
        try:
            result = subprocess.run(
                ["netsh", "interface", "ip", "show", "config", interface_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("📋 Interface Information:")
                for line in result.stdout.splitlines()[:10]:
                    if line.strip():
                        print(f"   {line.strip()}")
            
        except Exception as e:
            print(f"⚠️ Could not get interface info: {e}")
        
        # Test de velocidad con iPerf
        print(f"\n🚀 Running Gigabit Speed Test...")
        print(f"   Server: {server}")
        print(f"   Duration: {duration} seconds")
        print("   " + "="*50)
        
        try:
            # TCP test con salida en tiempo real
            process = subprocess.Popen(
                ["C:\\iperf3\\iperf3.exe\\iperf3.exe", "-c", server, "-t", str(duration), "-i", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            tcp_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(f"   {output.strip()}")
                    tcp_lines.append(output)
            
            process.wait(timeout=duration + 10)
            
            # Test UDP a 1 Gbps
            print(f"\n🔄 Running UDP Test at 1 Gbps...")
            print("   " + "="*50)
            
            udp_process = subprocess.Popen(
                ["C:\\iperf3\\iperf3.exe\\iperf3.exe", "-c", server, "-u", "-b", "1G", "-t", str(duration), "-i", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            while True:
                output = udp_process.stdout.readline()
                if output == '' and udp_process.poll() is not None:
                    break
                if output:
                    print(f"   {output.strip()}")
            
            udp_process.wait(timeout=duration + 10)
            
            return {"success": True, "raw_output": "".join(tcp_lines)}
            
        except Exception as e:
            print(f"❌ Error durante test Ethernet: {e}")
            return {"success": False, "error": str(e)}

