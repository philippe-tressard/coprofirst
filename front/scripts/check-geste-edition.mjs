#!/usr/bin/env node
/**
 * Le GESTE D'ÉDITION se rend partout de la même façon.
 *
 * ## Pourquoi ce contrôle existe (10/09/2026)
 *
 * Deux anomalies signalées à l'écran sur les contrats — *« il n'y a pas d'icône
 * édition mais un bouton Modifier »*, et *« le formulaire d'édition apparaît en
 * bas de page »*. L'audit qui a suivi en a trouvé **cinq autres** du premier
 * genre et **un** du second, sur des écrans que personne n'avait signalés.
 *
 * 🔴 **Et la décision était déjà prise.** `RubriqueHistorique` porte, depuis un
 * lot antérieur, ce commentaire :
 *
 *   « Le CRAYON SEUL, comme partout ailleurs sur le site : ce bouton portait
 *     "✏️ Modifier" et était **le dernier à écrire le mot**. »
 *
 * Il en restait cinq. C'est le motif que ce dépôt connaît déjà — *le seul
 * fichier qui parle du sujet affirme que le problème n'existe plus*, et cette
 * affirmation dispense tout le monde de vérifier. Une consigne écrite dans un
 * commentaire ne se maintient pas : il faut un contrôle qui échoue.
 *
 * ## Les cinq règles
 *
 * **A. Le crayon SEUL.** Un bouton qui ouvre une édition porte `btn-icon-edit`
 * ou `btn-icon`, l'icône, et son sens dans `title` + `aria-label`. Le MOT
 * « Modifier » à côté de l'icône est la seconde forme du même geste.
 *
 * **B. Un formulaire, un endroit.** Le même composant de formulaire rendu deux
 * fois dans un écran, à plus de `ECART_MAX` lignes d'écart, n'est pas « la même
 * boîte » : c'est la même boîte à deux endroits, dont un que l'utilisateur ne
 * voit pas. `ux-patterns` §14 bis dit *créer et corriger emploient la même
 * boîte* — et la lettre en était respectée sur les contrats, l'esprit non.
 *
 * **C. Un identifiant d'édition ne gouverne qu'UN rendu.** La variable qui dit
 * *quel objet est en cours de correction* ne peut pas à la fois ouvrir un
 * formulaire dans l'écran ET être déléguée à un composant enfant : les deux
 * rendus s'affichent alors ENSEMBLE. Signalé à l'écran le 10/09/2026 —
 * *« plusieurs contrats sont ouverts en édition simultanément »* — quelques
 * heures après que la correction d'un contrat eut déménagé dans sa carte. Le
 * bloc de tête était resté ouvert sur `contratFormOuvert || editContratId`.
 *
 * 🔴 **La règle B ne pouvait pas le voir, et c'est l'extraction qui l'a
 * aveuglée** : elle compte les rendus d'un formulaire FICHIER PAR FICHIER, et
 * le second venait d'être déplacé dans un second fichier. Un contrôle dont la
 * portée est le fichier perd sa prise le jour où l'on découpe — la portée du
 * contrôle fait partie du contrôle (`standards/05` §9).
 *
 * **D. Le formulaire ne défile QUE s'il s'ouvre ailleurs que sous les yeux.**
 * `FormulaireCreation` ne peut appeler `ramener()` que depuis la ligne réactive
 * gardée par `cle !== undefined`. Signalé à l'écran le 10/09/2026, trois fois de
 * suite : *« le contrat édité remonte en haut »*. Le montage appelait
 * `ramener(cle)` sans condition — donc `ramener(undefined)` pour tous les
 * formulaires qui s'ouvrent DANS la carte de l'objet corrigé, lesquels se
 * faisaient ramener en haut de l'écran dès qu'ils dépassaient la bande visible
 * de quelques pixels, en emportant leur carte.
 *
 * 🔴 **L'intention était écrite dans le fichier même**, à dix lignes de là : *« un
 * formulaire qui s'ouvre sous les yeux n'a pas à faire sauter la page »*. Le code
 * ne testait que la POSITION, jamais la raison d'être là — et la position seule
 * ne distingue pas « ouvert loin du geste » de « ouvert un peu bas ».
 *
 * **E. La correction d'un objet ne s'ouvre pas dans une FENÊTRE.** `<Modale
 * edition>` est refusée : une boîte flottante sort l'objet de sa liste, et c'est
 * le paradigme que #367 a retiré du produit après trois signalements. La
 * correction s'ouvre DANS la carte de l'objet, à la place de son corps — le
 * motif des tickets (`ux-patterns` §14 ter).
 *
 * Signalé à l'écran le 10/09/2026 sur l'administration des périmètres — *« le
 * crayon provoque l'affichage d'une fenêtre indépendante (hors UX) »* — puis
 * généralisé sur demande : *« ce problème apparaît parfois en édition, en
 * commentaire ou en + ; faire un audit général »*.
 *
 * ⚠️ **Une `Modale` SANS `edition` n'est pas visée** : confirmer une suppression,
 * montrer un aperçu avant envoi, poser une question fermée — ce ne sont pas des
 * corrections, et la fenêtre y est le bon format. Le produit distingue déjà les
 * deux par cette propriété ; le contrôle s'appuie sur la distinction qui existe
 * plutôt que d'en inventer une.
 *
 * 🔴 Les huit occurrences relevées par l'audit sont déclarées dans `MODALES` avec
 * leur motif et leur ticket. Elles ne sont pas tolérées « en attendant » : elles
 * sont NOMMÉES, elles ne peuvent plus se multiplier, et une déclaration qui ne
 * sert plus fait échouer le contrôle.
 *
 * ⚠️ La règle B admet des séparations JUSTIFIÉES : deux rendus dont les
 * propriétés diffèrent réellement (un bail à la création porte des lots, pas à
 * la correction) restent séparés — mais le second doit alors se ramener à
 * l'écran, ce que `FormulaireCreation` fait par sa `cle`. Le contrôle exige donc
 * cette clé, pas la fusion.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep as SEP } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const SRC = join(ICI, '..', 'src');

/** Deux rendus plus éloignés que cela ne sont plus « au même endroit ». */
const ECART_MAX = 200;

