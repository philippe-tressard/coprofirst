/**
 * Ce qui fait ARRIVER l'arrêt propre en production (#1590) : le module est dans
 * l'image, et Docker laisse au bridge le temps de s'arrêter. Un test de
 * `arret.js` qui passe ne dit rien de ces deux-là — ils vivent dans d'autres
 * fichiers, et les oublier rend le bridge à son SIGKILL d'avant sans qu'aucun
 * autre test ne bouge.
 */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const BRIDGE = path.join(__dirname, "..");
const lire = (...p) => fs.readFileSync(path.join(...p), "utf8");

// Le minuteur de sécurité du bridge, lu dans index.js : jamais recopié ici.
function delaiBridgeMs() {
  const m = lire(BRIDGE, "index.js").match(/WA_ARRET_DELAI_MS \|\| "(\d+)"/);
  assert.ok(m, "le délai d'arrêt n'est plus déclaré dans index.js");
  return Number(m[1]);
}

// Chaque module local qu'`index.js` requiert, lu dans index.js : un module
// oublié dans le Dockerfile, et le bridge plante au démarrage en production —
// alors que tous les tests, lancés depuis le dépôt, le trouvent (accuses.js,
// 12/10/2026 : ce test ne nommait qu'arret.js).
const modulesRequis = () =>
  [...lire(BRIDGE, "index.js").matchAll(/require\("\.\/([\w-]+)"\)/g)].map((m) => `${m[1]}.js`);

test("l'image du bridge embarque chaque module local requis par index.js", () => {
  const dockerfile = lire(BRIDGE, "Dockerfile");
  const copies = dockerfile.split(/\r?\n/).filter((l) => /^COPY\s/.test(l) && !l.includes("package"));
  const requis = modulesRequis();
  // Témoin : la lecture des `require` doit trouver au moins le module d'arrêt.
  assert.ok(requis.includes("arret.js"), `modules requis lus dans index.js : ${requis.join(", ")}`);
  for (const module of requis) {
    assert.ok(
      copies.some((l) => l.split(/\s+/).includes(module)),
      `${module} n'est copié par aucune ligne COPY : ${copies.join(" | ")}`
    );
  }
});

test("docker-compose : stop_grace_period du bridge, strictement au-dessus du minuteur du bridge", () => {
  const compose = lire(BRIDGE, "..", "docker-compose.yml");
  const debut = compose.search(/^\s{2}whatsapp-bridge:\s*$/m);
  assert.ok(debut >= 0, "service whatsapp-bridge introuvable");
  // Le bloc du service : jusqu'au service ou à la section suivante.
  const reste = compose.slice(debut).split(/\r?\n/).slice(1);
  const bloc = [];
  for (const ligne of reste) {
    if (/^\S/.test(ligne) || /^\s{2}\S/.test(ligne)) break;
    bloc.push(ligne);
  }
  const m = bloc.join("\n").match(/^\s{4}stop_grace_period:\s*(\d+)s\s*$/m);
  assert.ok(m, "whatsapp-bridge n'a pas de stop_grace_period : Docker le tue à 10 s (exit 137)");
  assert.ok(
    Number(m[1]) * 1000 > delaiBridgeMs(),
    `stop_grace_period (${m[1]} s) doit dépasser le minuteur du bridge (${delaiBridgeMs()} ms)`
  );
});
