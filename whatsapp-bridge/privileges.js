/**
 * Descendre de root vers le compte `node` (#2368) — le premier geste du bridge.
 *
 * Le conteneur est DURCI (`docker-compose.yml`, `conteneur_durci`) : aucune
 * capacité hors des quatre que ce premier pas demande, système de fichiers en
 * lecture seule. Le bridge démarre en root le temps de rendre son état
 * d'authentification à `node` — la bascule le recopie d'un nœud à l'autre avec
 * l'uid du compte qui l'a transporté, et une installation neuve le crée en root —,
 * puis il descend : Baileys, le serveur HTTP et tout ce qu'un message reçu
 * pourrait atteindre tournent en `node`, sans aucune capacité (le noyau les retire
 * quand root devient un autre uid). C'est le pas que `api/start.sh` fait pour
 * l'API par `setpriv`.
 *
 * Pur : le processus et le système de fichiers sont injectés — c'est ce qui le
 * teste (`tests/privileges.test.js`) sans être root.
 */
const fs = require("fs");
const path = require("path");

//: Le compte de l'image `node:*-alpine` — son uid est vérifié à la construction
//: (`whatsapp-bridge/Dockerfile`), jamais supposé au démarrage.
const COMPTE_NODE = { nom: "node", uid: 1000, gid: 1000 };

// Rend `racine` et tout ce qu'elle contient à uid:gid ; rend le nombre d'entrées
// réalignées. `lchown` : un lien symbolique se réaligne lui-même, sans suivre sa
// cible hors du volume.
function realignerProprietaire(racine, uid, gid, f = fs) {
  let realignes = 0;
  const pile = [racine];
  while (pile.length) {
    const chemin = pile.pop();
    const st = f.lstatSync(chemin);
    if (st.uid !== uid || st.gid !== gid) {
      f.lchownSync(chemin, uid, gid);
      realignes += 1;
    }
    if (st.isDirectory()) {
      for (const nom of f.readdirSync(chemin)) pile.push(path.join(chemin, nom));
    }
  }
  return realignes;
}

// Root : réaligne `dossier` puis descend vers `compte`. Un autre uid (poste de
// développement, tests) : rien à faire. Toute erreur remonte — un bridge resté
// root, ou incapable d'écrire son état, ne doit pas démarrer comme si de rien.
function descendreDeRoot(dossier, { proc = process, f = fs, compte = COMPTE_NODE } = {}) {
  if (typeof proc.getuid !== "function" || proc.getuid() !== 0) {
    return { descendu: false, realignes: 0 };
  }
  const realignes = f.existsSync(dossier) ? realignerProprietaire(dossier, compte.uid, compte.gid, f) : 0;
  proc.setgroups([compte.gid]);
  proc.setgid(compte.gid);
  proc.setuid(compte.uid);
  if (proc.getuid() !== compte.uid || proc.getgid() !== compte.gid) {
    throw new Error(`toujours uid ${proc.getuid()}, gid ${proc.getgid()} après la descente vers ${compte.nom}`);
  }
  return { descendu: true, realignes };
}

module.exports = { COMPTE_NODE, descendreDeRoot, realignerProprietaire };
