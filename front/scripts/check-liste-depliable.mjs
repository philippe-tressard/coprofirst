/**
 * Auto-test de `#lib/listeDepliable.ts` — la mécanique des cartes dépliables.
 *
 * 🔴 POURQUOI (#640, 01/09/2026). Cette mécanique vivait **deux fois** dans
 * `espace-cs/+page.svelte` — une pour les membres du conseil syndical, une pour
 * ceux du syndic —, à l'identifiant près, et **rien ne l'éprouvait** : le front
 * n'a pas de lanceur de tests.
 *
 * Le décalage d'index après un retrait est la partie subtile, celle qu'on recopie
 * sans la relire. Une erreur d'un cran y ouvre la carte du voisin, ou passe en
 * édition une fiche qu'on n'a pas demandée — et cela ne se voit qu'en supprimant
 * un membre du milieu de la liste, donc jamais pendant une relecture.
 *
 * Le pattern est celui de `check-init-prestataires.mjs` : fonction PURE +
 * `--selftest`, sur le module que le site embarque, pas une copie.
 *
 * Usage : node scripts/check-liste-depliable.mjs --selftest
 *
 * Le module est en TypeScript : Node le lit sans drapeau depuis 22.18 (#2293).
 */
import {
	REPLIE,
	ajouter,
	basculer,
	editer,
	retirer,
	terminerEdition,
} from '../src/lib/listeDepliable.ts';

const echecs = [];
//  Compté, jamais écrit en dur : un nombre recopié dans le message de succès
//  devient faux au premier cas ajouté.
let cas = 0;
const verifier = (nom, obtenu, attendu) => {
	cas++;
	const a = JSON.stringify(obtenu);
	const b = JSON.stringify(attendu);
	if (a !== b) echecs.push(`  ✗ ${nom}\n      attendu ${b}\n      obtenu  ${a}`);
};

const etat = (ouvert, edite) => ({ ouvert, edite });

// ── Déplier / replier ────────────────────────────────────────────────────────
verifier('rien d’ouvert → déplier la 2e', basculer(REPLIE, 2), etat(2, null));
verifier('la 2e ouverte → la replier', basculer(etat(2, null), 2), etat(null, null));
verifier('la 2e ouverte → ouvrir la 5e', basculer(etat(2, null), 5), etat(5, null));
//  🔴 Le clic ne referme PAS une carte en édition : il sert à poser le curseur
//  dans un champ, et replier effacerait la saisie sans prévenir.
verifier('la 2e en édition → le clic ne fait rien', basculer(etat(2, 2), 2), etat(2, 2));
//  … mais il ouvre bien une AUTRE carte, sinon la liste serait bloquée dès qu'une
//  fiche est en cours d'édition.
verifier('la 2e en édition → ouvrir la 5e', basculer(etat(2, 2), 5), etat(5, 2));

// ── Éditer / terminer ────────────────────────────────────────────────────────
verifier('« Modifier » ouvre ET édite', editer(3), etat(3, 3));
verifier('fin d’édition : la carte reste ouverte', terminerEdition(etat(3, 3)), etat(3, null));

// ── Ajouter ──────────────────────────────────────────────────────────────────
//  La longueur passée est celle d'APRÈS l'ajout : c'est ce dont l'appelant
//  dispose. Lui demander `longueur - 1` inviterait à l'erreur d'un cran.
verifier('ajout dans une liste vide', ajouter(1), etat(0, 0));
verifier('ajout en 4e position', ajouter(4), etat(3, 3));

// ── Retirer : le décalage d’index ────────────────────────────────────────────
verifier('retirer la carte ouverte', retirer(etat(2, null), 2), etat(null, null));
verifier('retirer la carte éditée', retirer(etat(2, 2), 2), etat(null, null));
//  Cas 2 : une carte APRÈS celle qu'on retire — son index descend d'un cran.
verifier('retirer avant l’ouverte', retirer(etat(5, null), 2), etat(4, null));
verifier('retirer avant l’éditée', retirer(etat(5, 5), 2), etat(4, 4));
//  Cas 3 : une carte AVANT — rien ne bouge. C'est celui qu'on oublie.
verifier('retirer après l’ouverte', retirer(etat(1, null), 4), etat(1, null));
verifier('retirer sur une liste sans rien d’ouvert', retirer(REPLIE, 0), etat(null, null));
//  🔴 L'écriture dupliquée ne traitait pas ce cas : elle supposait qu'on ne peut
//  pas éditer une carte sans l'avoir ouverte. Vrai aujourd'hui — le bouton pose
//  les deux ensemble —, mais l'invariance n'était écrite nulle part, et `edite`
//  serait resté pointé sur la carte suivante.
verifier('éditée sans être ouverte, on la retire', retirer(etat(null, 2), 2), etat(null, null));

if (echecs.length > 0) {
	console.error(`✗ listeDepliable — ${echecs.length} cas en échec sur ${cas} :\n`);
	console.error(echecs.join('\n'));
	process.exit(1);
}

//  Le relevé légitime est vide : sans le compte des cas, ce message serait
//  identique si le module n'exportait plus rien (`standards/04` §27).
if (cas === 0) {
	console.error('✗ Aucun cas exécuté — le module ne s’importe plus. INCONNU, pas OK.');
	process.exit(1);
}
console.log(`✓ listeDepliable : ${cas} cas vérifiés — déplier, éditer, ajouter, retirer.`);
