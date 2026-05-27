import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} from "@whiskeysockets/baileys";
import dotenv from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";
import WebSocket from "ws";
import qrcode from "qrcode-terminal";
import pino from "pino";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.resolve(__dirname, "../.env") });

const PYTHON_WS_URL =
  process.env.PYTHON_WS_URL || "ws://127.0.0.1:8000/ws/whatsapp";
const AUTH_DIR = process.env.WA_AUTH_DIR || "./auth_info";
const ALLOW_FROM_ME =
  String(process.env.WA_BRIDGE_ALLOW_FROM_ME || "false").toLowerCase() === "true";
const RECONNECT_MS = 5000;

let socket = null;
let pythonSocket = null;
let whatsappConnected = false;
const outboundIds = new Set();
const expectedOutboundTexts = new Map();

function outboundTextKey(to, text) {
  return `${to}\n${text}`;
}

function expectOutbound(to, text) {
  const key = outboundTextKey(to, text);
  expectedOutboundTexts.set(key, (expectedOutboundTexts.get(key) || 0) + 1);
}

function consumeExpectedOutbound(to, text) {
  const key = outboundTextKey(to, text);
  const pending = expectedOutboundTexts.get(key) || 0;
  if (!pending) return false;
  if (pending === 1) {
    expectedOutboundTexts.delete(key);
  } else {
    expectedOutboundTexts.set(key, pending - 1);
  }
  return true;
}

function connectPython() {
  if (pythonSocket && pythonSocket.readyState === WebSocket.OPEN) return;
  console.log(`Conectando con FastAPI: ${PYTHON_WS_URL}`);
  pythonSocket = new WebSocket(PYTHON_WS_URL);

  pythonSocket.on("open", () => {
    console.log("FastAPI conectado.");
  });

  pythonSocket.on("message", async (raw) => {
    let message = null;
    try {
      message = JSON.parse(raw.toString());
      if (!message.to || !message.text || !socket || !whatsappConnected) return;
      expectOutbound(message.to, message.text);
      const sent = await socket.sendMessage(message.to, { text: message.text });
      if (sent.key && sent.key.id) outboundIds.add(sent.key.id);
      console.log(`Bot -> WhatsApp (${message.to}): respuesta enviada`);
    } catch (error) {
      if (message?.to && message?.text) consumeExpectedOutbound(message.to, message.text);
      console.error("No se pudo enviar respuesta a WhatsApp:", error.message);
    }
  });

  pythonSocket.on("close", () => {
    pythonSocket = null;
    console.log("FastAPI desconectado. Reintentando...");
    setTimeout(connectPython, RECONNECT_MS);
  });

  pythonSocket.on("error", (error) => {
    console.error("Error WebSocket FastAPI:", error.message);
  });
}

function sendInbound(payload) {
  if (!pythonSocket || pythonSocket.readyState !== WebSocket.OPEN) {
    console.warn("FastAPI aun no esta conectado; mensaje ignorado.");
    return;
  }
  pythonSocket.send(JSON.stringify(payload));
}

function textFrom(message) {
  return (
    message.message?.conversation ||
    message.message?.extendedTextMessage?.text ||
    message.message?.imageMessage?.caption ||
    message.message?.videoMessage?.caption ||
    ""
  ).trim();
}

async function startWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();
  socket = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    logger: pino({ level: "silent" }),
    browser: ["Retornar Demo", "Chrome", "1.0.0"],
    syncFullHistory: false,
  });

  socket.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      console.log("\nEscanea este QR: WhatsApp > Dispositivos vinculados > Vincular dispositivo\n");
      qrcode.generate(qr, { small: true });
    }
    if (connection === "open") {
      whatsappConnected = true;
      console.log("WhatsApp conectado.");
      connectPython();
    }
    if (connection === "close") {
      whatsappConnected = false;
      const status = lastDisconnect?.error?.output?.statusCode;
      if (status !== DisconnectReason.loggedOut) {
        setTimeout(startWhatsApp, RECONNECT_MS);
      } else {
        console.error("La sesion fue cerrada. Elimina auth_info/ y vuelve a escanear.");
      }
    }
  });

  socket.ev.on("creds.update", saveCreds);
  socket.ev.on("messages.upsert", ({ messages, type }) => {
    if (type !== "notify") return;
    for (const message of messages) {
      const messageId = message.key?.id;
      const to = message.key?.remoteJid || "";
      if (!to || to.endsWith("@g.us") || !messageId) continue;
      const text = textFrom(message);
      if (!text) continue;
      if (message.key.fromMe && consumeExpectedOutbound(to, text)) {
        outboundIds.delete(messageId);
        continue;
      }
      if (outboundIds.delete(messageId)) continue;
      if (message.key.fromMe && !ALLOW_FROM_ME) continue;
      console.log(`WhatsApp -> Bot (${to}): mensaje recibido (${text.length} caracteres)`);
      sendInbound({
        from: to,
        message_id: messageId,
        text,
        push_name: message.pushName || "",
      });
    }
  });
}

console.log("Retornar WhatsApp Bridge - solo desarrollo local");
console.log("Este conector usa WhatsApp Web/Baileys, no la API oficial de Meta.");
startWhatsApp().catch((error) => {
  console.error("Error fatal iniciando bridge:", error);
  process.exit(1);
});
