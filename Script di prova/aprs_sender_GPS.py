#!/usr/bin/env python3
"""
Invia un frame KISS via TCP per trasmettere la posizione GPS tramite APRS.
Coordinate: 43.93706804594771, 12.768742598481566
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
    # Posizione in formato APRS:
    # Latitudine: 43°56.22'N, Longitudine: 012°46.12'E con simbolo ">" (veicolo)
    gps_info = "!4356.22N/01246.12E>"
    frame = Frame.ui(
        destination="APRS",
        source=MYCALL,
        path=["WIDE1-1"],
        info=gps_info,
    )
    ki.write(frame)

if __name__ == "__main__":
    main()