/**
 * Les fichiers où le MOT « Modifier » accompagne l'icône pour une raison.
 * Chacun avec son motif — une tolérance sans raison devient un dépotoir.
 */
const EXCEPTIONS = {
	'lib/components/RubriqueHistorique.svelte':
		"le mot n'apparaît que dans le COMMENTAIRE qui raconte sa suppression — " +
		"et c'est ce commentaire qui affirmait être « le dernier », alors qu'il " +
		'en restait cinq. Le garder est utile : il porte la décision.',
};

/**
 * Les `<Modale edition>` relevées par l'audit du 10/09/2026 (issue #889).
 *
 * Chacune est une correction qui s'ouvre dans une fenêtre au lieu de s'ouvrir à
 * la place de l'objet. Elles se convertissent **un écran à la fois**, chacun
 * constaté à l'écran avant le suivant (R5 du cadre) — c'est ce qui a manqué aux
 * trois tentatives de la journée sur les contrats.
 */
const MODALES = {
	//  Suivie du balisage le 30/09/2026 (#779) : elle était déclarée sur
	//  `admin/+page.svelte` tant que l'onglet Utilisateurs y vivait.
	'lib/components/ModaleAccueilArrivant.svelte':
		'accueil du nouvel arrivant — un geste sur un utilisateur EXISTANT, déclenché depuis l’annuaire et non depuis une liste de comptes en attente. La validation, elle, est convertie (12/09/2026). #889',
	'lib/components/ModaleAccesBail.svelte':
		'ce n’est PAS la correction d’un objet de liste mais un sous-écran entier (accès Vigik et télécommandes d’un bail, plusieurs listes et plusieurs gestes). À trancher devant l’écran. #889',
};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const tous = fichiers(SRC);
const fautes = [];
const exceptionsVues = new Set();

