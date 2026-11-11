/**
 * Arrêt du bridge de bout en bout (#1590) : `index.js` tel quel, Baileys simulé
 * (`baileys-simule.js`, scénario SIMULE_*). Le signal est émis dans le processus
 * (`process.emit`), qui appelle les écouteurs exactement comme le ferait l'OS —
 * sauf sous Windows où un vrai `kill` ne les appelle pas. Un dernier test, sous
 * Linux seulement, envoie un VRAI SIGTERM.
 *
 * Le défaut d'origine : aucun écouteur, Node en PID 1 ne réagit pas à SIGTERM,
 * `docker compose stop` attend 10 s puis SIGKILL (exit 137) — au milieu d'une
 * écriture de `creds.json` ou d'une clé, à chaque bascule et chaque déploiement.
 */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CLE = "cle-de-test-assez-longue";

function lancer(env, logLevel = "warn") {
  const trace = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "arret-")), "trace.txt");
  const port = 19090 + Math.floor(Math.random() * 500);
  const enfant = spawn(process.execPath, ["-r", "./tests/baileys-simule.js", "index.js"], {
    cwd: path.join(__dirname, ".."),
    env: { ...process.env, WA_PORT: String(port), WA_API_KEY: CLE, WA_LOG_LEVEL: logLevel, SIMULE_TRACE: trace, ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const etat = { sortie: "" };
  enfant.stdout.on("data", (d) => {
    etat.sortie += d;
  });
  enfant.stderr.on("data", (d) => {
    etat.sortie += d;
  });
  return { enfant, trace, etat };
}

const lireTrace = (trace) => (fs.existsSync(trace) ? fs.readFileSync(trace, "utf8").split("\n").filter(Boolean) : []);

// Lance le bridge dans un scénario et rend ce qu'on peut en observer.
// Une garde tue le processus (SIGKILL) s'il tourne encore à `attenteMax` : un
// bridge qui ne réagit pas au signal se lit alors `signal === "SIGKILL"`.
function scenario(env, { attenteMax = 6000 } = {}) {
  const { enfant, trace, etat } = lancer(env);
  const debut = Date.now();
  return new Promise((ok) => {
    const garde = setTimeout(() => enfant.kill("SIGKILL"), attenteMax);
    enfant.on("exit", (code, signal) => {
      clearTimeout(garde);
      ok({ code, signal, lignes: lireTrace(trace), sortie: etat.sortie, duree: Date.now() - debut });
    });
  });
}

test("SIGTERM pendant une écriture : socket fermé, écritures finies, sortie 0, sans reconnexion", async () => {
  const r = await scenario({ SIMULE_SIGNAL: "SIGTERM", SIMULE_ECRITURE_MS: "400" });
  assert.equal(r.signal, null, `le bridge devait sortir de lui-même : ${r.lignes}`);
  assert.equal(r.code, 0);
  const i = (x) => r.lignes.indexOf(x);
  assert.ok(i("signal") >= 0 && i("socket-end") > i("signal"), `socket fermé après le signal : ${r.lignes}`);
  // Les écritures commencées avant le signal sont allées jusqu'au bout…
  assert.ok(i("creds-fin") > i("socket-end"), `creds-fin manque ou précède la fermeture : ${r.lignes}`);
  assert.ok(i("cle-fin") > i("socket-end"), `cle-fin manque : ${r.lignes}`);
  // …et la sortie est venue d'elles, pas du minuteur de sécurité (8 s).
  assert.ok(r.duree < 4000, `sortie en ${r.duree} ms`);
  // Aucune reconnexion : un seul socket, pas de « Reconnexion programmée ».
  assert.equal(r.lignes.filter((l) => l === "socket-cree").length, 1, `socket recréé : ${r.lignes}`);
  assert.ok(!r.sortie.includes("Reconnexion programmée"), r.sortie);
});

test("SIGINT : même arrêt propre", async () => {
  const r = await scenario({ SIMULE_SIGNAL: "SIGINT", SIMULE_ECRITURE_MS: "200" });
  assert.equal(r.signal, null, `le bridge devait sortir de lui-même : ${r.lignes}`);
  assert.equal(r.code, 0);
  assert.ok(r.lignes.includes("creds-fin") && r.lignes.includes("cle-fin"), String(r.lignes));
});

test("un second signal pendant l'arrêt est sans effet", async () => {
  const r = await scenario({ SIMULE_SIGNAL: "SIGTERM", SIMULE_SECOND_SIGNAL: "SIGINT", SIMULE_ECRITURE_MS: "400" });
  assert.equal(r.code, 0);
  assert.equal(r.lignes.filter((l) => l === "socket-end").length, 1, `fermé deux fois : ${r.lignes}`);
  assert.ok(r.lignes.includes("second-signal"));
  assert.ok(r.lignes.includes("creds-fin"), "le second signal n'a pas coupé l'écriture");
});

test("une écriture qui ne finit pas est coupée par le minuteur de sécurité, en 0", async () => {
  const r = await scenario({
    SIMULE_SIGNAL: "SIGTERM",
    SIMULE_ECRITURE_MS: "60000",
    WA_ARRET_DELAI_MS: "500",
  });
  assert.equal(r.signal, null, `le bridge devait sortir de lui-même : ${r.lignes}`);
  assert.equal(r.code, 0);
  assert.ok(r.duree >= 500 && r.duree < 5000, `sortie en ${r.duree} ms`);
  assert.ok(!r.lignes.includes("creds-fin"));
});

test("sans signal, rien ne s'arrête et la connexion se tient", async () => {
  // Écritures lancées, mais aucun signal : le bridge doit rester debout.
  const { enfant, trace } = lancer({ SIMULE_ECRITURE_MS: "50" });
  await new Promise((ok) => setTimeout(ok, 1200));
  const vivant = enfant.exitCode === null && enfant.signalCode === null;
  enfant.kill("SIGKILL");
  assert.ok(vivant, "le bridge s'est arrêté sans signal");
  assert.ok(!lireTrace(trace).includes("socket-end"));
});

// Attend qu'une ligne paraisse dans la trace — un FAIT, jamais une durée (#2656).
// Le plafond, large, ne sert qu'à ne pas pendre : sous une charge de 588 sur 12
// cœurs, 500 ms fixes ne suffisaient plus à l'enfant pour poser ses écouteurs,
// et le test mesurait la vitesse du poste au lieu de l'arrêt propre.
async function attendreLigne(trace, ligne, enfant, plafondMs = 30000) {
  const debut = Date.now();
  while (!lireTrace(trace).includes(ligne)) {
    if (enfant.exitCode !== null || enfant.signalCode !== null) {
      throw new Error(`l'enfant est sorti avant « ${ligne} » (code ${enfant.exitCode}, signal ${enfant.signalCode})`);
    }
    if (Date.now() - debut > plafondMs) throw new Error(`« ${ligne} » absente de la trace après ${plafondMs} ms`);
    await new Promise((ok) => setTimeout(ok, 20));
  }
}

test("un VRAI SIGTERM de l'OS (Linux)", { skip: process.platform === "win32" }, async () => {
  const { enfant, trace } = lancer({ SIMULE_ECRITURE_MS: "300" }, "silent");
  // `index.js` pose ses écouteurs de SIGTERM AVANT d'ouvrir le port ; la socket
  // simulée ne naît qu'une fois le port ouvert. Sa ligne dit donc que l'arrêt
  // propre est prêt.
  await attendreLigne(trace, "socket-cree", enfant);
  const fin = new Promise((ok) => enfant.on("exit", (code, signal) => ok({ code, signal })));
  enfant.kill("SIGTERM");
  const garde = setTimeout(() => enfant.kill("SIGKILL"), 4000);
  const { code, signal } = await fin;
  clearTimeout(garde);
  assert.equal(signal, null);
  assert.equal(code, 0);
});
