#!/usr/bin/env python3
"""
Legge frame KISS da un socket TCP e stampa, per i pacchetti APRS di posizione,
la riga:

    NOMINATIVO > POSIZIONE: lat long

- Riconosce un eventuale simbolo introduttore (!, =, /, @)
- Gestisce un timestamp zulu opzionale (hhmmssz) subito dopo l’introduttore
- Accetta sia "/" che ""\\"" come separatore lat/lon
- Formato delle coordinate: DDMM.mmN/DDDMM.mmE
"""

import os
import re
from ax253 import Frame
import kiss

KISS_HOST = os.environ.get("KISS_HOST", "localhost")
KISS_PORT = int(os.environ.get("KISS_PORT", "8001"))

# Regex per estrarre coordinate
POSITION_RE = re.compile(
    r'(?:[!=/@])?'                 # uso futuro?
    r'(?:\d{6}z)?'                 # timestamp zulu (hhmmssz) uso futuro?
    r'(?P<lat_deg>\d{2})'
    r'(?P<lat_min>\d{2}\.\d{2})'
    r'(?P<lat_dir>[NS])'
    r'[/\\]'
    r'(?P<lon_deg>\d{3})'
    r'(?P<lon_min>\d{2}\.\d{2})'
    r'(?P<lon_dir>[EW])'
)

def extract_source(aprs_msg: str) -> str | None:
    """Restituisce il nominativo (campo source) dal messaggio APRS."""
    return aprs_msg.split('>', 1)[0] if '>' in aprs_msg else None


def parse_position(aprs_msg: str) -> tuple[float | None, float | None]:
    """Estrae latitudine e longitudine (gradi decimali) dal messaggio APRS."""
    match = POSITION_RE.search(aprs_msg)
    if not match:
        return None, None

    try:
        lat_deg = int(match.group("lat_deg"))
        lat_min = float(match.group("lat_min"))
        latitude = lat_deg + lat_min / 60
        if match.group("lat_dir") == "S":
            latitude = -latitude

        lon_deg = int(match.group("lon_deg"))
        lon_min = float(match.group("lon_min"))
        longitude = lon_deg + lon_min / 60
        if match.group("lon_dir") == "W":
            longitude = -longitude

        return latitude, longitude
    except (ValueError, TypeError):
        return None, None


def handle_frame(raw_frame: bytes) -> None:
    """Callback per kiss.TCPKISS.read: deframma, estrae e stampa la posizione."""
    frame = Frame.from_bytes(raw_frame)
    aprs_msg = str(frame)

    source = extract_source(aprs_msg)
    latitude, longitude = parse_position(aprs_msg)

    if source and latitude is not None and longitude is not None:
        print(f"{source} > POSIZIONE: {latitude:.5f} {longitude:.5f}")


def main() -> None:
    """Apre la sessione KISS/TCP e resta in ascolto finchè non riceve Ctrl-C."""
    ki = kiss.TCPKISS(host=KISS_HOST, port=KISS_PORT, strip_df_start=True)
    ki.start()

    try:
        ki.read(callback=handle_frame)  # ciclo continuo
    except KeyboardInterrupt:
        pass
    finally:
        ki.stop()


if __name__ == "__main__":
    main()

