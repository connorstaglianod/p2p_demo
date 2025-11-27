"""
TCP Ping - A simple TCP-based ping implementation for LAN devices
Usage:
    Server mode: python tcp_ping.py server [port]
    Client mode: python tcp_ping.py client <host> [port] [count]
"""

import socket
import sys
import time
import struct
from datetime import datetime

DEFAULT_PORT = 9999
DEFAULT_COUNT = 4
BUFFER_SIZE = 1024


def run_server(port=DEFAULT_PORT):
    """Run the TCP ping server"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(5)
        print(f"TCP Ping Server listening on port {port}")
        print("Waiting for connections...\n")

        while True:
            client_socket, address = server_socket.accept()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection from {address[0]}:{address[1]}")

            try:
                while True:
                    data = client_socket.recv(BUFFER_SIZE)
                    if not data:
                        break

                    # Echo the data back
                    client_socket.sendall(data)

            except Exception as e:
                print(f"Error handling client: {e}")
            finally:
                client_socket.close()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection closed from {address[0]}:{address[1]}\n")

    except KeyboardInterrupt:
        print("\nServer shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()


def run_client(host, port=DEFAULT_PORT, count=DEFAULT_COUNT):
    """Run the TCP ping client"""
    print(f"TCP PING {host}:{port}")
    print(f"Sending {count} ping(s)...\n")

    results = []
    successful = 0

    for seq in range(count):
        try:
            # Create a new socket for each ping
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5.0)  # 5 second timeout

            # Measure connection time
            start_time = time.time()
            client_socket.connect((host, port))

            # Send ping message
            message = f"PING {seq}".encode()
            client_socket.sendall(message)

            # Receive response
            response = client_socket.recv(BUFFER_SIZE)
            end_time = time.time()

            if response:
                rtt = (end_time - start_time) * 1000  # Convert to milliseconds
                results.append(rtt)
                successful += 1
                print(f"Reply from {host}: seq={seq} time={rtt:.2f}ms")
            else:
                print(f"No reply from {host}: seq={seq}")

            client_socket.close()

            # Wait before next ping (except for the last one)
            if seq < count - 1:
                time.sleep(1)

        except socket.timeout:
            print(f"Request timeout for seq={seq}")
        except ConnectionRefusedError:
            print(f"Connection refused by {host}:{port}")
            break
        except Exception as e:
            print(f"Error: {e}")

    # Print statistics
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
    print("\nExamples:")
    print("  python tcp_ping.py server")
    print("  python tcp_ping.py server 8080")
    print("  python tcp_ping.py client 192.168.1.100")
    print("  python tcp_ping.py client 192.168.1.100 8080 10")


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

    else:
        print(f"Error: Unknown mode '{mode}'")
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()