const ws = new WebSocket(`ws://${window.location.host}/ws`);
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
    wsStatus.innerText = "Verbindung verloren";
    wsStatus.style.color = "red";
  };

  ws.onmessage = (event) => {
    console.log("message: ", event);
    const data = JSON.parse(event.data);

    // 1. Update Status Card
    if (data.mailbox_state) {
      updateState(data.mailbox_state);
    }

    // 2. Update Metriken
    if (data.filtered_cm !== undefined) {
      document.getElementById("distance").innerText =
        data.filtered_cm.toFixed(1);
      // Angenommen 40cm ist leer (100%), 0cm ist voll
      // Wir mappen das grob für die Progressbar
      let progress = ((40 - data.filtered_cm) / 40) * 100;
      document.getElementById("dist-progress").value = Math.max(0, progress);
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
  const time = new Date().toLocaleTimeString();

  let details = "";
  if (data.event_type === "mail_drop")
    details = `Delta: ${data.delta_cm.toFixed(1)}cm`;
  if (data.event_type === "mail_collected")
    details = `Dauer: ${data.duration_ms}ms`;

  row.innerHTML = `<td>${time}</td><td>${data.event_type}</td><td>${details}</td>`;
  tbody.insertBefore(row, tbody.firstChild);

  // Behalte nur die letzten 5 Einträge
  if (tbody.children.length > 5) tbody.removeChild(tbody.lastChild);
}
