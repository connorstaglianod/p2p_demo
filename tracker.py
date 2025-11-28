#!/usr/bin/env python3
"""
BitTorrent-style P2P Tracker Server
Usage: python tracker.py <port>
"""

import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from bencodepy import encode, decode

ANNOUNCE_INTERVAL = 120  # seconds
PEER_TIMEOUT = 180  # seconds


class TrackerData:
    """Store and manage peer information"""

    def __init__(self):
        self.torrents = {}  # info_hash -> list of peers
        self.lock = threading.Lock()

    def add_peer(self, info_hash, peer_id, ip, port, event):
        """Add or update peer information"""
        with self.lock:
            if info_hash not in self.torrents:
                self.torrents[info_hash] = {}

            peer_key = f"{ip}:{port}"

            if event == 'stopped':
                # Remove peer
                if peer_key in self.torrents[info_hash]:
                    del self.torrents[info_hash][peer_key]
                    print(f"Peer stopped: {peer_key} for torrent {info_hash.hex()[:8]}")
            else:
                # Add or update peer
                self.torrents[info_hash][peer_key] = {
                    'peer_id': peer_id,
                    'ip': ip,
                    'port': port,
                    'status': event,
                    'last_announce': time.time()
                }

                status_msg = "completed" if event == 'completed' else "announced"
                print(f"Peer {status_msg}: {peer_key} for torrent {info_hash.hex()[:8]}")

    def get_peers(self, info_hash, exclude_ip=None, exclude_port=None):
        """Get list of peers for a torrent"""
        with self.lock:
            if info_hash not in self.torrents:
                return []

            peers = []
            for peer_key, peer_info in self.torrents[info_hash].items():
                # Don't return the requesting peer
                if peer_info['ip'] == exclude_ip and peer_info['port'] == exclude_port:
                    continue

                peers.append({
                    'peer_id': peer_info['peer_id'],
                    'ip': peer_info['ip'],
                    'port': peer_info['port']
                })

            return peers

    def cleanup_stale_peers(self):
        """Remove peers that haven't announced recently"""
        with self.lock:
            current_time = time.time()
            torrents_to_remove = []

            for info_hash, peers in self.torrents.items():
                peers_to_remove = []

                for peer_key, peer_info in peers.items():
                    if current_time - peer_info['last_announce'] > PEER_TIMEOUT:
                        peers_to_remove.append(peer_key)

                for peer_key in peers_to_remove:
                    print(f"Removing stale peer: {peer_key}")
                    del peers[peer_key]

                if not peers:
                    torrents_to_remove.append(info_hash)

            for info_hash in torrents_to_remove:
                del self.torrents[info_hash]

    def get_stats(self):
        """Get tracker statistics"""
        with self.lock:
            stats = []
            for info_hash, peers in self.torrents.items():
                completed = sum(1 for p in peers.values() if p['status'] == 'completed')
                stats.append({
                    'info_hash': info_hash.hex()[:16],
                    'peers': len(peers),
                    'seeders': completed,
                    'leechers': len(peers) - completed
                })
            return stats


class TrackerRequestHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests to tracker"""

    def log_message(self, format, *args):
        """Suppress default HTTP logging"""
        pass

    def do_GET(self):
        """Handle GET request (announce)"""
        parsed_url = urlparse(self.path)

        if parsed_url.path == '/announce':
            self.handle_announce(parsed_url)
        elif parsed_url.path == '/stats':
            self.handle_stats()
        else:
            self.send_error(404, "Not Found")

    def handle_announce(self, parsed_url):
        """Handle announce request from peer"""
        try:
            # Parse query parameters
            params = parse_qs(parsed_url.query)

            # Extract required parameters
            info_hash_encoded = params.get('info_hash', [None])[0]
            peer_id_encoded = params.get('peer_id', [None])[0]
            port = params.get('port', [None])[0]
            event = params.get('event', [''])[0]

            if not info_hash_encoded or not peer_id_encoded or not port:
                self.send_error(400, "Missing required parameters")
                return

            # URL-decode the binary data
            from urllib.parse import unquote_to_bytes
            info_hash = unquote_to_bytes(info_hash_encoded)
            peer_id = unquote_to_bytes(peer_id_encoded)

            port = int(port)
            ip = self.client_address[0]

            # Update tracker data
            self.server.tracker_data.add_peer(info_hash, peer_id, ip, port, event)

            # Get peer list (excluding requesting peer)
            peers = self.server.tracker_data.get_peers(info_hash, ip, port)

            # Build response
            response = {
                b'interval': ANNOUNCE_INTERVAL,
                b'peers': [
                    {
                        b'peer_id': p['peer_id'],
                        b'ip': p['ip'].encode('utf-8'),
                        b'port': p['port']
                    }
                    for p in peers
                ]
            }

            # Send bencoded response
            response_data = encode(response)

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', len(response_data))
            self.end_headers()
            self.wfile.write(response_data)

        except Exception as e:
            print(f"Error handling announce: {e}")
            self.send_error(500, f"Internal Server Error: {e}")

    def handle_stats(self):
        """Handle stats request"""
        try:
            stats = self.server.tracker_data.get_stats()

            response = "<html><head><title>Tracker Stats</title></head><body>"
            response += "<h1>BitTorrent Tracker Statistics</h1>"
            response += f"<p>Total torrents: {len(stats)}</p>"
            response += "<table border='1'><tr><th>Info Hash</th><th>Peers</th><th>Seeders</th><th>Leechers</th></tr>"

            for stat in stats:
                response += f"<tr><td>{stat['info_hash']}</td>"
                response += f"<td>{stat['peers']}</td>"
                response += f"<td>{stat['seeders']}</td>"
                response += f"<td>{stat['leechers']}</td></tr>"

            response += "</table></body></html>"

            response_data = response.encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(response_data))
            self.end_headers()
            self.wfile.write(response_data)

        except Exception as e:
            print(f"Error handling stats: {e}")
            self.send_error(500, "Internal Server Error")


class TrackerServer(HTTPServer):
    """Extended HTTPServer with tracker data"""

    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.tracker_data = TrackerData()


def cleanup_thread(tracker_data):
    """Background thread to cleanup stale peers"""
    while True:
        time.sleep(60)  # Check every minute
        tracker_data.cleanup_stale_peers()


def monitor_thread(tracker_data):
    """Background thread to monitor tracker status"""
    while True:
        time.sleep(30)  # Update every 30 seconds
        stats = tracker_data.get_stats()

        if stats:
            print("\n=== Tracker Status ===")
            for stat in stats:
                print(f"Torrent {stat['info_hash']}: "
                      f"{stat['peers']} peers "
                      f"({stat['seeders']} seeders, {stat['leechers']} leechers)")
            print("=" * 40 + "\n")


def run_tracker(port):
    """Run the tracker server"""
    server_address = ('', port)
    httpd = TrackerServer(server_address, TrackerRequestHandler)

    print(f"Starting BitTorrent Tracker on port {port}")
    print(f"Announce URL: http://localhost:{port}/announce")
    print(f"Stats URL: http://localhost:{port}/stats")

    # Start cleanup thread
    cleanup = threading.Thread(target=cleanup_thread, args=(httpd.tracker_data,))
    cleanup.daemon = True
    cleanup.start()

    # Start monitor thread
    monitor = threading.Thread(target=monitor_thread, args=(httpd.tracker_data,))
    monitor.daemon = True
    monitor.start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down tracker...")
        httpd.shutdown()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python tracker.py <port>")
        sys.exit(1)

    try:
        port = int(sys.argv[1])
        run_tracker(port)
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)