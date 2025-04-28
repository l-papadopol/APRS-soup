#!/usr/bin/env python3
"""
Server APRS con Leaflet + Flask.
Usa aprslib per il parsing e aggiorna le posizioni in tempo reale con mappa dinamica.
Utilizza SQLite per salvare le posizioni con storico.
Ogni tipo di SSID ha un'icona diversa.
"""

import os
import time
import json
import sqlite3
import aprslib
from ax253 import Frame
import kiss
from flask import Flask, send_from_directory, request

# Nome file del database SQLite
DB_FILE = "positions.db"

# Configurazione KISS
KISS_HOST = os.environ.get("KISS_HOST", "localhost")
KISS_PORT = int(os.environ.get("KISS_PORT", "8001"))

def init_db():
    """Crea la tabella positions se non esiste."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        callsign TEXT,
        lat REAL,
        lon REAL,
        ssid TEXT,
        timestamp REAL
    )
    """)
    conn.commit()
    conn.close()

def extract_ssid(callsign):
    if '-' in callsign:
        return callsign.split('-')[-1]
    return "0"

def handle_frame(raw_frame):
    try:
        frame = Frame.from_bytes(raw_frame)
        aprs_msg = str(frame)
        parsed = aprslib.parse(aprs_msg)

        if 'latitude' in parsed and 'longitude' in parsed:
            lat = parsed['latitude']
            lon = parsed['longitude']
            source = parsed['from']
            ssid = extract_ssid(source)
            ts = time.time()

            print(f"{source} > POSIZIONE: {lat:.5f}, {lon:.5f} (SSID: -{ssid})", flush=True)

            # Inserisce la posizione nel database
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO positions (callsign, lat, lon, ssid, timestamp) VALUES (?,?,?,?,?)",
                               (source, lat, lon, ssid, ts))
                conn.commit()
                conn.close()
            except Exception as db_e:
                print(f"Errore nell'inserimento su DB: {db_e}", flush=True)
    except Exception as e:
        print(f"Errore nel parsing frame: {e}", flush=True)

def kiss_reader():
    ki = kiss.TCPKISS(host=KISS_HOST, port=KISS_PORT, strip_df_start=True)
    ki.start()
    ki.read(callback=handle_frame, min_frames=None)

def get_realtime_positions():
    """Recupera per ogni callsign la posizione più recente, inclusa il timestamp."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    query = """
    SELECT p1.callsign, p1.lat, p1.lon, p1.ssid, p1.timestamp FROM positions p1
    INNER JOIN (
        SELECT callsign, MAX(timestamp) as maxts FROM positions GROUP BY callsign
    ) p2 ON p1.callsign = p2.callsign AND p1.timestamp = p2.maxts
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    positions = {}
    for row in rows:
        callsign, lat, lon, ssid, ts = row
        positions[callsign] = {"lat": lat, "lon": lon, "ssid": ssid, "timestamp": ts}
    return positions

def get_history_positions(interval_seconds):
    """Recupera le posizioni registrate nell'intervallo (in secondi) passato."""
    cutoff = time.time() - interval_seconds
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT callsign, lat, lon, ssid, timestamp FROM positions WHERE timestamp >= ? ORDER BY timestamp", (cutoff,))
    rows = cursor.fetchall()
    conn.close()
    history = {}
    for row in rows:
        callsign, lat, lon, ssid, ts = row
        if callsign not in history:
            history[callsign] = []
        history[callsign].append({"lat": lat, "lon": lon, "ssid": ssid, "timestamp": ts})
    return history

def main():
    init_db()
    threading_thread = __import__("threading")
    threading_thread.Thread(target=kiss_reader, daemon=True).start()

    app = Flask(__name__)

    @app.route('/')
    def index():
        return send_from_directory('.', 'map_template.html')

    @app.route('/positions.json')
    def json_data():
        data = get_realtime_positions()
        return json.dumps(data)

    @app.route('/icons/<path:filename>')
    def serve_icons(filename):
        return send_from_directory('icons', filename)

    @app.route('/geo/<path:filename>')
    def serve_geo_tiles(filename):
        return send_from_directory('geo', filename)

    app.run(host='0.0.0.0', port=5021)

if __name__ == "__main__":
    main()
