"""
p2p_node.py - One peer = TCP server + TCP client.

The node:
  * listens for incoming connections (server role)
  * connects to other peers          (client role)
  * does the HELLO handshake
  * runs one receiving thread per connected peer
  * sends/receives text and files
"""

import ipaddress
import os
import socket
import threading
import uuid

import protocol as proto


def _close_socket(sock):
    """shutdown() first so threads blocked in recv()/accept() wake up and the
    remote side is told the connection ended; then close()."""
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


class Peer:
    """A remote peer we are connected to."""

    def __init__(self, peer_id, name, sock, ip, listen_port):
        self.peer_id = peer_id
        self.name = name
        self.sock = sock
        self.ip = ip
        self.listen_port = listen_port
        self.send_lock = threading.Lock()   # keeps text/file sends from interleaving

    def display(self):
        return f"{self.name} [{self.peer_id}] {self.ip}:{self.listen_port}"


class P2PNode:
    def __init__(self, name, port, on_event=None, on_peers_changed=None,
                 download_dir="downloads"):
        self.name = name
        self.port = port
        self.peer_id = uuid.uuid4().hex[:8]
        self.download_dir = download_dir

        self._on_event = on_event or (lambda text, kind: None)
        self._on_peers_changed = on_peers_changed or (lambda peers: None)

        self.peers = {}                      # peer_id -> Peer
        self._peers_lock = threading.Lock()
        self._server = None
        self._running = False

    # ------------------------------------------------------------ helpers
    def _event(self, text, kind="system"):
        self._on_event(text, kind)

    def _notify_peers(self):
        self._on_peers_changed(self.peer_list())

    def peer_list(self):
        """List of (peer_id, display_text) for the GUI."""
        with self._peers_lock:
            return [(p.peer_id, p.display()) for p in self.peers.values()]

    # ------------------------------------------------------ start / stop
    def start(self):
        """Create the listening socket and start accepting peers."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", self.port))
            server.listen()
        except OSError:
            server.close()
            raise
        self._server = server
        self._running = True
        os.makedirs(self.download_dir, exist_ok=True)
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self._event(f"Peer started: {self.name} [{self.peer_id}] on port {self.port}")

    def stop(self):
        """Close the server socket and all peer connections."""
        self._running = False
        if self._server:
            _close_socket(self._server)
            self._server = None
        with self._peers_lock:
            peers = list(self.peers.values())
            self.peers.clear()
        for p in peers:
            _close_socket(p.sock)
        self._notify_peers()
        self._event("Peer stopped")

    # ---------------------------------------------------- server role
    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._server.accept()
            except OSError:
                break                        # server socket closed
            threading.Thread(target=self._handle_incoming,
                             args=(conn, addr), daemon=True).start()

    def _handle_incoming(self, conn, addr):
        """Someone connected to us: expect HELLO, reply HELLO_ACK."""
        try:
            conn.settimeout(10)
            hello = proto.recv_message(conn)
            if hello.get("type") != proto.HELLO:
                raise proto.ProtocolError("expected hello")
            proto.send_message(conn, proto.make_hello(
                self.peer_id, self.name, self.port, ack=True))
            conn.settimeout(None)
            peer = Peer(hello["peer_id"], hello["peer_name"], conn,
                        addr[0], int(hello["port"]))
        except (OSError, proto.ConnectionClosed, proto.ProtocolError,
                KeyError, ValueError) as exc:
            self._event(f"Incoming connection from {addr[0]} failed: {exc}", "error")
            conn.close()
            return
        self._register(peer)

    # ---------------------------------------------------- client role
    def connect(self, ip, port):
        """Connect to another peer. Returns True on success."""
        # ---- validate input
        try:
            if ip.strip().lower() != "localhost":
                ipaddress.ip_address(ip.strip())
        except ValueError:
            self._event(f"Invalid IP address: {ip!r}", "error")
            return False
        try:
            port = int(port)
            if not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            self._event(f"Invalid port: {port!r}", "error")
            return False
        if not self._running:
            self._event("Start your peer first", "error")
            return False

        ip = ip.strip()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5)
            sock.connect((ip, port))
            proto.send_message(sock, proto.make_hello(
                self.peer_id, self.name, self.port))
            ack = proto.recv_message(sock)
            if ack.get("type") != proto.HELLO_ACK:
                raise proto.ProtocolError("expected hello_ack")
            sock.settimeout(None)
            peer = Peer(ack["peer_id"], ack["peer_name"], sock, ip, int(ack["port"]))
        except (OSError, proto.ConnectionClosed, proto.ProtocolError,
                KeyError, ValueError) as exc:
            self._event(f"Connection failed: {exc}", "error")
            sock.close()
            return False
        return self._register(peer)

    # ------------------------------------------------ peer bookkeeping
    def _register(self, peer):
        if peer.peer_id == self.peer_id:
            self._event("Cannot connect to yourself", "error")
            peer.sock.close()
            return False
        with self._peers_lock:
            if peer.peer_id in self.peers:
                duplicate = True
            else:
                duplicate = False
                self.peers[peer.peer_id] = peer
        if duplicate:
            self._event(f"Already connected to {peer.name}", "error")
            peer.sock.close()
            return False
        self._event(f"Connected to {peer.name} ({peer.ip}:{peer.listen_port})")
        self._notify_peers()
        threading.Thread(target=self._receive_loop, args=(peer,), daemon=True).start()
        return True

    def _remove_peer(self, peer, reason):
        with self._peers_lock:
            removed = self.peers.pop(peer.peer_id, None) is peer
        _close_socket(peer.sock)
        if removed:
            self._event(f"{peer.name} disconnected ({reason})", "error")
            self._notify_peers()

    # ------------------------------------------------- receiving
    def _receive_loop(self, peer):
        """One thread per peer: read messages until the connection ends."""
        try:
            while True:
                msg = proto.recv_message(peer.sock)
                kind = msg["type"]
                if kind == proto.TEXT:
                    self._event(f"{peer.name} -> You: {msg.get('message', '')}", "message")
                elif kind == proto.FILE:
                    self._receive_file(peer, msg)
                else:
                    self._event(f"Ignored unknown message type: {kind}", "error")
        except proto.ConnectionClosed:
            self._remove_peer(peer, "connection closed")
        except (OSError, proto.ProtocolError) as exc:
            self._remove_peer(peer, str(exc))

    def _receive_file(self, peer, meta):
        try:
            filesize = int(meta["filesize"])
            if filesize < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise proto.ProtocolError("invalid file size in metadata")

        # basename() prevents a malicious name like ../../x from escaping downloads/
        filename = os.path.basename(str(meta.get("filename", ""))) or "received_file"
        dest = self._unique_path(filename)
        self._event(f"{peer.name} is sending {filename} ({filesize} bytes)...")
        try:
            proto.recv_file_body(peer.sock, dest, filesize)
        except Exception:
            if os.path.exists(dest):
                os.remove(dest)              # don't keep a partial file
            raise
        self._event(f"{peer.name} -> You: File received: {dest}", "message")

    def _unique_path(self, filename):
        path = os.path.join(self.download_dir, filename)
        base, ext = os.path.splitext(filename)
        n = 1
        while os.path.exists(path):
            path = os.path.join(self.download_dir, f"{base} ({n}){ext}")
            n += 1
        return path

    # --------------------------------------------------- sending
    def _get_peer(self, peer_id):
        if not peer_id:
            self._event("Select a peer first", "error")
            return None
        with self._peers_lock:
            peer = self.peers.get(peer_id)
        if peer is None:
            self._event("That peer is no longer connected", "error")
        return peer

    def send_text(self, peer_id, text):
        peer = self._get_peer(peer_id)
        if peer is None:
            return False
        if not text.strip():
            self._event("Cannot send an empty message", "error")
            return False
        try:
            with peer.send_lock:
                proto.send_message(peer.sock, proto.make_text(self.peer_id, self.name, text))
        except OSError as exc:
            self._remove_peer(peer, str(exc))
            return False
        self._event(f"You -> {peer.name}: {text}", "message")
        return True

    def send_file(self, peer_id, path):
        peer = self._get_peer(peer_id)
        if peer is None:
            return False
        if not path or not os.path.isfile(path):
            self._event(f"File does not exist: {path}", "error")
            return False
        try:
            filesize = os.path.getsize(path)
        except OSError as exc:
            self._event(f"Cannot read file: {exc}", "error")
            return False

        filename = os.path.basename(path)
        self._event(f"Sending {filename} ({filesize} bytes) to {peer.name}...")
        try:
            with peer.send_lock:             # metadata + body must stay together
                proto.send_message(peer.sock, proto.make_file_meta(
                    self.peer_id, self.name, filename, filesize))
                proto.send_file_body(peer.sock, path, filesize)
        except OSError as exc:
            self._remove_peer(peer, str(exc))
            self._event(f"File transfer failed: {exc}", "error")
            return False
        self._event(f"You -> {peer.name}: File sent: {filename}", "message")
        return True
