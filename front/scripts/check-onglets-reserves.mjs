#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Un onglet réservé n'apparaît qu'aux personnes que le SERVEUR laisse entrer.
 *
 * ## Pourquoi ce contrôle (#1039, audit du 19/09/2026)
 *
 * `residence/+page.svelte` rendait la rangée d'onglets **sans rien masquer** :
 * l'onglet « 📒 Carnet d'entretien » s'affichait donc à un locataire, alors que
 * `api/app/routers/carnet.py` répond **403** (`require_proprietaire` —
 * propriétaire, conseil syndical ou admin). Le locataire voyait une entrée,
 * cliquait, et obtenait une erreur : le contraire de la règle que `Nav.svelte`
 * applique déjà au menu.
 *
 * ⚠️ Masquer ne protège rien — `BarreOnglets` le dit dans sa propre docstring, et
 * le serveur reste le gardien. Mais un écran qui propose un geste interdit use la
 * confiance : l'utilisateur apprend que l'application se trompe, et il cesse de
 * distinguer ses refus légitimes de ses bogues.
 *
 * ## Le contrôle tient les DEUX bouts
 *
 * Une table déclarée ne vaudrait rien si elle ne parlait que du front : elle
 * dirait « cet onglet est masqué », sans jamais vérifier qu'il doit l'être. Pour
 * chaque entrée, ce contrôle exige donc :
 *
 *   1. que le **routeur API** cité porte encore la dépendance déclarée — si le
 *      serveur s'ouvre ou se ferme, la déclaration devient fausse et rougit ;
 *   2. que l'onglet porte `reserve: '<prédicat>'` dans `pages.ts` — là où celui
 *      qui ajoute un onglet regarde ;
 *   3. que l'**onglet existe** dans `pages.ts` — un onglet renommé ou retiré
 *      laisserait sinon une entrée qui protège un écran disparu.
 *
 * ## 🔴 Ce que ce contrôle NE couvre PAS, et il faut le savoir
 *
 * Il ne découvre pas tout seul qu'un onglet neuf appelle une route réservée :
 * aucune cartographie ne relie une route SvelteKit à son routeur FastAPI, et
 * l'inventer donnerait des correspondances plausibles et parfois fausses. Il
 * vérifie ce qui est **déclaré** ici, et rien d'autre (`standards/04` §12 — un
 * contrôle borné dit ce qu'il ne couvre pas).
 *
 * Le geste qui reste humain, et qui est écrit dans la checklist de `CLAUDE.md` :
 * en ajoutant un onglet, confronter sa route à la dépendance d'auth de l'API
 * qu'elle appelle, et l'inscrire ici s'il est réservé.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ICI = dirname(fileURLToPath(import.meta.url));
const FRONT = join(ICI, '..');
const RACINE = join(FRONT, '..');

/**
 * Les onglets réservés, et ce qui le justifie **des deux côtés**.
 *
 * `predicat` est le store qui doit décider du masquage ; `dependance` la
 * dépendance FastAPI qui refuse côté serveur. Les deux doivent dire la même
 * chose — c'est au lecteur de cette table de s'en assurer, et au contrôle de
 * vérifier qu'aucune des deux n'a bougé depuis.
 */
const RESERVES = [
	{
		page: 'residence',
		onglet: 'carnet',
		predicat: 'proprioOuCS',
		routeurApi: 'api/app/routers/carnet.py',
		dependance: 'require_proprietaire',
		pourquoi:
			'décret n° 2001-477 — le carnet est destiné aux copropriétaires, et il porte ' +
			'des références de contrats qui ne regardent pas un locataire',
	},
	{
		//  11/10/2026 : venu de l'Espace CS, ouvert aux copropriétaires. La
		//  dépendance prend `require_proprietaire` et y ajoute la case de
		//  l'administration ; la page MASQUE en plus l'onglet quand l'usage n'est
		//  pas ouvert aux copropriétaires (`GET /reglement/acces`).
		page: 'residence',
		onglet: 'reglement',
		predicat: 'proprioOuCS',
		routeurApi: 'api/app/routers/reglement.py',
		dependance: 'require_questions_reglement',
		pourquoi:
			"un appel facturé, ouvert aux copropriétaires par l'administration — ni " +
			'aux locataires, ni aux mandataires, ni au syndic',
	},
	//  Les onglets Kanban et Archives du Calendrier sont partis avec lui le
	//  23/09/2026 (#1092). Ceux d'Affaires montrent des affaires que le serveur
	//  filtre déjà (`ticket_visible`) : ils n'ont pas de place dans cette table,
	//  qui n'admet qu'un onglet dont la route REFUSE.
	//
	{
		//  13/10/2026 (#1880) : le registre des installations, chez la référence.
		//  La page d'administration MASQUE en plus l'onglet hors de la référence.
		page: 'admin',
		onglet: 'installations',
		predicat: 'operateur',
		routeurApi: 'api/app/routers/admin/installations.py',
		dependance: 'require_operateur',
		pourquoi:
			"le registre et le contact des administrateurs d'installation ne regardent que " +
			"l'opérateur de la plateforme (§4.11, règle 7) — jamais l'administrateur de copropriété",
	},
	{
		//  21/10/2026 (#2062) : le bloc « Installation » quitte Maintenance pour son
		//  onglet. Le serveur le refusait déjà à l'administrateur de copropriété ;
		//  Maintenance, elle, reste ouverte aux deux (`ouvertOperateur`).
		page: 'admin',
		onglet: 'installation',
		predicat: 'operateur',
		routeurApi: 'api/app/routers/admin/installation.py',
		dependance: 'require_operateur',
		pourquoi:
			"le rôle, la version et l'inscription au registre de l'installation sont la " +
			"supervision de l'opérateur de la plateforme (#1750) — jamais celle de l'administrateur",
	},
	//  18/10/2026 (#2075) : la Communauté s'ouvre au syndic et au mandataire pour
	//  son SEUL onglet Avis. Les trois autres leur restent fermés — le serveur
	//  refuse par `exiger_acces` (le profil), l'écran masque et redirige vers l'Avis.
	...[
		['sondages', 'api/app/routers/sondages/crud.py'],
		['idees', 'api/app/routers/idees.py'],
		['annonces', 'api/app/routers/annonces.py'],
	].map(([onglet, routeurApi]) => ({
		page: 'communaute',
		onglet,
		predicat: 'nonGestionnaire',
		routeurApi,
		dependance: 'exiger_acces',
		pourquoi:
			"l'espace entre résidents : ni le syndic, ni un mandataire — l'avis sur " +
			"l'application, seul, leur est ouvert",
	})),
	//  ⚠️ Le Kanban d'Affaires porte pourtant `reserve: 'nonLocataire'` depuis
	//  le 28/09/2026 (#1428) — arbitré à l'écran : un locataire ne suit pas les
	//  dossiers. C'est un masque d'ERGONOMIE, pas une protection : ce qu'il
	//  cacherait, `ticket_visible` le refuse déjà affaire par affaire. Ne pas
	//  l'inscrire ici avec une dépendance inventée.
];

