/**
 * Garde-fou : le fond d'une modale s'écrit d'UNE seule façon — `Modale`.
 *
 * ## Pourquoi ce contrôle existe (#561, 28/08/2026)
 *
 * `Modale.svelte` a été créé le 28/08/2026 pour porter le fond, le rôle, `Échap`
 * et le verrou de défilement une seule fois. Le lot qui l'a créé a converti **un
 * écran sur dix** : `residence`. Les **dix-neuf autres modales** sont restées
 * écrites à la main dans neuf fichiers, et **seize d'entre elles ne se fermaient
 * toujours qu'à la souris** — c'est-à-dire exactement le défaut que le composant
 * venait corriger.
 *
 * 🔴 La CI était verte. Rien ne rapproche un composant neuf des copies qu'il est
 * censé remplacer : `standards/05-tests-et-garde-fous.md` — *un défaut corrigé
 * sans garde-fou revient*. Ici il n'est même pas revenu, il n'était jamais parti.
 *
 * C'est le motif de la mémoire projet « PR vide : un titre sans code » : le
 * paquet est ajouté, le monolithe reste. Ce contrôle est ce qui manquait pour
 * que « le composant existe » et « le composant est employé » cessent d'être
 * deux choses différentes.
 *
 * ## Ce qui est interdit hors de `Modale.svelte`
 *
 *   1. rendre `class="modal-overlay"` à la main — passer par `<Modale>` ;
 *   2. redéfinir `.modal-overlay`, `.modal` ou `.modal-box` en CSS local — les
 *      trois vivent dans `styles/composants.css`. Les copies avaient divergé :
 *      elles perdaient le `padding` et l'animation du fond, et l'une réduisait
 *      la boîte de 560 à 420 px sans que personne l'ait décidé.
 *
 * ## Ce qui s'y ajoute le 29/08/2026 — l'EN-TÊTE et le TITRE
 *
 * Le contrôle ne regardait que le fond, et il était vert sur trois défauts que
 * la même famille produit un cran plus bas :
 *
 *   3. `class="modal-header"` écrit à la main — **15 recopies** ;
 *   4. le TITRE réécrit dans le contenu, alors que `<Modale>` le reçoit DÉJÀ en
 *      prop pour l'`aria-label`. Deux écritures pour un objet, donc deux textes
 *      libres de diverger : **onze des vingt-six avaient divergé**, et ce qu'un
 *      lecteur d'écran annonçait n'était pas ce que l'écran affichait ;
 *   5. toute règle `.modal-…` **déjà portée par la feuille commune**, redéfinie
 *      localement. ⚠️ L'ancien motif n'acceptait que `.modal`, `.modal-overlay`
 *      et `.modal-box` : `.modal-header h3` a donc survécu à l'identique dans
 *      trois écrans, seule règle du bloc que #607 n'a pas pu solder — un
 *      contrôle qui énumère les noms qu'il connaît est aveugle au suivant.
 *      Une classe `.modal-…` **absente** du global reste permise : c'est une
 *      classe propre à l'écran, pas un héritage partiel (`.modal-code`).
 *
 * Le contrôle s'auto-contrôle : si le composant disparaît, change de contrat ou
 * n'est plus employé, il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { cssGlobal } from './lib-css-global.mjs';
import { FORMES_CADRES, modales } from './lib-cadres.mjs';
import { emploieComposant } from './lib-lecture-source.mjs';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const COMPOSANT = join(RACINE, 'lib', 'components', 'Modale.svelte');

/**
 * Emplois légitimes du fond hors du composant, avec leur raison.
 *
 * Vide, et c'est l'état voulu : les vingt-six copies ont toutes été converties.
 * Une entrée ajoutée ici doit dire POURQUOI cette modale ne peut pas passer par
 * le composant — et le contrôle la refuse dès qu'elle cesse de servir.
 */
const EXCEPTIONS = {};

