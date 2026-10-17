#!/usr/bin/env node
/**
 * Garde-fou : un composant qui PORTE une section en transmet le pliage.
 *
 * ## Le défaut, signalé deux fois à l'écran (22/09/2026)
 *
 * > « le périmètre "Pièces jointes" optionnel doit être plié »
 * > « PJ toujours déplié »
 *
 * La table le déclarait `pliee: true` **dans les cinq entités concernées**, et
 * la section restait ouverte. « Au nom de » aussi — alors que c'est la seule
 * exception de pliage du cadre, celle qu'on a pris le soin de motiver.
 *
 * ## 🔴 L'angle mort des composants PORTEURS
 *
 * `SectionsPiecesJointes` et `ChampSaisiPour` rendent leur propre
 * `SectionFormulaire`. Le pliage lu dans la table par `ChampsCommuns` ne leur
 * était donc jamais passé : il n'existait pas de prop pour le recevoir.
 *
 * C'est **exactement** l'angle mort qui avait rendu l'ordre des sections
 * incontrôlable (#1124) : ces composants n'écrivent aucun `titre=`, aucun
 * `pliable=`, et aucun contrôle ne les regardait. Deux défauts distincts, une
 * seule cause — une section rendue par un composant échappe à ce qui gouverne
 * les sections rendues par un écran.
 *
 * ## Ce qui est vérifié
 *
 * Tout composant qui rend `<SectionFormulaire>` avec un `titre` issu de
 * `SECTIONS_LIBELLE` doit :
 *
 *   1. accepter une prop `pliable`,
 *   2. la transmettre à ce `SectionFormulaire`.
 *
 * ⚠️ Ce contrôle ne dit pas si l'APPELANT passe la bonne valeur — cela, c'est
 * `lint:etats` qui le gouverne depuis la table. Il dit que le chemin existe :
 * sans lui, la valeur juste n'arrive nulle part.
 *
 * ## 🔴 …et l'appelant l'EMPRUNTE (#1329, 25/09/2026)
 *
 * Le chemin existait, et la Suite d'une affaire ne l'empruntait pas : `EvolForm`
 * rendait Pièces jointes et Diffusion sans `pliable`, les créneaux du conseil
 * l'écrivaient en dur (`pliable` nu). Même section, pliée en Édition, ouverte
 * en Suite — relevé par l'audit, jamais vu par ce contrôle, qui ne regardait
 * que le porteur.
 *
 * Tout appel d'un PORTEUR (un composant qui accepte `pliable` et rend une
 * section du cadre) doit donc passer `pliable={…}` — une valeur LUE, jamais
 * absente, jamais `pliable` nu ni `{true}`/`{false}`.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

import { balisesOuvrantes, ligneDe } from './lib-balises.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

function svelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...svelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

/** Les manquements d'une source. PURE : éprouvable sans arborescence. */
export function pliageManquant(source) {
	//  Seuls les composants qui rendent une section DU CADRE sont concernés :
	//  une section « Le contrat » ou « Activation » n'est pas gouvernée par la
	//  table, et n'a donc pas de pliage déclaré.
	//  L'automate vit dans `lib-balises.mjs` depuis le 22/09/2026 : il etait
	//  ecrit ici, et une troisieme fois ailleurs. Le `>` d'une expression ne ferme
	//  pas une balise (`standards/04` §48) — et la quatrieme recopie manquerait le
	//  cas suivant.
	const balises = balisesOuvrantes(source, 'SectionFormulaire').filter((b) =>
		b.balise.includes('SECTIONS_LIBELLE.'),
	);
	if (balises.length === 0) return [];
	//  🔴 Ce qui compte est que la BALISE porte `pliable` — peu importe d'où la
	//  valeur vient. Un composant qui lit la table lui-même
	//  (`pliable={plie('quand')}`) est aussi juste qu'un composant qui reçoit la
	//  prop d'un appelant : dans les deux cas, le chemin existe.
	//
	//  ⚠️ Ma première écriture exigeait `export let pliable` partout, et criait
	//  donc sur `ChampsCommuns` — c'est-à-dire sur celui qui fait exactement ce
	//  qu'il faut. Un contrôle qui crie sur du légitime finit désarmé.
	const manques = [];
	for (const m of balises) {
		if (!/[^A-Za-z]pliable[^A-Za-z]/.test(m.balise)) {
			manques.push({ ligne: ligneDe(source, m.index), quoi: 'pliable' });
		}
		//  🔴 `requis` ÉCRIT EN DUR — le même angle mort, une section plus loin
		//  (22/09/2026). `SectionDestinataires` posait `requis` lui-même : la
		//  déclaration ne savait donc pas que la section était obligatoire, et
		//  `lint:etats` — qui CALCULE le pliage à partir d'elle — ne voyait aucune
		//  contradiction à la déclarer pliée. L'écran affichait « DESTINATAIRES* »
		//  sur une ligne fermée, ce que la règle interdit. Signalé deux fois.
		//
		//  ⚠️ Un attribut NU (`requis`) est une valeur écrite ici ; `{requis}` ou
		//  `requis={…}` vient d'ailleurs, et c'est ce qu'on veut.
		if (/[^A-Za-z]requis(?=[\s/>])/.test(m.balise)) {
			manques.push({ ligne: ligneDe(source, m.index), quoi: 'requis en dur' });
		}
	}
	return manques;
}

