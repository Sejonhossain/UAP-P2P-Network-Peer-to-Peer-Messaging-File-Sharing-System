# UAP P2P Network (CSE 433)

A lightweight peer-to-peer application in Python. Every running copy is a **peer** that is both a
TCP server (accepts connections) and a TCP client (connects to others). Peers exchange text
messages and files directly, with no central server.

## Requirements
- Python 3.9 or later
- Tkinter (included with Python on Windows/macOS; on Linux: `sudo apt install python3-tk`)
- No third-party packages

## Project structure
| File | Responsibility |
|---|---|
| `main.py` | Tkinter GUI |
| `p2p_node.py` | Server + client, handshake, threads, text and file transfer |
| `protocol.py` | Message framing (`[4-byte length][JSON]`), message builders, file body send/receive |
| `downloads/` | Received files are saved here |

## Run
```
python main.py
```

## Connect two peers
1. **Peer A:** enter Name `Alice`, Port `5000`, click **Start Peer**.
2. **Peer B** (second window/computer): Name `Bob`, Port `5001`, click **Start Peer**.
3. On Bob, enter IP `127.0.0.1` (same computer) or Alice's LAN IP (e.g. `192.168.1.10`),
   Port `5000`, click **Connect**.
4. Both peers now show each other under **Connected Peers**.

Different computers: put them on the same Wi-Fi/LAN and allow Python through the firewall for the
chosen port. Find your IP with `ipconfig` (Windows) or `ip a` / `ifconfig` (Linux/macOS).

## Send text
Select a peer in the list, type in **Send Text**, press **Send** (or Enter).

## Transfer files
Select a peer, click **Choose File & Send**, pick any file (image, audio, video, PDF, ZIP, ...).
The receiver saves it in `downloads/`. Existing names are kept: a duplicate becomes `name (1).ext`.

## How it works
1. **Handshake:** the connecting peer sends `hello` (id, name, port); the other replies `hello_ack`.
2. **Framing:** every JSON message is preceded by its 4-byte length, so the receiver reads exactly
   one message regardless of how TCP splits the stream.
3. **Threads:** one accept thread plus one receive thread per connected peer.
4. **Files:** a `file` JSON message (filename, filesize) is sent first, then exactly `filesize` raw
   bytes in 64 KB chunks. The receiver reads until it has that many bytes.
5. **Errors:** invalid IP/port, refused connections, missing files, no peer selected and
   disconnected peers are reported in the log without crashing.

## Screenshots
_Add your screenshots here (start peer, connected peer list, text, file transfer, 3 peers)._
