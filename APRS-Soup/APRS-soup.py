#!/usr/bin/env python3
# --------------------------------------------------------------------------- #
# APRS-soup – server Flask + Leaflet                                          #
#                                                                             #
# • legge i frame AX.25 da Direwolf/KISS e li analizza con aprslib            #
# • salva posizioni e messaggi in SQLite                                      #
# • invia aggiornamenti ai browser via Server-Sent Events                     #
# • offre mappa e API JSON                                                    #
#                                                                             #
# © 2025 Papadopol Lucian Ioan – CC BY-NC-ND 3.0 IT                            #
# --------------------------------------------------------------------------- #

import os, time, json, sqlite3, queue, threading
import aprslib, kiss
from ax253 import Frame
from flask import Flask, send_from_directory, request, Response

# --------------------------------------------------------------------------- #
# Config                                                                      #
# --------------------------------------------------------------------------- #
DB_FILE   = "positions.db"
KISS_HOST = os.getenv("KISS_HOST", "localhost")
KISS_PORT = int(os.getenv("KISS_PORT", "8001"))
MYCALL    = os.getenv("MYCALL",   "IZ6NNH")

subscribers = []          # code SSE
_kiss_link  = None        # link KISS attualmente attivo
_kiss_lock  = threading.Lock()  # protegge l’accesso a _kiss_link

# --------------------------------------------------------------------------- #
# Database                                                                    #
# --------------------------------------------------------------------------- #
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur  = conn.cursor()
    cur.executescript("""
      CREATE TABLE IF NOT EXISTS positions (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        callsign  TEXT,
        lat       REAL,
        lon       REAL,
        ssid      TEXT,
        timestamp REAL
      );
      CREATE TABLE IF NOT EXISTS messages (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        sender    TEXT,
        recipient TEXT,
        info      TEXT,
        timestamp REAL
      );
    """)
    conn.commit()
    conn.close()

# --------------------------------------------------------------------------- #
# Utilità                                                                     #
# --------------------------------------------------------------------------- #
def extract_ssid(callsign):
    return callsign.split('-')[-1] if '-' in callsign else "0"

def notify(msg):
    data = json.dumps(msg)
    for q in list(subscribers):
        q.put(data)

# --------------------------------------------------------------------------- #
# Gestione frame KISS                                                         #
# --------------------------------------------------------------------------- #
def handle_frame(raw):
    try:
        pkt = aprslib.parse(str(Frame.from_bytes(raw)))
        print("PARSED:", pkt, flush=True)

        # posizione
        if 'latitude' in pkt and 'longitude' in pkt:
            lat, lon = pkt['latitude'], pkt['longitude']
            call     = pkt['from']
            ssid     = extract_ssid(call)
            ts       = time.time()

            with sqlite3.connect(DB_FILE) as c:
                c.execute(
                  "INSERT INTO positions (callsign,lat,lon,ssid,timestamp) "
                  "VALUES (?,?,?,?,?)",
                  (call, lat, lon, ssid, ts)
                )

            notify({
              "type":"position", "callsign":call,
              "lat":lat, "lon":lon, "ssid":ssid, "timestamp":ts
            })

        # messaggio
        elif pkt.get('type') == 'message' or (
             'to' in pkt and 'info' in pkt and 'latitude' not in pkt):
            sender, dest, txt = pkt['from'], pkt['to'], pkt['info']
            ts = time.time()

            with sqlite3.connect(DB_FILE) as c:
                c.execute(
                  "INSERT INTO messages (sender,recipient,info,timestamp) "
                  "VALUES (?,?,?,?)",
                  (sender, dest, txt, ts)
                )

    except Exception as e:
        print("PARSE ERROR:", e, flush=True)

# thread di riconnessione KISS: tenta, e se cade, riprova ogni 5 s
def kiss_worker():
    global _kiss_link
    while True:
        try:
            link = kiss.TCPKISS(host=KISS_HOST, port=KISS_PORT, strip_df_start=True)
            link.start()
            with _kiss_lock:
                _kiss_link = link
            print(f"KISS connesso a {KISS_HOST}:{KISS_PORT}", flush=True)

            # resta bloccato finché il socket è vivo
            link.read(callback=handle_frame)

        except Exception as e:
            print("KISS worker error:", e, flush=True)

        finally:
            with _kiss_lock:
                _kiss_link = None

        time.sleep(5)

