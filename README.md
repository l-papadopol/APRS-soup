# APRS-soup — Server APRS in tempo reale (Flask + Leaflet)

> **Visualizzatore APRS progettato per funzionare anche senza connessione Internet**  
> Riceve frame AX.25 da un TNC KISS (ad es. Direwolf), li analizza con `aprslib`, li salva in SQLite, invia *Server-Sent Events* ai browser collegati e disegna le stazioni su una mappa Leaflet alimentata da tile locali.

---

## Funzionalità principali
* **Posizioni e messaggi live** — aggiornamento istantaneo tramite SSE.
* **Mappe offline** — servi tile PNG dal percorso `./geo/**` e lavora fuori rete.
* **Persistenza su SQLite** — conserva l’ultima posizione di ogni stazione e lo storico dei messaggi.
* **API JSON minimale** — perfetta per dashboard o bot esterni.
* **Backend in un unico file** — `aprs_soup.py`, solo librerie Python pure.
* **Licenza CC BY-NC-ND 3.0** — uso libero per scopi personali e didattici.

---

## Screenshot

![Schermata APRS-soup](aprs_soup.png)

---

## 🗂 Struttura del repository

```text
aprs_soup.py                   ← server backend
map_template.html              ← pagina Leaflet
APRS-soup.js                   ← logica frontend
leaflet.js / leaflet_customized.css  ← CSS di Leaflet
icons/                         ← simboli APRS (PNG)
geo/                           ← tile XYZ (z/x/y.png) prerenderizzate
LICENSE
