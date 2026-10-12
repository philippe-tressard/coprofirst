/**
 * Contrat HTTP du bridge — ce que l'API reçoit, quelle que soit la version
 * d'express ou de pino installée.
 *
 * Lancé par la CI (job « Build SvelteKit ») : `npm test`, dans `whatsapp-bridge/`.
 * `index.js` tourne tel quel dans un processus enfant, Baileys simulé
 * (`baileys-simule.js`) — aucun appel ne quitte la machine.
 *
 * ⚠️ Ce test ne dit RIEN de Baileys lui-même : une montée de `baileys` se juge
 * toujours sur un envoi réel constaté (`.github/dependabot.yml`).
 */
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const PORT = 18090 + Math.floor(Math.random() * 500);
const BASE = `http://127.0.0.1:${PORT}`;
const CLE = "cle-de-test-assez-longue";
const JSON_CLE = { "x-api-key": CLE, "content-type": "application/json" };

let bridge;

before(async () => {
  bridge = spawn(process.execPath, ["-r", "./tests/baileys-simule.js", "index.js"], {
    cwd: path.join(__dirname, ".."),
    env: { ...process.env, WA_PORT: String(PORT), WA_API_KEY: CLE, WA_LOG_LEVEL: "silent", WA_ACK_DELAI_MS: "400" },
    stdio: "ignore",
  });
  // Attendre que le bridge écoute ET que la connexion simulée soit ouverte.
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch(`${BASE}/status`, { headers: { "x-api-key": CLE } });
      if ((await r.json()).state === "open") return;
    } catch (_) {}
    await new Promise((ok) => setTimeout(ok, 50));
  }
  throw new Error("le bridge n'a pas démarré");
});

after(() => bridge?.kill());

async function appel(chemin, options = {}) {
  const r = await fetch(BASE + chemin, options);
  const texte = await r.text();
  let corps = null;
  try { corps = JSON.parse(texte); } catch (_) {}
  return { statut: r.status, corps };
}

test("sans clé d'API : 401", async () => {
  assert.equal((await appel("/status")).statut, 401);
});

// #1596 : un secret en paramètre d'URL finit dans les journaux d'accès.
test("clé en paramètre de requête : ignorée, 401", async () => {
  assert.equal((await appel(`/status?apikey=${CLE}`)).statut, 401);
});

test("mauvaise clé, même longueur ou plus longue que 64 : 401, jamais 500", async () => {
  assert.equal((await appel("/status", { headers: { "x-api-key": "x".repeat(CLE.length) } })).statut, 401);
  assert.equal((await appel("/status", { headers: { "x-api-key": "x".repeat(200) } })).statut, 401);
});

// ── Démarrage refusé sur une clé faible (#1596) ─────────────────────
// Le bridge ne doit pas écouter du tout : on lance index.js et on attend sa
// sortie. Le message dit pourquoi, et ne cite JAMAIS la valeur reçue.
function demarrer(cle) {
  return spawnSync(process.execPath, ["-r", "./tests/baileys-simule.js", "index.js"], {
    cwd: path.join(__dirname, ".."),
    env: { ...process.env, WA_PORT: "0", WA_API_KEY: cle, WA_LOG_LEVEL: "silent" },
    encoding: "utf8",
    timeout: 10_000,
  });
}

// La valeur d'exemple est lue dans `.env.example` lui-même : si le gabarit
// change de valeur sans que le bridge suive, ce test échoue (contrat entre
// les deux fichiers, `standards/05` §3).
const EXEMPLE = fs
  .readFileSync(path.join(__dirname, "..", "..", ".env.example"), "utf8")
  .match(/^WHATSAPP_API_KEY=(.*)$/m)[1]
  .trim();

for (const [cas, cle] of [
  ["valeur de .env.example", EXEMPLE],
  ["clé trop courte", "court-15-carac."],
  ["clé vide", ""],
]) {
  test(`démarrage refusé : ${cas}`, () => {
    const r = demarrer(cle);
    assert.equal(r.status, 1, `sortie ${r.status} — le bridge a démarré`);
    assert.match(r.stderr, /démarrage refusé — WA_API_KEY/);
    if (cle) assert.ok(!r.stderr.includes(cle), "le message cite la valeur de la clé");
  });
}

