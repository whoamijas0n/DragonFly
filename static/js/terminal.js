// ==========================================
// DRAGONFLY REMOTE - TERMINAL WEBSOCKET
// Reutilizable en todas las vistas (base.html)
// ==========================================

(function () {
    const terminal = document.getElementById("ws-output");
    if (!terminal) return;

    const protocol = location.protocol === "https:" ? "wss://" : "ws://";
    const ws = new WebSocket(protocol + location.host + "/ws");

    function log(line) {
        terminal.innerText += "\n" + line;
        terminal.scrollTop = terminal.scrollHeight;
    }

    ws.onopen = function () {
        log("[+] WebSocket conectado al backend.");
        ws.send("Cliente Web Inicializado");
    };

    ws.onmessage = function (event) {
        log("> " + event.data);
    };

    ws.onerror = function () {
        log("[!] Error en la conexión WebSocket.");
    };

    ws.onclose = function () {
        log("[!] Conexión WebSocket cerrada.");
    };

    // Expuesto globalmente por si una vista específica
    // necesita enviar comandos desde su propio script.
    window.dragonflyWS = ws;
})();
