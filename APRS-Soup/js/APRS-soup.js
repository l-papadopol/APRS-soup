// APRS-soup.js
// Questo script gestisce la parte frontend dell'applicazione APRS-soup
// ovvero caricamento della mappa da tiles, piazzamento icone stazioni, invio e ricezione messaggi
// (C) 2025 Papadopol Lucian Ioan - licenza CC BY-NC-ND 3.0 IT

// SSE per aggiornamento istantaneo
const es = new EventSource('/stream');
es.onmessage = e => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'position') {
    updateSingle(msg);
  }
};

// funzione per gestire singolo aggiornamento
function updateSingle(pos) {
  const cs = pos.callsign;
  const range = document.getElementById('timeFilter').value;
  const M = {'15m':15*60,'30m':30*60,'1h':3600,'6h':6*3600,'12h':12*3600,'24h':24*3600};
  if (range !== 'realtime') {
    const secs = M[range];
    if ((Date.now()/1000 - pos.timestamp) > secs) {
      if (markers[cs]) {
        map.removeLayer(markers[cs]);
        delete markers[cs];
      }
      if (trackedStations[cs]) {
        map.removeLayer(trackedStations[cs].polyline);
        delete trackedStations[cs];
      }
      return;
    }
  }
  if (markers[cs]) {
    markers[cs].setLatLng([pos.lat, pos.lon]);
    if (markers[cs].isPopupOpen()) {
      markers[cs].setPopupContent(updatePopupContent(cs, pos));
    }
  } else {
    let m = L.marker([pos.lat, pos.lon], { icon: getIcon(pos.ssid) }).addTo(map);
    m.bindPopup(updatePopupContent(cs, pos));
    markers[cs] = m;
    m.on('click', () => m.setPopupContent(updatePopupContent(cs, pos)));
  }
  if (trackedStations[cs]) {
    let ll  = markers[cs].getLatLng();
    let rec = trackedStations[cs];
    let last= rec.positions[rec.positions.length-1];
    if (!last || last.lat!==ll.lat || last.lng!==ll.lng) {
      rec.positions.push(ll);
      rec.polyline.setLatLngs(rec.positions);
    }
  }
}

// associo ad ogni SSID un icona PNG
const ssidIcons = {
  "0":  "icons/home.png",
  "1":  "icons/digipeater.png",
  "3":  "icons/car.png",
  "5":  "icons/igate.png",
  "6":  "icons/weather.png",
  "9":  "icons/vehicle.png",
  "14": "icons/truck.png",
  "default": "icons/default.png"
};

// creo una mappa e la centro su 44°N 11.5°E zoom 6
const map = L.map('map').setView([44.0, 11.5], 6);

