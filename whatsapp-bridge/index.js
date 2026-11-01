/**
 * WhatsApp Bridge — Minimal Baileys service for 5Hostachy.
 *
 * Endpoints:
 *   GET  /status        → connection state
 *   GET  /qr            → QR code as PNG image (for pairing)
 *   POST /send          → send a message  { number, text, imageBase64?, imageUrl? }
 *                         corps borné à 2 × WA_PHOTO_BUDGET_KO (413 au-delà)
 *   GET  /groups        → list groups the account is in
 *   POST /restart       → reconnect
 *
 * Auth: header `x-api-key` must match WA_API_KEY env var — en-tête SEULEMENT.
 */

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} = require("baileys");
const express = require("express");
const QRCode = require("qrcode");
const pino = require("pino");
const path = require("path");
const crypto = require("crypto");
const fs = require("fs");
const { creerArret, creerSuiviEcritures } = require("./arret");
const { AccuseRefuse, brancherAccuses, creerSuiviAccuses } = require("./accuses");
const { COMPTE_NODE, descendreDeRoot } = require("./privileges");

const PORT = parseInt(process.env.WA_PORT || "8090", 10);
const API_KEY = process.env.WA_API_KEY || "";

// ── La clé : refusée au démarrage plutôt qu'acceptée faible (#1596) ─────
// `docker-compose.yml` ne refusait que la clé VIDE (`:?`) : la valeur de
// `.env.example` démarrait sans un mot — quand `SECRET_KEY`, côté API, refuse
// la sienne depuis toujours (`config.py`). Le bridge tient le compte WhatsApp
// de la résidence : une clé publiée dans un dépôt public n'en protège rien.
// 🔴 Le message ne cite JAMAIS la valeur reçue — elle finirait dans
// `docker logs`, puis dans une capture de diagnostic (`standards/03` §3).
// Les valeurs d'exemple : celle de `.env.example` (le test du contrat
// vérifie qu'elle est bien refusée) et l'ancien défaut de compose (#776).
const CLES_EXEMPLE = new Set(["changez-cette-cle-whatsapp-min-16-chars", "changeme"]);
const CLE_LONGUEUR_MIN = 16;

function motifRefusCle(cle) {
  if (!cle) return "WA_API_KEY est vide";
  if (CLES_EXEMPLE.has(cle)) return "WA_API_KEY vaut la valeur d'exemple de .env.example";
  if (cle.length < CLE_LONGUEUR_MIN) return `WA_API_KEY fait moins de ${CLE_LONGUEUR_MIN} caractères`;
  return null;
}

const refusCle = motifRefusCle(API_KEY);
if (refusCle) {
  // `console.error` et non le logger : `WA_LOG_LEVEL` peut le rendre muet, et
  // un refus de démarrer qui ne se lit nulle part ressemble à un plantage.
  console.error(
    `Bridge WhatsApp : démarrage refusé — ${refusCle}. Définir WHATSAPP_API_KEY ` +
      `dans .env (au moins ${CLE_LONGUEUR_MIN} caractères aléatoires : openssl rand -hex 24), ` +
      "puis : docker compose up -d whatsapp-bridge api"
  );
  process.exit(1);
}
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(__dirname, "auth_state");

// ── Descendre de root, avant tout le reste (#2368) ────────────────────────────
// Le conteneur ne donne à root que de quoi rendre `auth_state` à `node` et
// changer d'identité (`docker-compose.yml`) ; tout ce qui suit tourne en `node`,
// sans capacité. Un échec arrête le démarrage, en le disant.
try {
  const descente = descendreDeRoot(AUTH_DIR);
  if (descente.descendu) {
    console.log(`Bridge WhatsApp : tourne en ${COMPTE_NODE.nom} (${descente.realignes} entrée(s) de ${AUTH_DIR} réalignée(s)).`);
  }
} catch (e) {
  console.error(`Bridge WhatsApp : démarrage refusé — descente vers ${COMPTE_NODE.nom} impossible (${e.message}).`);
  process.exit(1);
}

const logger = pino({ level: process.env.WA_LOG_LEVEL || "warn" });
const app = express();

