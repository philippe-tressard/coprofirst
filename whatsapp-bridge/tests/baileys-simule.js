/**
 * Baileys SIMULÉ — préchargé par `node -r` avant `index.js`.
 *
 * Le bridge ne peut pas se tester contre WhatsApp : aucune CI ne tient une
 * session, et en ouvrir une depuis un test serait un appareil de plus sur le
 * compte. Ce qu'on peut vérifier sans lui, c'est tout ce qu'`index.js` fait
 * AUTOUR de Baileys — clé d'API, plafond du corps, codes de réponse, accusé du
 * serveur — et c'est précisément ce qu'une montée d'express peut casser.
 *
 * Né le 27/09/2026 avec la montée d'express 4 → 5 (PR Dependabot #1289) : le
 * banc qui l'a précédé a trouvé un `POST /send` sans corps JSON passé de 400 à
 * 500, que rien d'autre n'aurait vu avant la production.
 */
const Module = require("module");
const { EventEmitter } = require("events");
const fs = require("fs");

// ── Scénario d'ARRÊT (#1590) — inerte tant que SIMULE_TRACE n'est pas posée ──
// Rejoue ce que fait Baileys au moment où `docker compose stop` arrive : une
// écriture d'état d'authentification EN COURS (creds + clé, lentes), puis le
// signal. Le signal est émis par `process.emit` et non envoyé par l'OS : sous
// Windows `kill("SIGTERM")` tue le processus sans passer par les écouteurs,
// et le test ne dirait rien du câblage d'`index.js`.
//   SIMULE_TRACE            fichier où chaque événement s'écrit, une ligne chacun
//   SIMULE_ECRITURE_MS      durée d'une écriture d'état (défaut 300)
//   SIMULE_SIGNAL           signal émis pendant l'écriture (ex. SIGTERM)
//   SIMULE_SECOND_SIGNAL    second signal, 50 ms plus tard
const TRACE = process.env.SIMULE_TRACE;
const trace = (ligne) => { if (TRACE) fs.appendFileSync(TRACE, `${ligne}\n`); };
const ECRITURE_MS = parseInt(process.env.SIMULE_ECRITURE_MS || "300", 10);
const attendre = (ms) => new Promise((ok) => setTimeout(ok, ms));

const simule = {
  default: (config) => {
    const ev = new EventEmitter();
    const ws = new EventEmitter();
    trace("socket-cree");
    setTimeout(() => ev.emit("connection.update", { connection: "open" }), 20);
    if (TRACE && process.env.SIMULE_SIGNAL) {
      setTimeout(() => {
        // Les deux écritures démarrent avant le signal, comme en vrai.
        ev.emit("creds.update", {});
        config.auth.keys.set({ session: { x: { k: 1 } } });
      }, 60);
      setTimeout(() => {
        trace("signal");
        process.emit(process.env.SIMULE_SIGNAL);
        if (process.env.SIMULE_SECOND_SIGNAL) {
          setTimeout(() => { trace("second-signal"); process.emit(process.env.SIMULE_SECOND_SIGNAL); }, 50);
        }
      }, 150);
    }
    return {
      ev,
      end() {
        trace("socket-end");
        // Baileys annonce la fermeture après `end()` : l'arrêt voulu ne doit
        // pas être pris pour une coupure à rattraper. (Seulement dans ce
        // scénario : les autres tests n'ont jamais vu `end()` fermer quoi que ce soit.)
        if (TRACE) setTimeout(() => ev.emit("connection.update", {
          connection: "close",
          lastDisconnect: { error: { output: { statusCode: 428 } } },
        }), 0);
      },
      groupFetchAllParticipating: async () => ({
        g1: { id: "g1", subject: "Hall", participants: [{}, {}] },
      }),
      ws,
      sendMessage: async (jid, contenu) => {
        const id = `M${Date.now()}${Math.random().toString(36).slice(2, 6)}`;
        const texte = contenu?.text ?? contenu?.caption ?? "";
        // 🔴 Ce que Baileys 6.7 émet VRAIMENT (`accuses.js`, 12/10/2026). Ce banc
        // émettait un `messages.update` statut 2 « comme en vrai » : Baileys ne
        // le fait jamais pour un groupe, et le bridge, vert ici, classait chaque
        // envoi au groupe « accusé non observé » en production.
        //   - l'accusé du serveur passe par `ws`, `CB:ack,class:message` ;
        //   - aucun `messages.update` de statut ≥ 2 pour un groupe.
        // Textes de scénario : SIMULE_SANS_ACCUSE (rien ne vient), SIMULE_ACCUSE_ERREUR.
        if (texte.includes("SIMULE_SANS_ACCUSE")) return { key: { id } };
        const attrs = { id, class: "message", from: jid };
        if (texte.includes("SIMULE_ACCUSE_ERREUR")) attrs.error = "479";
        setTimeout(() => ws.emit("CB:ack,class:message", { tag: "ack", attrs }), 10);
        return { key: { id } };
      },
    };
  },
  useMultiFileAuthState: async () => ({
    state: {
      creds: {},
      keys: {
        get: async () => ({}),
        set: async () => {
          trace("cle-debut");
          await attendre(ECRITURE_MS);
          trace("cle-fin");
        },
      },
    },
    saveCreds: async () => {
      trace("creds-debut");
      await attendre(ECRITURE_MS);
      trace("creds-fin");
    },
  }),
  DisconnectReason: { loggedOut: 401 },
  fetchLatestBaileysVersion: async () => ({ version: [2, 3000, 0] }),
  makeCacheableSignalKeyStore: (cles) => cles,
};

const chargerOrigine = Module._load;
Module._load = function (demande, ...reste) {
  if (demande === "baileys") return simule;
  return chargerOrigine.call(this, demande, ...reste);
};
