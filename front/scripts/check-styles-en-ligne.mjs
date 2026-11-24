#!/usr/bin/env node
/**
 *  Un style s'écrit dans une feuille, pas dans un attribut `style="…"` (#1329,
 *  28/09/2026).
 *
 *  ## Pourquoi
 *
 *  La passe de cohérence demandée le 25/09/2026 (« j'ai l'impression qu'il y a
 *  du laisser-aller ») a relevé des écrans entiers composés d'attributs
 *  `style` : quarante dans l'onglet WhatsApp, dix-sept sur la page d'un
 *  sondage. Un style en ligne échappe à tout ce qui tient la charte — il ne se
 *  réemploie pas, ne se surcharge pas au doigt (`@media`), et deux écrans qui
 *  veulent la même allure la réécrivent chacun. 524 dans le front ce jour-là,
 *  et rien pour dire qu'il n'en fallait pas un de plus.
 *
 *  ## Ce qu'il mesure
 *
 *  Les attributs `style="…"` **statiques** des `.svelte`, commentaires HTML
 *  retirés. Un style qui porte une expression (`style="width:{pct}%"`) est
 *  légitime : la valeur vient des données, aucune feuille ne peut la porter.
 *
 *  ⚠️ L'expression ne couvre QUE sa déclaration (#2946, 24/11/2026). Un attribut
 *  passait entier dès qu'il contenait une accolade : le badge d'état de WhatsApp
 *  écrivait `font-size`, `padding` et `border-radius` en dur à côté d'une
 *  expression qui choisissait ses couleurs. Les déclarations sans expression d'un
 *  attribut mixte sont comptées comme un style statique.
 *
 *  ## Un PLAFOND, et il ne fait que baisser
 *
 *  Tout convertir d'un coup changerait des centaines de rendus sans qu'on en
 *  regarde un seul. Le plafond refuse d'en AJOUTER ; il échoue aussi quand le
 *  compte passe DESSOUS — le plafond se baisse alors dans le même lot, sinon
 *  la marge regagnée serait reprise sans un mot par le suivant.
 *
 *  Lancer : node scripts/check-styles-en-ligne.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 *  Le compte autorisé, et son historique.
 *  28/09/2026 (#1329) : 495 relevés ; 474 le même jour — l'onglet WhatsApp
 *  a rendu 21 des siens en extrayant ses messages planifiés et son historique,
 *  rendu identique au pixel près (bureau et mobile). Puis 458 : la page d'un
 *  sondage, ses résultats extraits en composant et ses styles passés en
 *  classes, rendu identique (quatre états, bureau et mobile). Puis 457 : le
 *  badge « Bail actif » du formulaire de bail, passé dans sa feuille (#1329).
 *  Puis 455 : la barre de réorganisation de la FAQ, extraite en composant (#779).
 *  Puis 451 : la démarche « Nouvel arrivant » du profil, idem (#779).
 *  Puis 449 : le bail parking/cave et le QR WhatsApp, passés par
 *  `EncartAvertissement` (#1455).
 *  Puis 445 : l'annuaire de l'espace CS, extrait en deux composants (#779).
 *  Puis 438 : le lien vers les consignes de la copropriété, écrit trois fois
 *  et deux fois en `style="…"`, devenu `LienConsignes` (#779).
 *  Puis 419 : « Mes lots » — la vue locataire extraite (`LotsLocataire`), les
 *  caractéristiques d'un lot (`CaracteristiquesLot`), deux modales de
 *  suppression remplacées par `SUPPRESSION` (#779).
 *  Puis 416 : `LegalEditor` fondu dans `RichEditor` — son espaceur
 *  `style="flex:1"` part avec lui (#1539).
 *  08/10/2026 (#1571) : 394 → 206. Les combinaisons qui avaient leur classe
 *  globale y passent (`.muted`, `.text-muted-sm`, et `-md`, `-base`, `.texte-code`,
 *  `.champ-double`, l'essai d'un canal d'administration, créées pour l'occasion) ;
 *  vingt-cinq écrans reçoivent des classes locales aux déclarations identiques.
 *  ⚠️ Une classe pèse MOINS qu'un attribut : là où une règle globale plus forte
 *  visait l'élément (`.field input[type='checkbox']`, `.field textarea`), le
 *  sélecteur est qualifié pour la battre comme l'attribut la battait.
 *  Puis 76 (#1571) : tous les fichiers qui avaient de la place sous 500 lignes.
 *  Restent ceux qui la frôlent — modèles d'e-mail, import des lots, comptes,
 *  profil, tâches planifiées, renouvellements de contrats, formulaire d'affaire :
 *  les découper d'abord, une classe ajoutée les ferait déborder.
 *  08/10/2026 (#1571) : ZÉRO. Les sept derniers fichiers ont d'abord été
 *  découpés — l'historique des envois d'e-mail, la table des exécutions d'une
 *  tâche, la correction d'une ligne d'import, les gestes de rôle d'un compte,
 *  les informations du profil sont devenus des composants —, puis convertis.
 *  🔴 À zéro, ce n'est plus un suivi de dette : c'est une INTERDICTION. Un style
 *  dont la valeur vient des données (`style="width:{pct}%"`) reste permis.
 */