test("envoi d'un texte : 200 avec l'identifiant du message", async () => {
  const r = await appel("/send", {
    method: "POST", headers: JSON_CLE, body: JSON.stringify({ number: "33600000000", text: "t" }),
  });
  assert.equal(r.statut, 200);
  assert.equal(r.corps.ok, true);
  assert.equal(r.corps.jid, "33600000000@s.whatsapp.net");
});

test("envoi avec photo en base64 : 200", async () => {
  const r = await appel("/send", {
    method: "POST", headers: JSON_CLE,
    body: JSON.stringify({ number: "33600000000", text: "t", imageBase64: "AAAA" }),
  });
  assert.equal(r.statut, 200);
});

test("champs manquants : 400 en JSON", async () => {
  const r = await appel("/send", { method: "POST", headers: JSON_CLE, body: "{}" });
  assert.equal(r.statut, 400);
  assert.match(r.corps.error, /required/);
});

// Express 5 : sans corps JSON, `req.body` vaut `undefined` — c'était un 500.
test("corps non JSON : 400, pas 500", async () => {
  const r = await appel("/send", { method: "POST", headers: { "x-api-key": CLE }, body: "x" });
  assert.equal(r.statut, 400);
});

// #1057 : le plafond d'express rejetait toute photo, et en HTML.
test("corps au-delà du plafond : 413 en JSON, avec le plafond", async () => {
  const r = await appel("/send", {
    method: "POST", headers: JSON_CLE,
    body: JSON.stringify({ number: "1", text: "x".repeat(900 * 1024) }),
  });
  assert.equal(r.statut, 413);
  assert.equal(r.corps.limitKo, 800);
});

test("corps d'une photo ordinaire (≈ 500 kio) : accepté", async () => {
  const r = await appel("/send", {
    method: "POST", headers: JSON_CLE,
    body: JSON.stringify({ number: "1", text: "t", imageBase64: "A".repeat(500 * 1024) }),
  });
  assert.equal(r.statut, 200);
});

test("liste des groupes : 200", async () => {
  const r = await appel("/groups", { headers: { "x-api-key": CLE } });
  assert.equal(r.statut, 200);
  assert.deepEqual(r.corps, [{ id: "g1", subject: "Hall", participants: 2 }]);
});

test("QR alors que connecté : 200, « Already connected »", async () => {
  const r = await appel("/qr", { headers: { "x-api-key": CLE } });
  assert.equal(r.statut, 200);
  assert.equal(r.corps.state, "open");
});

// ── L'accusé du serveur (12/10/2026) ─────────────────────────────────────
// Chaque envoi au GROUPE de la résidence rendait 202 « accusé non observé » en
// production, et un courriel d'alerte partait à chaque message arrivé.

const envoyer = (number, text) =>
  appel("/send", { method: "POST", headers: JSON_CLE, body: JSON.stringify({ number, text }) });

test("envoi à un GROUPE : 200 — l'accusé du serveur suffit, sans accusé de destinataire", async () => {
  const r = await envoyer("120363000000000000@g.us", "t");
  assert.equal(r.statut, 200);
  assert.equal(r.corps.ok, true);
});

test("accusé d'erreur du serveur : 502 « refusé », jamais 202 « probablement remis »", async () => {
  const r = await envoyer("120363000000000000@g.us", "SIMULE_ACCUSE_ERREUR");
  assert.equal(r.statut, 502);
  assert.equal(r.corps.refuse, true);
  assert.match(r.corps.error, /479/);
});

// En DERNIER : le 202 déclenche une reconnexion du socket.
test("aucun accusé dans le délai : 202, message émis mais non acquitté", async () => {
  const r = await envoyer("120363000000000000@g.us", "SIMULE_SANS_ACCUSE");
  assert.equal(r.statut, 202);
  assert.equal(r.corps.envoye, true);
  assert.equal(r.corps.acquitte, false);
});
