# APRS-soup.py
#!/usr/bin/env python3
"""
Server APRS con Leaflet + Flask.
Usa aprslib per il parsing e aggiorna le posizioni in tempo reale con mappa dinamica.
Utilizza SQLite per salvare i dati stazione/posizione/timestamp e i messaggi.
Ogni tipo di SSID ha un'icona diversa.
Include la possibilità di inviare e ricevere messaggi APRS e notifica in real-time via SSE.

(C) 2025 Papadopol Lucian Ioan - licenza CC BY-NC-ND 3.0 IT
"""

import os
import time
import json
import sqlite3
import aprslib
import queue
import kiss
from ax253 import Frame
from flask import Flask, send_from_directory, request, Response

DB_FILE     = "positions.db"
KISS_HOST   = os.environ.get("KISS_HOST", "localhost")
KISS_PORT   = int(os.environ.get("KISS_PORT", "8001"))
MYCALL      = os.environ.get("MYCALL", "IZ6NNH")

subscribers = []  # list of Queue for SSE

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        callsign TEXT, lat REAL, lon REAL,
        ssid TEXT, timestamp REAL
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT, recipient TEXT,
        info TEXT, timestamp REAL
      )
    """)
    conn.commit()
    conn.close()

def extract_ssid(callsign):
    return callsign.split('-')[-1] if '-' in callsign else "0"

def notify_subscribers(msg):
    data = json.dumps(msg)
    for q in list(subscribers):
        q.put(data)

def handle_frame(raw_frame):
    try:
        frame    = Frame.from_bytes(raw_frame)
        aprs_msg = str(frame)
        parsed   = aprslib.parse(aprs_msg)
        print(f"PARSED: {parsed}", flush=True)

        # posizione APRS?
        if 'latitude' in parsed and 'longitude' in parsed:
            lat, lon = parsed['latitude'], parsed['longitude']
            src      = parsed['from']
            ssid     = extract_ssid(src)
            ts       = time.time()
            try:
                conn = sqlite3.connect(DB_FILE)
                c    = conn.cursor()
                c.execute(
                  "INSERT INTO positions (callsign,lat,lon,ssid,timestamp) VALUES (?,?,?,?,?)",
                  (src, lat, lon, ssid, ts)
                )
                conn.commit()
            except Exception as e:
                print(f"DB error pos: {e}", flush=True)
            finally:
                conn.close()
            # SSE notify
            notify_subscribers({
                "type": "position",
                "callsign": src,
                "lat": lat,
                "lon": lon,
                "ssid": ssid,
                "timestamp": ts
            })

        # messaggio APRS?
        elif parsed.get('type') == 'message' or (
             'to' in parsed and 'info' in parsed and 'latitude' not in parsed):
            sender    = parsed['from']
            recipient = parsed['to']
            info      = parsed['info']
            ts        = time.time()
            print(f"MESSAGE: from={sender} to={recipient} info={info}", flush=True)
            try:
                conn = sqlite3.connect(DB_FILE)
                c    = conn.cursor()
                c.execute(
                  "INSERT INTO messages (sender,recipient,info,timestamp) VALUES (?,?,?,?)",
                  (sender, recipient, info, ts)
                )
                conn.commit()
            except Exception as e:
                print(f"DB error msg: {e}", flush=True)
            finally:
                conn.close()

    except Exception as e:
        print(f"PARSE ERROR: {e}", flush=True)

def get_realtime_positions():
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("""
      SELECT p1.callsign,p1.lat,p1.lon,p1.ssid,p1.timestamp
      FROM positions p1
      JOIN (
        SELECT callsign, MAX(timestamp) AS maxts
        FROM positions GROUP BY callsign
      ) p2 ON p1.callsign=p2.callsign AND p1.timestamp=p2.maxts
    """)
    rows = c.fetchall()
    conn.close()
    out = {}
    for callsign, lat, lon, ssid, ts in rows:
        out[callsign] = {
            "lat": lat, "lon": lon,
            "ssid": ssid, "timestamp": ts
        }
    return out

def get_recent_messages(limit=50):
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("""
      SELECT sender,recipient,info,timestamp
      FROM messages
      ORDER BY timestamp DESC
      LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [
      {"sender":s,"recipient":r,"info":i,"timestamp":t}
      for s,r,i,t in rows
    ]

def sse_stream():
    q = queue.Queue()
    subscribers.append(q)
    try:
        while True:
            data = q.get()
            yield f"data: {data}\n\n"
    except GeneratorExit:
        subscribers.remove(q)

def main():
    init_db()

    # connessione KISS unica
    global global_kiss
    global_kiss = kiss.TCPKISS(
        host=KISS_HOST,
        port=KISS_PORT,
        strip_df_start=True
    )
    global_kiss.start()

    import threading
    threading.Thread(
      target=global_kiss.read,
      kwargs={'callback': handle_frame, 'min_frames': None},
      daemon=True
    ).start()

    app = Flask(__name__)

    @app.route('/')
    def index():
        return send_from_directory('.', 'map_template.html')

    @app.route('/positions.json')
    def positions_json():
        rp = request.args.get('range', 'realtime')
        data = get_realtime_positions()
        if rp != 'realtime':
            M = {'15m':15*60,'30m':30*60,'1h':3600,'6h':6*3600,'12h':12*3600,'24h':24*3600}
            secs = M.get(rp)
            if secs:
                cutoff = time.time() - secs
                data = {cs:pos for cs,pos in data.items() if pos['timestamp']>=cutoff}
        return json.dumps(data)

    @app.route('/messages.json')
    def messages_json():
        return json.dumps(get_recent_messages())

    @app.route('/icons/<path:f>')
    def icons(f):
        return send_from_directory('icons', f)

    @app.route('/geo/<path:f>')
    def geo(f):
        return send_from_directory('geo', f)

    @app.route('/leaflet_customized.css')
    def css():
        return send_from_directory('.', 'leaflet.css')

    @app.route('/js/leaflet.js')
    def js():
        return send_from_directory('.', 'leaflet.js')

    @app.route('/js/APRS-soup.js')
    def app_js():
        return send_from_directory('.', 'APRS-soup.js')

    @app.route('/stream')
    def stream():
        return Response(sse_stream(), mimetype="text/event-stream")

    @app.route('/send_message', methods=['POST'])
    def send_message():
        dest = request.form.get('destination')
        msg  = request.form.get('message')
        if not dest or not msg:
            return "destination e message necessari", 400
        try:
            frame = Frame.ui(
                destination=dest,
                source=MYCALL,
                path=["WIDE2-2"],
                info=">" + msg
            )
            global_kiss.write(frame)
            return "Messaggio inviato", 200
        except Exception as e:
            return str(e), 500

    app.run(host='0.0.0.0', port=5032)

if __name__ == "__main__":
    main()