/** Retire commentaires et balisage commenté : expliquer la règle ne doit pas l'enfreindre. */

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
if (!existsSync(COMPOSANT)) {
	console.error(`✗ Cas zéro : ${COMPOSANT} est introuvable — contrôle inopérant.`);
	process.exit(1);
}
const composant = readFileSync(COMPOSANT, 'utf8');
//  `titre` devient l'`aria-label` de la boîte, `fermetureAuFond` porte la
//  décision d'écran qu'`OngletPerimetres` avait raison de prendre. Si l'un des
//  deux disparaît, ce contrôle interdirait des copies sans offrir de remplaçant.
for (const prop of ['titre', 'classeBoite', 'styleBoite', 'fermetureAuFond']) {
	if (!new RegExp(`export let ${prop}\\b`).test(composant)) {
		console.error(
			`✗ Cas zéro : Modale n'expose plus \`${prop}\`. Le contrat a changé — mettre ce ` +
				'contrôle à jour, sinon il interdit un geste sans en offrir le remplaçant.',
		);
		process.exit(1);
	}
}
//  Le fond, le rôle et `Échap` sont ce que les copies oubliaient. S'ils quittent
//  le composant, interdire les copies ne protège plus de rien.
for (const [motif, quoi] of [
	[/class="modal-overlay"/, 'le fond'],
	[/role="dialog"/, 'le rôle de dialogue'],
	//  Échap passe par `#lib/couche.ts` depuis #1042 : c'est `poserCouche(fermer)`
	//  qui porte la fermeture au clavier, et `lint:couches` en garde le module.
	[/poserCouche\(\s*fermer\s*\)/, 'la fermeture au clavier (poserCouche)'],
	[/class="modal-header"/, "l'en-tête"],
	[/class="modal-titre"/, 'le titre affiché'],
	[/class="modal-close"/, 'le bouton de fermeture'],
]) {
	if (!motif.test(composant)) {
		console.error(`✗ Cas zéro : Modale ne porte plus ${quoi} — ce contrôle ne mesure plus rien.`);
		process.exit(1);
	}
}
if (!/^\.modal-overlay\s*\{/m.test(cssGlobal(RACINE))) {
	console.error(
		'✗ Cas zéro : la feuille commune ne porte plus `.modal-overlay`. Elle a déménagé, et ' +
			"interdire les redéfinitions locales n'aurait plus de sens.",
	);
	process.exit(1);
}

const tous = [...fichiers(join(RACINE, 'routes')), ...fichiers(join(RACINE, 'lib'))].filter(
	(f) => f !== COMPOSANT,
);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

//  ── Recherche ───────────────────────────────────────────────────────────────
const MOTIFS = [
	{
		regex: /class="[^"]*\bmodal-overlay\b/g,
		quoi: 'le fond de modale est rendu à la main',
		remede: '<Modale titre="…" on:fermer={…}> … </Modale>',
	},
	{
		regex: /class="[^"]*\bmodal-header\b/g,
		quoi: "l'en-tête de modale est rendu à la main",
		remede: 'le titre passe par la prop `titre` de <Modale> — ou par son slot `titre`',
	},
];

/**
 * Toute règle `.modal-…` que la feuille commune porte DÉJÀ, redéfinie en local.
 *
 * Le motif se construit à partir du global plutôt que d'énumérer les noms
 * connus : c'est l'énumération qui avait laissé passer `.modal-header h3`.
 */
