#!/usr/bin/env python3
#
# LX200GPS Simulator
#

from __future__ import annotations

import argparse
import sys
import time
import subprocess
import sys
import os

from telescope import TelescopeState, MountState
from simulator import TelescopeSimulator
from protocol import LX200Protocol

from tcp_server import LX200TCPServer


# ------------------------------------------------------------
# Command line
# ------------------------------------------------------------

def parse_args():

    parser = argparse.ArgumentParser(
        description="LX200GPS Telescope Simulator"
    )




    # TCP options

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="TCP bind address",
    )

    parser.add_argument(
        "--tcp-port",
        type=int,
        default=4030,
        help="TCP port",
    )

    return parser.parse_args()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    args = parse_args()

    print("========================================")
    print(" LX200GPS Simulator")
    print("========================================")

    print(f"Host      : {args.host}")
    print(f"TCP Port  : {args.tcp_port}")

    print("========================================")



    # --------------------------------------------------------
    # Motion simulator
    # --------------------------------------------------------
    server = None
    sim = None

    try:
        while True:

            state = TelescopeState()
            state.state_mode = MountState.NORMAL
            state.pending_park = False
            state.slewing = False
            state.tracking = True

            protocol = LX200Protocol(state)
            sim = TelescopeSimulator(state)
            sim.start()

            # --------------------------------------------------------
            # Communication server
            # --------------------------------------------------------


            server = LX200TCPServer(
                host=args.host,
                port=args.tcp_port,
                protocol=protocol,
            )
            
            server.start()

            print("Simulator running. Press Ctrl+C to stop.")

            server.join()

            sim.stop()
            sim.join()

            print("Restarting simulator...")

    except KeyboardInterrupt:

        print("\nStopping...")

        if server is not None:
            server.stop()
            server.join()

        if sim is not None:
            sim.stop()
            sim.join()

        print("Stopped cleanly.")
        sys.exit(0)


if __name__ == "__main__":
    main()