// creo il layer dei tile PNG che sono la mappa effettiva
// root directory dei tile /geo/
// {z} directory corrispondenti al livello di zoom da 4 a 13
// {x} directory corrispondenti alla longitudine
// {y} directory corrispondenti alla latitudine
L.tileLayer('/geo/{z}/{x}/{y}.png', {
  minZoom: 4, maxZoom: 13,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

// array di markers e stazioni tracciate
let markers = {};
let trackedStations = {};

// acquisisce una icona e la scala con ancora nel suo centro
function getIcon(ssid) {
  const url = ssidIcons[ssid] || ssidIcons.default;
  return L.icon({ iconUrl: url, iconSize:[28,28], iconAnchor:[14,14] });
}

// data un timestamp restituisce una stringa con ore e minuti
function formatTime(ts) {
  let d = new Date(ts*1000);
  return d.toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit'});
}

// data una timestamp restituisce una stringa con data, ore, minuti
function formatDateTime(ts) {
  let d = new Date(ts*1000);
  return d.toLocaleString('it-IT',{
    day:'2-digit',month:'2-digit',year:'numeric',
    hour:'2-digit',minute:'2-digit',second:'2-digit'
  });
}

// converte una coordinata in formato decimale in formato DMS
// ovvero in gradi minuti secondi cardinalità
function decimalToDMS(value, isLat=true) {
  const card = isLat ? (value>=0?'N':'S') : (value>=0?'E':'W');
  const absV = Math.abs(value), deg = Math.floor(absV);
  const minF = (absV - deg)*60, min = Math.floor(minF);
  const sec = ((minF - min)*60).toFixed(2);
  return `${deg}° ${min}' ${sec}" ${card}`;
}

// update del popup che appare quando si fa click su di una icona (stazione) sulla mappa
function updatePopupContent(callsign,pos) {
  let t    = formatTime(pos.timestamp);
  let ld   = decimalToDMS(pos.lat,true),
      lg   = decimalToDMS(pos.lon,false);
  let glat = pos.lat.toFixed(6), glon = pos.lon.toFixed(6);
  let checked = trackedStations[callsign] ? 'checked' : '';
  return `
    <strong>${callsign}</strong><br>
    Lat: ${ld}<br>
    Lon: ${lg}<br>
    Formato G-Maps: ${glat},${glon}<br>
    Ultimo segnale: ${t}<br>
    <label><input type="checkbox"
           onchange="toggleTracking('${callsign}',this.checked)"
           ${checked}> Traccia</label>
    <br>
    <textarea id="msg_${callsign}"
      placeholder="Inserisci messaggio"
      style="width:100%;height:3em"></textarea>
    <br>
    <button onclick="sendMessage('${callsign}')">Invia</button>
  `;
}

// funzionalità di tracking di una stazione ovvero unisce con una polilinea tutte le posizioni geografiche
// ricevute da una singola stazione. se la stazione si muove mostra quindi lo spostamento (anche se non segue le strade)
function toggleTracking(callsign,on) {
  if(on) {
    if(!trackedStations[callsign]) {
      let m = markers[callsign];
      let ll = m.getLatLng();
      let pl = L.polyline([ll],{color:'blue'}).addTo(map);
      trackedStations[callsign] = { polyline:pl, positions:[ll] };
    }
  } else {
    let rec = trackedStations[callsign];
    if(rec) {
      map.removeLayer(rec.polyline);
      delete trackedStations[callsign];
    }
  }
}

// invia un messaggio arbitrario alla stazione selezionata
async function sendMessage(callsign) {
  let txt = document.getElementById("msg_"+callsign).value;
  if(!txt) return alert("Inserisci un messaggio");
  let fd = new FormData();
  fd.append("destination",callsign);
  fd.append("message",txt);
  try {
    let res = await fetch("/send_message",{method:"POST",body:fd});
    alert(await res.text());
  } catch(e) {
    alert("Errore: "+e);
  }
}

// layer clean up
function cleanupOld(data) {
  for(let cs in markers) {
    if(!data.hasOwnProperty(cs)) {
      map.removeLayer(markers[cs]);
      delete markers[cs];
      if(trackedStations[cs]) {
        map.removeLayer(trackedStations[cs].polyline);
        delete trackedStations[cs];
      }
    }
  }
}

// update della mappa
async function updateMap() {
  const range = document.getElementById('timeFilter').value;
  let res = await fetch(`/positions.json?range=${range}`);
  let data = await res.json();
  cleanupOld(data);
  for(let [cs,pos] of Object.entries(data)) {
    if(markers[cs]) {
      markers[cs].setLatLng([pos.lat,pos.lon]);
      if(markers[cs].isPopupOpen()) {
        markers[cs].setPopupContent(updatePopupContent(cs,pos));
      }
    } else {
      let m = L.marker([pos.lat,pos.lon],{icon:getIcon(pos.ssid)}).addTo(map);
      m.bindPopup(updatePopupContent(cs,pos));
      markers[cs] = m;
      m.on('click',()=>m.setPopupContent(updatePopupContent(cs,pos)));
    }
    if(trackedStations[cs]) {
      let ll = markers[cs].getLatLng();
      let rec = trackedStations[cs];
      let last = rec.positions[rec.positions.length-1];
      if(!last || last.lat!==ll.lat|| last.lng!==ll.lng) {
        rec.positions.push(ll);
        rec.polyline.setLatLngs(rec.positions);
      }
    }
  }
}

// gestisce e visualizza i messaggi ricevuti
document.getElementById('toggleMsgs').onclick = async ()=>{
  let p = document.getElementById('msgsPanel');
  if(p.style.display==='none') {
    p.style.display='block';
    try {
      let res = await fetch('/messages.json'), msgs = await res.json();
      p.innerHTML = msgs.length
        ? msgs.map(m=>`
          <div class="msg">
            <strong>${m.sender} → ${m.recipient}</strong><br>
            ${m.info}<br>
            <small>${formatDateTime(m.timestamp)}</small><hr>
          </div>
        `).join('')
        : '<em>Nessun messaggio ricevuto.</em>';
    } catch {
      p.innerHTML = '<em>Errore nel caricamento.</em>';
    }
  } else p.style.display='none';
};

// aggiunge un event listener per aggiornare la mappa in base all'intervallo temporale selezionato dall'utente
document.getElementById('timeFilter').addEventListener('change', updateMap);

// intervallo di update della mappa automatico
setInterval(updateMap,15000);
updateMap();
