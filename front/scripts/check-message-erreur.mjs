#!/usr/bin/env node
/**
 *  Le message d'erreur d'un appel API vient de `messageErreur`, pas d'un ternaire
 *  recopié.
 *
 *  ## Le relevé du 12/09/2026
 *
 *  `e instanceof ApiError ? e.message : 'Erreur'` est écrit **127 fois dans 41
 *  fichiers**. Quatre-vingt-deux de ces copies retombent sur le mot « Erreur ».
 *
 *  🔴 Ce n'est pas une duplication cosmétique : c'est **la même information
 *  perdue 82 fois**. `#lib/erreurs.messageErreur` sait dire :
 *
 *    401 → « Votre session a expiré — rechargez la page pour vous reconnecter. »
 *    403 → le message du serveur, ou « Vous n'avez pas accès à cette rubrique. »
 *    réseau → « Impossible de joindre le serveur — vérifiez votre connexion. »
 *
 *  Le ternaire, lui, affiche « Erreur » dès que l'erreur n'est pas une réponse
 *  HTTP — c'est-à-dire exactement quand l'utilisateur aurait besoin qu'on lui
 *  dise que sa connexion est coupée.
 *
 *  ⚠️ Et la duplication avait déjà produit sa divergence : `messageErreur`
 *  existait **en DEUX exemplaires**, dans `#lib/erreurs` et dans `#lib/comptes`,
 *  sous le même nom et avec des comportements différents. Deux écrans
 *  importaient la moins disante.
 *
 *  ## Le plafond a fait son travail : il est à ZÉRO depuis le 18/09/2026
 *
 *  Cent vingt-trois occurrences subsistaient au relevé. Les convertir d'un coup
 *  aurait touché 43 fichiers dans un seul lot, sans qu'aucun écran ne soit
 *  regardé : le genre de changement massif que ce dépôt a appris à ne pas
 *  faire. Le plafond a donc empêché la cent vingt-quatrième, et il est DESCENDU
 *  à chaque lot — 123, puis 67, 45, 14, et zéro.
 *
 *  🔴 **À zéro, ce n'est plus un suivi de dette : c'est une interdiction**, et
 *  elle n'a rien à tolérer. Le jour où une exception paraîtra nécessaire, la
 *  vraie question sera : que manque-t-il à `messageErreur` ? C'est ainsi que le
 *  dernier lot s'est terminé — les trois écrans d'authentification résistaient
 *  parce qu'un 401 y signifie « identifiants refusés » et non « session
 *  expirée ». Le remède n'a pas été de les tolérer, mais d'apprendre la
 *  distinction à `messageErreur` (`ApiError.chemin`).
 *
 *  Lancer : node scripts/check-message-erreur.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';

/**  Le plafond, à baisser à chaque conversion. Il ne remonte jamais. */
//  123 → 119 → 113 le 12/09/2026 : converties en migrant `mon-lot` puis `espace-cs`
//  vers `tenter` (#928). Le contrôle a EXIGÉ cette baisse — il échoue aussi
//  quand le compte descend sous le plafond, et c'est ce qui l'empêche de
//  devenir un plafond qu'on oublie.
//  113 → 67 les 12 et 13/09/2026 : `residence`, `sondages/[id]`, `PageCommunaute`,
//  `tickets`, `HistoriqueAnnoncesHall`, `SectionDiagnostics`,
//  `profil`, `OngletPerimetres` et `OngletAcces`. Les copies qui portaient un
//  repli CONTEXTUEL n'en perdent aucun : `tenter` a reçu un troisième
//  paramètre plutôt que de les niveler sur la phrase générique.
const PLAFOND = 0;

/**  Le ternaire recopié : `<e> instanceof ApiError ? <e>.message : …`.
 *   La rétro-référence `\1` exige la MÊME variable des deux côtés — sans elle,
 *   un test légitime sur deux erreurs distinctes serait compté à tort. */
const TERNAIRE = /(\w+)\s+instanceof\s+ApiError\s*\?\s*\1\.message/g;

/**  🔴 Deux autres écritures de la MÊME notion, que le ternaire ne voyait pas
 *   (#1571, 08/10/2026) — 31 copies dans 13 fichiers, et une forme du ternaire
 *   écrite sur plusieurs lignes (`FormulaireTicket`) qu'un motif sans `\s`
 *   laissait passer :
 *     `e.message ?? 'Erreur'`               — un `catch (e: any)`, qui affiche
 *                                             « Failed to fetch » à une coupure ;
 *     `e instanceof Error ? e.message : …`  — même chose, sous un autre test.
 *   Toutes disent moins que `messageErreur` : ni session expirée, ni réseau. */
//  Les noms d'une ERREUR seulement : `res.message ?? 'Vote enregistré'` est le
//  message de succès qu'une réponse du serveur porte (`PageCommunaute`).
//  `e?.message ??` et `(e as …).message ??` sont la même lecture (08/10/2026) :
//  treize copies à chaînage optionnel et le corps d'`apiMessage` y échappaient.
//  `reason` : le rejet d'un `Promise.allSettled` (`OngletModelesEmail`).
const REPLI_LOCAL = /(?:\b(?:e|err|erreur|error|reason)\??|\))\.message\s*\?\?/g;
const TERNAIRE_ERROR = /(\w+)\s+instanceof\s+Error\s*\?\s*\1\.message/g;

/**  Les lectures de `.message` qui ne SONT PAS un message à l'utilisateur, avec
 *   leur raison. Une entrée qui ne sert plus fait échouer le contrôle. */
