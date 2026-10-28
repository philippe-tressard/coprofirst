#!/usr/bin/env node
/**
 * Garde-fou : un objet porteur de « Saisi pour » affiche son PROPRIÉTAIRE.
 *
 * ## 🔴 Le défaut, signalé deux fois (15/09 puis 21/09/2026, #1104)
 *
 * Un ticket, une actualité ou un événement peut être ouvert **au nom d'un
 * tiers** : le conseil syndical enregistre ce qu'un résident a signalé par
 * téléphone. L'**auteur** est alors celui qui a tapé, et le **propriétaire**
 * celui que ça concerne. L'arbitrage du 12/09/2026 est sans ambiguïté :
 *
 * > « pour un ticket dont le "Saisi pour" possède un résident inscrit ou une
 * >   personne extérieure, ce dernier se substitue à l'auteur »
 *
 * Le 15/09, `nomCopie` a été écrite pour la case « Envoyer une copie à … » —
 * et les **cartes de liste** sont restées sur `auteur_nom` brut. Le 21/09, la
 * carte de TK-417640 affichait donc « Paul DELMAS », celui qui a tapé,
 * pour une affaire saisie pour quelqu'un d'autre. Le même composant employait
 * les deux : le bon nom pour la copie, le mauvais pour ce qui s'affiche.
 *
 * ⚠️ Et la FAQ servie aux résidents promettait l'inverse de ce que l'écran
 * faisait : *« c'est votre nom qui s'affiche sur la fiche »*.
 *
 * ## Ce qui est vérifié
 *
 * Aucun `<objet>.auteur_nom` dans un écran, **quand `<objet>` est d'un type
 * porteur de « Saisi pour »**. Le nom affiché passe par `nomProprietaire`
 * (`#lib/saisi-pour`), le nom de la copie par `nomCopie` — deux questions, un
 * seul module.
 *
 * 🔴 **La liste des types porteurs n'est pas écrite ici** : elle se lit dans
 * `src/lib/api/types.ts`, où ce sont les interfaces qui `extends
 * PorteSaisiPourLu`. Une liste recopiée diverge au premier type ajouté — et
 * c'est précisément le type ajouté qui n'aurait aucun contrôle.
 *
 * ## Deux listes déclarées, et elles ne font PAS la même chose
 *
 * - `PORTEURS_NON_TYPES` **étend** le contrôle à des écrans que le type ne
 *   trahit pas (`export let ev: any`). Ce n'est pas un passe-droit, c'est
 *   l'inverse.
 * - `EXCEPTIONS` **autorise** `auteur_nom`, là où c'est bien l'auteur qu'on
 *   nomme, et le dit. Chacune échoue si elle cesse de servir : une exception
 *   qui ne sert plus est un oubli qui ressemble à une décision.
 *
 * ⚠️ Une exception porte sur une **ligne**, jamais sur un fichier entier. La
 * fiche `tickets/[id]` (rendue par la carte depuis le 15/10/2026) l'a prouvé : il contient à la fois la seule phrase du
 * site qui nomme légitimement l'auteur (« Saisi par … pour … ») et, soixante
 * lignes plus bas, une case de copie qui affichait le mauvais nom. Exempter le
 * fichier aurait couvert la seconde en autorisant la première.
 *
 * Usage : npm run lint:nom-proprietaire  ·  --selftest pour exercer le contrôle
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');
const TYPES = join(SOURCE, 'lib', 'api', 'types.ts');

/**
 * Les écrans qui rendent un porteur **sans que leur type le dise**.
 *
 * ⚠️ Cette liste ÉTEND le contrôle, elle n'exempte rien. `CarteEvenement` et
 * `HistoriqueEvenement` y figuraient ; ils sont partis le 23/09/2026 avec
 * l'événement, devenu une affaire (#1092). Le contrôle échoue si un fichier de
 * la liste n'existe plus, pour qu'on l'en retire.
 */
//  La fiche d'un ticket (`let ticket: any`) y figurait ; elle est partie le
//  15/10/2026 — le lien d'une affaire rend sa carte, typée.
const PORTEURS_NON_TYPES = [];

/**
 * Où `auteur_nom` est bien ce qu'il faut dire — chacune avec sa raison.
 *
 * ⚠️ Une exception qui cesse de servir fait ÉCHOUER le contrôle : sans cela
 * elle survivrait à son objet et couvrirait un défaut réintroduit au même
 * endroit.
 */
