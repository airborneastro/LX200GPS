#!/usr/bin/env python3
import subprocess
import signal
import sys
import time
import argparse

def parse_args():

    parser = argparse.ArgumentParser(
        description="LX200GPS Telescope Simulator"
    )


    parser.add_argument(
        "--clientport",
        default="/tmp/lx200client",
        help="Serial client port (indi-port), default /tmp/lx200client",
    )
    parser.add_argument(
        "--server",
        default="127.0.0.1",
        help="Simulator server IP, default localhost",
    )
    return parser.parse_args()

args = parse_args()
sim = None
if args.server == "127.0.0.1":
# simulator is on same machine, start it here
    sim = subprocess.Popen([
        "python", "/home/pi/LX200GPS/lx200gps_sim.py"
    ])

    time.sleep(1.0)
#simulator is on same machine, just open TCP2Serial
client = subprocess.Popen([
    "python", "/usr/local/bin/lx200gps_tcp.py",
    "--serial_port",
    args.clientport,
    "--server",
    args.server,
])


def shutdown(sig, frame):
    print("\nStopping all processes...")
    for p in (client, sim):
        if p is not None:
            p.terminate()

    time.sleep(1)

    for p in (client, sim):
        if p is not None:
            if p.poll() is None:
                p.kill()

    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

client.wait()
shutdown(None, None)