# --------------------------------------------------------------------------- #
# Query                                                                       #
# --------------------------------------------------------------------------- #
def last_positions():
    conn = sqlite3.connect(DB_FILE)
    cur  = conn.cursor()
    cur.execute("""
      SELECT p1.callsign,p1.lat,p1.lon,p1.ssid,p1.timestamp
      FROM positions p1
      JOIN (
        SELECT callsign, MAX(timestamp) AS ts
        FROM positions GROUP BY callsign
      ) p2 ON p1.callsign=p2.callsign AND p1.timestamp=p2.ts
    """)
    rows = cur.fetchall()
    conn.close()
    return {cs:{"lat":lat,"lon":lon,"ssid":ssid,"timestamp":ts}
            for cs,lat,lon,ssid,ts in rows}

def last_messages(limit=50):
    conn = sqlite3.connect(DB_FILE)
    cur  = conn.cursor()
    cur.execute("""
      SELECT sender,recipient,info,timestamp
      FROM messages ORDER BY timestamp DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(sender=s,recipient=r,info=i,timestamp=t) for s,r,i,t in rows]

# --------------------------------------------------------------------------- #
# Server-Sent Events                                                          #
# --------------------------------------------------------------------------- #
def sse_stream():
    q = queue.Queue()
    subscribers.append(q)
    try:
        while True:
            yield f"data: {q.get()}\n\n"
    finally:
        subscribers.remove(q)

# --------------------------------------------------------------------------- #
# Avvio                                                                        #
# --------------------------------------------------------------------------- #
def main():
    init_db()

    # avvia thread di (ri)connessione KISS
    threading.Thread(target=kiss_worker, daemon=True).start()

    app = Flask(__name__)

    # statici
    app.add_url_rule('/',              'idx',
                     lambda: send_from_directory('.', 'map_template.html'))
    app.add_url_rule('/icons/<path:f>','ico',
                     lambda f: send_from_directory('icons', f))
    app.add_url_rule('/geo/<path:f>',  'geo',
                     lambda f: send_from_directory('geo', f))
    app.add_url_rule('/leaflet_customized.css','css',
                     lambda: send_from_directory('.', 'leaflet_customized.css'))
    app.add_url_rule('/leaflet.js',    'leaf',
                     lambda: send_from_directory('.', 'leaflet.js'))
    app.add_url_rule('/APRS-soup.js',  'js',
                     lambda: send_from_directory('.', 'APRS-soup.js'))

    # API
    @app.route('/positions.json')
    def positions():
        rng = request.args.get('range', 'realtime')
        data = last_positions()
        if rng != 'realtime':
            secs = {'15m':900,'30m':1800,'1h':3600,
                    '6h':21600,'12h':43200,'24h':86400}.get(rng)
            if secs:
                cut = time.time() - secs
                data = {cs:p for cs,p in data.items() if p['timestamp'] >= cut}
        return json.dumps(data)

    @app.route('/messages.json')
    def messages():
        return json.dumps(last_messages())

    @app.route('/stream')
    def stream():
        return Response(sse_stream(), mimetype='text/event-stream')

    @app.route('/send_message', methods=['POST'])
    def send_msg():
        dest = request.form.get('destination', '').strip()
        txt  = request.form.get('message', '').strip()
        if not dest or not txt:
            return "dest e message obbligatori", 400

        with _kiss_lock:
            link = _kiss_link
        if link is None:
            return "TNC non connesso – ritenta più tardi", 503

        try:
            frm = Frame.ui(destination=dest, source=MYCALL,
                           path=["WIDE2-2"], info=">"+txt)
            link.write(frm)
            return "ok", 200
        except Exception as e:
            return str(e), 500

    app.run(host='0.0.0.0', port=5032)

# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()

