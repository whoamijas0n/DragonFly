/**
 * ═══════════════════════════════════════════════════════════════
 * DRAGONFLY TERMINAL - WebSocket Client
 * Maneja la conexión WebSocket con el backend FastAPI
 * ═══════════════════════════════════════════════════════════════
 */

(function() {
    'use strict';

    // ─── CONFIGURACIÓN ───────────────────────────────────────
    const WS_URL = `ws://${location.host}/ws`;
    const RECONNECT_DELAY = 3000; // ms
    const MAX_RECONNECT_ATTEMPTS = 10;

    // ─── ESTADO ──────────────────────────────────────────────
    let ws = null;
    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let terminalEl = null;
    let statusConnEl = null;

    // ─── INICIALIZACIÓN ──────────────────────────────────────
    function init() {
        terminalEl = document.getElementById('ws-output');
        statusConnEl = document.getElementById('status-conn');
        
        if (!terminalEl) {
            console.warn('[DragonFly] Terminal element not found.');
            return;
        }

        connect();
        updateNetworkStatus();
        
        // Actualizar estado de red cada 10 segundos
        setInterval(updateNetworkStatus, 10000);
    }

    // ─── CONEXIÓN WEBSOCKET ──────────────────────────────────
    function connect() {
        if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
            return;
        }

        try {
            ws = new WebSocket(WS_URL);
        } catch (e) {
            logMessage(`[!] Error creando WebSocket: ${e.message}`, 'error');
            scheduleReconnect();
            return;
        }

        ws.onopen = function(event) {
            reconnectAttempts = 0;
            logMessage('[+] WebSocket conectado al backend.', 'success');
            updateConnectionStatus(true);
            ws.send('Cliente Web Inicializado');
        };

        ws.onmessage = function(event) {
            const data = event.data;
            // Clasificar tipo de mensaje por prefijo
            if (data.startsWith('[+]')) {
                logMessage(data, 'success');
            } else if (data.startsWith('[!]') || data.startsWith('[☠]')) {
                logMessage(data, 'error');
            } else if (data.startsWith('[*]')) {
                logMessage(data, 'info');
            } else {
                logMessage(`> ${data}`, 'output');
            }
        };

        ws.onerror = function(event) {
            logMessage('[!] Error en la conexión WebSocket.', 'error');
            updateConnectionStatus(false);
        };

        ws.onclose = function(event) {
            logMessage(`[!] Conexión cerrada (código: ${event.code}).`, 'warning');
            updateConnectionStatus(false);
            scheduleReconnect();
        };
    }

    // ─── RECONEXIÓN AUTOMÁTICA ───────────────────────────────
    function scheduleReconnect() {
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            logMessage('[!] Máximo de reintentos alcanzado. Recarga la página.', 'error');
            return;
        }

        reconnectAttempts++;
        const delay = RECONNECT_DELAY * reconnectAttempts;
        
        logMessage(`[*] Reconectando en ${(delay/1000).toFixed(1)}s... (intento ${reconnectAttempts})`, 'info');
        
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connect, delay);
    }

    // ─── LOGGING EN TERMINAL ─────────────────────────────────
    function logMessage(message, type) {
        if (!terminalEl) return;

        const line = document.createElement('div');
        line.className = `terminal-line terminal-${type || 'default'}`;
        line.textContent = message;
        
        terminalEl.appendChild(line);
        
        // Auto-scroll al final
        terminalEl.scrollTop = terminalEl.scrollHeight;
        
        // Limitar líneas para evitar consumo excesivo de memoria
        const maxLines = 200;
        while (terminalEl.children.length > maxLines) {
            terminalEl.removeChild(terminalEl.firstChild);
        }
    }

    // ─── ENVIAR COMANDO AL BACKEND ───────────────────────────
    function sendCommand(command) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(command);
            logMessage(`$ ${command}`, 'command');
        } else {
            logMessage('[!] No se puede enviar: WebSocket desconectado.', 'error');
        }
    }

    // ─── ESTADO DE CONEXIÓN ──────────────────────────────────
    function updateConnectionStatus(connected) {
        if (!statusConnEl) return;
        
        if (connected) {
            statusConnEl.textContent = 'WS ●';
            statusConnEl.style.color = '#33cc66';
        } else {
            statusConnEl.textContent = 'WS ○';
            statusConnEl.style.color = '#ff4d4d';
        }
    }

    // ─── ESTADO DE RED (IP) ──────────────────────────────────
    function updateNetworkStatus() {
        const statusNetEl = document.getElementById('status-net');
        if (!statusNetEl) return;
        
        // Fetch de la IP actual desde el backend (endpoint futuro)
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                if (data.ip) {
                    statusNetEl.textContent = `[NET] ${data.ip}`;
                }
            })
            .catch(() => {
                statusNetEl.textContent = '[NET] ---.---.---';
            });
    }

    // ─── EXPONER API GLOBAL ──────────────────────────────────
    window.DragonFlyTerminal = {
        send: sendCommand,
        log: logMessage,
        connect: connect,
        getStatus: function() {
            return ws ? ws.readyState : WebSocket.CLOSED;
        }
    };

    // ─── ESTILOS DINÁMICOS PARA TIPOS DE MENSAJE ─────────────
    const style = document.createElement('style');
    style.textContent = `
        .terminal-line { margin-bottom: 2px; }
        .terminal-success { color: #33cc66; }
        .terminal-error { color: #ff4d4d; }
        .terminal-warning { color: #ffaa00; }
        .terminal-info { color: #ff3333; }
        .terminal-output { color: #e2e2e2; }
        .terminal-command { color: #787878; font-style: italic; }
    `;
    document.head.appendChild(style);

    // ─── ARRANQUE ────────────────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();