function reglesRedefinies(contenu, classesGlobales) {
	const trouves = [];
	for (const m of contenu.matchAll(/^[\t ]*\.(modal[\w-]*)(?=[\s.,:[{])/gm)) {
		if (classesGlobales.has(m[1])) trouves.push(m[0].trim());
	}
	return trouves;
}

/**
 * Les cadres du fichier — le contenu qui suit chaque balise ouvrante.
 *
 * 🔴 LA LECTURE DU BALISAGE A DÉMÉNAGÉ (02/09/2026) dans `lib-cadres.mjs`. Elle
 * s'écrivait ici ET dans `check-formulaire-creation.mjs`, en deux versions qui
 * avaient divergé : celle-ci ne comptait pas les imbrications (une modale de
 * confirmation par-dessus un formulaire coupait le contenu de la première au
 * milieu) et rendait la suite sans la balise.
 *
 * Le coût de la duplication était concret : apprendre une forme d'ouverture à
 * l'une ne l'apprenait pas à l'autre. La forme dynamique a dû être ajoutée deux
 * fois, à dix jours d'écart.
 *
 * ⚠️ Ce contrôle veut les TROIS formes (`FORMES_CADRES`), y compris
 * `<CadreFormulaire>` : l'invariant qu'il garde — le titre ne se réécrit pas
 * dans le contenu — vaut dès qu'un cadre reçoit `titre` en prop, ce que ce
 * dernier fait dans les deux gestes. `check-formulaire-creation`, lui, n'en veut
 * que deux ; la raison est écrite dans `lib-cadres.mjs`.
 */
const ouverturesModale = (contenu) => modales(contenu, FORMES_CADRES).map((m) => m.suite);

const compterModales = (contenu) => ouverturesModale(contenu).length;

/**
 * Un titre réécrit : un `<h1>`–`<h3>` en **premier** élément du contenu.
 *
 * Volontairement étroit — c'est la position qui trahit la recopie. Un `<h3>`
 * plus bas nomme une section du contenu (`ApercuDiffusion` en a quatre), et
 * l'interdire ferait de ce contrôle un contrôle qu'on désarme.
 */
function titresReecrits(contenu) {
	const trouves = [];
	for (const debut of ouverturesModale(contenu)) {
		const m = debut.match(/^\s*<(h[1-3])\b[^>]*>([\s\S]*?)<\/\1>/);
		if (m) trouves.push(`<${m[1]}> ${m[2].trim().split(/\s+/).slice(0, 6).join(' ')}`);
	}
	return trouves;
}

//  Les classes `.modal-…` que la feuille commune définit. Redéfinir l'une d'elles
//  dans un écran, c'est l'héritage PARTIEL que `standards/11` §1 bis décrit ;
//  en définir une qu'elle ignore, c'est une classe propre à l'écran — permis.
const CSS_COMMUN = cssGlobal(RACINE);
const classesGlobalesModal = new Set(
	[...CSS_COMMUN.matchAll(/^[\t ]*\.(modal[\w-]*)(?=[\s.,:[{])/gm)].map((m) => m[1]),
);
if (classesGlobalesModal.size < 4) {
	console.error(
		`✗ Cas zéro : ${classesGlobalesModal.size} classe(s) \`.modal-…\` dans la feuille commune. ` +
			'Elles ont déménagé — ce contrôle ne saurait plus dire ce qui est une redéfinition.',
	);
	process.exit(1);
}

const fautifs = [];
const exceptionsUtiles = new Set();
let fichiersAvecModale = 0;
let titresRendus = 0;

for (const f of tous) {
	const rel = relative(RACINE, f).split(sep).join('/');
	const brut = readFileSync(f, 'utf8');
	//  ⚠️ `includes('<Modale ')` exigeait une ESPACE littérale : Prettier écrit
	//  `<Modale` puis l'attribut à la ligne dès qu'il y en a plusieurs, et le
	//  contrôle annonçait alors « 0 fichier emploie <Modale> » (#419).
	if (emploieComposant(brut, 'Modale')) fichiersAvecModale++;
	const contenu = sansCommentaires(brut);
	const trouves = [];
	for (const motif of MOTIFS) {
		const m = contenu.match(motif.regex);
		if (m) trouves.push({ ...motif, exemples: [...new Set(m.map((s) => s.trim()))].slice(0, 3) });
	}
	const redefinies = reglesRedefinies(contenu, classesGlobalesModal);
	if (redefinies.length > 0) {
		trouves.push({
			quoi: 'une règle de modale est redéfinie en CSS local',
			remede: 'elle vit dans `styles/composants.css` — passer par `classeBoite`/`styleBoite`',
			exemples: [...new Set(redefinies)].slice(0, 3),
		});
	}
	const reecrits = titresReecrits(contenu);
	titresRendus += compterModales(contenu);
	if (reecrits.length > 0) {
		trouves.push({
			quoi: 'le titre est réécrit dans le contenu, alors que <Modale> le reçoit déjà',
			remede: 'le supprimer — la prop `titre` est affichée ; pour un rendu riche, le slot `titre`',
			exemples: reecrits.slice(0, 3),
		});
	}
	if (trouves.length === 0) continue;
	if (rel in EXCEPTIONS) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push({ fichier: rel, trouves });
}

//  Le composant peut exister, être conforme, et n'être employé nulle part : le
//  contrôle serait alors vert sur un site qui aurait tout réécrit à la main.
//  C'est EXACTEMENT l'état du 28/08/2026 au matin — un seul écran l'employait.
if (fichiersAvecModale < 2) {
	console.error(
		`✗ Cas zéro : ${fichiersAvecModale} fichier(s) emploient <Modale>. Le composant existe ` +
			'mais ne sert pas — ce contrôle ne mesure alors plus rien.',
	);
	process.exit(1);
}

//  Le contrôle du titre ne vaut que s'il a des modales à regarder : sans ce
//  compte, un jour où plus rien n'emploierait `<Modale>` il annoncerait « aucun
//  titre réécrit » — vrai, et sans aucun rapport avec ce qu'il prétend garder.
//  ⚠️ Le plancher a BAISSÉ le 31/08/2026, de 25 à 22, et c'est une baisse
//  légitime : la page Résidence a rendu ses six formulaires à `FormulaireDocument`
//  (#672). Six modales sont devenues une, qui sert les six.
//
//  🔴 Un plancher qu'on baisse à chaque échec cesse d'être un témoin. Celui-ci
//  n'a été baissé qu'APRÈS avoir appris à compter la seconde forme d'ouverture
//  (voir `ouverturesModale`) — sans quoi on aurait entériné un aveuglement en
//  croyant enregistrer un progrès.
//
//  ⚠️ 22 → 21 le 01/09/2026, et pour la même raison : « Modifier les informations »
//  d'un bail était une SECONDE écriture du formulaire de création — mêmes champs,
//  même recherche de locataire, six variables d'état en double. Les deux gestes
//  passent maintenant par `FormulaireBail`, qui pose la boîte à la création et la
//  modale à la correction. Une modale de moins, et une écriture de moins (#672).
//
//  La vérification qui autorise la baisse : le contrôle voit toujours les 21
//  autres, et `lint:formulaires` ne porte plus AUCUNE exception.
//  ⬇️ 21 → 20 le 12/09/2026 : la fenêtre de validation d'un compte est partie
//  dans `ValidationCompte`, où elle s'ouvre DANS la ligne de l'objet (#889).
//  Le plancher SUIT le relevé — le laisser au-dessus rendrait le cas zéro
//  permanent, et un contrôle qui échoue toujours finit par être désarmé.
//  ⬇️ idem — la fenêtre de fin de bail est partie. Le plancher SUIT le relevé.
//  ⬇️ « noter un prestataire » s'ouvre dans la carte (12/09/2026, #889).
//  ⬇️ 18 → 16 le 01/10/2026 (#779) : les confirmations de suppression d'un bail
//  et d'un compte passent par `confirmer(SUPPRESSION(…))` — deux modales
//  écrites à la main de moins (`lint:suppression-confirmee`).
//  ⬇️ 16 → 15 le 02/10/2026 (#1539) : `InventaireBail` rendait le formulaire
//  d'un objet remis DEUX fois (création, correction), donc deux
//  `<CadreFormulaire>` ; il l'écrit une fois (`{#snippet formulaireObjet}`).
//  Un cadre de moins, une écriture de moins — les quinze autres sont vus.
const PLANCHER_MODALES = 15;
if (titresRendus < PLANCHER_MODALES) {
	console.error(
		`✗ Cas zéro : ${titresRendus} modale(s) recensée(s), ${PLANCHER_MODALES} attendues au minimum. ` +
			'Le repérage des balises ouvrantes ne mord plus — ne pas lire ce contrôle comme vert.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error('✗ Modale(s) recomposée(s) hors du composant :');
	for (const { fichier, trouves } of fautifs) {
		for (const t of trouves) {
			console.error(`    ${fichier} — ${t.exemples.join(' · ')}`);
			console.error(`        ${t.quoi}`);
			console.error(`        → ${t.remede}`);
		}
	}
	console.error(
		"\n  Une copie du fond n'emporte pas ce qui compte : `Échap`, le rôle et le verrou de\n" +
			"  défilement. Seize modales sur vingt-six ne se fermaient qu'à la souris (#561).\n" +
			'  Et un titre écrit deux fois finit par dire deux choses : onze des vingt-six\n' +
			"  annonçaient au lecteur d'écran autre chose que ce qu'elles affichaient.",
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s) :');
	for (const f of inutiles) console.error(`    ${f} — retirer l'entrée de EXCEPTIONS`);
	process.exit(1);
}

console.log(
	`✓ Modales : ${fichiersAvecModale} fichier(s) passent par Modale, ${titresRendus} modale(s) dont le ` +
		`titre n'est écrit qu'une fois, ${tous.length} fichier(s) ` +
		`vérifié(s), ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s) et justifiée(s).`,
);
