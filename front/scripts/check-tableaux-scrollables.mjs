/**
 * Garde-fou : un `<table>` doit vivre dans un conteneur qui DÉFILE.
 *
 * ## 🔴 Pourquoi (04/09/2026)
 *
 * Un tableau ne se comprime pas. `normes.css` pose même `white-space: nowrap`
 * sur ses cellules sous 767 px — ce qui est juste, une date coupée en deux est
 * illisible. Sa largeur est donc incompressible.
 *
 * Et `socle.css` porte `body { overflow-x: hidden }`. Les deux ensemble
 * produisent le pire résultat possible : le tableau **dépasse l'écran et le
 * dépassement est masqué**. Les dernières colonnes ne sont pas seulement hors du
 * cadre — elles sont inatteignables, sans barre de défilement, sans geste
 * possible. Un débordement visible se contourne ; celui-là, non.
 *
 * ⚠️ Le remède existait déjà : `.table-wrap` (`normes.css`), et `.card` porte
 * `overflow-x: auto` sous 767 px — la plupart des tableaux du site en héritent.
 * **Cinq** y échappaient : historique des demandes, fiche résidence, tâches
 * planifiées, et deux tableaux de « Mes lots ». Personne ne l'avait vu parce que
 * rien ne le signale : sur un grand écran, tout va bien.
 *
 * ## Ce que ce contrôle regarde
 *
 * Chaque `<table>` doit avoir, parmi ses ancêtres proches dans le fichier, un
 * élément portant `.card`, `.table-wrap` ou un `overflow-x` explicite.
 *
 * ⚠️ La fenêtre est bornée (`PORTEE`) : au-delà, on ne lit plus la structure du
 * tableau mais celle de la page. Un contrôle qui remonterait indéfiniment finirait
 * par trouver une `.card` quelque part et ne dirait plus rien.
 *
 * ## 🔴 Le conteneur ne doit pas se RENIER (22/10/2026)
 *
 * Ce contrôle acceptait toute `.card` sur la foi de `normes.css`. Or trois écrans
 * posaient sur leur carte une classe locale à `overflow: hidden` — Utilisateurs,
 * À traiter (trois tableaux), Modèles d'e-mail : la règle du composant, plus
 * précise, l'emportait sur celle de `.card`, et le tableau des utilisateurs était
 * rogné sur téléphone. Le contrôle disait ✓ : il lisait la classe, pas son effet.
 * Il refuse désormais un conteneur dont une classe reçoit, dans le `<style>` du
 * même fichier, `overflow` ou `overflow-x` à `hidden` ou `clip`.
 *
 * Usage : npm run lint:tableaux (`--selftest` rejoue les cas)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** Caractères remontés au-dessus d'un `<table>` pour y chercher son conteneur. */
const PORTEE = 1500;

/** Ce qui fait défiler : la classe dédiée, la carte, ou un style explicite. */
const CONTENEUR = /class="[^"]*\b(card|table-wrap|table-scroll)\b|overflow-x/;
const CONTENEURS = new RegExp(CONTENEUR.source, 'g');

/** Les classes d'un `<style>` qui coupent le débordement au lieu de le faire défiler. */
function classesQuiRognent(style) {
	const rognent = new Set();
	for (const [, selecteurs, corps] of style.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
		if (!/overflow(-x)?\s*:\s*(hidden|clip)\b/.test(corps)) continue;
		for (const [, nom] of selecteurs.matchAll(/\.([\w-]+)/g)) rognent.add(nom);
	}
	return rognent;
}

/**
 * 🔴 AUCUNE EXCEPTION, et ce n'est pas un oubli.
 *
 * Un tableau qui n'a pas besoin de défiler n'est pas gêné par un conteneur qui
 * le permet : `overflow-x: auto` ne montre une barre que s'il y a de quoi
 * défiler. Il n'y a donc pas de cas où l'enveloppe nuit — donc pas de raison
 * d'en dispenser un.
 */
const EXCEPTIONS = new Set();

function fichiersSvelte(dossier) {
	const trouves = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) trouves.push(...fichiersSvelte(chemin));
		else if (entree.endsWith('.svelte')) trouves.push(chemin);
	}
	return trouves;
}

/**
 * Les `<table>` réellement rendus — pas ceux cités dans un commentaire.
 *
 * ⚠️ Défaut du premier relevé : `ApercuDiffusion.svelte` explique dans un
 * commentaire que l'assainisseur « n'autorise ni `<table>` ni `<tr>` », et il
 * était compté comme un tableau nu. Un contrôle qui crie sur du texte finit
 * désarmé.
 */
