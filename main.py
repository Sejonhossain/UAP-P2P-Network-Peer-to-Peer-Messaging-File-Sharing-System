"""
main.py - Tkinter GUI for the P2P network.  Run with:  python main.py
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from p2p_node import P2PNode

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")


class App:
    def __init__(self, root):
        self.root = root
        self.node = None
        self.peer_ids = []                   # parallel to the listbox rows
        self.ui_queue = queue.Queue()        # worker threads -> GUI thread

        root.title("UAP P2P Network")
        root.geometry("900x620")
        root.minsize(700, 500)
        self._build_ui()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_queue()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # --- My Peer
        my = ttk.LabelFrame(self.root, text="My Peer")
        my.pack(fill="x", **pad)
        ttk.Label(my, text="Name:").grid(row=0, column=0, padx=4, pady=4)
        self.name_var = tk.StringVar(value="Alice")
        ttk.Entry(my, textvariable=self.name_var, width=16).grid(row=0, column=1)
        ttk.Label(my, text="Port:").grid(row=0, column=2, padx=4)
        self.port_var = tk.StringVar(value="5000")
        ttk.Entry(my, textvariable=self.port_var, width=8).grid(row=0, column=3)
        self.start_btn = ttk.Button(my, text="Start Peer", command=self.start_peer)
        self.start_btn.grid(row=0, column=4, padx=8)
        self.stop_btn = ttk.Button(my, text="Stop", command=self.stop_peer,
                                   state="disabled")
        self.stop_btn.grid(row=0, column=5)
        self.info_var = tk.StringVar(value="Peer not started")
        ttk.Label(my, textvariable=self.info_var).grid(
            row=1, column=0, columnspan=6, sticky="w", padx=4, pady=2)

        # --- Connect
        con = ttk.LabelFrame(self.root, text="Connect to Another Peer")
        con.pack(fill="x", **pad)
        ttk.Label(con, text="IP:").grid(row=0, column=0, padx=4, pady=4)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(con, textvariable=self.ip_var, width=18).grid(row=0, column=1)
        ttk.Label(con, text="Port:").grid(row=0, column=2, padx=4)
        self.rport_var = tk.StringVar(value="5001")
        ttk.Entry(con, textvariable=self.rport_var, width=8).grid(row=0, column=3)
        self.connect_btn = ttk.Button(con, text="Connect", command=self.connect_peer)
        self.connect_btn.grid(row=0, column=4, padx=8)

        # --- Middle: peer list + log
        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, **pad)
        mid.columnconfigure(1, weight=1)
        mid.rowconfigure(0, weight=1)

        peers_frame = ttk.LabelFrame(mid, text="Connected Peers")
        peers_frame.grid(row=0, column=0, sticky="ns", padx=(0, 6))
        self.peer_list = tk.Listbox(peers_frame, width=30, exportselection=False)
        self.peer_list.pack(fill="both", expand=True, padx=4, pady=4)

        log_frame = ttk.LabelFrame(mid, text="Messages / Events")
        log_frame.grid(row=0, column=1, sticky="nsew")
        self.log = tk.Text(log_frame, state="disabled", wrap="word",
                           font=("Courier", 10))
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True, padx=(4, 0), pady=4)
        self.log.tag_config("system", foreground="#555555")
        self.log.tag_config("error", foreground="#c62828")
        self.log.tag_config("message", foreground="#1b5e20")

        # --- Send text
        txt = ttk.LabelFrame(self.root, text="Send Text")
        txt.pack(fill="x", **pad)
        self.msg_var = tk.StringVar()
        entry = ttk.Entry(txt, textvariable=self.msg_var)
        entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        entry.bind("<Return>", lambda e: self.send_text())
        ttk.Button(txt, text="Send", command=self.send_text).pack(
            side="right", padx=4, pady=4)

        # --- Send file
        fil = ttk.LabelFrame(self.root, text="Send File")
        fil.pack(fill="x", **pad)
        ttk.Label(fil, text="Text, image, audio, video, PDF, ZIP, etc.").pack(
            side="left", padx=4, pady=4)
        ttk.Button(fil, text="Choose File & Send", command=self.send_file).pack(
            side="right", padx=4, pady=4)

        # --- Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")

    # ------------------------------------------- thread-safe callbacks
    def _on_event(self, text, kind):
        self.ui_queue.put(("event", text, kind))

    def _on_peers_changed(self, peers):
        self.ui_queue.put(("peers", peers))

    def _poll_queue(self):
        """Runs on the GUI thread; applies updates queued by worker threads."""
        try:
            while True:
                item = self.ui_queue.get_nowait()
                if item[0] == "event":
                    self._append_log(item[1], item[2])
                elif item[0] == "peers":
                    self._refresh_peers(item[1])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _append_log(self, text, kind):
        prefix = {"system": "[SYSTEM] ", "error": "[ERROR] "}.get(kind, "")
        self.log.configure(state="normal")
        self.log.insert("end", prefix + text + "\n", kind)
        self.log.see("end")
        self.log.configure(state="disabled")
        self.status_var.set(text)

    def _refresh_peers(self, peers):
        selected = self._selected_peer_id()
        self.peer_list.delete(0, "end")
        self.peer_ids = []
        for peer_id, display in peers:
            self.peer_list.insert("end", display)
            self.peer_ids.append(peer_id)
            if peer_id == selected:
                self.peer_list.selection_set("end")

    def _selected_peer_id(self):
        sel = self.peer_list.curselection()
        if sel and sel[0] < len(self.peer_ids):
            return self.peer_ids[sel[0]]
        if len(self.peer_ids) == 1:          # convenience: only one peer -> use it
            return self.peer_ids[0]
        return None

    # ------------------------------------------------------- actions
    def start_peer(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a peer name.")
            return
        try:
            port = int(self.port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Port must be a number from 1 to 65535.")
            return

        node = P2PNode(name, port, self._on_event, self._on_peers_changed,
                       DOWNLOAD_DIR)
        try:
            node.start()
        except OSError as exc:
            self._append_log(f"Could not start peer on port {port}: {exc}", "error")
            return
        self.node = node
        self.info_var.set(f"{name} | ID: {node.peer_id} | Port: {port}")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

    def stop_peer(self):
        if self.node:
            self.node.stop()
            self.node = None
        self.info_var.set("Peer not started")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _require_node(self):
        if self.node is None:
            self._append_log("Start your peer first", "error")
            return False
        return True

    def connect_peer(self):
        if not self._require_node():
            return
        ip, port = self.ip_var.get(), self.rport_var.get()
        # connect() can block for a few seconds, so run it off the GUI thread
        threading.Thread(target=self.node.connect, args=(ip, port),
                         daemon=True).start()

    def send_text(self):
        if not self._require_node():
            return
        text = self.msg_var.get()
        if self.node.send_text(self._selected_peer_id(), text):
            self.msg_var.set("")

    def send_file(self):
        if not self._require_node():
            return
        peer_id = self._selected_peer_id()
        if peer_id is None:
            self._append_log("Select a peer first", "error")
            return
        path = filedialog.askopenfilename(title="Choose a file to send")
        if not path:
            return
        threading.Thread(target=self.node.send_file, args=(peer_id, path),
                         daemon=True).start()

    def _on_close(self):
        if self.node:
            self.node.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
