#!/usr/bin/env python3
"""
Legge frame KISS da un socket TCP e mostra solo il nominativo e la posizione GPS in formato:
NOMINATIVO > POSIZIONE: lat long

Il parsing della posizione gestisce:
- il caso in cui la posizione inizia direttamente con "!" (o altri simboli)
- il caso in cui è preceduta da un timestamp in formato zulu (6 cifre seguite da "z")
Il formato previsto per le coordinate è: DDMM.mmN/DDDMM.mmE
"""
import os
import re
from ax253 import Frame
import kiss

KISS_HOST = os.environ.get("KISS_HOST", "localhost")
KISS_PORT = int(os.environ.get("KISS_PORT", "8001"))

def extract_source(aprs_msg):
    """
    Estrae il nominativo (mittente) dalla parte header del messaggio APRS,
    ovvero la parte che precede il carattere '>'.
    """
    if '>' in aprs_msg:
        return aprs_msg.split('>')[0]
    return None

def parse_position(aprs_msg):
    """
    Estrae la posizione GPS dal messaggio APRS.

    Cerca (opzionalmente) un timestamp in formato zulu (6 cifre seguite da "z")
    e poi i dati della posizione nel formato:
      DDMM.mmN/DDDMM.mmE
    """
    pattern = r'(?:\d{6}z)?(?P<lat_deg>\d{2})(?P<lat_min>\d{2}\.\d{2})(?P<lat_dir>[NS])[/\\](?P<lon_deg>\d{3})(?P<lon_min>\d{2}\.\d{2})(?P<lon_dir>[EW])'
    m = re.search(pattern, aprs_msg)
    if m:
        try:
            # Calcolo della latitudine in gradi decimali
            lat_deg = int(m.group("lat_deg"))
            lat_min = float(m.group("lat_min"))
            latitude = lat_deg + lat_min / 60.0
            if m.group("lat_dir") == "S":
                latitude = -latitude

            # Calcolo della longitudine in gradi decimali
            lon_deg = int(m.group("lon_deg"))
            lon_min = float(m.group("lon_min"))
            longitude = lon_deg + lon_min / 60.0
            if m.group("lon_dir") == "W":
                longitude = -longitude

            return latitude, longitude
        except Exception:
            return None, None
    return None, None

def handle_frame(raw_frame):
    frame = Frame.from_bytes(raw_frame)
    aprs_msg = str(frame)
    source = extract_source(aprs_msg)
    latitude, longitude = parse_position(aprs_msg)
    if source and latitude is not None and longitude is not None:
        print(f"{source} > POSIZIONE: {latitude:.5f} {longitude:.5f}")

def main():
    ki = kiss.TCPKISS(host=KISS_HOST, port=KISS_PORT, strip_df_start=True)
    ki.start()
    ki.read(callback=handle_frame, min_frames=None)

if __name__ == "__main__":
    main()
