#!/usr/bin/env python3

import os
import pty
import socket
import select
import time
import errno
import sys   # <-- ADDED
import argparse

RECONNECT_DELAY = 1.0

def parse_args():

    parser = argparse.ArgumentParser(
        description="LX200GPS Simulator TCP2Serial client"
    )

   # TCP options

    parser.add_argument(
        "--server",
        default="127.0.0.1",
        help="TCP server address",
    )

    parser.add_argument(
        "--tcp_port",
        type=int,
        default=4030,
        help="TCP port",
    )
        # Serial options

    parser.add_argument(
        "--serial_port",
        default="/tmp/lx200client",
        help="Serial client port name",
    )

    return parser.parse_args()


# -----------------------------
# PTY (RECREATED ON EACH RECONNECT)
# -----------------------------

def create_pty(link):
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)

    try:
        os.remove(link)
    except FileNotFoundError:
        pass

    os.symlink(slave_name, link)

    os.close(slave_fd)

    return master_fd


# -----------------------------
# TCP CONNECT
# -----------------------------

def connect_tcp(server,tcp_port):
    while True:
        try:
            print(f"[lx200] Connecting to {server}:{tcp_port} ...")
#            print(f"[lx200] Connecting to {SERVER}:{PORT} ...")
            sock = socket.create_connection((server, tcp_port), timeout=5)
            sock.setblocking(False)
            print("[lx200] TCP connected")
            return sock

        except Exception as e:
            print(f"[lx200] connect failed: {e}")
            time.sleep(RECONNECT_DELAY)


# -----------------------------
# FULL RESTART (CRITICAL)
# -----------------------------

def restart(server,tcp_port,link):
    time.sleep(1)
    master = create_pty(link)
    sock = connect_tcp(server,tcp_port)
    return master, sock


# -----------------------------
# MAIN LOOP
# -----------------------------

def main():
    args = parse_args()
    master = create_pty(args.serial_port)
    sock = connect_tcp(args.server,args.tcp_port)
    print(f"Connect your client to : {args.serial_port}")
    try:   

        while True:

            try:
                r, _, _ = select.select([master, sock], [], [], 0.5)

                # PTY -> TCP
                if master in r:
                    try:
                        data = os.read(master, 1024)
                        if data:
                            sock.sendall(data)
                    except OSError as e:
                        if e.errno != errno.EIO:
                            print(f"[lx200] PTY error: {e}")

                # TCP -> PTY
                if sock in r:
                    data = sock.recv(1024)

                    if not data:
                        print("[lx200] TCP closed ? full restart")
                        try:
                            sock.close()
                        except:
                            pass
                        master, sock = restart(args.server,args.tcp_port,args.serial_port)
                        print(f"Connect your client to : {args.serial_port}")
                        continue

                    os.write(master, data)

            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                print(f"[lx200] socket error: {e}")
                try:
                    sock.close()
                except:
                    pass
                master, sock = restart(args.server,args.tcp_port,args.serial_port)
                print(f"Connect your client to : {args.serial_port}")
            except Exception as e:
                print(f"[lx200] unexpected error: {e}")
                try:
                    sock.close()
                except:
                    pass
                master, sock = restart(args.server,args.tcp_port,args.serial_port)
                print(f"Connect your client to : {args.serial_port}")
    except KeyboardInterrupt:   
        print("\n[lx200] Ctrl-C received, shutting down...")

    finally:   
        try:
            sock.close()
        except:
            pass

        try:
            os.close(master)
        except:
            pass

        try:
            if os.path.exists(args_serial_port):
                os.remove(args_serial_port)
        except:
            pass

        print("[lx200] stopped cleanly")


if __name__ == "__main__":
    main()