const EXCEPTIONS = [
	{
		fichier: 'lib/components/CorpsCarteTicket.svelte',
		//  « 👤 Saisi par <auteur> pour <propriétaire> » — la phrase NOMME les
		//  deux rôles, et c'est le seul endroit du site qui les distingue à
		//  l'écran. Y substituer le propriétaire dirait « saisi par lui-même ».
		//  Elle vivait sur la fiche du lien direct, que la carte remplace (15/10/2026).
		ligneContient: 'Saisi par',
		raison: 'la phrase « Saisi par … pour … » nomme explicitement les deux rôles',
	},
];

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

/**
 * Les types porteurs, LUS dans `types.ts` — jamais recopiés ici.
 *
 * Le marqueur est l'héritage de `PorteSaisiPourLu`, qui existe précisément
 * pour que la notion ne soit écrite qu'une fois (types.ts, 15/09/2026).
 */
export function typesPorteurs(sourceTypes) {
	const noms = [];
	const re = /export\s+interface\s+([A-Za-z_$][\w$]*)\s+extends\s+([^{]+)\{/g;
	let m;
	while ((m = re.exec(sourceTypes))) {
		if (/\bPorteSaisiPourLu\b/.test(m[2])) noms.push(m[1]);
	}
	return noms;
}

/**
 * Les identifiants d'un fichier qui portent l'un de ces types.
 *
 * Trois formes, et la troisième compte autant que les deux autres : une liste
 * typée parcourue par `{#each}` donne à son alias le type de ses éléments, et
 * c'est sous cet alias que la carte s'écrit.
 */
export function identifiantsPorteurs(source, types) {
	if (!types.length) return [];
	const alternative = types.join('|');
	const trouves = new Set();

	//  1. `let x: Ticket`, `export let pub: Publication`, `(t: Ticket) => …`
	const declare = new RegExp(`\\b([A-Za-z_$][\\w$]*)\\s*:\\s*(?:${alternative})\\b`, 'g');
	//  2. `… as Ticket[]`, `= x as Publication`
	const transtype = new RegExp(
		`\\b([A-Za-z_$][\\w$]*)\\s*=[^;\\n]*\\bas\\s+(?:${alternative})\\b`,
		'g',
	);
	for (const re of [declare, transtype]) {
		let m;
		while ((m = re.exec(source))) trouves.add(m[1]);
	}

	//  3. `{#each tickets as ticket}` — l'alias hérite du type de la liste.
	//     Répété tant que de nouveaux alias apparaissent : une liste dérivée
	//     d'une liste typée (`{#each filtres as t}`) en est encore une.
	let ajout = true;
	while (ajout) {
		ajout = false;
		const listes = [...trouves].map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
		if (!listes) break;
		const each = new RegExp(`\\{#each\\s+(?:${listes})\\b[^}]*?\\bas\\s+([A-Za-z_$][\\w$]*)`, 'g');
		let m;
		while ((m = each.exec(source))) {
			if (!trouves.has(m[1])) {
				trouves.add(m[1]);
				ajout = true;
			}
		}
	}
	return [...trouves];
}

/** Les occurrences fautives d'un fichier : `<porteur>.auteur_nom`. */
export function occurrencesFautives(source, identifiants, toutIdentifiant = false) {
	const propre = sansCommentaires(source);
	const fautes = [];
	const lignes = propre.split('\n');
	const motif = toutIdentifiant
		? /\b([A-Za-z_$][\w$]*)(?:\?)?\.auteur_nom\b/g
		: new RegExp(
				`\\b(${identifiants.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})(?:\\?)?\\.auteur_nom\\b`,
				'g',
			);
	if (!toutIdentifiant && !identifiants.length) return fautes;
	lignes.forEach((ligne, i) => {
		motif.lastIndex = 0;
		let m;
		while ((m = motif.exec(ligne))) fautes.push({ ligne: i + 1, objet: m[1], texte: ligne });
	});
	return fautes;
}

function selftest() {
	const cas = [];
	const verifier = (titre, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		cas.push({ titre, ok, obtenu, attendu });
	};

	//  Les types se LISENT, et seul l'héritage du marqueur compte.
	verifier(
		'types porteurs lus dans types.ts',
		typesPorteurs(
			'export interface Ticket extends PorteSaisiPourLu {\n}\n' +
				'export interface Document {\n}\n' +
				'export interface Publication extends PorteSaisiPourLu {\n}\n',
		),
		['Ticket', 'Publication'],
	);
	verifier(
		'aucun type porteur si le marqueur disparaît',
		typesPorteurs('export interface X {}'),
		[],
	);

	//  Le cas fautif du 21/09 — celui qui a produit #1104.
	verifier(
		'la carte qui affiche auteur_nom brut est refusée',
		occurrencesFautives(
			'export let ticket: Ticket;\n{#if ticket.auteur_nom}<span>{ticket.auteur_nom}</span>{/if}',
			identifiantsPorteurs('export let ticket: Ticket;', ['Ticket', 'Publication']),
		).map((f) => f.objet),
		['ticket', 'ticket'],
	);
	//  Et le correctif passe.
	verifier(
		'nomProprietaire passe',
		occurrencesFautives(
			'export let ticket: Ticket;\n{@const n = nomProprietaire(ticket)}',
			identifiantsPorteurs('export let ticket: Ticket;', ['Ticket', 'Publication']),
		),
		[],
	);
	//  Un objet NON porteur garde son auteur — sinon le contrôle crie sur du
	//  légitime, et un contrôle qui crie sur du légitime finit désarmé.
	verifier(
		'un objet non porteur est ignoré',
		occurrencesFautives(
			'export let annonce: AnnonceHall;\n{annonce.auteur_nom}',
			identifiantsPorteurs('export let annonce: AnnonceHall;', ['Ticket', 'Publication']),
		),
		[],
	);
	//  L'alias d'un `{#each}` sur une liste typée est lui aussi un porteur.
	verifier(
		'alias de {#each} sur une liste typée',
		occurrencesFautives(
			'let tickets: Ticket[] = [];\n{#each tickets as t (t.id)}{t.auteur_nom}{/each}',
			identifiantsPorteurs('let tickets: Ticket[] = [];\n{#each tickets as t (t.id)}', [
				'Ticket',
				'Publication',
			]),
		).map((f) => f.objet),
		['t'],
	);
	//  Un commentaire qui CITE la règle ne la viole pas (leçon du 20/08/2026).
	verifier(
		'un commentaire citant auteur_nom ne compte pas',
		occurrencesFautives(
			'export let ticket: Ticket;\n<!--  ne pas écrire ticket.auteur_nom ici -->',
			identifiantsPorteurs('export let ticket: Ticket;', ['Ticket', 'Publication']),
		),
		[],
	);
	//  🔴 L'exception porte sur la LIGNE : dans un même fichier, la phrase
	//  « Saisi par … » passe et la case de copie, soixante lignes plus bas, non.
	{
		const src =
			'export let ticket: Ticket;\n' +
			"Saisi par <strong>{ticket.auteur_nom ?? 'inconnu'}</strong> pour\n" +
			"auteurNom={ticket?.auteur_nom ?? ''}\n";
		const ids = identifiantsPorteurs(src, ['Ticket']);
		const restantes = occurrencesFautives(src, ids).filter((f) => !f.texte.includes('Saisi par'));
		verifier(
			'l’exception couvre sa ligne, pas le fichier',
			restantes.map((f) => f.ligne),
			[3],
		);
	}

	//  Un écran non typé est contrôlé sur TOUT identifiant.
	verifier(
		'porteur non typé : tout identifiant est contrôlé',
		occurrencesFautives('export let ev: any;\n{ev.auteur_nom}', [], true).map((f) => f.objet),
		['ev'],
	);

	const echecs = cas.filter((c) => !c.ok);
	for (const c of cas) console.log(`${c.ok ? '  ✓' : '  ✗'} ${c.titre}`);
	if (echecs.length) {
		for (const c of echecs) {
			console.error(`\n✗ ${c.titre}\n  attendu : ${JSON.stringify(c.attendu)}`);
			console.error(`  obtenu  : ${JSON.stringify(c.obtenu)}`);
		}
		process.exit(1);
	}
	console.log(`\n✓ selftest : ${cas.length} cas, tous vérifiés.`);
	process.exit(0);
}

if (process.argv.includes('--selftest')) selftest();

const types = typesPorteurs(readFileSync(TYPES, 'utf8'));

//  🔴 Cas zéro : un relevé vide ne se distingue pas d'une lecture ratée. Le
//  témoin est le nombre de types porteurs — s'il tombe à zéro, c'est le
//  marqueur qui a bougé, pas le dépôt qui s'est assaini.
if (!types.length) {
	console.error(
		'\n✗ Cas zéro : aucune interface n’hérite de `PorteSaisiPourLu` dans\n' +
			`  ${relative(RACINE, TYPES)}. Soit le marqueur a été renommé, soit la notion\n` +
			'  a disparu — ne pas lire ceci comme un succès.\n',
	);
	process.exit(1);
}

const fautifs = [];
const exceptionsVues = new Set();
const porteursNonTypesVus = new Set();
let controles = 0;

for (const chemin of fichiers(SOURCE)) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	if (rel === 'lib/api/types.ts' || rel === 'lib/saisi-pour.ts') continue;

	const source = readFileSync(chemin, 'utf8');
	const nonType = PORTEURS_NON_TYPES.includes(rel);
	if (nonType) porteursNonTypesVus.add(rel);

	const identifiants = nonType ? [] : identifiantsPorteurs(source, types);
	if (!nonType && !identifiants.length) continue;
	controles++;

	const toutes = occurrencesFautives(source, identifiants, nonType);
	if (!toutes.length) continue;

	//  Une exception couvre les LIGNES qui portent son fragment, et elles
	//  seules — le reste du fichier reste contrôlé.
	const exceptions = EXCEPTIONS.filter((e) => e.fichier === rel);
	const fautes = toutes.filter((f) => {
		const couverte = exceptions.find((e) => f.texte.includes(e.ligneContient));
		if (couverte) exceptionsVues.add(`${rel}::${couverte.ligneContient}`);
		return !couverte;
	});
	if (fautes.length) fautifs.push({ rel, fautes });
}

const exceptionsMortes = EXCEPTIONS.filter(
	(e) => !exceptionsVues.has(`${e.fichier}::${e.ligneContient}`),
);
const porteursDisparus = PORTEURS_NON_TYPES.filter((f) => !porteursNonTypesVus.has(f));

if (fautifs.length) {
	console.error('\n✗ Le nom AFFICHÉ est celui de l’auteur, pas du propriétaire :\n');
	for (const f of fautifs) {
		for (const o of f.fautes) console.error(`   ${f.rel}:${o.ligne}  →  ${o.objet}.auteur_nom`);
	}
	console.error(
		'\n  🔴 Un objet « Saisi pour » appartient à celui pour QUI il a été ouvert,' +
			'\n  pas à celui qui a tapé (arbitrage du 12/09/2026). C’est le défaut #1104 :' +
			'\n  la carte annonçait le rédacteur, et la FAQ promettait l’inverse.' +
			'\n\n  Employer `nomProprietaire(objet)` pour ce qui s’AFFICHE, et `nomCopie()`' +
			'\n  pour ce que la case « Envoyer une copie à … » annonce — les deux dans' +
			'\n  `#lib/saisi-pour`, jamais réécrites dans un écran.\n',
	);
	process.exit(1);
}

if (exceptionsMortes.length) {
	console.error('\n✗ Exception(s) déclarée(s) qui ne servent plus :\n');
	for (const e of exceptionsMortes)
		console.error(`   ${e.fichier} — ligne portant « ${e.ligneContient} » : ${e.raison}`);
	console.error(
		'\n  Une exception qui survit à son objet couvre un défaut réintroduit au' +
			'\n  même endroit. La retirer d’`EXCEPTIONS`.\n',
	);
	process.exit(1);
}

if (porteursDisparus.length) {
	console.error('\n✗ Porteur(s) non typé(s) déclaré(s) et introuvable(s) :\n');
	for (const f of porteursDisparus) console.error(`   ${f}`);
	console.error(
		'\n  Le fichier a été supprimé ou renommé : la ligne de `PORTEURS_NON_TYPES`' +
			'\n  n’étend plus rien et doit partir (l’événement devient une propriété, #1094).\n',
	);
	process.exit(1);
}

console.log(
	`✓ Propriétaire : ${controles} écran(s) rendent un objet « Saisi pour » ` +
		`(${types.join(', ')}), tous affichent le propriétaire ` +
		`— ${EXCEPTIONS.length} exception(s) déclarée(s), toutes encore utiles.`,
);
