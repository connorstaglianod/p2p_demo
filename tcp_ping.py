#!/usr/bin/env python3
"""
TCP Ping - A simple TCP-based ping implementation for LAN devices
Usage:
    Server mode: python tcp_ping.py server [port]
    Client mode: python tcp_ping.py client <host> [port] [count]
    Multi-client: python tcp_ping.py multi <host1> <host2> <host3> ... [port] [count]
"""

import socket
import sys
import time
import struct
import threading
from datetime import datetime
from queue import Queue

DEFAULT_PORT = 9999
DEFAULT_COUNT = 4
BUFFER_SIZE = 1024


def run_server(port=DEFAULT_PORT):
    """Run the TCP ping server with multi-threading support"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def handle_client(client_socket, address):
        """Handle a single client connection in a separate thread"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection from {address[0]}:{address[1]}")
        try:
            while True:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break
                client_socket.sendall(data)
        except Exception as e:
            print(f"Error handling client {address[0]}: {e}")
        finally:
            client_socket.close()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection closed from {address[0]}:{address[1]}")

    try:
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(10)
        print(f"TCP Ping Server listening on port {port}")
        print("Waiting for connections...\n")

        while True:
            client_socket, address = server_socket.accept()
            # Create a new thread for each client
            client_thread = threading.Thread(target=handle_client, args=(client_socket, address))
            client_thread.daemon = True
            client_thread.start()

    except KeyboardInterrupt:
        print("\nServer shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()


def ping_host(host, port, count, results_dict, lock):
    """Ping a single host and store results"""
    results = []
    successful = 0

    for seq in range(count):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5.0)

            start_time = time.time()
            client_socket.connect((host, port))

            message = f"PING {seq}".encode()
            client_socket.sendall(message)

            response = client_socket.recv(BUFFER_SIZE)
            end_time = time.time()

            if response:
                rtt = (end_time - start_time) * 1000
                results.append(rtt)
                successful += 1

                with lock:
                    print(f"[{host}] Reply: seq={seq} time={rtt:.2f}ms")
            else:
                with lock:
                    print(f"[{host}] No reply: seq={seq}")

            client_socket.close()

            if seq < count - 1:
                time.sleep(1)

        except socket.timeout:
            with lock:
                print(f"[{host}] Request timeout: seq={seq}")
        except ConnectionRefusedError:
            with lock:
                print(f"[{host}] Connection refused")
            break
        except Exception as e:
            with lock:
                print(f"[{host}] Error: {e}")

    # Store results
    results_dict[host] = {
        'total': count,
        'successful': successful,
        'times': results
    }


def run_multi_client(hosts, port=DEFAULT_PORT, count=DEFAULT_COUNT):
    """Ping multiple hosts simultaneously using threads"""
    print(f"TCP PING to {len(hosts)} host(s) on port {port}")
    print(f"Sending {count} ping(s) to each host...\n")

    results_dict = {}
    lock = threading.Lock()
    threads = []

    # Create and start a thread for each host
    for host in hosts:
        thread = threading.Thread(target=ping_host, args=(host, port, count, results_dict, lock))
        thread.start()
        threads.append(thread)

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Print summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    for host in hosts:
        if host in results_dict:
            stats = results_dict[host]
            total = stats['total']
            successful = stats['successful']
            times = stats['times']
            loss = ((total - successful) / total) * 100

            print(f"\n{host}:")
            print(f"  {total} packets transmitted, {successful} received, {loss:.1f}% packet loss")

            if times:
                print(f"  rtt min/avg/max = {min(times):.2f}/{sum(times) / len(times):.2f}/{max(times):.2f} ms")
            else:
                print(f"  No successful responses")


def run_client(host, port=DEFAULT_PORT, count=DEFAULT_COUNT):
    """Run the TCP ping client for a single host"""
    print(f"TCP PING {host}:{port}")
    print(f"Sending {count} ping(s)...\n")

    results = []
    successful = 0

    for seq in range(count):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5.0)

            start_time = time.time()
            client_socket.connect((host, port))

            message = f"PING {seq}".encode()
            client_socket.sendall(message)

            response = client_socket.recv(BUFFER_SIZE)
            end_time = time.time()

            if response:
                rtt = (end_time - start_time) * 1000
                results.append(rtt)
                successful += 1
                print(f"Reply from {host}: seq={seq} time={rtt:.2f}ms")
            else:
                print(f"No reply from {host}: seq={seq}")

            client_socket.close()

            if seq < count - 1:
                time.sleep(1)

        except socket.timeout:
            print(f"Request timeout for seq={seq}")
        except ConnectionRefusedError:
            print(f"Connection refused by {host}:{port}")
            break
        except Exception as e:
            print(f"Error: {e}")

    print(f"\n--- {host} TCP ping statistics ---")
    print(
        f"{count} packets transmitted, {successful} received, {((count - successful) / count) * 100:.1f}% packet loss")

    if results:
        print(f"rtt min/avg/max = {min(results):.2f}/{sum(results) / len(results):.2f}/{max(results):.2f} ms")


def print_usage():
    """Print usage information"""
    print("Usage:")
    print("  Server mode: python tcp_ping.py server [port]")
    print("  Client mode: python tcp_ping.py client <host> [port] [count]")
    print("  Multi-client: python tcp_ping.py multi <host1> <host2> <host3> ... [--port PORT] [--count COUNT]")
    print("\nExamples:")
    print("  python tcp_ping.py server")
    print("  python tcp_ping.py server 8080")
    print("  python tcp_ping.py client 192.168.1.100")
    print("  python tcp_ping.py client 192.168.1.100 8080 10")
    print("  python tcp_ping.py multi 192.168.1.100 192.168.1.101 192.168.1.102")
    print("  python tcp_ping.py multi 192.168.1.100 192.168.1.101 --port 8080 --count 10")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == 'server':
        port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
        run_server(port)

    elif mode == 'client':
        if len(sys.argv) < 3:
            print("Error: Host address required for client mode")
            print_usage()
            sys.exit(1)

        host = sys.argv[2]
        port = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_PORT
        count = int(sys.argv[4]) if len(sys.argv) > 4 else DEFAULT_COUNT

        run_client(host, port, count)

    elif mode == 'multi':
        if len(sys.argv) < 3:
            print("Error: At least one host address required for multi mode")
            print_usage()
            sys.exit(1)

        # Parse hosts and optional parameters
        hosts = []
        port = DEFAULT_PORT
        count = DEFAULT_COUNT

        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--port':
                port = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == '--count':
                count = int(sys.argv[i + 1])
                i += 2
            else:
                hosts.append(sys.argv[i])
                i += 1

        if not hosts:
            print("Error: No hosts specified")
            print_usage()
            sys.exit(1)

        run_multi_client(hosts, port, count)

    else:
        print(f"Error: Unknown mode '{mode}'")
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