// ── Plafond du corps JSON ──────────────────────────────────
// Incident #1057 (19/09/2026) : `express.json()` sans option laissait le
// plafond par défaut d’express — 100 kio — alors que l’API envoie la photo en
// base64 dans le corps, soit 200 kio pour une image ordinaire du site. Le
// bridge rendait 413 AVANT de lire la requête : tout partage portant une
// photo était perdu, sur tous les objets, et rien ne l’avait jamais signalé.
//
// 🔴 Le budget d’une photo est déclaré UNE fois, dans `docker-compose.yml`
// (`WA_PHOTO_BUDGET_KO`), et lu des deux côtés : ici, et par l’API qui réduit
// la photo pour tenir dessous. Deux nombres écrits séparément divergeraient
// au premier ajustement, et c’est l’écart entre eux qui coûte le message.
//
// Le double du budget : la base64 coûte 4/3 du fichier, le reste couvre le
// texte et l’enveloppe JSON.
const PHOTO_BUDGET_KO = parseInt(process.env.WA_PHOTO_BUDGET_KO || "400", 10);
const BODY_LIMIT_KO = PHOTO_BUDGET_KO * 2;
app.use(express.json({ limit: `${BODY_LIMIT_KO}kb` }));

// Un corps refusé doit se lire comme tel côté API : sans ce gestionnaire,
// express rend une page d’erreur HTML et le journal ne montre qu’une trace.
app.use((err, req, res, next) => {
  if (err && err.type === "entity.too.large") {
    logger.warn({ limit: `${BODY_LIMIT_KO}kb`, length: err.length }, "Corps refusé : trop volumineux");
    return res.status(413).json({
      error: "payload too large",
      limitKo: BODY_LIMIT_KO,
      photoBudgetKo: PHOTO_BUDGET_KO,
    });
  }
  return next(err);
});

let sock = null;
let qrCode = null;       // latest QR string (null when connected)
let connectionState = "disconnected"; // disconnected | connecting | open
// Depuis QUAND le bridge est hors ligne, et le DERNIER code de fermeture (#1061).
// Une coupure ordinaire (428) se rétablit en minutes ; un 401 ou un 403 venus de
// WhatsApp disent un compte déconnecté d'office — possiblement bloqué. L'API
// (`utils/verdict_whatsapp`) lit les deux pour ne pas confondre les pannes.
let horsLigneDepuis = new Date().toISOString();
let dernierCode = null;
function marquerHorsLigne() {
  connectionState = "disconnected";
  if (horsLigneDepuis === null) horsLigneDepuis = new Date().toISOString();
}

// ── Reconnect supervision ────────────────────────────────────────────
// Incident 2026-07-24 : après une bascule, le bridge est resté bloqué
// hors état "open" pendant 2h23 sans aucune tentative de reconnexion —
// une reconnexion planifiée avait rejeté une promesse non interceptée
// (startBaileys() est async, appelé nu dans un setTimeout), ce qui a
// tué la chaîne de reconnexion silencieusement. Cf. CLAUDE.md.
let starting = false;          // anti-concurrence : un seul startBaileys() à la fois
let reconnectTimer = null;     // timer de reconnexion déjà programmé
let reconnectAttempt = 0;      // pour le backoff exponentiel
const RECONNECT_BASE_MS = 5_000;
const RECONNECT_MAX_MS = 60_000;
const WATCHDOG_INTERVAL_MS = 60_000;

// ── Arrêt propre (#1590) ─────────────────────────────────────────────
// `docker compose stop` envoie SIGTERM ; Node en PID 1 n'y réagit pas sans
// écouteur, et SIGKILL tombait 10 s plus tard — possiblement au milieu d'une
// écriture de `creds.json` ou d'un fichier de clé. La décision est dans
// `arret.js` (pure, testée) ; ici, seulement ce qu'on lui branche.
// Le minuteur de sécurité (8 s) est SOUS `stop_grace_period` (20 s,
// docker-compose.yml) : c'est le bridge qui sort, jamais Docker qui tue.
const ARRET_DELAI_MS = parseInt(process.env.WA_ARRET_DELAI_MS || "8000", 10);
const suiviEcritures = creerSuiviEcritures();