//  Les pages vivent dans DEUX fichiers depuis le découpage de la table (`pages.ts`
//  et `pages-roles.ts`, où sont les onglets d'administration) : lire l'un seul
//  rendait invisible tout onglet de l'autre.
const pages = ['src/lib/pages.ts', 'src/lib/pages-roles.ts']
	.map((f) => readFileSync(join(FRONT, f), 'utf8'))
	.join('\n');
const fautes = [];

for (const r of RESERVES) {
	//  1. Le serveur refuse-t-il encore ?
	const api = readFileSync(join(RACINE, r.routeurApi), 'utf8');
	if (!api.includes(r.dependance)) {
		fautes.push(
			`${r.routeurApi} ne porte plus \`${r.dependance}\` : la réservation de l'onglet ` +
				`« ${r.onglet} » n'a peut-être plus lieu d'être, ou le serveur s'est ouvert ` +
				`sans que l'écran le sache.`,
		);
	}

	//  2. L'onglet existe-t-il encore ?
	if (!new RegExp(`id:\\s*'${r.onglet}'`).test(pages)) {
		fautes.push(
			`l'onglet « ${r.onglet} » n'existe plus dans pages.ts : retirer son entrée de ` +
				`RESERVES, sinon elle protège un écran disparu.`,
		);
	}

	//  3. La réservation est-elle déclarée SUR l'onglet, avec le bon prédicat ?
	//
	//  Elle vivait d'abord dans la page, sous forme de `masques` — et ce contrôle
	//  lisait alors la balise `<BarreOnglets>`. Deux défauts, tous deux réels :
	//  la page pouvait calculer la liste dix lignes plus haut (le motif a rougi à
	//  tort dès la première factorisation, `standards/04` §40), et surtout RIEN
	//  n'obligeait une page à déclarer quoi que ce soit — `residence` ne masquait
	//  pas, et il n'existait aucun endroit où cela se voyait.
	//
	//  Déclarée avec l'onglet, la réservation est là où celui qui ajoute un onglet
	//  regarde. `BarreOnglets` l'applique des deux côtés, pour toutes les pages à
	//  la fois.
	//  ⚠️ L'onglet se désigne par PAGE **et** id : « archives » existe deux fois —
	//  celui du calendrier, et un sous-onglet de « Mes lots & accès ». Chercher
	//  l'id seul lisait le premier venu, et ce contrôle a rougi à tort là-dessus
	//  avant d'être repris.
	const segmentPage = pages.split(/\n\t\{\n/).find((b) => b.includes(`id: '${r.page}'`));
	const bloc = segmentPage?.match(new RegExp(`id:\\s*'${r.onglet}'[\\s\\S]{0,800}?\\n\\t{3}\\}`));
	if (!bloc) {
		fautes.push(
			`l'onglet « ${r.onglet} » de la page « ${r.page} » n'a pas pu être relu dans pages.ts.`,
		);
	} else if (!new RegExp(`reserve:\\s*'${r.predicat}'`).test(bloc[0])) {
		fautes.push(
			`pages.ts : l'onglet « ${r.onglet} » ne porte pas \`reserve: '${r.predicat}'\` — ` +
				`il s'affichera à tout le monde, alors que sa route répond 403.`,
		);
	}
}

//  Auto-test : la table doit être non vide, sinon ce contrôle passe au vert en ne
//  mesurant rien — le faux vert par ensemble vide (`standards/04` §1 et §27).
if (RESERVES.length === 0) {
	console.error('✗ RESERVES est vide : ce contrôle ne mesure plus rien.');
	process.exit(2);
}
console.log(`✓ Auto-test : ${RESERVES.length} onglet(s) réservé(s) déclaré(s), table non vide.`);

if (fautes.length > 0) {
	console.error(
		`\n✗ ${fautes.length} écart(s) entre ce que l'écran montre et ce que le serveur permet :\n`,
	);
	for (const f of fautes) console.error(`  • ${f}`);
	console.error(
		'\n  Un onglet réservé se masque par la prop `masques` de <BarreOnglets>, sur le\n' +
			"  MÊME prédicat que la dépendance d'auth de sa route.\n",
	);
	process.exit(1);
}

console.log("✓ Chaque onglet réservé est masqué sur le prédicat de sa route d'API.");
