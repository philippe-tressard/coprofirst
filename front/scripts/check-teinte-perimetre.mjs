#!/usr/bin/env node
/**
 *  Self-test de la **teinte d'une pastille de périmètre** (`#lib/perimetres/teinte`).
 *
 *  ## La règle, arbitrée à l'écran
 *
 *  > « La couleur des catégories de niveau *n* hérite de la catégorie de
 *  >   niveau 1. » (13/09/2026)
 *
 *  ## Trois corrections, et ce que chacune a appris
 *
 *  **12/09** — « Bât. 1 » bleu clair, « Ascenseur » (qui est DANS le bâtiment 1)
 *  rose : la couleur venait d'un condensat du code entier. Corrigé, livré.
 *
 *  **13/09, matin** — toujours là. Le correctif lisait le champ `profondeur`
 *  pour remonter l'arbre, et ce champ ne portait pas ce qu'on croyait :
 *  `undefined > 1` vaut `false`, la remontée s'arrêtait aussitôt.
 *  ⚠️ Mes onze cas passaient, parce qu'ils fournissaient eux-mêmes un
 *  `profondeur` juste.
 *
 *  **13/09, soir** — 🔴 TOUJOURS LÀ, sur la même paire : « Bâtiment 1 » et
 *  « Locaux techniques › Local eau » tous deux orange. Le niveau se calculait
 *  bien depuis les `parent`, mais **l'arbre d'essai ci-dessous n'avait pas la
 *  forme de l'arbre réel** : il rangeait `bat:1` et `local-technique` côte à
 *  côte sous une racine unique. En production, `Bâtiments` est un nœud
 *  d'ORGANISATION qui porte les bâtiments, tandis que `Locaux techniques` est
 *  une racine que l'on cible directement. Compter les parents mettait donc
 *  `bat:1` au même rang que `locaux-techniques/local-eau`, la rangée des têtes
 *  gonflait à plusieurs dizaines d'entrées, et le modulo de la palette rendait
 *  les collisions certaines.
 *
 *  🔴 **La leçon, la même à chaque fois, sous une forme nouvelle** : un test qui
 *  construit sa donnée d'entrée ne prouve rien sur celle que la production
 *  fournit. Ce n'était plus un champ inventé, c'était une FORME inventée — plus
 *  difficile à voir, et tout aussi fausse. L'arbre ci-dessous reprend donc
 *  exactement celui de `api/app/seed/patrimoine.py` : ses deux formes de racine,
 *  ses dix têtes, et le gabarit sous les bâtiments.
 *
 *  Lancer : npm run lint:teinte
 */
import {
	PALETTE_PERIMETRE,
	TEINTE_COPROPRIETE,
	codeDeTeinte,
	estRegroupement,
	premierNiveauDe,
	rangPremierNiveau,
	teinteDuCode,
} from '../src/lib/perimetres/teinte.ts';

//  🔴 LA FORME DU SEED, PAS UNE FORME COMMODE. Deux genres de racine coexistent,
//  et c'est tout le sujet :
//    · `batiments` et `cave` — non sélectionnables : des REGROUPEMENTS. On ne les
//      cible pas, ils ne portent donc aucune couleur, et leurs enfants sont des
//      têtes.
//    · `residence`, `parking`, `aful`, `cheminements`, `locaux-techniques` —
//      sélectionnables : des TÊTES à part entière.
//  Compter les parents confond les deux. C'est le défaut du 13/09.
const n = (code, parent, selectionnable = true) => ({ code, parent, selectionnable });
const ARBRE = Object.fromEntries(
	[
		n('residence', null),
		n('batiments', null, false),
		n('bat:1', 'batiments'),
		n('bat:2', 'batiments'),
		n('bat:1/ascenseur', 'bat:1'),
		n('bat:1/hall', 'bat:1'),
		n('bat:1/hall/sas', 'bat:1/hall'),
		n('bat:2/ascenseur', 'bat:2'),
		n('cave', null, false),
		n('parking', null),
		n('parking/places', 'parking'),
		n('aful', null),
		n('espaces-verts', null),
		n('cheminements', null),
		n('cheminements/portillon', 'cheminements'),
		n('locaux-techniques', null),
		n('locaux-techniques/local-eau', 'locaux-techniques'),
		//  Un cycle, écrit à la main en base : il ne doit pas figer l'écran.
		n('boucleA', 'boucleB'),
		n('boucleB', 'boucleA'),
	].map((x) => [x.code, x]),
);
const lire = (c) => ARBRE[c];
const PREMIER = premierNiveauDe(Object.keys(ARBRE), lire);
const couleur = (code) => teinteDuCode(code, rangPremierNiveau(codeDeTeinte(code, lire), PREMIER));