export function tableauxNus(source) {
	//  Les retours à la ligne restent : sans eux, la ligne citée était fausse.
	const blanchir = (bloc) => bloc.replace(/[^\n]/g, ' ');
	const sansCommentaires = source
		.replace(/<!--[\s\S]*?-->/g, blanchir)
		.replace(/\/\*[\s\S]*?\*\//g, blanchir);

	const style = (sansCommentaires.match(/<style[^>]*>([\s\S]*?)<\/style>/) || [])[1] || '';
	const rognent = classesQuiRognent(style);

	const nus = [];
	for (const m of sansCommentaires.matchAll(/<table\b/g)) {
		const avant = sansCommentaires.slice(Math.max(0, m.index - PORTEE), m.index);
		//  Le conteneur le plus PROCHE : c'est lui qui décide du débordement.
		const proche = [...avant.matchAll(CONTENEURS)].pop();
		//  Toutes ses classes : le motif s'arrête à `card`, l'attribut va plus loin.
		const attribut = proche ? avant.slice(proche.index).match(/^class="([^"]*)/) : null;
		const classes = attribut ? attribut[1].split(/\s+/) : [];
		if (proche && !classes.some((c) => rognent.has(c))) continue;
		nus.push(sansCommentaires.slice(0, m.index).split('\n').length);
	}
	return nus;
}

if (process.argv.includes('--selftest')) {
	const carte = (classe, regle) =>
		`<div class="${classe}"><table></table></div><style>${regle}</style>`;
	const cas = [
		['<div class="card"><table></table></div>', 0],
		['<div class="table-wrap"><table></table></div>', 0],
		['<section><table></table></section>', 1],
		//  Le défaut du 22/10/2026 : la carte se renie par une classe locale.
		[carte('card carte-comptes', '.carte-comptes { overflow: hidden; }'), 1],
		[carte('card carte-x', '.a, .carte-x { overflow-x: clip }'), 1],
		[carte('card carte-x', '.carte-x { overflow: auto; }'), 0],
		//  Une autre classe du fichier qui rogne ne touche pas ce tableau.
		[carte('card', '.sujet { overflow: hidden; }'), 0],
		//  Le plus proche décide : une enveloppe défilante DANS une carte qui rogne.
		[
			'<div class="card r"><div class="table-wrap"><table></table></div></div>' +
				'<style>.r { overflow: hidden }</style>',
			0,
		],
	];
	let ko = 0;
	for (const [source, attendu] of cas) {
		const obtenu = tableauxNus(source).length;
		console.log(`${obtenu === attendu ? 'PASS' : 'FAIL'}  ${source.slice(0, 70)}`);
		if (obtenu !== attendu) ko = 1;
	}
	process.exit(ko);
}

const fautifs = [];
let tableauxVus = 0;

for (const chemin of fichiersSvelte(RACINE)) {
	const source = readFileSync(chemin, 'utf8');
	if (!source.includes('<table')) continue;
	const court = chemin.slice(RACINE.length + 1).replace(/\\/g, '/');
	tableauxVus += (source.match(/<table\b/g) || []).length;
	if (EXCEPTIONS.has(court)) continue;
	for (const ligne of tableauxNus(source)) {
		fautifs.push(`  ${court}:${ligne}`);
	}
}

//  Cas zéro : un scan qui ne trouve aucun tableau rendrait la même liste vide
//  qu'un site irréprochable.
if (tableauxVus < 10) {
	console.error(
		`\n✗ lint:tableaux — ${tableauxVus} tableau(x) trouvé(s) : le repérage ne ` +
			`voit presque rien, son verdict ne vaut rien.\n`,
	);
	process.exit(1);
}

if (fautifs.length) {
	console.error(
		`\n✗ lint:tableaux — ${fautifs.length} tableau(x) sans conteneur défilant :\n\n` +
			fautifs.join('\n') +
			`\n\n  Sur téléphone, ` +
			`\`white-space: nowrap\` rend leur largeur incompressible et\n` +
			`  \`body { overflow-x: hidden }\` MASQUE le dépassement : les dernières\n` +
			`  colonnes deviennent inatteignables, sans barre ni geste possible.\n\n` +
			`  Remède : envelopper dans \`<div class="table-wrap">\` — la classe existe\n` +
			`  déjà dans \`styles/normes.css\` —, et ne jamais poser \`overflow: hidden\`\n` +
			`  sur le conteneur d'un tableau : il annule le défilement de \`.card\`.\n`,
	);
	process.exit(1);
}

console.log(
	`✓ Tableaux : ${tableauxVus} rendus, tous dans un conteneur défilant ` +
		`(.card, .table-wrap ou overflow-x).`,
);
