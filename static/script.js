// whether we need to append an `s` to the websocket address
// based on whether we're using http or https
const securePrefix = window.location.href.match("^http(s?)")[1]

const ws = new WebSocket(`ws${securePrefix}://${window.location.host}/ws`);
const statusCard = document.getElementById("status-card");
const statusIcon = document.getElementById("status-icon");
const statusText = document.getElementById("status-text");
const wsStatus = document.getElementById("ws-status");

connectToSocket();

function connectToSocket() {
  ws.onopen = () => {
    console.log("connected to websocket");
    wsStatus.innerText = "Verbunden";
    wsStatus.style.color = "green";
  };

  ws.onclose = () => {
    console.warn("ws connection closed")
    wsStatus.innerText = "Verbindung verloren";
    wsStatus.style.color = "red";
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("message: ", data);

    // 1. Update Status Card
    if (data.mailbox_state) {
      updateState(data.mailbox_state);
    }

    // 2. Update Metriken
    if (data.distance !== undefined) {
      document.getElementById("distance").innerText =
        data.distance.toFixed(1);

      // Calculate progress based on baseline (baseline = empty = 0% filled)
      const baseline = data.baseline || 40.0;
      let progress = ((baseline - data.distance) / baseline) * 100;
      document.getElementById("dist-progress").value = Math.max(0, Math.min(100, progress));
    }

    if (data.success_rate !== undefined) {
      document.getElementById("confidence").innerText = (
        data.success_rate * 100
      ).toFixed(0);
    }

    // 3. Update Event Log (nur wenn es eine Event-Nachricht ist)
    if (data.event_type) {
      addLogEntry(data);
    }
  };
}

function updateState(state) {
  // Reset classes
  statusCard.className = "status-card";

  switch (state) {
    case "empty":
      statusCard.classList.add("state-empty");
      statusIcon.innerText = "📭";
      statusText.innerText = "Briefkasten ist leer";
      break;
    case "has_mail":
      statusCard.classList.add("state-mail");
      statusIcon.innerText = "📬";
      statusText.innerText = "Neue Post ist da!";
      break;
    case "full":
      statusCard.classList.add("state-full");
      statusIcon.innerText = "🈵";
      statusText.innerText = "Briefkasten ist voll!";
      break;
    case "emptied":
      statusCard.classList.add("state-emptied");
      statusIcon.innerText = "🗑️";
      statusText.innerText = "Wurde gerade geleert";
      break;
    default:
      statusCard.classList.add("state-empty");
      statusText.innerText = state;
  }
}

function addLogEntry(data) {
  const tbody = document.getElementById("event-log");
  const row = document.createElement("tr");

  // Use timestamp from data if available, otherwise use current time
  // Unix timestamp is in seconds, JavaScript Date needs milliseconds
  const time = data.timestamp ? new Date(data.timestamp * 1000) : new Date();

  let details = "";
  if (data.event_type === "mail_drop") {
    const delta = data.baseline - data.distance;
    details = `Distanz: ${data.distance.toFixed(1)}cm, Confidence: ${(data.confidence * 100).toFixed(0)}%`;
  }
  if (data.event_type === "mail_collected") {
    details = `Distanz: ${data.distance.toFixed(1)}cm, Success Rate: ${(data.success_rate * 100).toFixed(0)}%`;
  }

  // formatted = `${time.getDay()}.${time.getMonth()}.${time.getFullYear()}` + `${time.getHours()}:${time.getMinutes()}:${time.getSeconds()}`;

  row.innerHTML = `<td>${formatDate(time)}</td><td>${data.event_type}</td><td>${details}</td>`;
  tbody.insertBefore(row, tbody.firstChild);

  // Behalte nur die letzten 5 Einträge
  if (tbody.children.length > 5) tbody.removeChild(tbody.lastChild);
}


function formatDate(date) {
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${day}.${month}.${year} ${hours}:${minutes}:${seconds}`;
}
