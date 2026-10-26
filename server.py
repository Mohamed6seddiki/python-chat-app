import queue
import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext

BUFFER_SIZE = 4096
DEFAULT_PORT = 5000
POLL_INTERVAL_MS = 100


class ChatServer:

    def __init__(self, events: queue.Queue):
        self.events = events
        self.server_socket = None
        self.running = False
        self.clients = {}
        self.lock = threading.Lock()

    
    def start(self, port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            sock.listen(5)
        except OSError:
            sock.close()
            raise
        self.server_socket = sock
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self.events.put(("log", f"Server listening on port {port}"))

    def stop(self) -> None:
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None
        with self.lock:
            conns = list(self.clients)
            self.clients.clear()
        for conn in conns:
            self._close(conn)
        self.events.put(("log", "Server stopped"))

    def _accept_loop(self) -> None:
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
            except OSError:
                break  
            with self.lock:
                self.clients[conn] = addr
            self.events.put(("log", f"Client connected: {addr[0]}:{addr[1]}"))
            self.events.put(("count", len(self.clients)))
            threading.Thread(
                target=self._client_loop, args=(conn, addr), daemon=True
            ).start()

    def _client_loop(self, conn: socket.socket, addr) -> None:
        label = f"{addr[0]}:{addr[1]}"
        buffer = b""
        try:
            while self.running:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break 
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").strip()
                    if text:
                        self.events.put(("log", f"[{label}] {text}"))
                        self._broadcast(f"[{label}] {text}", exclude=conn)
        except OSError:
            pass  
        finally:
            with self.lock:
                was_known = self.clients.pop(conn, None) is not None
            self._close(conn)
            if was_known:
                self.events.put(("log", f"Client disconnected: {label}"))
                self.events.put(("count", len(self.clients)))

    def _broadcast(self, text: str, exclude=None) -> None:
        payload = (text + "\n").encode("utf-8")
        with self.lock:
            targets = [c for c in self.clients if c is not exclude]
        for conn in targets:
            try:
                conn.sendall(payload)
            except OSError:
                pass 

    @staticmethod
    def _close(conn: socket.socket) -> None:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass


class ServerApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Chat Server")
        self.root.geometry("560x420")
        self.root.minsize(420, 300)

        self.events = queue.Queue()
        self.server = ChatServer(self.events)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(POLL_INTERVAL_MS, self._process_events)

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, padx=10, pady=10)
        top.pack(fill=tk.X)

        tk.Label(top, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.port_entry = tk.Entry(top, textvariable=self.port_var, width=8)
        self.port_entry.pack(side=tk.LEFT, padx=(5, 10))
        self.port_entry.bind("<Return>", lambda _e: self.toggle_server())

        self.listen_btn = tk.Button(
            top, text="Listen", width=10, command=self.toggle_server
        )
        self.listen_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Stopped | Clients: 0")
        tk.Label(top, textvariable=self.status_var, fg="gray30").pack(side=tk.RIGHT)

        self.log = scrolledtext.ScrolledText(
            self.root, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 10)
        )
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def toggle_server(self) -> None:
        if self.server.running:
            self.server.stop()
            self.listen_btn.config(text="Listen")
            self.port_entry.config(state=tk.NORMAL)
            self.status_var.set("Stopped | Clients: 0")
            return

        try:
            port = int(self.port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid port", "Enter a port between 1 and 65535.")
            return

        try:
            self.server.start(port)
        except OSError as exc:
            messagebox.showerror("Cannot start server", str(exc))
            return

        self.listen_btn.config(text="Stop")
        self.port_entry.config(state=tk.DISABLED)
        self.status_var.set("Listening | Clients: 0")

    def _append_log(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, f"[{stamp}] {text}\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def _process_events(self) -> None:
        """Runs in the GUI thread: drain events posted by worker threads."""
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self._append_log(value)
                elif kind == "count" and self.server.running:
                    self.status_var.set(f"Listening | Clients: {value}")
        except queue.Empty:
            pass
        self.root.after(POLL_INTERVAL_MS, self._process_events)

    def _on_close(self) -> None:
        self.server.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ServerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
