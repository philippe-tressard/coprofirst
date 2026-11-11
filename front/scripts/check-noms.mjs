#!/usr/bin/env node
/**
 * Garde-fou : « Prénom NOM » ne se COMPOSE pas dans le front, et les personnes
 * s'y CLASSENT d'une seule façon.
 *
 * ## Le nom affiché est SERVI (#2633, 11/11/2026)
 *
 * La règle « le nom passe en capitales, le prénom garde sa casse » (arbitrée à
 * l'écran le 31/08/2026) était écrite deux fois — `api/app/utils/noms.py` et un
 * jumeau `nomAffiche` dans `front/src/lib/noms.ts`, que ce contrôle exécutait
 * contre les cas du test Python. L'app iOS aurait dû en écrire une troisième.
 * Le serveur la sert désormais (`nom_affiche`, `schemas_nom_servi.NomServi`) et
 * le front LIT ; une SAISIE est nommée par le serveur aussi (`#lib/apercu-nom`).
 * Le jumeau est retiré, et `lint:regles-partagees` refuse qu'il revienne.
 *
 * Ce contrôle garde les deux autres moitiés de la notion :
 *   1. aucun écran ne recompose « Prénom NOM » à la main ;
 *   2. le CLASSEMENT des personnes passe par `comparerParNom`.
 *
 * Usage : npm run lint:noms
 */
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, relative, join, sep } from 'node:path';

const ICI = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(ICI, '..', 'src', 'lib', 'noms.ts');

const RACINE_SRC = resolve(ICI, '..', 'src');
const SAUT = String.fromCharCode(10);

/** Tous les .svelte et .ts de `src/`. */
function fichiersSources(dossier) {
	const out = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) out.push(...fichiersSources(chemin));
		else if (/\.(svelte|ts)$/.test(entree)) out.push(chemin);
	}
	return out;
}

function echouer(message) {
	console.error(`\n✗ ${message}\n`);
	process.exit(1);
}

//  Cas zéro : la source du CLASSEMENT doit exister, sinon rien n'est mesuré.
if (!existsSync(SOURCE)) {
	echouer(`Cas zéro : ${SOURCE} est introuvable — contrôle inopérant.`);
}

const echecs = [];

