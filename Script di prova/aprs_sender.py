#!/usr/bin/env python3
"""
Invia un frame KISS via TCP per essere trasmesso e ripetuto.
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
        destination="IR6A",
        source=MYCALL,
        path=["WIDE1-1,WIDE2-2"],
        info=">Test invio APRS via KISS3 + Python",
    )
    ki.write(frame)

if __name__ == "__main__":
    main()
