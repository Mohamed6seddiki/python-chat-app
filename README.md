# TCP Chat Application

A simple multi-client chat application built with Python, Tkinter, and TCP
sockets. The server displays connection and message logs, while each client has
a chat window for sending and receiving messages.

## Demo

<video src="./demo.mp4" controls width="720">
  Your browser cannot play the video. [Open the demo video](./demo.mp4).
</video>

## Requirements

- Python 3.8 or later
- Tkinter, which is included with most standard Python installations

The application uses only Python's standard library; no additional packages
are required.

## Run the application

1. Open a terminal in the project directory.
2. Start the server:

   ```bash
   python server.py
   ```

3. In another terminal, start a client:

   ```bash
   python client.py
   ```

4. In the server window, leave the port set to `5000` and click **Listen**.
5. In the client window, connect to `127.0.0.1` on port `5000`.
6. Start another client to chat between multiple clients. Messages are
   broadcast to the other connected clients and shown in the server log.

To connect from another computer on the same network, start the server on the
host computer and enter that computer's local IP address in the client. Ensure
the server port is allowed through the host's firewall.

## Configuration

Both programs default to port `5000`. The port can be changed in the respective
window before starting or connecting. The client defaults to `127.0.0.1`, which
connects to a server running on the same computer.

## Notes

This is a basic demonstration project. Messages are not encrypted, and the
server does not authenticate clients. Use it only on trusted networks.
