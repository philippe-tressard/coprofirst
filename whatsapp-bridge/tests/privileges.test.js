/**
 * La descente de root vers `node` (#2368) — processus et système de fichiers
 * simulés : la règle s'éprouve sans être root.
 *
 * Lancé par la CI avec le reste (`npm test`, dans `whatsapp-bridge/`).
 */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { COMPTE_NODE, descendreDeRoot, realignerProprietaire } = require("../privileges");

// Un arbre en mémoire : chemin → { uid, gid, enfants? }. Les chemins sont
// ramenés à la forme POSIX : `path.join` écrit `\` quand le test tourne sous Windows.
function fauxFs(arbre) {
  const chown = [];
  const n = (p) => p.replace(/\\/g, "/");
  return {
    chown,
    existsSync: (p) => n(p) in arbre,
    lstatSync: (p) => {
      if (!(n(p) in arbre)) throw Object.assign(new Error(`ENOENT ${p}`), { code: "ENOENT" });
      const e = arbre[n(p)];
      return { uid: e.uid, gid: e.gid, isDirectory: () => Array.isArray(e.enfants) };
    },
    readdirSync: (p) => arbre[n(p)].enfants,
    lchownSync: (p, uid, gid) => {
      chown.push(n(p));
      Object.assign(arbre[n(p)], { uid, gid });
    },
  };
}

// Un processus root qui obéit (ou non) à setuid/setgid.
function fauxProc({ uid = 0, obeit = true } = {}) {
  const etat = { uid, gid: uid, groupes: null, appels: [] };
  return {
    etat,
    getuid: () => etat.uid,
    getgid: () => etat.gid,
    setgroups: (g) => {
      etat.appels.push("setgroups");
      etat.groupes = g;
    },
    setgid: (g) => {
      etat.appels.push("setgid");
      if (obeit) etat.gid = g;
    },
    setuid: (u) => {
      etat.appels.push("setuid");
      if (obeit) etat.uid = u;
    },
  };
}

const ARBRE = () => ({
  "/auth": { uid: 0, gid: 0, enfants: ["creds.json", "cles"] },
  "/auth/creds.json": { uid: 1000, gid: 1000 },
  "/auth/cles": { uid: 0, gid: 0, enfants: ["a.json"] },
  "/auth/cles/a.json": { uid: 0, gid: 0 },
});

test("root : l'état est rendu à node, puis le processus descend — groupes, gid, uid, dans cet ordre", () => {
  const f = fauxFs(ARBRE());
  const proc = fauxProc();
  const r = descendreDeRoot("/auth", { proc, f });
  assert.deepEqual(r, { descendu: true, realignes: 3 });
  assert.deepEqual(f.chown.sort(), ["/auth", "/auth/cles", "/auth/cles/a.json"]);
  assert.deepEqual(proc.etat.appels, ["setgroups", "setgid", "setuid"]);
  assert.equal(proc.etat.uid, COMPTE_NODE.uid);
  assert.deepEqual(proc.etat.groupes, [COMPTE_NODE.gid]);
});

test("une entrée déjà à node n'est pas touchée (le cas ordinaire, après la première descente)", () => {
  const arbre = ARBRE();
  for (const e of Object.values(arbre)) Object.assign(e, { uid: 1000, gid: 1000 });
  const f = fauxFs(arbre);
  assert.equal(realignerProprietaire("/auth", 1000, 1000, f), 0);
  assert.deepEqual(f.chown, []);
});

test("pas root : rien n'est réaligné, rien ne change d'identité", () => {
  const f = fauxFs(ARBRE());
  const proc = fauxProc({ uid: 1000 });
  assert.deepEqual(descendreDeRoot("/auth", { proc, f }), { descendu: false, realignes: 0 });
  assert.deepEqual(f.chown, []);
  assert.deepEqual(proc.etat.appels, []);
});

test("dossier absent : la descente a lieu quand même, sans réalignement", () => {
  const proc = fauxProc();
  assert.deepEqual(descendreDeRoot("/absent", { proc, f: fauxFs({}) }), { descendu: true, realignes: 0 });
  assert.equal(proc.etat.uid, COMPTE_NODE.uid);
});

test("une descente refusée par le noyau ne passe pas pour réussie", () => {
  assert.throws(() => descendreDeRoot("/auth", { proc: fauxProc({ obeit: false }), f: fauxFs(ARBRE()) }), /toujours uid 0/);
});

test("un réalignement impossible arrête le démarrage, avant toute descente", () => {
  const f = fauxFs(ARBRE());
  f.lchownSync = () => {
    throw Object.assign(new Error("EPERM"), { code: "EPERM" });
  };
  const proc = fauxProc();
  assert.throws(() => descendreDeRoot("/auth", { proc, f }), /EPERM/);
  assert.deepEqual(proc.etat.appels, []);
});