function scheduleReconnect() {
  if (arret.enCours()) return; // arrêt demandé : plus aucune reconnexion
  if (reconnectTimer) return; // déjà programmé
  const delay = Math.min(RECONNECT_BASE_MS * 2 ** reconnectAttempt, RECONNECT_MAX_MS);
  reconnectAttempt += 1;
  logger.warn({ delay, attempt: reconnectAttempt }, "Reconnexion programmée");
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    startBaileys().catch((err) => {
      logger.warn({ err: err.message }, "startBaileys() a échoué — nouvelle tentative programmée");
      scheduleReconnect();
    });
  }, delay);
}

// ── Accusés du serveur (détection de session fantôme) ─────────────────
// Quelles sources d'accusé existent, et pourquoi une seule ne suffisait pas :
// `accuses.js`. Le délai se règle par l'environnement pour les tests seulement.
const ACK_TIMEOUT_MS = parseInt(process.env.WA_ACK_DELAI_MS || "15000", 10);
const accuses = creerSuiviAccuses({ delaiMs: ACK_TIMEOUT_MS });

// ── Auth middleware ──────────────────────────────────────────────────
// La clé ne se lit que dans l'EN-TÊTE (#1596). `?apikey=` était accepté :
// un secret en paramètre d'URL finit dans les journaux d'accès, l'historique
// d'un navigateur et l'en-tête Referer (`standards/03` §4). L'API ne l'a
// jamais employé (`utils/whatsapp.entetes_bridge`).
// Comparaison des EMPREINTES : longueur fixe, donc `timingSafeEqual` ne lève
// jamais — l'ancien `padEnd(64)` levait (500) sur une valeur de plus de 64
// caractères — et rien ne fuit de la longueur de la clé.
const empreinte = (v) => crypto.createHash("sha256").update(String(v)).digest();
const EMPREINTE_CLE = empreinte(API_KEY);

function authMiddleware(req, res, next) {
  const provided = req.headers["x-api-key"] || "";
  if (crypto.timingSafeEqual(empreinte(provided), EMPREINTE_CLE)) {
    return next();
  }
  return res.status(401).json({ error: "Unauthorized" });
}
app.use(authMiddleware);

// ── Baileys connection ──────────────────────────────────────────────
async function startBaileys() {
  if (starting) {
    logger.warn("startBaileys() déjà en cours — appel ignoré (anti-concurrence)");
    return;
  }
  starting = true;
  try {
    await startBaileysInner();
  } finally {
    starting = false;
  }
}

async function startBaileysInner() {
  // Ferme proprement le socket précédent avant d'en ouvrir un nouveau —
  // sans ça, un ancien socket encore vivant peut se battre avec le nouveau
  // pour la même session (source probable des tempêtes "conflict: replaced").
  if (sock) {
    try { sock.end(undefined); } catch (_) {}
    sock = null;
  }

  // Un arrêt demandé pendant que le démarrage attendait ne doit pas ouvrir de
  // socket de plus.
  if (arret.enCours()) return;

  connectionState = "connecting";
  if (horsLigneDepuis === null) horsLigneDepuis = new Date().toISOString();
  qrCode = null;

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      // Les écritures de clés sont suivies, pour que l'arrêt les attende
      // (comportement inchangé : mêmes appels, mêmes valeurs).
      keys: makeCacheableSignalKeyStore(
        {
          get: (...args) => state.keys.get(...args),
          set: suiviEcritures.suivre((...args) => state.keys.set(...args)),
        },
        logger
      ),
    },
    logger,
    printQRInTerminal: true,
    connectTimeoutMs: 60_000,
    defaultQueryTimeoutMs: 60_000,
    browser: ["5Hostachy", "Chrome", "1.0.0"],
  });

  sock.ev.on("creds.update", suiviEcritures.suivre(saveCreds));

  brancherAccuses(sock, accuses);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      qrCode = qr;
      connectionState = "waiting_qr";
      logger.info("New QR code generated — scan it to connect");
    }

    if (connection === "open") {
      connectionState = "open";
      horsLigneDepuis = null;
      qrCode = null;
      reconnectAttempt = 0; // reset du backoff après une connexion réussie
      logger.warn("WhatsApp connected ✓");
    }

    if (connection === "close") {
      marquerHorsLigne();
      accuses.toutRejeter("Connection closed");
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      dernierCode = statusCode ?? null;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      logger.warn({ statusCode, shouldReconnect }, "Connection closed");
      if (arret.enCours()) {
        logger.warn("Arrêt demandé — pas de reconnexion");
      } else if (shouldReconnect) {
        scheduleReconnect();
      } else {
        logger.warn("Logged out — delete auth_state and restart to re-pair");
      }
    }
  });
}