//  ── Et le CLASSEMENT, qui est l'autre moitié de la notion ──────────────────
//
//  🔴 Signalé à l'écran le 15/09/2026 : « le classement des badges &
//  télécommandes par Nom doit se faire sur le nom et pas le prénom ». La table
//  triait sur `porteur_nom`, qui vaut « Alain FAURE » — donc sur le prénom. Et
//  `FormulaireTicket` comparait littéralement le prénom suivi du nom.
//
//  ⚠️ La règle juste existait déjà, écrite TROIS fois (annuaire, administration,
//  espace CS). Elle vit maintenant dans `comparerParNom`, et ce contrôle exige
//  qu'aucun écran ne la recompose : une quatrième copie reviendrait au premier
//  tableau ajouté.
//
//  La cible est reconnue à sa FORME — une comparaison de `.nom` par
//  `localeCompare` —, pas au mot « nom » : `batiment_nom`, `prestataire_nom` et
//  les autres libellés sont des chaînes, pas des personnes, et crier dessus
//  désarmerait le contrôle (la leçon de C16 et de `check-stack`).
const COMPARAISON_NOM =
	/\.nom\s*\?\?\s*''\)\s*\.localeCompare|\$\{[a-z.]*prenom\}[^`]*\$\{[a-z.]*nom\}`\s*\.localeCompare/;
const recomposent = [];
for (const chemin of fichiersSources(RACINE_SRC)) {
	const rel = relative(RACINE_SRC, chemin).split(sep).join('/');
	if (rel === 'lib/noms.ts') continue; // la source a le droit : c'est elle la règle
	const source = readFileSync(chemin, 'utf8');
	for (const ligne of source.split(SAUT)) {
		if (COMPARAISON_NOM.test(ligne)) recomposent.push(`   ${rel} : ${ligne.trim().slice(0, 100)}`);
	}
}
//  ── Et l'AFFICHAGE recomposé dans un écran ─────────────────────────────────
//
//  🔴 Signalé à l'écran le 17/10/2026 : le Qui du point CS / Syndic rendait
//  les noms tels que tapés (« ForT »). `nomPresent` les joignait par
//  `[p.prenom, p.nom].filter(Boolean).join(' ')` — une forme que rien ne
//  regardait : ce contrôle-ci ne vérifiait que la concordance des DEUX
//  implémentations et le classement, pas qu'on s'en serve.
//
//  Trois formes, toutes rencontrées : le gabarit Svelte `{x.prenom} {x.nom}`,
//  le littéral `${x.prenom} ${x.nom}`, et le tableau `[x.prenom, x.nom]`
//  aussitôt filtré ou joint — le nom passé en capitales compris
//  (`[p.prenom, (p.nom ?? '').toUpperCase()]`, que `saisi-pour.ts` portait
//  jusqu'au 11/11/2026 sans que le motif le voie, #2633). Un tableau qui ne fait
//  que rassembler des champs de recherche (`[c.prenom, c.nom, c.fonction, …]`)
//  n'est pas pris.
const COMPOSITION_NOM = new RegExp(
	[
		String.raw`\{[\w.?]*prenom[^}]*\}\s*\{[\w.?]*\bnom\b`,
		String.raw`\$\{[\w.?]*prenom[^}]*\}\s*\$\{[\w.?]*\bnom\b`,
		String.raw`\[\s*[\w.?]*prenom\s*,\s*\(?[\w.?]*\bnom\b[^\],]*\]\s*\.(filter|join)`,
	].join('|'),
);
//  Cas zéro du motif : sans lui, le contrôle passe en ne trouvant jamais rien.
for (const [texte, attendu] of [
	['<dd>{i.contact.prenom} {i.contact.nom}</dd>', true],
	['`${u.prenom} ${u.nom}`', true],
	["[p.prenom, p.nom].filter(Boolean).join(' ')", true],
	["[p.prenom, (p.nom ?? '').toUpperCase()].filter(Boolean).join(' ')", true],
	['[c.prenom, c.nom, c.fonction, c.telephone]', false],
	['{u.nom_affiche}', false],
]) {
	if (COMPOSITION_NOM.test(texte) !== attendu) {
		echouer(`Cas zéro : le motif de composition juge mal ${JSON.stringify(texte)}.`);
	}
}
const composent = [];
for (const chemin of fichiersSources(RACINE_SRC)) {
	const rel = relative(RACINE_SRC, chemin).split(sep).join('/');
	if (rel === 'lib/noms.ts') continue;
	const lignes = readFileSync(chemin, 'utf8').split(SAUT);
	lignes.forEach((ligne, i) => {
		const nue = ligne.trim();
		if (nue.startsWith('//') || nue.startsWith('*')) return; // un commentaire raconte
		if (COMPOSITION_NOM.test(ligne)) composent.push(`   ${rel}:${i + 1} : ${nue.slice(0, 100)}`);
	});
}
if (composent.length) {
	echecs.push(
		['Ces écrans composent « Prénom NOM » à la main :', ...composent].join(SAUT) +
			SAUT +
			'   Lis le champ servi `nom_affiche` (#2633) ; une personne en cours de saisie :\n' +
			'   `$nomSaisi` de #lib/apercu-nom, nommée par le serveur.',
	);
}

if (recomposent.length) {
	echecs.push(
		['Ces écrans recomposent le CLASSEMENT des personnes :', ...recomposent].join(SAUT) +
			SAUT +
			'   Emploie `comparerParNom` de #lib/noms — nom de famille, puis prénom.',
	);
}

if (echecs.length) {
	//  ⚠️ DEUX familles d'échec passent par ici — l'AFFICHAGE d'un nom et son
	//  CLASSEMENT. L'en-tête ne doit pas n'en nommer qu'une : il enverrait
	//  chercher au mauvais endroit, ce qui est le défaut d'un contrôle qui dit
	//  autre chose que ce qu'il a mesuré.
	console.error('\n✗ La règle du NOM d’une personne n’est pas tenue :\n');
	console.error(echecs.join('\n'));
	console.error(
		'\n  Le nom d’une personne est rendu par le SERVEUR (`utils/noms.nom_affiche`) :' +
			'\n  le front le lit, il ne le compose pas — l’app iOS lit le même champ (#2633).\n',
	);
	process.exit(1);
}

console.log(
	'✓ Nom d’une personne : aucun écran ne compose « Prénom NOM », ' +
		'et le classement passe par `comparerParNom`.',
);
