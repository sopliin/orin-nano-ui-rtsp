const peopleCount = document.getElementById("people-count");
const vehicleCount = document.getElementById("vehicle-count");
const fpsValue = document.getElementById("fps-value");
const frameId = document.getElementById("frame-id");
const connection = document.getElementById("connection");
const timestamp = document.getElementById("timestamp");

async function refreshCounts() {
  try {
    const response = await fetch("/api/counts", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    peopleCount.textContent = data.people;
    vehicleCount.textContent = data.vehicles;
    fpsValue.textContent = Number(data.fps).toFixed(2);
    frameId.textContent = data.frame_id;
    connection.textContent = `Estado RTSP: ${data.connected ? "conectado" : "desconectado"}`;
    timestamp.textContent = `Timestamp: ${data.timestamp || "-"}`;
  } catch (_) {
    connection.textContent = "Estado RTSP: error consultando API";
  }
}

setInterval(refreshCounts, 300);
refreshCounts();