const PLAFOND = 0;

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

/** Les déclarations d'un attribut `style` qui ne portent aucune expression `{…}`. */
export function partieStatique(valeur) {
	let hors = '';
	let profondeur = 0;
	for (const c of valeur) {
		if (c === '{' && !profondeur++) hors += '§';
		else if (c === '}') profondeur--;
		else if (!profondeur) hors += c;
	}
	return hors
		.split(';')
		.map((d) => d.trim())
		.filter((d) => d && !d.includes('§'))
		.join(';');
}

/** Les styles en ligne STATIQUES d'une source — ou la partie statique d'un attribut mixte. */
export function stylesEnLigne(source) {
	//  Le CSS du composant n'est pas du balisage : un commentaire qui y CITE un
	//  `style="…"` (le récit d'une conversion) n'est pas un attribut.
	const sans = source.replace(/<!--[\s\S]*?-->/g, '').replace(/<style[^>]*>[\s\S]*?<\/style>/g, '');
	return [...sans.matchAll(/\bstyle="([^"]*)"/g)].map((m) => partieStatique(m[1])).filter(Boolean);
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
	};
	cas(
		'un style statique compte, un style tiré des données non',
		stylesEnLigne('<div style="margin:0">a</div><div style="width:{pct}%"></div>'),
		['margin:0'],
	);
	cas('un commentaire ne compte pas', stylesEnLigne('<!-- <p style="color:red"></p> -->'), []);
	//  🔴 #2946 : l'accolade ne couvre que sa déclaration.
	cas(
		'un attribut mixte compte par sa partie statique',
		stylesEnLigne(`<span style="font-size:var(--fs-sm);padding:.1rem;{ok ? 'color:green' : ''}">`),
		['font-size:var(--fs-sm);padding:.1rem'],
	);
	cas(
		'une expression dans une valeur reste sa déclaration',
		stylesEnLigne('<i style="left:{x}%;width:{w}px"></i>'),
		[],
	);
	cas('un attribut vide ne compte pas', stylesEnLigne('<p style="">a</p>'), []);
	//  08/10/2026 : deux commentaires CSS qui racontent la conversion (« les styles
	//  étaient EN LIGNE, `style="…"` ») étaient comptés comme des attributs.
	cas(
		'un style cité dans le CSS du composant ne compte pas',
		stylesEnLigne('<style>\n\t/*  `style="display:flex"` */\n</style>'),
		[],
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) fichiers(chemin, acc);
		else if (nom.endsWith('.svelte')) acc.push(chemin);
	}
	return acc;
}

let total = 0;
let lus = 0;
const parFichier = [];
for (const chemin of fichiers(RACINE)) {
	lus++;
	const n = stylesEnLigne(readFileSync(chemin, 'utf8')).length;
	total += n;
	if (n) parFichier.push([relative(RACINE, chemin).split(sep).join('/'), n]);
}

if (!lus) {
	console.error('\n✗ Aucun composant lu : contrôle inopérant (INCONNU).\n');
	process.exit(2);
}
if (total > PLAFOND) {
	console.error(
		`\n✗ ${total} styles en ligne statiques, plafond ${PLAFOND}. Écrire le style dans ` +
			'le `<style>` du composant ou dans `src/styles/`. Les plus chargés :',
	);
	parFichier
		.sort((a, b) => b[1] - a[1])
		.slice(0, 8)
		.forEach(([f, n]) => console.error(`   ${n}  ${f}`));
	process.exit(1);
}
if (total < PLAFOND) {
	console.error(
		`\n✗ ${total} styles en ligne statiques, sous le plafond de ${PLAFOND} : ` +
			`le baisser à ${total} dans ce lot (PLAFOND, en tête du fichier).`,
	);
	process.exit(1);
}
console.log(
	`✓ Styles en ligne : ${total}, au plafond — aucun ajouté (${parFichier.length} fichiers en portent).`,
);