/**
 * 🔴 `requis` VRAI PAR DÉFAUT — le troisième chemin du même angle mort (#1186,
 * 24/09/2026). Ni attribut nu, ni valeur lue : une prop `export let requis =
 * true` (ou `perimetreRequis = true`) dans un porteur. Tout appelant qui ne dit
 * rien reçoit l'astérisque — et la déclaration n'en sait rien.
 *
 * C'est ce qui affichait « PÉRIMÈTRE* » PLIÉ sur la Boîte à idées : `idee.ts`
 * ne déclarait pas le périmètre obligatoire, `lint:etats` ne voyait donc
 * aucune raison de le déplier, et `ChampsCommuns` posait l'étoile quand même.
 *
 * PURE : rend les noms de props fautives.
 */
export function requisParDefaut(source) {
	return [...source.matchAll(/export\s+let\s+(\w*[Rr]equis\w*)\s*(?::[^=;]+)?=\s*true\b/g)].map(
		(m) => ({ ligne: ligneDe(source, m.index), nom: m[1] }),
	);
}

/**  Les écrans HORS cadre, déclarés avec leur raison : ils rendent un porteur
 *   sans déclaration d'entité, donc sans pliage à lire. Le contrôle échoue si
 *   l'une ne sert plus. */
const HORS_CADRE = {
	'lib/components/FormulaireAnnonceHall.svelte':
		"l'affiche de hall n'a pas de déclaration d'entité (`check-intitules-section`, HORS_CADRE)",
	'lib/components/PanneauOptionsPublication.svelte':
		"le panneau n'a qu'une section, ouverte par son propre geste sur la carte : la plier " +
		'imposerait un second clic pour atteindre ce qu’on vient de demander (#1329)',
	'lib/components/FormulaireDocument.svelte':
		"le document n'est pas une entité du cadre (`ux-patterns` : Document et Utilisateur " +
		'exemptés) : pas de déclaration, donc pas de pliage à lire (#1329)',
	'lib/components/reporting/SaisieCrAffaire.svelte':
		"le compte rendu d'une affaire dans un point CS / Syndic n'est pas une entité du cadre : " +
		'sa seule section s’ouvre par le geste « Compte rendu », la plier imposerait un second clic (#2041)',
	'lib/components/FormulaireFaq.svelte':
		"la FAQ n'a pas de déclaration d'entité : sa Réponse, obligatoire, reste dépliée (#1329)",
};

