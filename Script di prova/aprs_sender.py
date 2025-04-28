#!/usr/bin/env python3
"""
Invia un frame KISS via TCP per essere trasmesso e ripetuto tramite WIDE1-1 e WIDE2-2.
"""
import os
from ax253 import Frame
import kiss

MYCALL = os.environ.get("MYCALL", "IZ6NNH")
KISS_HOST = os.environ.get("KISS_HOST", "localhost")
KISS_PORT = os.environ.get("KISS_PORT", "8001")

def main():
    ki = kiss.TCPKISS(host=KISS_HOST, port=int(KISS_PORT), strip_df_start=True)
    ki.start()
    frame = Frame.ui(
        destination="IZ6NNH-8",
        source=MYCALL,
        path=["WIDE3-3"],
        info=">Test invio APRS via KISS3 + Python",
    )
    ki.write(frame)

if __name__ == "__main__":
    main()
