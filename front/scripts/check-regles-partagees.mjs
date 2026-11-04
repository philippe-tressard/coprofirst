/**
 * **Une règle que deux clients affichent se calcule côté serveur** (#2501).
 *
 * ## Pourquoi il existe (03/11/2026)
 *
 * CoproFirst a deux clients : le site et l'app iOS. L'app ne parle qu'au contrat
 * de l'API et ne recopie aucune règle du front — elle ne peut donc afficher que ce
 * que l'API lui sert. Le libellé du logement (« Bât. A, T3, 2ème ») se composait
 * dans `utils.ts` : l'API ne le servait pas, et l'app n'affichait rien (#2500).
 * La règle du socle : `standards/09-livraison-et-mep.md` §8, règle 1.
 *
 * ## Ce qu'il tient
 *
 * Chaque règle que les deux clients affichent est DÉCLARÉE dans
 * `check-regles-partagees.regles.mjs`, sous le nom qu'elle porte dans le front.
 * Pour chacune :
 *
 * - **servie** (`api`, sans `migration`) : la fonction du serveur existe (témoin),
 *   et AUCUN fichier de `src/` ne définit plus la règle — le front lit le champ ;
 * - **à migrer** (`migration` : ticket et raison) : le front la calcule encore, et
 *   c'est une dérogation nommée. Elle doit servir : une règle que le front ne
 *   définit plus fait échouer, pour qu'on retire la dérogation ;
 * - **ni l'un ni l'autre** : la règle est écrite dans le front seulement (ou
 *   recopiée à côté de celle du serveur), sans dérogation — c'est la faute.
 *
 * Cas zéro : aucun fichier lu, ou aucune règle déclarée, rend un échec.
 *
 * ⚠️ Il ne DÉCOUVRE pas une règle : il tient celles qu'on a déclarées partagées.
 * L'inventaire de départ, et ce qui reste au front par décision, est écrit dans
 * #2501 ; une règle neuve qu'un second client affiche s'ajoute à la déclaration.
 *
 * Lancer : node scripts/check-regles-partagees.mjs [--selftest]
 */
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { fichiersSources, rejouerAttendus } from './lib-source-unique.mjs';
import { REGLES_PARTAGEES } from './check-regles-partagees.regles.mjs';

const RACINE_DEPOT = fileURLToPath(new URL('../../', import.meta.url));

/** Une définition de `nom` dans un module ou le script d'un composant. */
function motifDefinition(nom) {
	return new RegExp(
		`(?:^|[\\s;])(?:export\\s+)?(?:(?:async\\s+)?function\\s*\\*?\\s*${nom}\\b|(?:const|let|var)\\s+${nom}\\s*[=:])`,
	);
}

/** Les `chemin:ligne` de `contenus` qui définissent `nom`, hors commentaires. PURE. */
export function definitionsFront(contenus, nom) {
	const motif = motifDefinition(nom);
	const trouvees = [];
	for (const [chemin, texte] of Object.entries(contenus)) {
		neutraliserCommentaires(texte)
			.split('\n')
			.forEach((ligne, i) => {
				if (motif.test(ligne)) trouvees.push(`${chemin}:${i + 1}`);
			});
	}
	return trouvees;
}

/** `api/app/x.py#fonction` → `[chemin, fonction]`. */
function cibleApi(api) {
	const [chemin, fonction] = api.split('#');
	return [chemin, fonction];
}

/** Le texte définit-il la fonction Python `fonction` ? PURE. */
export function definitPython(texte, fonction) {
	return new RegExp(`^\\s*(?:async\\s+)?def\\s+${fonction}\\s*\\(`, 'm').test(texte ?? '');
}

/**
 * Le relevé, sans entrée ni sortie. PURE.
 *
 * @param {Record<string, object>} regles   nom dans le front → déclaration
 * @param {Record<string, string>} front    chemin → texte (sous `src/`)
 * @param {Record<string, string|null>} api chemin → texte (null : fichier absent)
 */
export function releveRegles(regles, front, api) {
	const r = {
		lus: Object.keys(front).length,
		declarees: Object.keys(regles).length,
		fautes: [],
		mortes: [],
		temoins: [],
		incompletes: [],
	};
	for (const [nom, d] of Object.entries(regles)) {
		const defs = definitionsFront(front, nom);
		if (!d.quoi) r.incompletes.push(`${nom} : « quoi » manque`);
		if (d.api) {
			const [chemin, fonction] = cibleApi(d.api);
			if (!definitPython(api[chemin], fonction)) r.temoins.push(`${nom} → ${d.api}`);
		}
		if (d.migration) {
			const { ticket, raison } = d.migration;
			if (!/^#\d+$/.test(ticket ?? '') || !raison) {
				r.incompletes.push(`${nom} : une dérogation porte un ticket (#NNNN) et sa raison`);
			}
			if (!defs.length) r.mortes.push(nom);
			continue;
		}
		if (!d.api) {
			r.incompletes.push(`${nom} : ni fonction du serveur (« api ») ni dérogation`);
		}
		for (const ou of defs) {
			r.fautes.push(
				`${ou} — « ${nom} » ${d.api ? `recopie ${d.api}` : 'écrite seulement dans le front'}`,
			);
		}
	}
	return r;
}

