/**
 * Refuse un titre de section d'archives écrit **en dur** (#516, point 4).
 *
 * ## Pourquoi ce contrôle
 *
 * Le ticket #516 s'ouvrait sur un relevé : six écrans, **trois mots** pour la
 * même notion — « Historique », « Archive », « Archives », plus « Historique des
 * demandes » et « Terminé ». Le pire n'était pas la diversité : « Historique »
 * désignait AUSSI le fil d'un objet (cadre #430), et les deux coexistaient sur
 * l'écran Tickets.
 *
 * Le mot a été unifié le 19/08 — **à la main**, écrit en dur dans cinq fichiers.
 * Les cinq concordaient parce qu'on venait de les aligner, à un instant où tout
 * coïncide. C'est exactement l'état d'avant le ticket, et rien ne le tenait :
 *
 * > « Un garde-fou : le titre de la section doit venir d'une constante partagée,
 * >   pas d'une chaîne écrite dans chaque page — sinon la divergence revient au
 * >   premier écran ajouté. »
 *
 * ## Ce qu'il refuse, exactement
 *
 * Une chaîne littérale contenant « Archive(s) » ou « Historique » **quand elle
 * sert de titre** — c'est-à-dire dans un attribut `titre=`, un `<h2>`/`<h3>`, ou
 * un libellé d'onglet. Le mot dans une phrase, un commentaire ou un message
 * d'aide ne regarde pas ce contrôle : interdire d'employer le mot rendrait
 * l'interface muette sur ce qu'elle fait.
 *
 * ⚠️ « Historique » reste **légitime** comme titre du fil d'un objet
 * (`RubriqueHistorique`, « 📋 Historique ») : c'est la notion que le cadre #430 a
 * tranchée. Ce sont donc les deux emplois qu'il faut distinguer, pas le mot.
 * D'où la liste `TITRES_LEGITIMES` ci-dessous, qui les nomme un par un.
 *
 * Test : node front/scripts/check-archives.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SRC = join(RACINE, 'src');

/**
 * Les titres littéraux ADMIS, et pourquoi.
 *
 * 🔴 Une exception non écrite n'est pas une exception, c'est un oubli qui
 * ressemble à une décision. Le contrôle échoue si l'une d'elles cesse de servir.
 */
const TITRES_LEGITIMES = {
	//  🔴 FAUX POSITIF, et il en dit long sur la limite du motif : « Historique
	//  illisible » n'est pas un titre de section, c'est un MESSAGE D'ERREUR —
	//  celui de l'historique d'une tâche planifiée qu'on n'a pas pu charger
	//  (#816). Le contrôle cherche le mot « historique » ; il ne peut pas savoir
	//  qu'ici il qualifie un échec et non une rubrique.
	//
	//  ⚠️ Le déclarer plutôt que reformuler le message : « Historique illisible »
	//  est exactement ce qu'il faut dire à quelqu'un dont le chargement a échoué,
	//  et tordre un message d'erreur pour contenter un contrôle, c'est laisser le
	//  contrôle décider de ce que l'utilisateur lit.
	'Historique illisible':
		"message d'ERREUR d'un chargement, pas un titre de section (TachesPlanifiees)",
	//  🔴 Un TROISIÈME sens d'« Historique », que le relevé de #516 n'avait pas
	//  vu : ni les objets rangés d'un écran, ni le fil d'un objet, mais le
	//  JOURNAL de ce qui a été envoyé. Deux écrans d'administration l'emploient,
	//  et sous deux formulations différentes — ce qui montre que le mot flotte
	//  encore là où on le croyait tranché.
	//
	//  Ils sont DÉCLARÉS plutôt que corrigés : renommer ces titres change ce que
	//  voit l'administrateur, et cela se décide à l'écran — pas dans un lot qui
	//  parle d'autre chose. Signalé dans #516 pour arbitrage.
	'\u{1F4EC} Historique des envois':
		"le JOURNAL des e-mails partis — ni des objets rangés, ni le fil d'un objet.",
	'Historique des envois (6 derniers)':
		'le JOURNAL des messages WhatsApp partis. Même notion, écrite autrement.',
	//  Un QUATRIÈME sens, propre à la conservation des affaires (#2014) : des
	//  FICHIERS d'archive (.zip), produits par la tâche nocturne et copiés sur le
	//  PC — pas des objets rangés qu'on rouvrirait.
	'Archives produites':
		'les fichiers .zip de la conservation des affaires (CarteConservationAffaires), pas des objets rangés',
};

/** La constante que tout le reste doit employer. */
const CONSTANTE = 'TITRE_ARCHIVES';

//  Un titre : `titre="…"`, `titre={'…'}`, ou un `<h2>`/`<h3>` dont le contenu
//  est du texte. Les libellés d'onglet passent par `?? '…'`, capturé aussi.
const MOTIFS = [
	/titre=(?:"([^"]*)"|\{'([^']*)'\})/g,
	/<h[23][^>]*>([^<{]*)<\/h[23]>/g,
	/\?\?\s*'([^']*)'/g,
];

