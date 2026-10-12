/**
 * Les trois sources d'accusé de Baileys (`accuses.js`, 12/10/2026) — chacune
 * suffit seule. Le défaut d'origine : seule `messages.update` était écoutée, et
 * Baileys ne l'émet jamais pour un groupe.
 */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const { AccuseRefuse, brancherAccuses, creerSuiviAccuses } = require("../accuses");

function monter(delaiMs = 200) {
  const sock = { ev: new EventEmitter(), ws: new EventEmitter() };
  const suivi = creerSuiviAccuses({ delaiMs });
  brancherAccuses(sock, suivi);
  return { sock, suivi };
}

test("accusé du serveur (ws, CB:ack,class:message) : tenu", async () => {
  const { sock, suivi } = monter();
  const attente = suivi.attendre("A1");
  sock.ws.emit("CB:ack,class:message", { tag: "ack", attrs: { id: "A1", class: "message" } });
  assert.equal(await attente, "serveur");
  assert.equal(suivi.nombre, 0);
});

test("accusé d'un participant du groupe (message-receipt.update) : tenu", async () => {
  const { sock, suivi } = monter();
  const attente = suivi.attendre("A2");
  sock.ev.emit("message-receipt.update", [{ key: { id: "A2" }, receipt: { userJid: "x", receiptTimestamp: 1 } }]);
  assert.equal(await attente, "participant");
});

test("conversation individuelle (messages.update statut ≥ 2) : tenu", async () => {
  const { sock, suivi } = monter();
  const attente = suivi.attendre("A3");
  sock.ev.emit("messages.update", [{ key: { id: "A3" }, update: { status: 3 } }]);
  assert.equal(await attente, "destinataire");
});

test("refus du serveur, par ws ou par messages.update statut ERROR : AccuseRefuse", async () => {
  const { sock, suivi } = monter();
  const parWs = suivi.attendre("R1");
  const parMaj = suivi.attendre("R2");
  sock.ws.emit("CB:ack,class:message", { attrs: { id: "R1", error: "479" } });
  sock.ev.emit("messages.update", [{ key: { id: "R2" }, update: { status: 0, messageStubParameters: ["421"] } }]);
  await assert.rejects(parWs, (e) => e instanceof AccuseRefuse && /479/.test(e.message));
  await assert.rejects(parMaj, (e) => e instanceof AccuseRefuse && /421/.test(e.message));
});

test("statut 1 (en attente) ou id inconnu : rien ne se solde, l'échéance rejette", async () => {
  const { sock, suivi } = monter(50);
  const attente = suivi.attendre("T1");
  sock.ev.emit("messages.update", [{ key: { id: "T1" }, update: { status: 1 } }]);
  sock.ws.emit("CB:ack,class:message", { attrs: { id: "AUTRE" } });
  await assert.rejects(attente, (e) => !(e instanceof AccuseRefuse) && /ACK timeout/.test(e.message));
  assert.equal(suivi.nombre, 0);
});

test("fermeture de connexion : toutes les attentes rejetées", async () => {
  const { suivi } = monter(10_000);
  const a = suivi.attendre("F1");
  const b = suivi.attendre("F2");
  suivi.toutRejeter("Connection closed");
  await assert.rejects(a, /Connection closed/);
  await assert.rejects(b, /Connection closed/);
  assert.equal(suivi.nombre, 0);
});
