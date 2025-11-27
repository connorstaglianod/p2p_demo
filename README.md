<h2>Implementation Phases</h2>
<h3>Phase 1: TorrentParser + TrackerClient (test tracker communication)</h3>

<h3>Phase 2: Tracker implementation (get peer discovery working)</h3>

<h3>Phase 3: Single PeerConnection (handshake, bitfield exchange)</h3>

<h3>Phase 4: PieceManager + FileManager (download from 1 peer)</h3>

<h3>Phase 5: Multi-threading (download from 2+ peers simultaneously)</h3>

<h3>Phase 6: Seeding (accept incoming, upload pieces)</h3>

<h3>Phase 7: Optimizations (rarest-first, choking algorithm)</h3>

<h2>tcp_ping.py</h2>
<h3>Server mode</h3>
py tcp_ping.py server [port]
<h3>Client mode</h3>
py tcp_ping.py client [server IP] [port]
