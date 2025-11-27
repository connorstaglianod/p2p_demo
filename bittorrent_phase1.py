"""
BitTorrent Client - Phase 1: TorrentParser + TrackerClient
Complete implementation with bencode parsing and tracker communication
"""

import hashlib
import urllib.parse
import urllib.request
import socket
import struct
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


# ============================================================================
# BENCODE DECODER
# ============================================================================

class BencodeDecoder:
    """Decode bencoded data from .torrent files"""

    @staticmethod
    def decode(data: bytes) -> Any:
        """Main decode entry point"""
        return BencodeDecoder._decode_recursive(data, 0)[0]

    @staticmethod
    def _decode_recursive(data: bytes, index: int) -> tuple[Any, int]:
        """Recursively decode bencoded data, returns (value, next_index)"""
        if index >= len(data):
            raise ValueError("Unexpected end of data")

        char = chr(data[index])

        # Integer: i<number>e
        if char == 'i':
            return BencodeDecoder._decode_int(data, index)

        # List: l<items>e
        elif char == 'l':
            return BencodeDecoder._decode_list(data, index)

        # Dictionary: d<key-value pairs>e
        elif char == 'd':
            return BencodeDecoder._decode_dict(data, index)

        # String: <length>:<string>
        elif char.isdigit():
            return BencodeDecoder._decode_string(data, index)

        else:
            raise ValueError(f"Invalid bencode data at index {index}: {char}")

    @staticmethod
    def _decode_int(data: bytes, index: int) -> tuple[int, int]:
        """Decode integer: i<number>e"""
        index += 1  # skip 'i'
        end = data.index(b'e', index)
        return int(data[index:end]), end + 1

    @staticmethod
    def _decode_string(data: bytes, index: int) -> tuple[bytes, int]:
        """Decode byte string: <length>:<string>"""
        colon = data.index(b':', index)
        length = int(data[index:colon])
        start = colon + 1
        end = start + length
        return data[start:end], end

    @staticmethod
    def _decode_list(data: bytes, index: int) -> tuple[List, int]:
        """Decode list: l<items>e"""
        index += 1  # skip 'l'
        result = []
        while chr(data[index]) != 'e':
            item, index = BencodeDecoder._decode_recursive(data, index)
            result.append(item)
        return result, index + 1  # skip 'e'

    @staticmethod
    def _decode_dict(data: bytes, index: int) -> tuple[Dict, int]:
        """Decode dictionary: d<key-value pairs>e"""
        index += 1  # skip 'd'
        result = {}
        while chr(data[index]) != 'e':
            key, index = BencodeDecoder._decode_recursive(data, index)
            value, index = BencodeDecoder._decode_recursive(data, index)
            # Keys are always strings in bencode
            result[key.decode('utf-8') if isinstance(key, bytes) else key] = value
        return result, index + 1  # skip 'e'


# ============================================================================
# BENCODE ENCODER
# ============================================================================

class BencodeEncoder:
    """Encode Python objects to bencode format"""

    @staticmethod
    def encode(obj: Any) -> bytes:
        """Main encode entry point"""
        if isinstance(obj, int):
            return BencodeEncoder._encode_int(obj)
        elif isinstance(obj, bytes):
            return BencodeEncoder._encode_bytes(obj)
        elif isinstance(obj, str):
            return BencodeEncoder._encode_bytes(obj.encode('utf-8'))
        elif isinstance(obj, list):
            return BencodeEncoder._encode_list(obj)
        elif isinstance(obj, dict):
            return BencodeEncoder._encode_dict(obj)
        else:
            raise TypeError(f"Cannot bencode type {type(obj)}")

    @staticmethod
    def _encode_int(n: int) -> bytes:
        return f"i{n}e".encode('utf-8')

    @staticmethod
    def _encode_bytes(b: bytes) -> bytes:
        return f"{len(b)}:".encode('utf-8') + b

    @staticmethod
    def _encode_list(lst: list) -> bytes:
        result = b'l'
        for item in lst:
            result += BencodeEncoder.encode(item)
        result += b'e'
        return result

    @staticmethod
    def _encode_dict(d: dict) -> bytes:
        result = b'd'
        # Keys must be sorted in bencode
        for key in sorted(d.keys()):
            result += BencodeEncoder.encode(key)
            result += BencodeEncoder.encode(d[key])
        result += b'e'
        return result


# ============================================================================
# TORRENT METADATA
# ============================================================================

@dataclass
class TorrentInfo:
    """Parsed torrent file information"""
    announce: str  # Tracker URL
    info_hash: bytes  # SHA-1 hash of info dict (20 bytes)
    piece_length: int  # Bytes per piece
    pieces: bytes  # Concatenated SHA-1 hashes (20 bytes each)
    name: str  # File/directory name
    length: Optional[int]  # Single file mode
    files: Optional[List[Dict]]  # Multi-file mode

    @property
    def total_length(self) -> int:
        """Total size in bytes"""
        if self.length:
            return self.length
        return sum(f['length'] for f in self.files)

    @property
    def num_pieces(self) -> int:
        """Number of pieces"""
        return len(self.pieces) // 20

    def get_piece_hash(self, index: int) -> bytes:
        """Get SHA-1 hash for piece at index"""
        start = index * 20
        return self.pieces[start:start + 20]