// Filet de sécurité : si plus aucune reconnexion n'est en cours ni programmée
// alors que l'état n'est pas "open", on en relance une. Couvre tout scénario
// où la chaîne de reconnexion s'arrêterait pour une raison non anticipée
// (cf. incident du 2026-07-24 : 2h23 sans la moindre tentative).
setInterval(() => {
  if (connectionState !== "open" && connectionState !== "connecting" && connectionState !== "waiting_qr" && !reconnectTimer && !starting) {
    logger.warn("Watchdog : aucune reconnexion en cours/programmée — relance forcée");
    scheduleReconnect();
  }
}, WATCHDOG_INTERVAL_MS);

// ── Routes ──────────────────────────────────────────────────────────
app.get("/status", (_req, res) => {
  res.json({
    state: connectionState,
    hasQR: !!qrCode,
    hors_ligne_depuis: horsLigneDepuis,
    dernier_code: dernierCode,
  });
});

app.get("/qr", async (req, res) => {
  if (connectionState === "open") {
    return res.json({ message: "Already connected", state: "open" });
  }
  if (!qrCode) {
    return res.status(503).json({ message: "No QR code available yet, wait a few seconds", state: connectionState });
  }
  const format = req.query.format || "png";
  if (format === "raw") {
    return res.json({ qr: qrCode, state: connectionState });
  }
  // Return PNG image
  res.setHeader("Content-Type", "image/png");
  QRCode.toFileStream(res, qrCode, { width: 300, margin: 2 });
});

