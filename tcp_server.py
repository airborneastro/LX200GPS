#!/usr/bin/env python3

from __future__ import annotations

import socket
import threading
import time

from protocol import LX200Protocol


class LX200TCPServer(threading.Thread):

    def __init__(
        self,
        host: str,
        port: int,
        protocol: LX200Protocol,
    ):
        super().__init__(daemon=True)

        self.host = host
        self.port = port
        self.protocol = protocol

        self.running = True

        self.server = None
        self.conn = None

    # ----------------------------------------------------------
    # MAIN LOOP
    # ----------------------------------------------------------

    def run(self):

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.server.bind((self.host, self.port))
        self.server.listen(1)

        print(f"[server] listening on {self.host}:{self.port}")

        while self.running:

            try:
                conn, addr = self.server.accept()

            except OSError:
                break

            self.conn = conn

            print(f"[server] connection from {addr}")

            try:
                restart = self.handle_client(conn)

            finally:
                self.conn = None
            if restart:
                print("[server] restarting requested")
                break

        print("[server] TCP thread stopped")

    # ----------------------------------------------------------
    # CLIENT HANDLER
    # ----------------------------------------------------------

    def handle_client(self, conn):
        
        conn.settimeout(1.0)          # wake every second
        last_rx = time.monotonic()

        buffer = bytearray()

        try:

            while self.running:
                try:
                    data = conn.recv(1024)

                except socket.timeout:
                    if time.monotonic() - last_rx > 60:
                        print("[server] idle timeout")
                        return True      #request restart
                    continue
#                data = conn.recv(1024)

                if not data:
                    print("[server] client disconnected")
                    return False     #wait for another client

#                print(f"RX RAW: {data!r}")
                last_rx = time.monotonic()
                buffer.extend(data)

                while buffer:

                    # ACK (0x06)
                    if buffer[0] == 0x06:

                        cmd = b"\x06"
                        buffer = buffer[1:]

                    else:

                        try:
                            end = buffer.index(ord('#'))

                        except ValueError:
                            break

                        cmd = bytes(buffer[:end + 1])
                        buffer = buffer[end + 1:]

                    print(f"RX: {cmd}")

                    try:
                        response = self.protocol.process(cmd)

                    except Exception as ex:
                        print(f"PROTOCOL ERROR: {ex}")
                        continue

                    if response is None:
                        continue

                    if not isinstance(response, (bytes, bytearray)):
                        response = str(response).encode(
                            "ascii",
                            errors="ignore",
                        )

                    print(f"TX: {response}\n")

                    conn.sendall(response)

        except Exception as ex:

            if self.running:
                print(f"[server] connection error: {ex}")

        finally:

            try:
                conn.close()
            except Exception:
                pass

    # ----------------------------------------------------------
    # STOP
    # ----------------------------------------------------------

    def stop(self):

        self.running = False

        if self.conn:
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass

            try:
                self.conn.close()
            except Exception:
                pass

        if self.server:
            try:
                self.server.close()
            except Exception:
                pass