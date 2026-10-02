# 🌐 UAP P2P Network

### Peer-to-Peer Communication and File Sharing System

A lightweight **Peer-to-Peer (P2P) communication and file-sharing application** developed in Python for the **CSE 433 — Blockchain & Distributed Security Lab** at the University of Asia Pacific.

The system allows multiple independent peers to communicate and exchange files directly over TCP connections without relying on a centralized server. Each running instance operates simultaneously as a **TCP server and TCP client**, enabling decentralized peer-to-peer communication.

---

## 📖 Overview

Traditional client-server applications depend on a central server to coordinate communication between users. This project demonstrates an alternative approach using a **peer-to-peer architecture**, where participating nodes communicate directly with one another.

Each peer:

- 🖥️ Runs its own TCP server to accept incoming connections.
- 🔌 Acts as a TCP client to connect to other peers.
- 🆔 Identifies itself using a unique peer ID, name, and listening port.
- 💬 Exchanges text messages directly with connected peers.
- 📁 Transfers files directly between peers.
- 🌐 Can maintain multiple peer connections simultaneously.

**No central server is required for communication.**

---

## ✨ Key Features

- 🔗 **Peer-to-Peer Architecture** — Direct communication between participating nodes.
- 🌐 **TCP Networking** — Reliable communication using Python TCP sockets.
- 🔄 **Dual Server/Client Peer** — Every peer can both accept and initiate connections.
- 🤝 **Peer Handshake** — HELLO / HELLO_ACK mechanism for peer identification.
- 💬 **Text Messaging** — Send messages directly to connected peers.
- 📁 **Binary File Transfer** — Transfer files of different formats without format-specific handling.
- 👥 **Multiple Peer Connections** — Connect to and communicate with multiple peers.
- 🧵 **Multithreaded Networking** — Network operations run independently from the GUI.
- 📦 **Message Framing** — Length-prefixed JSON messages prevent TCP stream-boundary issues.
- 💾 **Automatic File Storage** — Received files are saved in the `downloads/` directory.
- 📄 **Duplicate File Handling** — Existing filenames are preserved by generating a new filename.
- 🖼️ **Tkinter GUI** — Simple graphical interface for managing peers and transfers.
- ⚠️ **Error Handling** — Common connection and file-transfer errors are handled without terminating the application.

---

## 🏗️ System Architecture

```text
                         ┌──────────────────────┐
                         │      Tkinter GUI     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       P2P Node       │
                         │                      │
                         │  TCP Server          │
                         │  TCP Client          │
                         │  Peer Management     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     TCP Socket       │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
            ┌─────────┐        ┌─────────┐        ┌─────────┐
            │ Peer A  │        │ Peer B  │        │ Peer C  │
            └─────────┘        └─────────┘        └─────────┘
