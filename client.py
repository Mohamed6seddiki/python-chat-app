import queue
import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext

BUFFER_SIZE = 4096
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
CONNECT_TIMEOUT = 5
POLL_INTERVAL_MS = 100


class ChatClient:
    """Socket logic only. Reports everything through an event queue."""

    def __init__(self, events: queue.Queue):
        self.events = events
        self.sock = None
        self.connected = False

    def connect(self, host: str, port: int) -> None:
        """Connect in a worker thread so the GUI stays responsive."""
        threading.Thread(
            target=self._connect_worker, args=(host, port), daemon=True
        ).start()

    def _connect_worker(self, host: str, port: int) -> None:
        try:
            sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
            sock.settimeout(None)  
        except OSError as exc:
            self.events.put(("connect_failed", str(exc)))
            return
        self.sock = sock
        self.connected = True
        self.events.put(("connected", f"{host}:{port}"))
        self._receive_loop(sock)

    def _receive_loop(self, sock: socket.socket) -> None:
        buffer = b""
        try:
            while self.connected:
                data = sock.recv(BUFFER_SIZE)
                if not data:
                    break 
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").strip()
                    if text:
                        self.events.put(("message", text))
        except OSError:
            pass  
        finally:
            was_connected = self.connected
            self._cleanup()
            if was_connected:  
                self.events.put(("disconnected", "Connection closed by server"))

    def send(self, text: str) -> None:
        if not self.connected or not self.sock:
            raise OSError("Not connected")
        self.sock.sendall((text + "\n").encode("utf-8"))

    def disconnect(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        self.connected = False
        sock, self.sock = self.sock, None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass


class ClientApp:
    """tkinter front-end."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Chat Client")
        self.root.geometry("520x500")
        self.root.minsize(400, 350)

        self.events = queue.Queue()
        self.client = ChatClient(self.events)

        self._build_ui()
        self._set_connected(False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(POLL_INTERVAL_MS, self._process_events)

    def _build_ui(self) -> None:

        top = tk.Frame(self.root, padx=10, pady=10)
        top.pack(fill=tk.X)

        tk.Label(top, text="Server IP:").pack(side=tk.LEFT)
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.host_entry = tk.Entry(top, textvariable=self.host_var, width=16)
        self.host_entry.pack(side=tk.LEFT, padx=(5, 10))

        tk.Label(top, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.port_entry = tk.Entry(top, textvariable=self.port_var, width=7)
        self.port_entry.pack(side=tk.LEFT, padx=(5, 10))

        self.connect_btn = tk.Button(
            top, text="Connect", width=10, command=self.toggle_connection
        )
        self.connect_btn.pack(side=tk.LEFT)

        self.history = scrolledtext.ScrolledText(
            self.root, state=tk.DISABLED, wrap=tk.WORD, font=("Segoe UI", 10)
        )
        self.history.pack(fill=tk.BOTH, expand=True, padx=10)
        self.history.tag_config("me", foreground="#1a5fb4")
        self.history.tag_config("other", foreground="#000000")
        self.history.tag_config("system", foreground="#777777", font=("Segoe UI", 9, "italic"))
        self.history.tag_config("error", foreground="#c01c28")

        bottom = tk.Frame(self.root, padx=10, pady=10)
        bottom.pack(fill=tk.X)

        self.message_var = tk.StringVar()
        self.message_entry = tk.Entry(bottom, textvariable=self.message_var)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.message_entry.bind("<Return>", lambda _e: self.send_message())

        self.send_btn = tk.Button(bottom, text="Send", width=10, command=self.send_message)
        self.send_btn.pack(side=tk.RIGHT)

    def _set_connected(self, connected: bool) -> None:
        conn_state = tk.DISABLED if connected else tk.NORMAL
        msg_state = tk.NORMAL if connected else tk.DISABLED
        self.host_entry.config(state=conn_state)
        self.port_entry.config(state=conn_state)
        self.message_entry.config(state=msg_state)
        self.send_btn.config(state=msg_state)
        self.connect_btn.config(
            text="Disconnect" if connected else "Connect", state=tk.NORMAL
        )
        if connected:
            self.message_entry.focus_set()

    def toggle_connection(self) -> None:
        if self.client.connected:
            self.client.disconnect()
            self._set_connected(False)
            self._append("Disconnected", "system")
            return

        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get())
            if not host or not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid input", "Enter a server IP and a port (1-65535).")
            return

        self.connect_btn.config(state=tk.DISABLED, text="Connecting...")
        self._append(f"Connecting to {host}:{port} ...", "system")
        self.client.connect(host, port)

    def send_message(self) -> None:
        text = self.message_var.get().strip()
        if not text:
            return
        try:
            self.client.send(text)
        except OSError as exc:
            self._append(f"Send failed: {exc}", "error")
            return
        self._append(f"You: {text}", "me")
        self.message_var.set("")

    def _append(self, text: str, tag: str = "other") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.history.config(state=tk.NORMAL)
        self.history.insert(tk.END, f"[{stamp}] {text}\n", tag)
        self.history.see(tk.END)
        self.history.config(state=tk.DISABLED)

    def _process_events(self) -> None:
        """Runs in the GUI thread: drain events posted by worker threads."""
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "connected":
                    self._set_connected(True)
                    self._append(f"Connected to {value}", "system")
                elif kind == "connect_failed":
                    self._set_connected(False)
                    self._append(f"Connection failed: {value}", "error")
                elif kind == "message":
                    self._append(value, "other")
                elif kind == "disconnected":
                    self._set_connected(False)
                    self._append(value, "error")
        except queue.Empty:
            pass
        self.root.after(POLL_INTERVAL_MS, self._process_events)

    def _on_close(self) -> None:
        self.client.disconnect()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ClientApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