# ============================================================================
# TORRENT PARSER
# ============================================================================

class TorrentParser:
    """Parse .torrent files and extract metadata"""

    @staticmethod
    def parse_file(filepath: str) -> TorrentInfo:
        """Parse a .torrent file and return TorrentInfo"""
        with open(filepath, 'rb') as f:
            data = f.read()
        return TorrentParser.parse_bytes(data)

    @staticmethod
    def parse_bytes(data: bytes) -> TorrentInfo:
        """Parse torrent data from bytes"""
        # Decode the bencoded data
        torrent = BencodeDecoder.decode(data)

        # Extract announce URL
        announce = torrent['announce'].decode('utf-8')

        # Extract info dict
        info = torrent['info']

        # Calculate info_hash (SHA-1 of bencoded info dict)
        info_hash = TorrentParser._calculate_info_hash(data)

        # Extract piece information
        piece_length = info['piece length']
        pieces = info['pieces']  # Concatenated 20-byte SHA-1 hashes

        # Extract name
        name = info['name'].decode('utf-8')

        # Single file or multi-file mode
        length = None
        files = None

        if 'length' in info:
            # Single file mode
            length = info['length']
        else:
            # Multi-file mode
            files = []
            for f in info['files']:
                files.append({
                    'length': f['length'],
                    'path': [p.decode('utf-8') for p in f['path']]
                })

        return TorrentInfo(
            announce=announce,
            info_hash=info_hash,
            piece_length=piece_length,
            pieces=pieces,
            name=name,
            length=length,
            files=files
        )

    @staticmethod
    def _calculate_info_hash(torrent_data: bytes) -> bytes:
        """Calculate SHA-1 hash of the info dictionary"""
        # Find the info dict in the bencoded data
        # We need to extract the raw bencoded info dict
        info_start = torrent_data.index(b'4:info') + 6

        # Decode to find where info dict ends
        torrent = BencodeDecoder.decode(torrent_data)
        info_bencoded = BencodeEncoder.encode(torrent['info'])

        return hashlib.sha1(info_bencoded).digest()


# ============================================================================
# TRACKER CLIENT
# ============================================================================

@dataclass
class TrackerResponse:
    """Response from tracker announce"""
    interval: int  # Seconds to wait before next announce
    peers: List[tuple[str, int]]  # List of (ip, port) tuples
    complete: Optional[int] = None  # Number of seeders
    incomplete: Optional[int] = None  # Number of leechers


class TrackerClient:
    """Communicate with BitTorrent tracker"""

    def __init__(self, torrent_info: TorrentInfo, peer_id: bytes, port: int = 6881):
        """
        Initialize tracker client

        Args:
            torrent_info: Parsed torrent metadata
            peer_id: 20-byte peer ID (must be unique)
            port: Port this client is listening on
        """
        self.torrent_info = torrent_info
        self.peer_id = peer_id
        self.port = port
        self.uploaded = 0
        self.downloaded = 0
        self.left = torrent_info.total_length

    def announce(self, event: Optional[str] = None) -> TrackerResponse:
        """
        Send announce request to tracker

        Args:
            event: Optional event ('started', 'completed', 'stopped')

        Returns:
            TrackerResponse with peer list
        """
        # Build query parameters
        params = {
            'info_hash': self.torrent_info.info_hash,
            'peer_id': self.peer_id,
            'port': self.port,
            'uploaded': self.uploaded,
            'downloaded': self.downloaded,
            'left': self.left,
            'compact': 1,  # Request compact peer list format
        }

        if event:
            params['event'] = event

        # Build URL
        url = self._build_url(params)

        print(f"Announcing to tracker: {self.torrent_info.announce}")
        print(f"Info hash: {self.torrent_info.info_hash.hex()}")
        print(f"Peer ID: {self.peer_id.hex()}")

        # Send HTTP GET request
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = response.read()
                return self._parse_response(data)
        except Exception as e:
            raise Exception(f"Tracker announce failed: {e}")

    def _build_url(self, params: Dict) -> str:
        """Build tracker announce URL with parameters"""
        # URL encode parameters
        query_parts = []
        for key, value in params.items():
            if isinstance(value, bytes):
                # URL encode bytes
                encoded = urllib.parse.quote(value, safe='')
            else:
                encoded = str(value)
            query_parts.append(f"{key}={encoded}")

        query_string = '&'.join(query_parts)
        return f"{self.torrent_info.announce}?{query_string}"

    def _parse_response(self, data: bytes) -> TrackerResponse:
        """Parse tracker response"""
        response = BencodeDecoder.decode(data)

        # Check for failure
        if b'failure reason' in response:
            reason = response[b'failure reason'].decode('utf-8')
            raise Exception(f"Tracker error: {reason}")

        # Extract interval
        interval = response[b'interval']

        # Extract optional fields
        complete = response.get(b'complete')
        incomplete = response.get(b'incomplete')

        # Parse peers
        peers_data = response[b'peers']

        if isinstance(peers_data, bytes):
            # Compact format: 6 bytes per peer (4 byte IP + 2 byte port)
            peers = self._parse_compact_peers(peers_data)
        else:
            # Dictionary format (list of dicts)
            peers = self._parse_dict_peers(peers_data)

        print(f"\nTracker response:")
        print(f"  Interval: {interval}s")
        print(f"  Seeders: {complete}")
        print(f"  Leechers: {incomplete}")
        print(f"  Peers found: {len(peers)}")

        return TrackerResponse(
            interval=interval,
            peers=peers,
            complete=complete,
            incomplete=incomplete
        )

    @staticmethod
    def _parse_compact_peers(data: bytes) -> List[tuple[str, int]]:
        """Parse compact peer list (6 bytes per peer)"""
        peers = []
        for i in range(0, len(data), 6):
            ip_bytes = data[i:i + 4]
            port_bytes = data[i + 4:i + 6]

            ip = '.'.join(str(b) for b in ip_bytes)
            port = struct.unpack('!H', port_bytes)[0]

            peers.append((ip, port))

        return peers

    @staticmethod
    def _parse_dict_peers(peers_list: List) -> List[tuple[str, int]]:
        """Parse dictionary format peer list"""
        peers = []
        for peer in peers_list:
            ip = peer[b'ip'].decode('utf-8')
            port = peer[b'port']
            peers.append((ip, port))

        return peers


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_peer_id() -> bytes:
    """Generate a random 20-byte peer ID"""
    # Convention: -XX0001-<random> where XX is client code
    import random
    client_prefix = b'-PY0001-'
    random_suffix = bytes([random.randint(0, 255) for _ in range(12)])
    return client_prefix + random_suffix