//  ── A. Le crayon seul ───────────────────────────────────────────────────────
const MOT = /(?:✏️|✏|&#x270F;&#xFE0F;|&#x270F;)\s*Modifier/g;
for (const f of tous) {
	const rel = relative(SRC, f).replace(/\\/g, '/');
	const src = readFileSync(f, 'utf8');
	const trouve = [...src.matchAll(MOT)];
	if (trouve.length === 0) continue;
	if (rel in EXCEPTIONS) {
		exceptionsVues.add(rel);
		continue;
	}
	for (const m of trouve) {
		fautes.push({
			regle: 'A',
			fichier: rel,
			ligne: src.slice(0, m.index).split('\n').length,
			quoi: 'le mot « Modifier » accompagne l’icône',
			remede: 'le crayon SEUL, le sens dans `title` et `aria-label` — `btn-icon-edit`',
		});
	}
}

//  ── B. Un formulaire, un endroit ────────────────────────────────────────────
const COMPOSANT = /<(Formulaire[A-Z][A-Za-z]*)\b/g;
for (const f of tous) {
	const rel = relative(SRC, f).replace(/\\/g, '/');
	const src = readFileSync(f, 'utf8');
	const parNom = new Map();
	for (const m of src.matchAll(COMPOSANT)) {
		const ligne = src.slice(0, m.index).split('\n').length;
		if (!parNom.has(m[1])) parNom.set(m[1], []);
		parNom.get(m[1]).push(ligne);
	}
	for (const [nom, lignes] of parNom) {
		if (lignes.length < 2) continue;
		const ecart = Math.max(...lignes) - Math.min(...lignes);
		if (ecart <= ECART_MAX) continue;
		//  Le second rendu doit au moins se ramener à l'écran : `cle` sur le
		//  `FormulaireCreation` qui l'enveloppe, ou sur lui-même.
		const zone = src
			.split('\n')
			.slice(Math.max(...lignes) - 12, Math.max(...lignes) + 4)
			.join('\n');
		if (/\bcle=\{/.test(zone)) continue;
		fautes.push({
			regle: 'B',
			fichier: rel,
			ligne: Math.max(...lignes),
			quoi: `<${nom}> rendu aux lignes ${lignes.join(', ')} — ${ecart} lignes d’écart`,
			remede:
				'un seul rendu au même endroit, ou `cle={…}` sur le second pour qu’il se ' +
				'ramène à l’écran (`FormulaireCreation`)',
		});
	}
}

//  ── C. Un identifiant d'édition ne gouverne qu'un rendu ─────────────────────
const IDENT_EDITION = /\bedit[A-Z][A-Za-z]*Id\b/;

for (const f of tous) {
	const rel = relative(SRC, f).replace(/\\/g, '/');
	const lignes = readFileSync(f, 'utf8').split('\n');

	for (let i = 0; i < lignes.length; i++) {
		const ouverture = lignes[i].match(/\{#if\s[^}]*/);
		if (!ouverture) continue;
		const nom = ouverture[0].match(IDENT_EDITION)?.[0];
		if (!nom) continue;

		//  Le bloc gouverné par ce `{#if}`, jusqu'à son `{/if}`.
		let prof = 0;
		let fin = lignes.length - 1;
		for (let j = i; j < lignes.length; j++) {
			prof += (lignes[j].match(/\{#if\b/g) || []).length;
			prof -= (lignes[j].match(/\{\/if\}/g) || []).length;
			if (prof <= 0) {
				fin = j;
				break;
			}
		}
		const bloc = lignes.slice(i, fin + 1).join('\n');
		if (!/<Formulaire[A-Z]/.test(bloc)) continue;

		//  Le même identifiant confié à un composant, HORS de ce bloc : l'enfant
		//  rendra sa propre boîte, et les deux seront à l'écran ensemble.
		const confie = `{${nom}}`;
		const nomme = `${nom}={`;
		const ailleurs = lignes.findIndex(
			(l, n) => (n < i || n > fin) && (l.trim().startsWith(confie) || l.trim().startsWith(nomme)),
		);
		if (ailleurs === -1) continue;

		fautes.push({
			regle: 'C',
			fichier: rel,
			ligne: i + 1,
			quoi:
				`\`${nom}\` ouvre un formulaire ici ET est confié à un composant ` +
				`(ligne ${ailleurs + 1}) — deux boîtes d'édition à l'écran en même temps`,
			remede:
				"ne garder qu'un rendu : l'écran ouvre la CRÉATION, le composant qui porte " +
				"l'objet ouvre sa CORRECTION",
		});
	}
}

//  ── D. Le formulaire ne défile que s'il porte une `cle` ─────────────────────
{
	const f = join(SRC, 'lib', 'components', 'FormulaireCreation.svelte');
	const src = readFileSync(f, 'utf8');
	//  Cas zéro : si ce composant cesse de défiler du tout, la règle n'a plus
	//  d'objet — et un contrôle sans objet doit le DIRE, pas rendre vert.
	//  Le défilement passe par `amenerEnVue` (`#lib/accordeon`) depuis le
	//  30/09/2026 : la règle y a été extraite quand l'accordéon en a eu besoin.
	if (!src.includes('scrollIntoView') && !/amenerEnVue\(/.test(src)) {
		console.error(
			'✗ Cas zéro : FormulaireCreation ne défile plus du tout — la règle D ne mesure rien.',
		);
		process.exit(1);
	}
	src.split('\n').forEach((ligne, i) => {
		//  ⚠️ Les COMMENTAIRES parlent de `ramener()` — c'est même là que
		//  l'intention est écrite. Les compter serait le faux positif de l'audit du
		//  10/09 (23 sur 23), qui attrapait des `role="button"` cités dans du texte.
		if (/^\s*(?:\/\/|\*|\/\*)/.test(ligne)) return;
		if (!/(?:^|[^a-zA-Z])ramener\(/.test(ligne)) return;
		//  Les deux seules écritures légitimes : la déclaration de la fonction, et
		//  l'appel réactif gardé par la présence d'une `cle`.
		if (/function ramener/.test(ligne)) return;
		if (/cle !== undefined\).*ramener\(/.test(ligne)) return;
		fautes.push({
			regle: 'D',
			fichier: 'lib/components/FormulaireCreation.svelte',
			ligne: i + 1,
			quoi: 'appel à `ramener()` hors de la garde `cle !== undefined`',
			remede:
				'un formulaire qui s’ouvre SOUS LES YEUX ne défile pas ; seule une `cle` ' +
				'demande à être ramené à l’écran',
		});
	});
}

//  ── E. La correction ne s'ouvre pas dans une fenêtre ────────────────────────
const modalesVues = new Set();

for (const f of tous) {
	const rel = relative(SRC, f).split(SEP).join('/');
	const src = readFileSync(f, 'utf8');
	//  Balayage littéral, sans expression rationnelle : la précédente portait
	//  un vrai caractère BACKSPACE à la place de la limite de mot, avalé à
	//  l'écriture — et ne correspondait à rien, en silence. Une chaîne cherchée
	//  par `indexOf` n'a pas d'échappement à perdre.
	let i = src.indexOf('<Modale');
	while (i !== -1) {
		//  ⚠️ Un COMMENTAIRE qui parle de `<Modale edition>` n'en est pas un —
		//  c'est même là que se raconte sa suppression. Les compter serait le faux
		//  positif de l'audit du 10/09 (23 sur 23), qui attrapait des `role="button"`
		//  cités dans du texte.
		const debutLigne = src.lastIndexOf('\n', i) + 1;
		const avant = src.slice(debutLigne, i);
		const estCommentaire = /^\s*(?:\*|\/\/|<!--)/.test(avant) || avant.endsWith('`');
		const fin = src.indexOf('>', i);
		const balise = fin === -1 ? src.slice(i) : src.slice(i, fin + 1);
		//  `edition` en tant que PROPRIÉTÉ, pas au milieu d'un autre mot.
		const estEdition = new RegExp('\\sedition(?:\\s|=|>|$)').test(balise);
		if (estEdition && !estCommentaire) {
			const ligne = src.slice(0, i).split('\n').length;
			if (rel in MODALES) {
				modalesVues.add(rel);
			} else {
				fautes.push({
					regle: 'E',
					fichier: rel,
					ligne,
					quoi: '<Modale edition> — la correction s’ouvre dans une fenêtre',
					remede:
						'la boîte s’ouvre DANS la carte de l’objet, à la place de son corps ' +
						'(`FormulaireCreation encadre={false}`) — le motif des tickets',
				});
			}
		}
		i = src.indexOf('<Modale', i + 7);
	}
}

//  ── F. Le formulaire s'ouvre LOIN du geste qui le déclenche ────────────────
//
//  🔴 Signalé à l'écran le 13/09/2026 :
//
//  > « quand je clique sur le crayon du kanban, j'avais l'impression que rien ne
//  >   se passe : l'écran d'édition apparaît hors écran. »
//
//  ⚠️ LA RÈGLE B NE POUVAIT PAS LE VOIR, et c'est la leçon de ce défaut. Elle
//  mesure l'écart entre DEUX rendus du même formulaire ; le calendrier n'en rend
//  qu'un, tout en bas de la page, sous un kanban de plusieurs écrans de haut. Un
//  seul rendu, donc aucune paire, donc rien à mesurer — et un formulaire qui
//  s'ouvrait à deux mille pixels du crayon cliqué.
//
//  La bonne distance n'est pas « d'un rendu à l'autre », c'est « du GESTE au
//  rendu ». On la mesure entre l'endroit où le drapeau d'ouverture passe à
//  `true` et l'endroit où le formulaire est rendu sous ce drapeau.
//
//  ⚠️ Mesure STATIQUE, donc approchée : les lignes d'un fichier ne sont pas des
//  pixels à l'écran. Elle attrape ce qu'elle vise — un formulaire relégué en pied
//  de gabarit — et laisse passer un écran court dont tout tient dans la fenêtre.
//  C'est le bon sens de l'erreur : `FormulaireCreation` ne défile de toute façon
//  QUE si le cadre est hors de la bande visible, donc une `cle` posée en trop ne
//  fait jamais sauter une page.
const OUVERTURE = /^[ \t]*(?:if\s*\(.*\)\s*)?([A-Za-z_$][\w$]*)\s*=\s*true\s*;/gm;

for (const f of tous) {
	const rel = relative(SRC, f).split(SEP).join('/');
	const src = readFileSync(f, 'utf8');
	const lignes = src.split('\n');

	//  Où chaque drapeau passe-t-il à `true` ?
	const poses = new Map();
	for (const m of src.matchAll(OUVERTURE)) {
		const ligne = src.slice(0, m.index).split('\n').length;
		if (!poses.has(m[1])) poses.set(m[1], []);
		poses.get(m[1]).push(ligne);
	}
	if (poses.size === 0) continue;

	//  Où un formulaire est-il rendu, et sous quel `{#if}` ?
	for (const m of src.matchAll(/<(Formulaire[A-Z][A-Za-z]*)\b/g)) {
		const ligneRendu = src.slice(0, m.index).split('\n').length;
		//  Le `{#if}` le plus proche AU-DESSUS du rendu — le gabarit n'en imbrique
		//  pas d'autre entre le drapeau et le formulaire dans les cas visés.
		let garde = null;
		for (let i = ligneRendu - 1; i >= Math.max(0, ligneRendu - 6); i--) {
			const g = /\{#if\s+([A-Za-z_$][\w$]*)\b/.exec(lignes[i] ?? '');
			if (g) {
				garde = g[1];
				break;
			}
		}
		if (!garde || !poses.has(garde)) continue;

		const ecart = Math.max(...poses.get(garde).map((l) => Math.abs(ligneRendu - l)));
		if (ecart <= ECART_MAX) continue;

		//  La `cle` se cherche dans la balise du rendu, pas dans le fichier : une
		//  `cle` posée sur un AUTRE formulaire du même écran ne protège pas celui-ci.
		const finBalise = src.indexOf('/>', m.index);
		const balise = src.slice(m.index, finBalise === -1 ? m.index + 400 : finBalise);
		//  `cle="…"` autant que `cle={…}` : une clé constante suffit, puisque
		//  `FormulaireCreation` défile au MONTAGE dès qu'une clé est définie.
		//  🔴 `indexOf` et non une limite de mot : la ligne précédente portait un
		//  vrai caractère RETOUR ARRIÈRE (0x08) à la place de `\b`, avalé à
		//  l'écriture — elle ne correspondait donc à rien, en silence, et la règle
		//  laissait passer les quatre écrans qu'elle venait de trouver. C'est le
		//  MÊME accident que la règle E, raconté vingt lignes plus haut, et la
		//  même conclusion : une chaîne cherchée littéralement ne perd rien.
		//
		//  `cle="…"` autant que `cle={…}` : une clé constante suffit, puisque
		//  `FormulaireCreation` défile au MONTAGE dès qu'une clé est définie.
		if (balise.includes('cle={') || balise.includes('cle="')) continue;

		fautes.push({
			regle: 'F',
			fichier: rel,
			ligne: ligneRendu,
			quoi: `<${m[1]}> rendu à ${ecart} lignes du geste qui l’ouvre (\`${garde} = true\`)`,
			remede:
				'`cle={…}` sur le rendu — `FormulaireCreation` ramène alors le formulaire ' +
				'à l’écran, et seulement s’il en est sorti',
		});
	}
}

const modalesInutiles = Object.keys(MODALES).filter((f) => !modalesVues.has(f));
if (modalesInutiles.length > 0) {
	console.error('✗ Déclaration(s) de MODALES devenue(s) inutile(s), à retirer :');
	for (const f of modalesInutiles) console.error(`    ${f}`);
	console.error('  L’écran a été converti : la dette part avec lui.');
	process.exit(1);
}

//  ── Cas zéro : le contrôle regarde-t-il quelque chose ? ─────────────────────
if (tous.length < 50) {
	console.error(`✗ Cas zéro : ${tous.length} composant(s) analysé(s) — le relevé est cassé.`);
	process.exit(1);
}

//  ── Une exception qui ne sert plus fait ÉCHOUER ─────────────────────────────
const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsVues.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s), à retirer d’EXCEPTIONS :');
	for (const f of inutiles) console.error(`    ${f}`);
	process.exit(1);
}

if (fautes.length > 0) {
	console.error('✗ Le geste d’édition n’est pas rendu partout de la même façon :\n');
	for (const d of fautes) {
		console.error(`  [${d.regle}] ${d.fichier}:${d.ligne}`);
		console.error(`      ${d.quoi}`);
		console.error(`      → ${d.remede}\n`);
	}
	console.error(
		'  Ces règles ont été signalées à l’écran les 10 et 13/09/2026, et la première\n' +
			'  était déjà écrite dans un commentaire qui se croyait le dernier concerné.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Geste d’édition : ${tous.length} composant(s) vérifié(s) — crayon seul partout, ` +
		`aucun formulaire rendu loin de son jumeau NI du geste qui l’ouvre, aucun identifiant d’édition à deux rendus, défilement gardé par une clé, ${Object.keys(MODALES).length} fenêtre(s) d’édition déclarée(s), ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s).`,
);
