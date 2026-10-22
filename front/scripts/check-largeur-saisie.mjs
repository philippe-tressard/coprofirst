/**
 * Garde-fou : **aucune largeur de saisie écrite dans un écran**.
 *
 * ## Le fait, signalé à l'écran le 30/08/2026
 *
 * > « Sur admin / paramétrage le texte ne prend pas la bonne largeur »
 *
 * La carte « Paramètres généraux » occupe toute la page, ses champs s'arrêtent à
 * 600 px, et les phrases d'aide se replient sur quatre lignes en laissant la
 * moitié droite vide. La cause tient en un attribut :
 *
 *     <div class="form-grid" style="max-width:600px">
 *
 * ## Pourquoi ce n'était pas une faute isolée
 *
 * `--largeur-saisie` a été **généralisée à 100 % le 18/08/2026**, après constat à
 * l'écran sur `/tickets` : *« le cap à 720 px était plus étroit que tout le reste
 * de la page »*. `normes.css` porte la décision, et son commentaire cite la prop
 * `marge` d'`EntetePage` (#372) — six écrans, six valeurs, centralisées mais
 * jamais réduites.
 *
 * 🔴 **Six écrans n'ont pas suivi cette généralisation**, parce qu'ils n'employaient
 * pas la classe : elle ne pouvait pas les atteindre.
 *
 *     OngletFonctionnement 600px  (form-grid) ·  600px  (form-actions)
 *     EnteteSyndic    580px
 *     espace-cs       460px
 *     residence       700px
 *     profil          580px
 *
 * Aucune n'est une décision : ce sont des valeurs posées à la main, chacune une
 * fois, et jamais rouvertes. C'est **exactement** le défaut que le commentaire de
 * `normes.css` raconte — reproduit un cran plus bas, sur le conteneur au lieu de
 * la prop.
 *
 * ⚠️ Et il l'a été **après** que la règle fut écrite. `ux-patterns` §9 dit en
 * toutes lettres : *« Ne jamais écrire une largeur dans une page. »* Elle était
 * là, elle était juste, et le défaut a été trouvé par l'utilisateur, à l'écran, en
 * production (`standards/05` : une règle sans garde-fou tient tant que celui qui
 * écrit s'en souvient).
 *
 * ## Ce que ce contrôle cherche — volontairement étroit
 *
 * Un `max-width` **en style en ligne** sur un conteneur de SAISIE :
 * `.form-grid`, `.form-actions`, `.largeur-saisie`, ou un bloc qui enveloppe un
 * `<form>`. Rien d'autre.
 *
 * Une largeur sur du **contenu** reste permise et n'est pas le sujet : tronquer
 * une cellule de tableau à 180 px, borner une pastille d'avertissement à 360 px.
 * Ce sont des décisions locales sur un objet local, pas la largeur du formulaire.
 *
 * Test : node front/scripts/check-largeur-saisie.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Emplois légitimes, avec leur raison. Vide, et c'est l'état voulu.
 *
 * Une entrée ajoutée ici doit dire POURQUOI cet écran ne peut pas suivre la
 * largeur commune — et le contrôle la refuse dès qu'elle cesse de servir.
 */
const EXCEPTIONS = {};

/** Nombre minimal de conteneurs de saisie attendus — cas zéro. */
const CONTENEURS_MINIMAUX = 15;

/**
 * Les balises ouvrantes portant un `max-width` en ligne ET une marque de saisie.
 *
 * ⚠️ Le `<form>` est cherché **après** la balise, dans une fenêtre courte : c'est
 * ce qui distingue « un bloc qui contient un formulaire » d'un bloc quelconque,
 * sans réclamer un analyseur d'arbre pour une règle qui tient en une ligne.
 */