const EXCEPTIONS = {
	//  La télémétrie des erreurs de navigateur relève le TEXTE brut de
	//  l'exception pour le classer : rien n'est affiché à personne.
	'lib/telemetry.ts': 'relevé brut d’une exception pour la télémétrie, jamais affiché',
};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.ts')) acc.push(p);
	}
	return acc;
}

/**  La décision, PURE — combien de copies dans cette source ? */
export function compterCopies(source) {
	return [TERNAIRE, REPLI_LOCAL, TERNAIRE_ERROR].reduce(
		(n, motif) => n + (source.match(motif) ?? []).length,
		0,
	);
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = compterCopies(src);
		if (r === attendu) console.log(`PASS  ${libelle} → ${r}`);
		else {
			console.error(`FAIL  ${libelle}  attendu=${attendu} obtenu=${r}`);
			ko = 1;
		}
	};
	t('la copie type', 1, "toast('error', e instanceof ApiError ? e.message : 'Erreur');");
	t(
		'deux copies',
		2,
		'a instanceof ApiError ? a.message : 1; b instanceof ApiError ? b.message : 2;',
	);
	t('appel conforme', 0, "toast('error', messageErreur(e));");
	//  ⚠️ DEUX variables différentes : ce n'est pas la copie, c'est un test sur
	//  une autre erreur. La rétro-référence l'exclut, et c'est le faux positif
	//  que trois contrôles de ce dépôt ont déjà rencontré.
	t('variables différentes', 0, 'e instanceof ApiError ? autre.message : 0');
	//  #1571 : les trois écritures que le motif d'origine laissait passer.
	t('repli local', 1, "toast('error', e.message ?? 'Erreur');");
	//  08/10/2026 : la forme à chaînage optionnel, et le corps d'`apiMessage`
	//  (`#lib/utils`), seconde écriture de `messageErreur` qu'aucun motif ne voyait.
	t('repli local optionnel', 1, "toast('error', e?.message ?? 'Erreur');");
	t('rejet d’un allSettled', 1, "x = r.reason?.message ?? 'Chargement impossible';");
	t(
		'repli sur une erreur convertie',
		1,
		'return String((e as { message?: unknown }).message ?? repli);',
	);
	t('message de succès d’une réponse', 0, "toast('success', res.message ?? 'Vote enregistré');");
	t('ternaire sur Error', 1, "toast('error', err instanceof Error ? err.message : 'x');");
	t(
		'ternaire sur plusieurs lignes',
		1,
		'error =\n\te instanceof ApiError\n\t\t? e.message\n\t\t: "x";',
	);
	//  Le cas zéro : une source vide ne compte rien, et ne prétend rien.
	t('source vide', 0, '');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const tous = fichiers(RACINE);
let total = 0;
let lus = 0;
const parFichier = [];

const exceptionsServies = new Set();
for (const f of tous) {
	lus++;
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	//  Un commentaire qui CITE la forme refusée n'en est pas une copie.
	const n = compterCopies(neutraliserCommentaires(readFileSync(f, 'utf8')));
	if (!n) continue;
	if (rel in EXCEPTIONS) {
		exceptionsServies.add(rel);
		continue;
	}
	total += n;
	parFichier.push([rel, n]);
}

const perimees = Object.keys(EXCEPTIONS).filter((r) => !exceptionsServies.has(r));
if (perimees.length) {
	console.error(
		`\n✗ Exception(s) qui ne servent plus : ${perimees.join(', ')} — la retirer d'EXCEPTIONS.\n`,
	);
	process.exit(1);
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : si aucun fichier n'a été lu, le contrôle
//  n'a pas mesuré — il ne rend pas OK. Un `0` sur zéro fichier lu serait le
//  meilleur résultat possible, et le plus faux.
if (lus === 0) {
	console.error('\n✗ INCONNU : aucun fichier lu sous `src/`. Le contrôle ne mesure rien.\n');
	process.exit(2);
}

if (total > PLAFOND) {
	console.error(
		`\n✗ ${total} copies du ternaire, plafond ${PLAFOND} — ${total - PLAFOND} de trop :\n`,
	);
	for (const [f, n] of parFichier.sort((a, b) => b[1] - a[1]).slice(0, 10)) {
		console.error(`  ${n}x  ${f}`);
	}
	console.error(
		'\n  `messageErreur(e)` de `#lib/erreurs` dit ce que le ternaire tait : une\n' +
			'  session expirée, un serveur injoignable. Il accepte un repli contextuel\n' +
			'  en second argument : `messageErreur(e, "Impossible de charger vos lots")`.\n' +
			'  → convertir, ou baisser le plafond si une conversion a eu lieu ailleurs.\n',
	);
	process.exit(1);
}

if (total < PLAFOND) {
	console.error(
		`\n✗ ${total} copies restantes, mais le plafond est à ${PLAFOND}.\n\n` +
			`  Des conversions ont eu lieu : baisser PLAFOND à ${total}.\n` +
			"  Un plafond qu'on ne baisse pas est un plafond qu'on oublie — et il\n" +
			'  laisserait revenir en silence ce qui vient d’être retiré.\n',
	);
	process.exit(1);
}

console.log(
	total === 0
		? `✓ Message d'erreur : aucune copie du ternaire (${lus} fichier(s) lus) — ` +
				`le message d'erreur vient de \`messageErreur\`, partout.`
		: `✓ Message d'erreur : ${total} copie(s) du ternaire, plafond ${PLAFOND} tenu ` +
				`(${lus} fichier(s) lus) — dette suivie, elle ne grandit plus.`,
);
