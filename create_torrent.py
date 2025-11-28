#!/usr/bin/env python3
"""
Create a .torrent file from a regular file
Usage: python create_torrent.py <file> <tracker_url> <output_torrent>
"""

import sys
import os
import hashlib
from bencodepy import encode

PIECE_LENGTH = 262144  # 256 KB


def create_torrent(file_path, tracker_url, output_path):
    """Create a torrent file"""

    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist")
        return False

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    print(f"Creating torrent for: {file_name}")
    print(f"File size: {file_size} bytes")
    print(f"Piece length: {PIECE_LENGTH} bytes")

    # Calculate piece hashes
    pieces = b''
    num_pieces = 0

    with open(file_path, 'rb') as f:
        while True:
            piece = f.read(PIECE_LENGTH)
            if not piece:
                break

            piece_hash = hashlib.sha1(piece).digest()
            pieces += piece_hash
            num_pieces += 1

    print(f"Number of pieces: {num_pieces}")

    # Build torrent structure
    info = {
        b'name': file_name.encode('utf-8'),
        b'piece length': PIECE_LENGTH,
        b'pieces': pieces,
        b'length': file_size
    }

    torrent = {
        b'announce': tracker_url.encode('utf-8'),
        b'info': info
    }

    # Calculate info hash
    info_encoded = encode(info)
    info_hash = hashlib.sha1(info_encoded).hexdigest()

    # Write torrent file
    torrent_data = encode(torrent)

    with open(output_path, 'wb') as f:
        f.write(torrent_data)

    print(f"Torrent created: {output_path}")
    print(f"Info hash: {info_hash}")
    print(f"Tracker URL: {tracker_url}")

    return True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python create_torrent.py <file> <tracker_url> <output_torrent>")
        print("Example: python create_torrent.py myfile.txt http://localhost:8000/announce myfile.torrent")
        sys.exit(1)

    file_path = sys.argv[1]
    tracker_url = sys.argv[2]
    output_path = sys.argv[3]

    if create_torrent(file_path, tracker_url, output_path):
        sys.exit(0)
    else:
        sys.exit(1)