export function largeursDeSaisie(source) {
	const trouves = [];
	const MARQUES = /\b(form-grid|form-actions|largeur-saisie)\b/;
	for (const m of source.matchAll(
		/<(?:div|section|form)\b[^<>]*style="[^"]*max-width[^"]*"[^<>]*>/g,
	)) {
		const balise = m[0];
		const suite = source.slice(m.index + balise.length, m.index + balise.length + 400);
		if (MARQUES.test(balise) || /<form\b/.test(suite)) {
			const largeur = balise.match(/max-width\s*:\s*([^;"']+)/)?.[1]?.trim() ?? '?';
			trouves.push({ largeur, extrait: balise.slice(0, 90) });
		}
	}
	return trouves;
}

/** Combien de conteneurs de saisie ce fichier porte — pour le cas zéro. */
function conteneursDeSaisie(source) {
	return (source.match(/\b(form-grid|form-actions|largeur-saisie)\b/g) ?? []).length;
}

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

function selftest() {
	let ko = 0;
	const t = (libelle, source, attendu) => {
		const n = largeursDeSaisie(source).length;
		if (n === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — ${n} trouvé(s), ${attendu} attendu(s)`);
			ko = 1;
		}
	};

	//  🔴 Le cas du 30/08/2026, celui que l'utilisateur a vu à l'écran.
	t('form-grid borné en ligne', '<div class="form-grid" style="max-width:600px">', 1);
	t('form-actions borné', '<div class="form-actions" style="max-width:600px">', 1);
	t('bloc nu enveloppant un form', '<div style="max-width:700px">\n<form on:submit>', 1);
	t('largeur-saisie re-bornée', '<div class="largeur-saisie" style="max-width:480px">', 1);

	//  ⚠️ Ce qui n'est PAS une largeur de saisie doit passer — sinon le contrôle
	//  produit des faux positifs, et un contrôle qu'on apprend à ignorer ne garde
	//  plus rien (`standards/04`).
	t('cellule de tableau tronquée', '<div style="max-width:180px;overflow:hidden">', 0);
	t('pastille d’avertissement', '<div style="padding:.75rem;max-width:360px">', 0);
	t('form-grid sans largeur', '<div class="form-grid largeur-saisie">', 0);
	t(
		'form loin derrière un bloc borné',
		'<div style="max-width:900px">' + 'x'.repeat(500) + '<form>',
		0,
	);

	console.log(
		ko === 0
			? '\n✓ Autotest : les conteneurs de saisie bornés sont vus, les largeurs de contenu passent.'
			: '\n✗ Autotest en échec',
	);
	return ko;
}

function controler() {
	const tous = fichiers(RACINE);
	if (tous.length === 0) {
		console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
		return 1;
	}

	const fautifs = [];
	const exceptionsUtiles = new Set();
	let conteneurs = 0;

	for (const f of tous) {
		const rel = relative(RACINE, f).split(sep).join('/');
		const source = sansCommentaires(readFileSync(f, 'utf8'));
		conteneurs += conteneursDeSaisie(source);
		const trouves = largeursDeSaisie(source);
		if (trouves.length === 0) continue;
		if (rel in EXCEPTIONS) {
			exceptionsUtiles.add(rel);
			continue;
		}
		fautifs.push({ fichier: rel, trouves });
	}

	//  Le contrôle serait vert sur un site qui n'aurait plus un seul formulaire :
	//  il ne mesurerait alors plus rien, et ne le dirait pas.
	if (conteneurs < CONTENEURS_MINIMAUX) {
		console.error(
			`✗ Cas zéro : ${conteneurs} conteneur(s) de saisie recensé(s), ${CONTENEURS_MINIMAUX} attendus ` +
				'au minimum. Le repérage ne mord plus — ne pas lire ceci comme un succès.',
		);
		return 1;
	}

	if (fautifs.length > 0) {
		console.error('✗ Largeur de saisie écrite dans un écran :');
		for (const { fichier, trouves } of fautifs) {
			for (const t of trouves)
				console.error(`    ${fichier} — max-width: ${t.largeur}\n        ${t.extrait}`);
		}
		console.error(
			'\n  La largeur appartient au SQUELETTE (`ux-patterns` §9, R1) : `--largeur-saisie`,\n' +
				'  dans `styles/normes.css`, employée par la classe `largeur-saisie`.\n' +
				'  Six écrans portaient six valeurs différentes le 30/08/2026 — aucune décidée, et\n' +
				"  aucun n'avait reçu la généralisation du 18/08 puisqu'aucun n'employait la classe.",
		);
		return 1;
	}

	const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
	if (inutiles.length > 0) {
		console.error('✗ Exception(s) devenue(s) inutile(s) :');
		for (const f of inutiles) console.error(`    ${f} — retirer l'entrée de EXCEPTIONS`);
		return 1;
	}

	console.log(
		`✓ Largeur de saisie : aucune écrite dans un écran, ${conteneurs} conteneur(s) de saisie ` +
			`sur ${tous.length} fichier(s), ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s).`,
	);
	return 0;
}

const _lance = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === _lance) {
	process.exit(process.argv.includes('--selftest') ? selftest() : controler());
}
