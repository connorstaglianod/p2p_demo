#!/usr/bin/env python3
"""
BitTorrent-style P2P Peer Client
Usage: python peer.py <torrent_file>
"""

import sys
import os
import hashlib
import struct
import socket
import threading
import time
import random
import urllib.parse
import urllib.request
from bencodepy import decode, encode

# Constants
BLOCK_SIZE = 16384  # 16 KB
PEER_ID = f"-PY0001-{random.randint(10 ** 11, 10 ** 12 - 1)}".encode()
HANDSHAKE_PSTR = b"BitTorrent protocol"
KEEP_ALIVE_INTERVAL = 120  # seconds

# Message types
MSG_CHOKE = 0
MSG_UNCHOKE = 1
MSG_INTERESTED = 2
MSG_NOT_INTERESTED = 3
MSG_HAVE = 4
MSG_BITFIELD = 5
MSG_REQUEST = 6
MSG_PIECE = 7
MSG_CANCEL = 8


class TorrentFile:
    """Parse and store torrent file metadata"""

    def __init__(self, filepath):
        with open(filepath, 'rb') as f:
            self.data = decode(f.read())

        self.announce = self.data[b'announce'].decode('utf-8')
        info = self.data[b'info']

        self.info_hash = hashlib.sha1(encode(info)).digest()
        self.piece_length = info[b'piece length']
        self.pieces = info[b'pieces']
        self.name = info[b'name'].decode('utf-8')
        self.length = info[b'length']

        self.num_pieces = len(self.pieces) // 20
        self.piece_hashes = [self.pieces[i:i + 20] for i in range(0, len(self.pieces), 20)]