/** Les cas : le premier est la faute que ce contrôle existe pour relever. */
function selftest() {
	const ecran = { 'src/lib/t.ts': 'export function estUrgent(t) { return t.p === "haute"; }' };
	const vide = { 'src/lib/t.ts': 'export const rien = 1;' };
	const py = { 'api/u.py': 'def est_urgent(t):\n    return t.p == "haute"\n' };
	const quoi = 'urgence';
	const derog = { ticket: '#1', raison: 'l’app n’en a pas encore besoin' };
	const cas = [
		[
			'une règle partagée écrite seulement dans le front ÉCHOUE',
			releveRegles({ estUrgent: { quoi } }, ecran, {}).fautes.length,
			1,
		],
		[
			'…et sa déclaration seule ne suffit pas : il faut une source au serveur',
			releveRegles({ estUrgent: { quoi } }, vide, {}).incompletes.length,
			1,
		],
		[
			'une règle recopiée à côté de celle du serveur échoue aussi',
			releveRegles({ estUrgent: { quoi, api: 'api/u.py#est_urgent' } }, ecran, py).fautes.length,
			1,
		],
		[
			'déclarée à migrer, avec ticket et raison, elle passe',
			releveRegles({ estUrgent: { quoi, migration: derog } }, ecran, {}),
			{ lus: 1, declarees: 1, fautes: [], mortes: [], temoins: [], incompletes: [] },
		],
		[
			'une dérogation sans ticket est incomplète',
			releveRegles({ estUrgent: { quoi, migration: { raison: 'x' } } }, ecran, {}).incompletes
				.length,
			1,
		],
		[
			'une dérogation qui ne sert plus (le front ne la calcule plus) échoue',
			releveRegles({ estUrgent: { quoi, migration: derog } }, vide, {}).mortes,
			['estUrgent'],
		],
		[
			'servie : fonction du serveur présente, front muet — rien à dire',
			releveRegles({ estUrgent: { quoi, api: 'api/u.py#est_urgent' } }, vide, py),
			{ lus: 1, declarees: 1, fautes: [], mortes: [], temoins: [], incompletes: [] },
		],
		[
			'servie, mais la fonction du serveur a disparu : le témoin le dit',
			releveRegles({ estUrgent: { quoi, api: 'api/u.py#est_urgent' } }, vide, { 'api/u.py': '' })
				.temoins.length,
			1,
		],
		[
			'un commentaire qui cite la règle n’est pas une définition',
			definitionsFront(
				{ 'a.ts': '// function estUrgent(t)\n/* const estUrgent = 1 */' },
				'estUrgent',
			),
			[],
		],
		[
			'le script d’un composant, une constante dérivée : des définitions',
			definitionsFront(
				{
					'a.svelte': '<script>\n\tfunction estUrgent(t) {}\n</script>',
					'b.ts': 'export const estUrgent = derived(x, f);',
				},
				'estUrgent',
			),
			['a.svelte:2', 'b.ts:1'],
		],
		[
			'un appel n’est pas une définition, ni un nom qui la prolonge',
			definitionsFront(
				{ 'a.ts': 'const x = estUrgent(t);\nfunction estUrgente() {}' },
				'estUrgent',
			),
			[],
		],
		['aucun fichier lu se compte zéro', releveRegles({}, {}, {}).lus, 0],
	];
	return rejouerAttendus(cas);
}

function principal() {
	const front = {};
	for (const f of fichiersSources('src', ['.ts', '.js', '.svelte'])) {
		front[f] = readFileSync(f, 'utf8');
	}
	const api = {};
	for (const d of Object.values(REGLES_PARTAGEES)) {
		if (!d.api) continue;
		const [chemin] = cibleApi(d.api);
		const absolu = RACINE_DEPOT + chemin;
		api[chemin] = existsSync(absolu) ? readFileSync(absolu, 'utf8') : null;
	}
	const r = releveRegles(REGLES_PARTAGEES, front, api);
	//  Cas zéro (standards/04 §2) : rien lu, ou rien déclaré, n'est pas « conforme ».
	if (!r.lus || !r.declarees) {
		console.error(`✗ ${r.lus} fichier(s) lu(s), ${r.declarees} règle(s) déclarée(s) : INCONNU.`);
		return 1;
	}
	let ko = 0;
	const dire = (titre, lignes, conseil) => {
		if (!lignes.length) return;
		ko = 1;
		console.error(`\n✗ ${titre} :`);
		for (const l of lignes) console.error(`   ${l}`);
		console.error(`  ${conseil}`);
	};
	dire(
		'Règle partagée calculée dans le front',
		r.fautes,
		"La servir par l'API et la lire (comme `libelle_logement`, #2500), ou la déclarer à migrer : `migration: { ticket, raison }`.",
	);
	dire(
		'Dérogation qui ne sert plus — le front ne définit plus la règle',
		r.mortes,
		'Retirer `migration`, et nommer la fonction du serveur dans `api`.',
	);
	dire(
		'Fonction du serveur introuvable',
		r.temoins,
		'Le chemin ou le nom de `api` ne désigne plus rien : la source unique manque.',
	);
	dire(
		'Déclaration incomplète',
		r.incompletes,
		'Voir l’en-tête de `check-regles-partagees.regles.mjs`.',
	);
	if (!ko) {
		const aMigrer = Object.values(REGLES_PARTAGEES).filter((d) => d.migration).length;
		console.log(
			`✓ Règles partagées : ${r.declarees} déclarée(s), ${r.declarees - aMigrer} servie(s) par l'API, ${aMigrer} à migrer avec leur ticket (${r.lus} fichiers lus).`,
		);
	}
	return ko;
}

process.exit(process.argv.includes('--selftest') ? selftest() : principal());
