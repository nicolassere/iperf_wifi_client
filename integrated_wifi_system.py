#!/usr/bin/env python3
"""
Integrated WiFi Analysis System with Persistent Heatmaps
Includes: WiFi scanning, network testing (ping, speedtest, iperf), and heatmap generation
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import re
import time
import os
from collections import defaultdict
import statistics
from scipy.interpolate import Rbf
from scipy.interpolate import griddata
import numpy as np
from functions.NetworkTester import NetworkTester
from functions.WifiScanner import WiFiScanner
from config.config import Config
from functions.HeatmapManager import HeatmapManager
from functions.EthernetTester import EthernetTester




# Main execution function
def main():
    """Main entry point for the integrated system."""
    print("🏠 INTEGRATED WIFI ANALYSIS & HEATMAP SYSTEM")
    print("=" * 60)
    
    # Initialize manager
    manager = HeatmapManager()
    
    # Configure iPerf server
    print("\n📡 IPERF SERVER CONFIGURATION")
    print("Default server: iperf.he.net (public server)")
    custom_server = input("Enter iPerf server IP (press Enter for default): ").strip()
    if custom_server:
        manager.tester.set_iperf_server(custom_server)
    else:
        print("✓ Using server :" + Config.IPERF_SERVER)
    
    # Ask about local server only if needed
    if custom_server == "127.0.0.1" or custom_server == "localhost":
        if not manager.tester.check_iperf_server():
            print("\n⚠️  Local iPerf3 server not running.")
            if input("Start local iPerf3 server? (y/n): ").lower() == 'y':
                manager.tester.start_iperf_server()
    
    # Setup rooms if needed
    if not manager.rooms:
        print("\nNo rooms defined. Using default layout...")
        manager.setup_default_layout()
        manager.save_data()
    
    # Main menu
    while True:
        print("\n" + "="*60)
        print("MAIN MENU")
        print("="*60)
        print("1. Collect measurement by ID (field mode)")
        print("2. Collect measurement with coordinates")
        print("3. Map IDs to coordinates")
        print("4. Test all networks by ID (field mode)")
        print("5. Auto-collect measurements")
        print("6. Generate individual AP heatmaps")
        print("7. Generate composite heatmap")
        print("8. View statistics")
        print("9. Continuous monitoring")
        print("10. Network diagnostics")
        print("11. Change iPerf server")
        print("12. Ethernet Test")
        print("0. Exit")
        print("="*60)
        
        choice = input("Select option: ").strip()
        
        if choice == "0":
            print("Goodbye!")
            break
            
        elif choice == "1":
            # Field mode - use ID

                manager.collect_measurement_by_id()
                
        elif choice == "2":
            # Original mode with coordinates
            try:
                coords = input("Enter x,y coordinates (e.g., 5.5,3.2): ").strip()
                x, y = map(float, coords.split(','))
                manager.collect_measurement_with_tests(x, y)
            except Exception as e:
                print(f"Error: {e}")
                
        elif choice == "3":
            # Map IDs to coordinates
            manager.batch_map_coordinates()
                
        elif choice == "4":
            # Test all networks by ID
                manager.test_all_networks_by_id()
                
        elif choice == "5":
            auto_collect(manager)
            
        elif choice == "6":
            for ap_key in manager.ap_data.keys():
                try:
                    manager.create_ap_heatmap(ap_key)
                except Exception as e:
                    print(f"Error creating heatmap for {ap_key}: {e}")
            
        elif choice == "7":
            manager.create_composite_heatmap()
            
        elif choice == "8":
            show_statistics(manager)
            
        elif choice == "9":
            continuous_monitoring(manager)
            
        elif choice == "10":
            network_diagnostics(manager)
            
        elif choice == "11":
            new_server = input("Enter new iPerf server IP: ").strip()
            if new_server:
                manager.tester.set_iperf_server(new_server)
        
        elif choice =="12":
            ethernet_diagnostics()


def ethernet_diagnostics():
    """Diagnósticos de red cableada."""
    print("\n🌐 ETHERNET DIAGNOSTICS")
    print("-" * 40)
    
    # Encontrar interfaces Ethernet
    interfaces = EthernetTester.get_ethernet_interfaces()
    
    if not interfaces:
        print("❌ No se encontraron interfaces Ethernet conectadas")
        return
    
    print("📋 Interfaces Ethernet encontradas:")
    for i, iface in enumerate(interfaces):
        print(f"   {i+1}. {iface['name']} ({iface['status']})")
    
    # Seleccionar interfaz
    if len(interfaces) == 1:
        selected = interfaces[0]
        print(f"\n✅ Usando interfaz: {selected['name']}")
    else:
        try:
            choice = int(input(f"\nSeleccionar interfaz (1-{len(interfaces)}): ")) - 1
            selected = interfaces[choice]
        except:
            print("❌ Selección inválida")
            return
    
    # Ejecutar test
    server = input("Servidor iPerf (Enter para iperf.he.net): ").strip() or "iperf.he.net"
    duration = int(input("Duración en segundos (Enter para 10): ").strip() or "10")
    
    EthernetTester.test_ethernet_speed(selected['name'], server, duration)

def auto_collect(manager):
    """Automated measurement collection."""
    try:
        num = int(input("Number of measurements: "))
        interval = float(input("Interval (seconds): ") or 30)
        run_tests = input("Run network tests? (y/n): ").lower() == 'y'
        
        print(f"\nCollecting {num} measurements...")
        for i in range(num):
            x = np.random.uniform(0, manager.house_width)
            y = np.random.uniform(0, manager.house_length)
            
            print(f"\n[{i+1}/{num}] Position: ({x:.1f}, {y:.1f})")
            manager.collect_measurement_with_tests(x, y, run_tests=run_tests)
            
            if i < num - 1:
                time.sleep(interval)
                
    except KeyboardInterrupt:
        print("\nStopped by user")


def continuous_monitoring(manager):
    """Continuous monitoring mode."""
    print("\nCONTINUOUS MONITORING MODE")
    print("Choose mode:")
    print("1. Random positions (original)")
    print("2. Fixed ID increments (field mode)")
    
    mode = input("Select mode (1 or 2): ").strip()
    
    if mode == "2":
        # Field mode with IDs
        print("\n- Measurements with auto-incrementing IDs")
        print("- Remember to map IDs to coordinates later")
        print("\nPress Ctrl+C to stop")
        
        measurement_count = 0
        
        try:
            while True:
                manager.collect_measurement_by_id(run_tests=False)
                measurement_count += 1
                
                # Periodic network test
                if measurement_count % 10 == 0:
                    print("\n🔄 Running network test...")
                    current_conn = manager.scanner.get_current_connection_info()
                    if 'ssid' in current_conn and 'error' not in current_conn:
                        # Run basic test
                        ping = manager.tester.run_ping()
                        if ping['success']:
                            print(f"✓ Ping: {ping['avg_time']:.1f}ms")
                
                time.sleep(30)
                
        except KeyboardInterrupt:
            print(f"\nMonitoring stopped. Total measurements: {measurement_count}")
            print("Remember to map IDs to coordinates using option 3!")
    
    else:
        # Original mode
        print("\n- Measurements every 30 seconds at random positions")
        print("- Test all networks every 5 minutes")
        print("- Update heatmaps every 10 minutes")
        print("\nPress Ctrl+C to stop")
        
        measurement_count = 0
        last_test_time = time.time()
        last_heatmap_time = time.time()
        
        try:
            while True:
                # Random position
                x = np.random.uniform(0, manager.house_width)
                y = np.random.uniform(0, manager.house_length)
                
                # Basic measurement
                manager.collect_measurement_with_tests(x, y, run_tests=False)
                measurement_count += 1
                
                # Test all networks every 5 minutes
                if time.time() - last_test_time > 300:
                    print("\n🔄 Testing all networks...")
                    manager.test_all_networks(x, y)
                    last_test_time = time.time()
                
                # Update heatmaps every 10 minutes
                if time.time() - last_heatmap_time > 600:
                    print("\n📊 Updating heatmaps...")
                    manager.create_composite_heatmap()
                    last_heatmap_time = time.time()
                
                time.sleep(30)
                
        except KeyboardInterrupt:
            print(f"\nMonitoring stopped. Total measurements: {measurement_count}")


def network_diagnostics(manager):
    """Run network diagnostics."""
    print("\nNETWORK DIAGNOSTICS")
    print("-" * 40)
    
    # Current connection
    current = manager.scanner.get_current_connection_info()
    
    if 'error' in current:
        print(f"⚠️  {current['error']}")
        print("\nPossible issues:")
        print("- Not connected to WiFi")
        print("- Need to run as Administrator")
        print("- WiFi adapter disabled")
        return
    
    if 'ssid' in current:
        print(f"Connected to: {current['ssid']}")
        print(f"Signal: {current.get('signal_percentage', 'N/A')}%")
        print(f"Channel: {current.get('channel', 'N/A')}")
        
        print("\nRunning tests...")
        
        # Ping
        ping = manager.tester.run_ping()
        if ping['success']:
            print(f"✓ Ping: {ping['avg_time']:.1f}ms (min: {ping['min_time']}, max: {ping['max_time']})")
        else:
            print(f"✗ Ping: {ping['error']}")
        
        # Traceroute
        if input("\nRun traceroute? (y/n): ").lower() == 'y':
            trace = manager.tester.run_traceroute()
            if trace['success']:
                print(f"✓ Traceroute: {trace['total_hops']} hops")
                for hop in trace['hops'][:10]:  # Show first 10 hops
                    print(f"   {hop['hop']}: {hop['info']}")
            else:
                print(f"✗ Traceroute: {trace['error']}")
        
        # Speedtest
        if input("\nRun speedtest? (y/n): ").lower() == 'y':
            speed = manager.tester.run_speedtest()
            if speed['success']:
                print(f"✓ Speedtest:")
                print(f"   Download: {speed['download_mbps']:.1f} Mbps")
                print(f"   Upload: {speed['upload_mbps']:.1f} Mbps")
                print(f"   Ping: {speed['ping_ms']:.1f} ms")
                print(f"   Server: {speed['server']}")
            else:
                print(f"✗ Speedtest: {speed['error']}")
        
        # iPerf
        if input("    Run iPerf test suite? (y/n): ").lower() == 'y':
            iperf_result = manager.tester.run_iperf_suite()
            if iperf_result['success']:
                print(f"✓ iPerf Test Suite:")
                print(f"   Throughput: {iperf_result['throughput_mbps']:.1f} Mbps")
                print(f"   Jitter: {iperf_result['jitter_ms']:.2f} ms")
                print(f"   Loss: {iperf_result['loss_percentage']:.2f}%")
            else:
                print(f"    ✗ iPerf: {iperf_result['error']}")


def show_statistics(manager):
    """Display comprehensive statistics."""
    stats = manager.get_statistics()
    
    print("\n" + "="*70)
    print("SYSTEM STATISTICS")
    print("="*70)
    print(f"Total measurements: {stats['total_measurements']}")
    print(f"Total APs tracked: {stats['total_aps']}")
    print(f"Networks tested: {stats['tested_networks']}")
    
    print("\n📊 TEST SUMMARY:")
    print(f"Ping tests: {stats['test_summary']['total_ping_tests']}")
    if stats['test_summary']['avg_ping']:
        print(f"  Average: {stats['test_summary']['avg_ping']:.1f} ms")
    
    print(f"Speed tests: {stats['test_summary']['total_speed_tests']}")
    if stats['test_summary']['avg_download']:
        print(f"  Avg Download: {stats['test_summary']['avg_download']:.1f} Mbps")
        print(f"  Avg Upload: {stats['test_summary']['avg_upload']:.1f} Mbps")
    
    print(f"iPerf tests: {stats['test_summary']['total_iperf_tests']}")
    if stats['test_summary']['avg_throughput']:
        print(f"  Avg Throughput: {stats['test_summary']['avg_throughput']:.1f} Mbps")
    
    print("\n📡 TOP ACCESS POINTS:")
    print("-"*70)
    print(f"{'SSID':<25} {'BSSID':<20} {'Avg Signal':<12} {'Tests':<8} {'Avg Ping':<10}")
    print("-"*70)
    
    for ap in stats['ap_details'][:10]:
        ssid = ap['name'][:24]
        bssid = ap['bssid'][:19]
        avg_ping = f"{ap.get('avg_ping', 0):.1f} ms" if 'avg_ping' in ap else "N/A"
        tests = ap.get('tests_performed', 0)
        
        print(f"{ssid:<25} {bssid:<20} {ap['avg_signal']:>10.1f}% {tests:>8} {avg_ping:>10}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()