class PeerConnection:
    """Manage connection to a single peer"""

    def __init__(self, ip, port, info_hash, peer_id, piece_manager):
        self.ip = ip
        self.port = port
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.piece_manager = piece_manager

        self.socket = None
        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False
        self.bitfield = None
        self.running = False
        self.last_message = time.time()

    def connect(self):
        """Establish connection and perform handshake"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.ip, self.port))

            # Send handshake
            handshake = self._build_handshake()
            self.socket.sendall(handshake)

            # Receive handshake
            response = self.socket.recv(68)
            if len(response) < 68:
                return False

            # Verify info_hash
            recv_info_hash = response[28:48]
            if recv_info_hash != self.info_hash:
                return False

            self.socket.settimeout(300)
            self.running = True
            return True

        except Exception as e:
            print(f"Connection failed to {self.ip}:{self.port} - {e}")
            return False

    def _build_handshake(self):
        """Build BitTorrent handshake message"""
        pstrlen = len(HANDSHAKE_PSTR)
        reserved = b'\x00' * 8
        return struct.pack('B', pstrlen) + HANDSHAKE_PSTR + reserved + self.info_hash + self.peer_id

    def send_interested(self):
        """Send interested message"""
        self._send_message(MSG_INTERESTED, b'')
        self.am_interested = True

    def send_not_interested(self):
        """Send not interested message"""
        self._send_message(MSG_NOT_INTERESTED, b'')
        self.am_interested = False

    def send_unchoke(self):
        """Send unchoke message"""
        self._send_message(MSG_UNCHOKE, b'')
        self.am_choking = False

    def send_have(self, piece_index):
        """Send have message"""
        payload = struct.pack('>I', piece_index)
        self._send_message(MSG_HAVE, payload)

    def send_bitfield(self, bitfield):
        """Send bitfield message"""
        self._send_message(MSG_BITFIELD, bitfield)

    def request_piece(self, piece_index, begin, length):
        """Request a block from peer"""
        payload = struct.pack('>III', piece_index, begin, length)
        self._send_message(MSG_REQUEST, payload)

    def send_piece(self, piece_index, begin, block):
        """Send a piece block to peer"""
        payload = struct.pack('>II', piece_index, begin) + block
        self._send_message(MSG_PIECE, payload)

    def _send_message(self, msg_id, payload):
        """Send a message to peer"""
        try:
            length = len(payload) + 1
            message = struct.pack('>I', length) + struct.pack('B', msg_id) + payload
            self.socket.sendall(message)
        except Exception as e:
            print(f"Error sending message: {e}")
            self.running = False

    def _send_keep_alive(self):
        """Send keep-alive message"""
        try:
            self.socket.sendall(struct.pack('>I', 0))
        except:
            self.running = False

    def receive_messages(self):
        """Receive and process messages from peer"""
        while self.running:
            try:
                # Keep-alive check
                if time.time() - self.last_message > KEEP_ALIVE_INTERVAL:
                    self._send_keep_alive()
                    self.last_message = time.time()

                # Read message length
                length_data = self._recv_exactly(4)
                if not length_data:
                    break

                length = struct.unpack('>I', length_data)[0]

                if length == 0:  # Keep-alive
                    self.last_message = time.time()
                    continue

                # Read message
                message = self._recv_exactly(length)
                if not message:
                    break

                self.last_message = time.time()
                msg_id = message[0]
                payload = message[1:]

                self._handle_message(msg_id, payload)

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error receiving from {self.ip}:{self.port} - {e}")
                break

        self.close()

    def _recv_exactly(self, num_bytes):
        """Receive exactly num_bytes from socket"""
        data = b''
        while len(data) < num_bytes:
            chunk = self.socket.recv(num_bytes - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _handle_message(self, msg_id, payload):
        """Handle received message"""
        if msg_id == MSG_CHOKE:
            self.peer_choking = True

        elif msg_id == MSG_UNCHOKE:
            self.peer_choking = False

        elif msg_id == MSG_INTERESTED:
            self.peer_interested = True

        elif msg_id == MSG_NOT_INTERESTED:
            self.peer_interested = False

        elif msg_id == MSG_HAVE:
            piece_index = struct.unpack('>I', payload)[0]
            if self.bitfield:
                byte_index = piece_index // 8
                bit_index = piece_index % 8
                if byte_index < len(self.bitfield):
                    self.bitfield[byte_index] |= (1 << (7 - bit_index))

        elif msg_id == MSG_BITFIELD:
            self.bitfield = bytearray(payload)

        elif msg_id == MSG_REQUEST:
            piece_index, begin, length = struct.unpack('>III', payload)
            if not self.am_choking and self.piece_manager.have_piece(piece_index):
                block = self.piece_manager.read_block(piece_index, begin, length)
                if block:
                    self.send_piece(piece_index, begin, block)

        elif msg_id == MSG_PIECE:
            piece_index, begin = struct.unpack('>II', payload[:8])
            block = payload[8:]
            self.piece_manager.write_block(piece_index, begin, block, self)

    def has_piece(self, piece_index):
        """Check if peer has a piece"""
        if not self.bitfield:
            return False
        byte_index = piece_index // 8
        bit_index = piece_index % 8
        if byte_index >= len(self.bitfield):
            return False
        return (self.bitfield[byte_index] & (1 << (7 - bit_index))) != 0

    def close(self):
        """Close connection"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass


class PieceManager:
    """Manage piece downloading and file assembly"""

    def __init__(self, torrent):
        self.torrent = torrent
        self.pieces = [None] * torrent.num_pieces
        self.piece_status = [False] * torrent.num_pieces
        self.pending_blocks = {}
        self.lock = threading.Lock()
        self.file_path = torrent.name

        # Create file with correct size
        with open(self.file_path, 'wb') as f:
            f.seek(torrent.length - 1)
            f.write(b'\0')

    def have_piece(self, piece_index):
        """Check if we have a piece"""
        with self.lock:
            return self.piece_status[piece_index]

    def get_bitfield(self):
        """Get bitfield representing pieces we have"""
        with self.lock:
            num_bytes = (self.torrent.num_pieces + 7) // 8
            bitfield = bytearray(num_bytes)
            for i in range(self.torrent.num_pieces):
                if self.piece_status[i]:
                    byte_index = i // 8
                    bit_index = i % 8
                    bitfield[byte_index] |= (1 << (7 - bit_index))
            return bytes(bitfield)

    def get_next_request(self, peer):
        """Get next piece/block to request from peer"""
        with self.lock:
            for piece_index in range(self.torrent.num_pieces):
                if not self.piece_status[piece_index] and peer.has_piece(piece_index):
                    piece_length = self.torrent.piece_length
                    if piece_index == self.torrent.num_pieces - 1:
                        piece_length = self.torrent.length % self.torrent.piece_length
                        if piece_length == 0:
                            piece_length = self.torrent.piece_length

                    # Find missing blocks in this piece
                    if piece_index not in self.pending_blocks:
                        self.pending_blocks[piece_index] = {}

                    for begin in range(0, piece_length, BLOCK_SIZE):
                        if begin not in self.pending_blocks[piece_index]:
                            length = min(BLOCK_SIZE, piece_length - begin)
                            self.pending_blocks[piece_index][begin] = None
                            return (piece_index, begin, length)
            return None

    def write_block(self, piece_index, begin, block, peer):
        """Write received block to memory"""
        with self.lock:
            if piece_index not in self.pending_blocks:
                self.pending_blocks[piece_index] = {}

            self.pending_blocks[piece_index][begin] = block

            # Check if piece is complete
            piece_length = self.torrent.piece_length
            if piece_index == self.torrent.num_pieces - 1:
                piece_length = self.torrent.length % self.torrent.piece_length
                if piece_length == 0:
                    piece_length = self.torrent.piece_length

            expected_blocks = (piece_length + BLOCK_SIZE - 1) // BLOCK_SIZE
            if len(self.pending_blocks[piece_index]) == expected_blocks:
                # Assemble piece
                piece_data = b''
                for offset in sorted(self.pending_blocks[piece_index].keys()):
                    piece_data += self.pending_blocks[piece_index][offset]

                # Verify hash
                piece_hash = hashlib.sha1(piece_data).digest()
                if piece_hash == self.torrent.piece_hashes[piece_index]:
                    self._write_piece_to_file(piece_index, piece_data)
                    self.piece_status[piece_index] = True
                    del self.pending_blocks[piece_index]
                    print(f"Completed piece {piece_index}/{self.torrent.num_pieces}")
                else:
                    print(f"Hash mismatch for piece {piece_index}")
                    del self.pending_blocks[piece_index]

    def _write_piece_to_file(self, piece_index, data):
        """Write piece to file"""
        offset = piece_index * self.torrent.piece_length
        with open(self.file_path, 'r+b') as f:
            f.seek(offset)
            f.write(data)

    def read_block(self, piece_index, begin, length):
        """Read block from file for uploading"""
        try:
            offset = piece_index * self.torrent.piece_length + begin
            with open(self.file_path, 'rb') as f:
                f.seek(offset)
                return f.read(length)
        except:
            return None

    def is_complete(self):
        """Check if download is complete"""
        with self.lock:
            return all(self.piece_status)

    def completion_percentage(self):
        """Get download completion percentage"""
        with self.lock:
            completed = sum(self.piece_status)
            return (completed / self.torrent.num_pieces) * 100


