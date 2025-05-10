#!/usr/bin/env python3
"""
Legge e stampa frame KISS da un socket TCP
"""
import os
from ax253 import Frame
import kiss

KISS_HOST = os.environ.get("KISS_HOST", "localhost")
KISS_PORT = os.environ.get("KISS_PORT", "8001")


def print_frame(frame):
    print(Frame.from_bytes(frame))


def main():
    ki = kiss.TCPKISS(host=KISS_HOST, port=int(KISS_PORT), strip_df_start=True)
    ki.start()
    ki.read(callback=print_frame, min_frames=None)


if __name__ == "__main__":
    main()