app.post("/send", async (req, res) => {
  if (connectionState !== "open") {
    return res.status(503).json({ error: "WhatsApp not connected", state: connectionState });
  }
  // Express 5 (27/09/2026) : sans corps JSON, `req.body` vaut `undefined` et non
  // plus `{}` — la déstructuration levait, et la requête rendait 500 au lieu de 400.
  const { number, text, imageUrl, imageBase64 } = req.body ?? {};
  if (!number || !text) {
    return res.status(400).json({ error: "number and text are required" });
  }
  try {
    const jid = number.includes("@") ? number : `${number}@s.whatsapp.net`;
    // `imageBase64` est la voie normale : l'API a le fichier sous la main et nous
    // l'envoie. `imageUrl` reste accepté par compatibilité, mais il oblige Baileys
    // à retélécharger le fichier PAR L'INTERNET PUBLIC — ce qui suppose que le
    // dossier soit servi en anonyme, et a cassé l'envoi le 10/08/2026 quand les
    // photos de publication ont rejoint le dossier authentifié.
    const media = imageBase64
      ? { image: Buffer.from(imageBase64, "base64"), caption: text }
      : imageUrl
        ? { image: { url: imageUrl }, caption: text }
        : null;

    let sentMsg;
    try {
      sentMsg = await sock.sendMessage(jid, media ?? { text });
    } catch (errMedia) {
      // ⚠️ Un échec sur l'IMAGE ne doit jamais faire perdre le MESSAGE. Le
      // 10/08/2026, un 401 sur la photo a supprimé l'annonce entière du groupe :
      // les résidents n'ont rien reçu du tout, et l'échec n'était visible que
      // dans les logs. Le texte part, l'image est signalée.
      if (!media) throw errMedia;
      logger.warn({ err: errMedia }, "Média refusé — repli sur le texte seul");
      sentMsg = await sock.sendMessage(jid, { text });
    }

    // Wait for SERVER_ACK to confirm the message actually reached WhatsApp servers.
    // If no ACK within ACK_TIMEOUT_MS, the session is likely a ghost (connected
    // in appearance but silently rejected by WhatsApp). Reconnect automatically.
    //
    // 🔴 MAIS L'ABSENCE D'ACCUSÉ N'EST PAS UN ÉCHEC D'ENVOI (19/08/2026).
    // `sendMessage()` a déjà rendu la main : le message est PARTI. Seule la
    // confirmation du serveur manque. Jusqu'ici cette branche tombait dans le
    // `catch` commun et répondait 500 — indistinguable d'un envoi qui n'a jamais
    // eu lieu. L'historique de l'administration affichait donc « incertain —
    // réponse 500 du bridge » sur deux messages que WhatsApp montrait remis,
    // double coche à l'appui. Signalé à l'écran par l'utilisateur.
    //
    // 202 Accepted dit exactement ce qui s'est passé : reçu et traité, résultat
    // non confirmé. L'API le traduit en « incertain », mais avec la bonne raison
    // — et `envoye: true` distingue ce cas de tous les autres.
    const msgId = sentMsg?.key?.id;
    if (msgId) {
      try {
        await accuses.attendre(msgId);
      } catch (errAck) {
        // Le serveur a RÉPONDU, et refusé : la session est vivante, rien à
        // reconnecter — mais le message n'est pas confirmé. 502, jamais 202 :
        // ce code dit « très probablement remis », ce qui serait faux ici.
        if (errAck instanceof AccuseRefuse) {
          logger.warn({ err: errAck, msgId }, "Message refusé par le serveur WhatsApp");
          return res.status(502).json({ ok: false, envoye: true, acquitte: false, refuse: true, id: msgId, jid, error: errAck.message });
        }
        logger.warn({ err: errAck, msgId }, "Message émis, accusé non observé — reconnexion");
        try { if (sock) sock.end(); } catch (_) {}
        marquerHorsLigne();
        reconnectAttempt = 0;
        scheduleReconnect();
        return res.status(202).json({
          ok: false,
          envoye: true,
          acquitte: false,
          id: msgId,
          jid,
          error: errAck.message,
        });
      }
    }

    res.json({ ok: true, jid, id: msgId ?? null });
  } catch (err) {
    // Ici, `sendMessage()` lui-même a échoué : RIEN n'est parti, et rejouer est
    // sûr. Le cas « émis sans accusé » est traité plus haut et ne descend pas
    // jusqu'ici — la garde ci-dessous reste par prudence si un autre chemin
    // venait à lever la même erreur.
    logger.error(err, "Send failed");
    if (err.message.includes("ghost session") || err.message.includes("ACK timeout")) {
      logger.warn("Ghost session detected — triggering reconnect");
      try { if (sock) sock.end(); } catch (_) {}
      marquerHorsLigne();
      reconnectAttempt = 0;
      scheduleReconnect();
    }
    res.status(500).json({ error: err.message });
  }
});

app.get("/groups", async (_req, res) => {
  if (connectionState !== "open") {
    return res.status(503).json({ error: "WhatsApp not connected", state: connectionState });
  }
  try {
    const groups = await sock.groupFetchAllParticipating();
    const list = Object.values(groups).map((g) => ({
      id: g.id,
      subject: g.subject,
      participants: g.participants?.length || 0,
    }));
    res.json(list);
  } catch (err) {
    logger.error(err, "Groups fetch failed");
    res.status(500).json({ error: err.message });
  }
});

app.post("/restart", async (_req, res) => {
  try {
    if (sock) sock.end();
  } catch (_) {}
  marquerHorsLigne();
  reconnectAttempt = 0;
  scheduleReconnect();
  res.json({ ok: true, message: "Restarting..." });
});

// ── Arrêt : SIGTERM (docker stop) et SIGINT ───────────────────────────
const arret = creerArret({
  fermer: () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    marquerHorsLigne();
    if (sock) sock.end(undefined);
  },
  attendreEcritures: () => suiviEcritures.attendre(),
  quitter: (code) => process.exit(code),
  delaiMs: ARRET_DELAI_MS,
  journal: (message) => logger.warn(message),
});
for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => {
    arret.demander(signal);
  });
}

// ── Start ───────────────────────────────────────────────────────────
app.listen(PORT, "0.0.0.0", () => {
  logger.info(`WhatsApp Bridge listening on port ${PORT}`);
  startBaileys().catch((err) => {
    logger.warn({ err: err.message }, "Échec du démarrage initial — nouvelle tentative programmée");
    scheduleReconnect();
  });
});