const SUSPECT = /\b(Archive|Archives|Historique)\b/;

function fichiers(dossier) {
	const out = [];
	for (const e of readdirSync(dossier)) {
		const p = join(dossier, e);
		if (statSync(p).isDirectory()) out.push(...fichiers(p));
		else if (e.endsWith('.svelte')) out.push(p);
	}
	return out;
}

/** Les titres littéraux suspects d'un contenu. **Pure** — éprouvable sans dépôt. */
export function titresSuspects(contenu) {
	//  Les commentaires ne rendent rien. Neutralisés en conservant la longueur,
	//  pour que les positions restent justes — la leçon de `check-html.mjs`, dont
	//  la détection line-locale refusait le fichier qui EXPLIQUE la règle.
	const neutre = neutraliserCommentaires(contenu);

	const trouves = [];
	for (const motif of MOTIFS) {
		for (const m of neutre.matchAll(motif)) {
			const texte = (m[1] ?? m[2] ?? '').trim();
			if (!texte || !SUSPECT.test(texte)) continue;
			if (texte in TITRES_LEGITIMES) continue;
			trouves.push(texte);
		}
	}
	return trouves;
}

function selftest() {
	let ko = 0;
	const t = (libelle, attendu, contenu) => {
		const n = titresSuspects(contenu).length;
		if (n === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — attendu ${attendu}, obtenu ${n}`);
			ko = 1;
		}
	};

	t('le cas de #516 : titre en dur', 1, '<SectionRepliee titre="\u{1F4C1} Archives" />');
	t('titre en dur, autre mot', 1, '<SectionRepliee titre="Historique des demandes" />');
	t('titre en h2', 1, '<h2 class="section-title">Archives de mes demandes</h2>');
	t("libellé d'onglet par défaut", 1, "{_pc.onglets?.archives?.label ?? '\u{1F4C1} Archives'}");
	//  🔴 Ce qu'il ne doit PAS refuser.
	t('la constante partagée', 0, '<SectionRepliee titre={TITRE_ARCHIVES} />');
	t("le fil d'un objet, par la constante", 0, '<RubriqueHistorique titre={TITRE_HISTORIQUE} />');
	t(
		'le journal des envois (déclaré)',
		0,
		'<SectionRepliee titre="\u{1F4EC} Historique des envois" />',
	);
	t('le mot dans une phrase', 0, '<p>Les annonces conclues sont rangées dans les Archives.</p>');
	t('le mot dans un commentaire', 0, '<!-- la section « Archives » vient de #516 -->');
	t('un titre sans rapport', 0, '<SectionRepliee titre="Documents" />');

	console.log(
		ko === 0
			? '\n✓ Autotest : un titre en dur est refusé, la constante et le fil passent.'
			: '\n✗ Autotest en échec',
	);
	return ko;
}

function main() {
	if (process.argv.includes('--selftest')) return selftest();

	const coupables = [];
	const legitimesVus = new Set();
	for (const f of fichiers(SRC)) {
		const rel = relative(RACINE, f).replace(/\\/g, '/');
		const contenu = readFileSync(f, 'utf8');
		for (const titre of Object.keys(TITRES_LEGITIMES)) {
			if (contenu.includes(titre)) legitimesVus.add(titre);
		}
		for (const titre of titresSuspects(contenu)) coupables.push([rel, titre]);
	}

	const mortes = Object.keys(TITRES_LEGITIMES).filter((x) => !legitimesVus.has(x));
	if (mortes.length) {
		console.error('✗ Titre(s) déclaré(s) légitime(s) qui ne servent plus — les retirer :');
		for (const m of mortes) console.error(`    « ${m} »`);
		return 1;
	}

	if (!coupables.length) {
		console.log(
			`✓ Archives : aucun titre de section écrit en dur — tous viennent de \`${CONSTANTE}\`,` +
				` ${Object.keys(TITRES_LEGITIMES).length} titre(s) légitime(s) déclaré(s) et servi(s).`,
		);
		return 0;
	}
	console.error('');
	console.error('✗ Titre de section écrit en dur — la divergence reviendra :');
	console.error('');
	for (const [f, titre] of coupables) console.error(`    ${f}  →  « ${titre} »`);
	console.error('');
	console.error(`  Employer \`${CONSTANTE}\` de \`#lib/archives\`. Cinq écrans l'avaient en dur`);
	console.error("  et concordaient parce qu'on venait de les aligner à la main (#516).");
	console.error('');
	console.error("  Si le titre est légitime — le FIL d'un objet, par exemple —, le déclarer");
	console.error('  dans `TITRES_LEGITIMES` avec sa raison.');
	console.error('');
	return 1;
}

process.exit(main());
