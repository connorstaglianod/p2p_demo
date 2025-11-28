# BitTorrent-Style P2P Client

A Python implementation of a BitTorrent-style peer-to-peer file sharing system for LAN use.

## Features

### Peer Features
- ✅ Tracker communication (announce, started, completed, stopped)
- ✅ Peer handshake and connection management
- ✅ Simultaneous downloading from multiple peers
- ✅ Simultaneous uploading to multiple peers
- ✅ Piece verification using SHA1 hashes
- ✅ Accept incoming peer connections
- ✅ Keep-alive messages
- ✅ Multithreaded architecture

### Tracker Features
- ✅ HTTP-based tracker server
- ✅ Peer list management
- ✅ Periodic cleanup of stale peers
- ✅ Statistics dashboard
- ✅ Bencoded responses

## Requirements

```bash
pip install bencodepy
```

## File Structure

```
bittorrent-p2p/
├── peer.py           # Peer client implementation
├── tracker.py        # Tracker server implementation
├── create_torrent.py # Utility to create .torrent files
└── README.md         # This file
```

## Quick Start

### 1. Start the Tracker

```bash
python tracker.py 8000
```

The tracker will start on port 8000 and display:
- Announce URL: `http://localhost:8000/announce`
- Stats URL: `http://localhost:8000/stats`

### 2. Create a Torrent File

```bash
python create_torrent.py myfile.txt http://localhost:8000/announce myfile.torrent
```

This creates a `.torrent` file containing:
- File metadata (name, size)
- Tracker URL
- Piece hashes for verification

### 3. Start the Initial Seeder

On the machine with the original file:

```bash
python peer.py myfile.torrent
```

The peer will:
- Announce to the tracker
- Start listening for connections
- Seed the complete file

### 4. Start Additional Peers (Leechers)

On other machines, copy the `.torrent` file and run:

```bash
python peer.py myfile.torrent
```

Each peer will:
- Connect to the tracker
- Discover other peers
- Download pieces simultaneously from multiple peers
- Upload pieces to other peers
- Continue seeding after download completes

## Usage Examples

### Example 1: Share a File on LAN

**Machine 1 (Seeder):**
```bash
# Start tracker
python tracker.py 8000

# Create torrent (use actual IP for LAN access)
python create_torrent.py document.pdf http://192.168.1.100:8000/announce document.torrent

# Start seeding
python peer.py document.torrent
```

**Machine 2 (Leecher):**
```bash
# Copy document.torrent to this machine
python peer.py document.torrent
```

**Machine 3 (Leecher):**
```bash
# Copy document.torrent to this machine
python peer.py document.torrent
```

### Example 2: Monitor Tracker Statistics

Visit `http://localhost:8000/stats` in a web browser to see:
- Number of active torrents
- Peers per torrent
- Seeders vs. leechers

### Example 3: Manual Peer Addition

Since this is designed for LAN use, you can manually share:
1. The `.torrent` file
2. The tracker URL

All peers using the same torrent file will automatically discover each other through the tracker.

## Architecture

### Peer Architecture

```
PeerClient
├── TorrentFile (metadata parser)
├── PieceManager (download/upload management)
│   ├── Piece verification
│   ├── Block assembly
│   └── File I/O
└── PeerConnection (per-peer threads)
    ├── Message handling
    ├── Download worker
    └── Upload responder
```

### Message Flow

1. **Startup:**
   - Parse torrent file
   - Announce to tracker
   - Receive peer list
   - Connect to peers

2. **Downloading:**
   - Send interested message
   - Wait for unchoke
   - Request blocks
   - Verify pieces
   - Write to disk

3. **Uploading:**
   - Send bitfield
   - Send unchoke
   - Respond to requests
   - Send pieces

4. **Completion:**
   - Announce completed
   - Continue seeding

### Threading Model

Each peer runs multiple threads:
- Main thread: Coordination
- Listen thread: Accept incoming connections
- Per-peer receive threads: Handle incoming messages
- Per-peer download threads: Request pieces
- Cleanup threads: Keep-alive, timeouts

## Protocol Details

### Handshake
```
<pstrlen><pstr><reserved><info_hash><peer_id>
```

### Messages
- `0`: Choke
- `1`: Unchoke
- `2`: Interested
- `3`: Not Interested
- `4`: Have (piece index)
- `5`: Bitfield
- `6`: Request (piece, begin, length)
- `7`: Piece (piece, begin, block)
- `8`: Cancel

### Piece Management
- Piece size: 256 KB (configurable)
- Block size: 16 KB
- Each piece verified with SHA1 hash

## Configuration

### Constants (in peer.py)
```python
BLOCK_SIZE = 16384           # 16 KB blocks
KEEP_ALIVE_INTERVAL = 120    # Keep-alive every 2 minutes
```

### Constants (in tracker.py)
```python
ANNOUNCE_INTERVAL = 120      # Reannounce every 2 minutes
PEER_TIMEOUT = 180          # Remove peers after 3 minutes
```

### Constants (in create_torrent.py)
```python
PIECE_LENGTH = 262144       # 256 KB pieces
```

## Troubleshooting

### "Connection refused" errors
- Ensure tracker is running
- Check tracker URL in torrent file
- Verify firewall settings

### "Hash mismatch" errors
- File may be corrupted
- Recreate torrent file
- Check original file integrity

### Slow downloads
- Ensure multiple peers are available
- Check network bandwidth
- Verify peers are unchoked

### Peers not connecting
- Check listen port is not blocked
- Verify all peers use same torrent file
- Ensure tracker URL is accessible from all machines

## Limitations

- **LAN only**: Not designed for internet-scale operation
- **No encryption**: Traffic is unencrypted
- **No DHT**: Requires tracker for peer discovery
- **No piece selection strategy**: Downloads sequentially
- **No choking algorithm**: Simple unchoke all peers
- **No NAT traversal**: Direct connections only

## Safety Notes

- Only share files you have permission to distribute
- This implementation is for educational/LAN use only
- No authentication or access control
- All connected peers can see each other's IPs

## Advanced Usage

### Running Multiple Trackers

You can run trackers on different ports:
```bash
python tracker.py 8000  # Tracker 1
python tracker.py 8001  # Tracker 2
```

Update torrent files to use the appropriate tracker.

### Seeding Multiple Files

Run separate peer instances:
```bash
python peer.py file1.torrent &
python peer.py file2.torrent &
```

### Custom Piece Sizes

Modify `PIECE_LENGTH` in `create_torrent.py`:
- Smaller pieces: More overhead, better parallelism
- Larger pieces: Less overhead, less granular

## License

Educational implementation - use responsibly.
