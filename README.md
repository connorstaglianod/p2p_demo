# BitTorrent-Style P2P Client
Python implementation of BitTorrent-style p2p file sharing over LAN, also includes a tracker server

Connor Stagliano



## Features
### Peer Features
- Tracker communication (announce, started, completed, stopped)
- Peer handshake and connection management
- Simultaneous downloading from multiple peers
- Simultaneous uploading to multiple peers
- Piece verification using SHA1 hashes
- Accept incoming peer connections
- Keep-alive messages
- Multithreaded architecture

### Tracker Features
- HTTP-based tracker server
- Peer list management
- Periodic cleanup of stale peers
- Statistics dashboard
- Bencoded responses



## Requirements
pip install -r requirements.txt

OR

pip install bencodepy



## Instructions for use and troubleshooting
### 1. Start the Tracker on the Initial Seeder
python tracker.py 8000

The tracker will start on port 8000 and display:
- Announce URL: http://localhost:8000/announce
- Stats URL: http://localhost:8000/stats

### 2. Create a Torrent File on the Initial Seeder
Ensure the file intended for sharing is in p2p_demo directory (same level as py scripts). Then run following cmd in a new terminal:

python create_torrent.py myfile.xxx http://192.168.1.100:8000/announce myfile.torrent
(replace 192.168.1.100 with initial seeder's IP)

.torrent file will contain:
- File metadata (name, size)
- Tracker URL
- Piece hashes for verification

### 3. Start the Initial Seeder
On the machine with the original file:

python peer.py myfile.torrent

The peer will:
- Announce to the tracker
- Start listening for connections
- Seed the complete file

### 4. Start Additional Peers (Leechers)
On other machines, copy the .torrent file into the p2p_demo directory. Then run following cmd:

python peer.py myfile.torrent

File with original extension should appear in p2p_demo directory on leecher machine after download completes.

Each peer will:
- Connect to the tracker
- Discover other peers
- Download pieces simultaneously from multiple peers
- Upload pieces to other peers
- Continue seeding after download completes



## Troubleshooting common issues
### Error receiving from (peer_IP) - can't concat NoneType to bytes
- Occurs because of connection issue, simply CTRL+C on leeching machine and run:

python peer.py myfile.torrent 

- File should resume downloading where it left off
- May need to do this multiple times to complete download

### If issue connecting to peers
Ensure create_torrent.py was run with correct local IP of initial seeder machine (not localhost)

Any peer wishing to connect to the network must be:
- On the same LAN
- Running peer.py with the same .torrent file in the p2p_demo directory

All peers using the same torrent file will automatically discover each other through the tracker



## Core Components and Implementation Details
### 1. peer.py - Peer Client (Main Component)
- Purpose: Download from and upload to other peers
- Key Classes:
  - TorrentFile: Parses .torrent metadata (hashes, tracker URL, file info)
  - PieceManager: Manages piece verification, block assembly, file I/O
  - PeerConnection: Handles individual peer connections and BitTorrent protocol messages
  - PeerClient: Orchestrates tracker communication, peer discovery, and transfers

### 2. tracker.py - Tracker Server
- Purpose: Coordinate peer discovery and maintain state
- Key Classes:
  - TrackerData: Thread-safe peer list management with timeout handling
  - TrackerRequestHandler: HTTP endpoint for announce requests
  - TrackerServer: HTTP server with integrated tracker data

### 3. create_torrent.py - Torrent Creation Utility
- Purpose: Generate .torrent files from source files
- Function: Calculates SHA1 hashes for each 256KB piece

### Message Flow
1. Startup:
   - Parse torrent file
   - Announce to tracker
   - Receive peer list
   - Connect to peers

2. Downloading:
   - Send interested message
   - Wait for unchoke
   - Request blocks
   - Verify pieces
   - Write to disk

3. Uploading:
   - Send bitfield
   - Send unchoke
   - Respond to requests
   - Send pieces

4. Completion:
   - Announce completed
   - Continue seeding

### Threading Model
Each peer runs multiple threads:
- Main thread: Coordination
- Listen thread: Accept incoming connections
- Per-peer receive threads: Handle incoming messages
- Per-peer download threads: Request pieces
- Cleanup threads: Keep-alive, timeouts

### Handshake
<pstrlen><pstr><reserved><info_hash><peer_id>

### Messages
- 0: Choke
- 1: Unchoke
- 2: Interested
- 3: Not Interested
- 4: Have (piece index)
- 5: Bitfield
- 6: Request (piece, begin, length)
- 7: Piece (piece, begin, block)
- 8: Cancel

### Piece Management
- Piece size: 256 KB
- Block size: 16 KB
- Each piece verified with SHA1 hash