let echecs = 0;
let cas = 0;
const verifier = (nom, obtenu, attendu) => {
	cas++;
	if (obtenu === attendu) return;
	echecs++;
	console.error(`  ✗ ${nom}\n      attendu : ${attendu}\n      obtenu  : ${obtenu}`);
};

//  ── Ce qu'est une TÊTE : deux formes de racine, une seule rangée ─────────────
verifier(
	'la rangée des têtes est celle du sélecteur',
	PREMIER.join(','),
	'residence,bat:1,bat:2,parking,aful,espaces-verts,cheminements,locaux-techniques',
);
verifier('un regroupement racine n’est pas une tête', estRegroupement(lire('batiments')), true);
verifier('une racine ciblable en est une', estRegroupement(lire('locaux-techniques')), false);
verifier('un enfant n’est jamais un regroupement', estRegroupement(lire('bat:1')), false);
verifier(
	'« Cave », retirée de la saisie, n’est plus une tête',
	rangPremierNiveau('cave', PREMIER),
	-1,
);

//  ── L'héritage : niveau n → sa tête ─────────────────────────────────────────
verifier("l'ascenseur du bât. 1 hérite du bât. 1", codeDeTeinte('bat:1/ascenseur', lire), 'bat:1');
verifier('à trois niveaux, on remonte à la tête', codeDeTeinte('bat:1/hall/sas', lire), 'bat:1');
verifier(
	'le local eau hérite des locaux techniques',
	codeDeTeinte('locaux-techniques/local-eau', lire),
	'locaux-techniques',
);
verifier('une tête est sa propre teinte', codeDeTeinte('bat:1', lire), 'bat:1');
//  🔴 On s'arrête AVANT le regroupement : sinon les quatre bâtiments, remontant
//  tous à « Bâtiments », porteraient une seule et même couleur.
verifier('on ne remonte pas dans un regroupement', codeDeTeinte('bat:2/ascenseur', lire), 'bat:2');
verifier('la racine reste elle-même', codeDeTeinte('residence', lire), 'residence');

//  ── 🔴 LE CAS SIGNALÉ TROIS FOIS ────────────────────────────────────────────
verifier(
	'Bâtiment 1 ≠ Locaux techniques › Local eau',
	couleur('bat:1') !== couleur('locaux-techniques/local-eau'),
	true,
);
verifier(
	'ascenseur du bât. 1 ≠ local eau',
	couleur('bat:1/ascenseur') !== couleur('locaux-techniques/local-eau'),
	true,
);
verifier(
	'deux espaces du MÊME bâtiment partagent leur couleur',
	couleur('bat:1/hall'),
	couleur('bat:1/ascenseur'),
);
verifier('bât. 1 ≠ bât. 2', couleur('bat:1/ascenseur') !== couleur('bat:2/ascenseur'), true);
verifier(
	'un espace hérite de la couleur de son bâtiment',
	couleur('bat:1/hall/sas'),
	couleur('bat:1'),
);

//  🔴 CAS ZÉRO DE LA PALETTE : toutes les têtes du seed, deux à deux distinctes.
//  C'est le contrôle qui manquait — les précédents comparaient des PAIRES, et
//  neuf couleurs pour dix têtes passent toutes les paires sauf une.
const couleursTetes = PREMIER.map((c) => couleur(c));
if (new Set(couleursTetes).size !== PREMIER.length) {
	console.error(
		`  ✗ ${PREMIER.length} espaces de tête, seulement ${new Set(couleursTetes).size} couleurs distinctes`,
	);
	echecs++;
}
cas++;
//  ⚠️ La palette doit rester plus LONGUE que la rangée : c'est la marge dont
//  dispose l'administration avant que le modulo ne recommence à confondre.
if (PALETTE_PERIMETRE.length <= PREMIER.length) {
	console.error(
		`  ✗ palette de ${PALETTE_PERIMETRE.length} couleurs pour ${PREMIER.length} têtes — aucune marge`,
	);
	echecs++;
}
cas++;
if (new Set(PALETTE_PERIMETRE).size !== PALETTE_PERIMETRE.length) {
	console.error('  ✗ la palette contient deux fois la même couleur');
	echecs++;
}
cas++;
//  ⚠️ Au-delà de la palette, la collision est inévitable. Le contrôle le
//  CONSTATE plutôt que de laisser croire à une garantie qui n'existe pas.
verifier(
	'au-delà de la palette, le rang reprend la première',
	teinteDuCode('x', PALETTE_PERIMETRE.length),
	teinteDuCode('x', 0),
);