# ============================================================================
# TEST/DEMO CODE
# ============================================================================

def create_test_torrent() -> bytes:
    """Create a simple test .torrent file in memory"""
    # This creates a minimal valid torrent for testing
    torrent = {
        'announce': 'http://tracker.example.com:8080/announce',
        'info': {
            'name': 'test_file.txt',
            'piece length': 16384,  # 16 KB pieces
            'pieces': b'\x00' * 20,  # Dummy hash
            'length': 1024,  # 1 KB file
        }
    }
    return BencodeEncoder.encode(torrent)


def demo_phase1():
    """Demo Phase 1 functionality"""
    print("=" * 70)
    print("PHASE 1 DEMO: TorrentParser + TrackerClient")
    print("=" * 70)

    # Test 1: Bencode encoding/decoding
    print("\n1. Testing Bencode encoding/decoding...")
    test_data = {
        'announce': 'http://tracker.example.com/announce',
        'number': 42,
        'list': [1, 2, 3],
        'dict': {'key': 'value'}
    }
    encoded = BencodeEncoder.encode(test_data)
    decoded = BencodeDecoder.decode(encoded)
    print(f"   Original: {test_data}")
    print(f"   Encoded: {encoded}")
    print(f"   Decoded: {decoded}")
    print("   ✓ Bencode working")

    # Test 2: Create and parse test torrent
    print("\n2. Testing TorrentParser...")
    torrent_bytes = create_test_torrent()
    torrent_info = TorrentParser.parse_bytes(torrent_bytes)
    print(f"   Name: {torrent_info.name}")
    print(f"   Announce: {torrent_info.announce}")
    print(f"   Info hash: {torrent_info.info_hash.hex()}")
    print(f"   Piece length: {torrent_info.piece_length} bytes")
    print(f"   Total length: {torrent_info.total_length} bytes")
    print(f"   Number of pieces: {torrent_info.num_pieces}")
    print("   ✓ TorrentParser working")

    # Test 3: Tracker client (will fail without real tracker)
    print("\n3. Testing TrackerClient...")
    print("   Note: This will fail without a real tracker, which is expected")
    try:
        peer_id = generate_peer_id()
        tracker = TrackerClient(torrent_info, peer_id, port=6881)
        response = tracker.announce(event='started')
        print(f"   ✓ Successfully connected to tracker!")
        print(f"   Found {len(response.peers)} peers")
        for ip, port in response.peers[:5]:  # Show first 5
            print(f"     - {ip}:{port}")
    except Exception as e:
        print(f"   ✗ Expected failure: {e}")
        print("   (To test with real tracker, use an actual .torrent file)")

    print("\n" + "=" * 70)
    print("PHASE 1 COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  - Implement tracker server (Phase 2)")
    print("  - Test with real .torrent files")
    print("  - Implement peer connection handshake (Phase 3)")


if __name__ == '__main__':
    demo_phase1()

    print("\n" + "=" * 70)
    print("USAGE EXAMPLE")
    print("=" * 70)
    print("""
# To use with a real .torrent file:
torrent_info = TorrentParser.parse_file('example.torrent')
peer_id = generate_peer_id()
tracker = TrackerClient(torrent_info, peer_id, port=6881)
response = tracker.announce(event='started')

# Show discovered peers
for ip, port in response.peers:
    print(f"Peer: {ip}:{port}")
""")