class PeerClient:
    """Main peer client"""

    def __init__(self, torrent_file):
        self.torrent = TorrentFile(torrent_file)
        self.piece_manager = PieceManager(self.torrent)
        self.peers = []
        self.peer_threads = []
        self.running = True
        self.listen_port = random.randint(6881, 6889)

        print(f"Starting peer for: {self.torrent.name}")
        print(f"File size: {self.torrent.length} bytes")
        print(f"Pieces: {self.torrent.num_pieces}")
        print(f"Listening on port: {self.listen_port}")

    def announce_to_tracker(self, event='started'):
        """Announce to tracker"""
        # Properly URL-encode binary data
        params = {
            'info_hash': urllib.parse.quote(self.torrent.info_hash, safe=''),
            'peer_id': urllib.parse.quote(PEER_ID, safe=''),
            'port': self.listen_port,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.torrent.length,
            'event': event
        }

        # Build URL manually since we've already encoded binary params
        param_str = '&'.join(f"{k}={v}" for k, v in params.items())
        url = f"{self.torrent.announce}?{param_str}"

        try:
            response = urllib.request.urlopen(url, timeout=10)
            data = decode(response.read())

            if b'peers' in data:
                peers_data = data[b'peers']
                for peer_dict in peers_data:
                    ip = peer_dict[b'ip'].decode('utf-8')
                    port = peer_dict[b'port']
                    if ip != 'localhost' or port != self.listen_port:
                        print(f"Found peer: {ip}:{port}")
                        self.connect_to_peer(ip, port)

            return True
        except Exception as e:
            print(f"Tracker announce failed: {e}")
            return False

    def connect_to_peer(self, ip, port):
        """Connect to a peer"""
        peer = PeerConnection(ip, port, self.torrent.info_hash, PEER_ID, self.piece_manager)
        if peer.connect():
            self.peers.append(peer)

            # Send bitfield
            bitfield = self.piece_manager.get_bitfield()
            peer.send_bitfield(bitfield)

            # Send interested
            peer.send_interested()

            # Start receive thread
            thread = threading.Thread(target=peer.receive_messages)
            thread.daemon = True
            thread.start()
            self.peer_threads.append(thread)

            # Start download thread
            thread = threading.Thread(target=self.download_from_peer, args=(peer,))
            thread.daemon = True
            thread.start()
            self.peer_threads.append(thread)

    def download_from_peer(self, peer):
        """Download pieces from peer"""
        while self.running and peer.running:
            if not peer.peer_choking and peer.am_interested:
                request = self.piece_manager.get_next_request(peer)
                if request:
                    piece_index, begin, length = request
                    peer.request_piece(piece_index, begin, length)
                    time.sleep(0.01)
                else:
                    time.sleep(1)
            else:
                time.sleep(1)

    def accept_connections(self):
        """Accept incoming peer connections"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('', self.listen_port))
        server.listen(5)
        server.settimeout(1)

        while self.running:
            try:
                client_socket, address = server.accept()
                thread = threading.Thread(target=self.handle_incoming_peer, args=(client_socket, address))
                thread.daemon = True
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error accepting connection: {e}")

    def handle_incoming_peer(self, client_socket, address):
        """Handle incoming peer connection"""
        try:
            # Receive handshake
            handshake = client_socket.recv(68)
            if len(handshake) < 68:
                return

            recv_info_hash = handshake[28:48]
            if recv_info_hash != self.torrent.info_hash:
                return

            # Send handshake
            pstrlen = len(HANDSHAKE_PSTR)
            reserved = b'\x00' * 8
            response = struct.pack('B', pstrlen) + HANDSHAKE_PSTR + reserved + self.torrent.info_hash + PEER_ID
            client_socket.sendall(response)

            # Create peer connection
            peer = PeerConnection(address[0], address[1], self.torrent.info_hash, PEER_ID, self.piece_manager)
            peer.socket = client_socket
            peer.running = True
            self.peers.append(peer)

            # Send bitfield and unchoke
            bitfield = self.piece_manager.get_bitfield()
            peer.send_bitfield(bitfield)
            peer.send_unchoke()

            # Handle messages
            peer.receive_messages()

        except Exception as e:
            print(f"Error handling incoming peer: {e}")

    def run(self):
        """Main run loop"""
        # Start listening for connections
        listen_thread = threading.Thread(target=self.accept_connections)
        listen_thread.daemon = True
        listen_thread.start()

        # Announce to tracker
        self.announce_to_tracker('started')

        # Monitor progress
        try:
            while not self.piece_manager.is_complete():
                time.sleep(5)
                progress = self.piece_manager.completion_percentage()
                active_peers = sum(1 for p in self.peers if p.running)
                print(f"Progress: {progress:.1f}% | Active peers: {active_peers}")

            print(f"Download complete! File saved as: {self.piece_manager.file_path}")
            self.announce_to_tracker('completed')

            # Continue seeding
            print("Seeding... Press Ctrl+C to stop")
            while True:
                time.sleep(10)

        except KeyboardInterrupt:
            print("\nStopping...")
            self.running = False
            self.announce_to_tracker('stopped')
            for peer in self.peers:
                peer.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python peer.py <torrent_file>")
        sys.exit(1)

    client = PeerClient(sys.argv[1])
    client.run()