/**  Les appels d'un porteur qui n'empruntent pas le chemin. PURE. */
export function appelantsSansPliage(source, porteurs) {
	const fautes = [];
	for (const p of porteurs) {
		for (const b of balisesOuvrantes(source, p)) {
			const t = b.balise;
			let quoi = null;
			if (!/[^A-Za-z]pliable[^A-Za-z]/.test(t)) quoi = 'absent';
			else if (/[^A-Za-z{]pliable(?=[\s/>])/.test(t) || /pliable=\{(true|false)\}/.test(t))
				quoi = 'en dur';
			if (quoi) fautes.push({ ligne: ligneDe(source, b.index), porteur: p, quoi });
		}
	}
	return fautes;
}

if (process.argv.includes('--selftest')) {
	//  L'appelant (#1329) : les trois formes vues le 25/09, et les deux justes.
	const casAppel = [
		['<SectionsPiecesJointes {idPrefixe} avecPhotos={x} />', 1],
		['<SectionQuand idPrefixe="s" pliable bind:debut={d} />', 1],
		['<SectionQuand idPrefixe="s" pliable={true} />', 1],
		['<SectionQuand idPrefixe="s" pliable={pliageDe(TICKET, \'quand\')} />', 0],
		['<SectionDiffusion {pliable} avecCanaux />', 0],
	];
	for (const [src, attendu] of casAppel) {
		const n = appelantsSansPliage(src, [
			'SectionsPiecesJointes',
			'SectionQuand',
			'SectionDiffusion',
		]).length;
		if (n !== attendu) {
			console.error(`  ✗ appel « ${src} » → ${n}, attendu ${attendu}`);
			process.exitCode = 1;
		}
	}
	const cas = [
		//  🔴 Le cas réel du 22/09 : la section du cadre, rendue sans pliage.
		['<SectionFormulaire titre={SECTIONS_LIBELLE.pieces_jointes}>', 1],
		//  La prop reçue d'un appelant…
		['<SectionFormulaire titre={SECTIONS_LIBELLE.pieces_jointes} {pliable}>', 0],
		//  …ou lue dans la table sur place : les deux sont justes.
		["<SectionFormulaire titre={SECTIONS_LIBELLE.quand} pliable={plie('quand')}>", 0],
		//  Une section HORS cadre n'est pas jugée.
		['<SectionFormulaire titre="Le contrat">', 0],
		//  🔴 Le `>` d'une EXPRESSION ne ferme pas la balise. Sans l'automate,
		//  l'analyse s'arretait a `length >` et ne voyait pas le `pliable` d'apres :
		//  le controle reclamait un attribut deja present (vecu le 22/09/2026).
		[
			'<SectionFormulaire titre={SECTIONS_LIBELLE.destinataires} rempli={d.length > 0} pliable={p}>',
			0,
		],
		//  Et l'autre sens : le meme `>` ne doit pas masquer un manque reel.
		['<SectionFormulaire titre={SECTIONS_LIBELLE.destinataires} rempli={d.length > 0}>', 1],
		//  🔴 `requis` NU : la valeur est écrite ici, la déclaration l'ignore.
		['<SectionFormulaire titre={SECTIONS_LIBELLE.destinataires} pliable={p} requis>', 1],
		//  Reçu d'ailleurs : c'est ce qu'on veut.
		['<SectionFormulaire titre={SECTIONS_LIBELLE.destinataires} pliable={p} {requis}>', 0],
		[
			"<SectionFormulaire titre={SECTIONS_LIBELLE.destinataires} pliable={p} requis={exige('x')}>",
			0,
		],
		//  ⚠️ Un attribut qui COMMENCE par « requis » n'est pas `requis`.
		['<SectionFormulaire titre={SECTIONS_LIBELLE.quand} pliable={p} requisAide="x">', 0],
		//  Aucun SectionFormulaire : rien à dire.
		['<div>rien</div>', 0],
	];
	//  `requis` vrai par défaut dans un porteur (#1186).
	const casDefaut = [
		['export let perimetreRequis = true;', 1],
		['export let requis: boolean = true;', 1],
		['export let requis = false;', 0],
		['export let perimetrePrecise = true;', 0],
	];
	let ko = 0;
	for (const [src, attendu] of casDefaut) {
		const n = requisParDefaut(src).length;
		if (n !== attendu) {
			console.error(`  ✗ « ${src} » → ${n}, attendu ${attendu}`);
			ko++;
		}
	}
	for (const [src, attendu] of cas) {
		const n = pliageManquant(src).length;
		if (n !== attendu) {
			console.error(`  ✗ « ${src.slice(0, 64).replace(/\n/g, ' ⏎ ')} » → ${n}, attendu ${attendu}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.\n`);
		process.exit(1);
	}
	console.log(
		`✓ Auto-test : ${cas.length + casDefaut.length + casAppel.length} cas — le pliage manquant est vu, chez le porteur comme chez l'appelant.`,
	);
	process.exit(process.exitCode ?? 0);
}

const fautifs = [];
let porteurs = 0;
//  Les PORTEURS : ils acceptent `pliable` et rendent une section du cadre.
const nomsPorteurs = [];
for (const chemin of svelte(RACINE)) {
	const source = readFileSync(chemin, 'utf8');
	if (/export\s+let\s+pliable\b/.test(source) && source.includes('<SectionFormulaire'))
		nomsPorteurs.push(
			chemin
				.split(sep)
				.pop()
				.replace(/\.svelte$/, ''),
		);
}
const horsCadreServis = new Set();
let appels = 0;
for (const chemin of svelte(RACINE)) {
	const source = readFileSync(chemin, 'utf8');
	const relatif = relative(RACINE, chemin).split(sep).join('/');
	const fautes = appelantsSansPliage(source, nomsPorteurs);
	appels += nomsPorteurs.reduce((n, p) => n + balisesOuvrantes(source, p).length, 0);
	if (fautes.length && HORS_CADRE[relatif]) {
		horsCadreServis.add(relatif);
		continue;
	}
	for (const f of fautes)
		fautifs.push(
			`src/${relatif}:${f.ligne}  <${f.porteur}> ` +
				(f.quoi === 'absent'
					? "appelé sans `pliable` — le pliage de la déclaration n'arrive pas"
					: '`pliable` écrit en dur — lire `pliageDe(<entité>, …)`'),
		);
}
for (const f of Object.keys(HORS_CADRE))
	if (!horsCadreServis.has(f))
		fautifs.push(`src/${f}  exception HORS_CADRE qui ne sert plus — la retirer`);
if (nomsPorteurs.length === 0 || appels === 0) {
	console.error(
		'\n✗ Cas zéro : aucun porteur ou aucun appel trouvé — le contrôle ne mesure rien.\n',
	);
	process.exit(1);
}
for (const chemin of svelte(RACINE)) {
	const source = readFileSync(chemin, 'utf8');
	if (!source.includes('SECTIONS_LIBELLE.')) continue;
	if (!source.includes('<SectionFormulaire')) continue;
	porteurs++;
	const relatif = relative(RACINE, chemin).split(sep).join('/');
	for (const m of requisParDefaut(source)) {
		fautifs.push(
			`src/${relatif}:${m.ligne}  \`${m.nom}\` vaut \`true\` par défaut — l'astérisque ` +
				'doit se lire dans la déclaration (`requisDe`), pas venir du composant',
		);
	}
	for (const m of pliageManquant(source)) {
		fautifs.push(
			`src/${relatif}:${m.ligne}  ` +
				(m.quoi === 'requis en dur'
					? '`requis` écrit dans le composant, pas lu dans la déclaration'
					: 'section du cadre rendue sans `pliable`'),
		);
	}
}

//  Cas zéro : plus aucun porteur, et le contrôle ne mesure plus rien.
if (porteurs === 0) {
	console.error(
		'\n✗ Cas zéro : aucun composant ne rend une section du cadre — le motif a\n' +
			'  dérivé. Ne pas lire ceci comme un succès.\n',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error(`\n✗ ${fautifs.length} section(s) du cadre dont le pliage n'arrive jamais :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		"\n  La table déclare `pliee`, et la section reste ouverte : le chemin n'existe" +
			"\n  pas. C'est l'angle mort des composants PORTEURS — ils ne s'écrivent pas" +
			'\n  dans l’écran, donc rien ne les gouverne.' +
			'\n\n  → `export let pliable = false;` puis `{pliable}` sur la section.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Pliage : ${porteurs} composant(s) portent une section du cadre, tous en transmettent le pliage ; ` +
		`${appels} appel(s) de ${nomsPorteurs.length} porteur(s), tous le reçoivent de la déclaration.`,
);