//  ── Le repli : le CODE DE TÊTE, jamais un écran monochrome ──────────────────
//
//  🔴 La version du 13/09 rendait le gris de la copropriété dès que le rang était
//  inconnu. En production, l'arbre ne répondait pas sur cet écran : le rang était
//  inconnu POUR TOUT LE MONDE, et la page a perdu toutes ses couleurs d'un coup.
//  Signalé aussitôt — « les pastilles n'ont plus de couleur par bâtiment ».
verifier(
	'rang inconnu → une couleur, pas le gris',
	teinteDuCode('bat:1', -1) !== TEINTE_COPROPRIETE,
	true,
);
verifier(
	"sans arbre, l'ascenseur garde la couleur de son bâtiment",
	teinteDuCode('bât. 1/ascenseur', -1),
	teinteDuCode('bât. 1', -1),
);
verifier(
	'sans arbre, deux branches restent distinctes',
	teinteDuCode('bât. 1/ascenseur', -1) !== teinteDuCode('locaux-techniques/local-eau', -1),
	true,
);
//  🔴 CAS ZÉRO : arbre non chargé. On rend le code de tête, donc le repli — et
//  jamais une pastille sans couleur, qui se lirait « aucun périmètre ».
verifier(
	'arbre vide → le code de tête',
	codeDeTeinte('bât. 1/ascenseur', () => undefined),
	'bât. 1',
);
verifier(
	'arbre vide, code plat → lui-même',
	codeDeTeinte('bat:1', () => undefined),
	'bat:1',
);
verifier('arbre vide → aucune tête', premierNiveauDe(['a', 'b'], () => undefined).length, 0);
//  Le gris ne reste que pour ce qui n'a AUCUN code de tête.
verifier('code vide → couleur de la copropriété', teinteDuCode('', -1), TEINTE_COPROPRIETE);
//  ⚠️ Le gris du repli n'est PAS dans la palette : un espace de tête ne peut pas
//  le porter, donc « non rattaché » ne peut pas se lire « rattaché à celui-là ».
if (PALETTE_PERIMETRE.includes(TEINTE_COPROPRIETE)) {
	console.error('  ✗ la couleur de repli appartient à la palette — elle serait ambiguë');
	echecs++;
}
cas++;

//  ── Robustesse ──────────────────────────────────────────────────────────────
verifier('cycle borné', codeDeTeinte('boucleA', lire), 'boucleA');
verifier(
	'rang insensible à la casse',
	rangPremierNiveau('BAT:1', PREMIER),
	rangPremierNiveau('bat:1', PREMIER),
);
//  Un arbre SANS regroupement — plusieurs têtes côte à côte — reste lisible.
const PLAT = { a: n('a', null), b: n('b', null) };
verifier(
	'arbre plat : les racines SONT les têtes',
	premierNiveauDe(['a', 'b'], (c) => PLAT[c]).join(','),
	'a,b',
);
verifier('teinte stable', teinteDuCode('x', 0), teinteDuCode('x', 0));
if (!/^#[0-9a-f]{6}$/.test(teinteDuCode('x', 0))) {
	console.error('  ✗ la teinte n’est pas une couleur hexadécimale');
	echecs++;
}
cas++;

if (echecs) {
	console.error(`\n✗ Teinte de périmètre : ${echecs} cas en échec sur ${cas}.\n`);
	process.exit(1);
}
console.log(
	`✓ Teinte de périmètre : ${cas} cas — ${PREMIER.length} têtes, ${PREMIER.length} couleurs distinctes, sur la forme d'arbre du seed.`,
);
