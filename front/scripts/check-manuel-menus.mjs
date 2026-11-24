/**
 * Garde-fou : le manuel annonce les MENUS du site, et le bon public pour chacun.
 *
 * ## 🔴 Pourquoi (#651, 02/09/2026)
 *
 * Le sujet de #651 tient en une phrase : *« le manuel RECOPIE des tables que le
 * code fait évoluer, et rien ne les rapproche »*. Périmètres, plafonds de pièces
 * jointes, types acceptés, table des pages : à chaque fois, la copie a divergé.
 *
 * La section « Les écrans » a remplacé une grille de captures d'écran datées de
 * mars, illisibles à 300 px et aux boutons inertes (signalé à l'écran). Ce qui la
 * remplace porte deux informations : **quels menus existent**, et **qui peut les
 * voir**. Ce sont exactement deux tables que le code tient déjà :
 *
 *   · `front/src/lib/pages.ts` — les pages et leur route ;
 *   · `front/src/lib/components/Nav.svelte` — qui voit quelle entrée.
 *
 * En écrire une troisième en prose, c'était refaire le défaut le jour même où on
 * le corrige. D'où ce contrôle.
 *
 * ## Ce qu'il vérifie, et pourquoi il lit une STRUCTURE et non de la prose
 *
 * Chaque carte porte \`data-page\` et \`data-acces\`. Le contrôle compare :
 *
 *   1. l'ensemble des routes citées = l'ensemble des routes de \`pages.ts\` ;
 *   2. le public annoncé = ce que \`Nav.svelte\` applique.
 *
 * ## L'ORDRE : vérifié depuis le 22/09/2026, et jusqu'où
 *
 * Ce paragraphe disait l'inverse — *« ce contrôle vérifie l'ENSEMBLE des routes
 * et le PUBLIC de chacune, jamais leur ordre »* — au motif que l'ordre vit dans
 * `pages_order`, une clé que l'administration réordonne.
 *
 * 🔴 C'était vrai de l'ordre **servi**, faux de l'ordre **par défaut**. Les
 * maquettes annoncent en toutes lettres « le menu le plus complet, dans son
 * ordre par défaut » : cet ordre-là, le code le porte, et il se compare. Il ne
 * l'était pas, et les deux listes écrites à la main avaient dérivé — signalé à
 * l'écran, capture à l'appui, huit entrées sur treize au mauvais rang.
 *
 * ⚠️ Ce qui reste hors de portée, et c'est #1114 : l'ordre **réellement servi**
 * si la copropriété l'a réordonné. Aucune sonde ne le compare au défaut — et
 * `pages_order` porte encore un identifiant qui n'existe plus (`acces-badges`,
 * retiré du menu le 12/09/2026), que `Nav.svelte` ignore en silence.
 *
 * Pour le relever :
 *
 *     curl -s https://5hostachy.fr/api/config | grep -o '"pages_order":"[^"]*"'
 *
 * ⚠️ **La prose ne se lit pas comme une table** — #651 le dit lui-même, et un
 * contrôle qui crie sur du légitime finit désarmé. Les attributs sont la réponse :
 * ils rendent la table lisible par une machine sans contraindre le texte, qui
 * reste libre.
 *
 * Usage : npm run lint:manuel-menus
 */
import { readFileSync } from 'node:fs';
import { FICHIERS_PAGES, blocsDePages } from './lib-pages.mjs';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const MANUEL = `${RACINE}../docs/manuel-utilisateur.html`;
const NAV = `${RACINE}src/lib/components/Nav.svelte`;

/**
 * Le public de chaque route : l'`acces` que sa page DÉCLARE (`pages.ts`,
 * `pages-roles.ts`), le même que le serveur confronte à `acces_menu` (#2969).
 * Il ne se déduit plus de `Nav.svelte`, qui ne raisonne plus sur aucun rôle : la
 * table tenue à la main que ce fichier portait (et son « tous » par défaut, qui
 * cachait que le syndic n'avait aucune entrée, #2905) a disparu.
 */
function publicsDeclares() {
	const publics = new Map();
	for (const bloc of blocsDePages()) {
		const href = bloc.match(/^\t\thref: '([^']+)',$/m);
		if (!href) continue;
		const acces = bloc.match(/^\t\tacces: '([^']+)',$/m);
		publics.set(href[1], acces ? acces[1] : null);
	}
	return publics;
}

const manuel = readFileSync(MANUEL, 'utf8');
//  🔴 DEUX fichiers depuis le 12/09/2026 (#928) : les pages réservées à un rôle
//  vivent dans `pages-roles.ts`. Sans cette seconde lecture, le contrôle a
//  aussitôt déclaré que le manuel citait des routes « qui n'existent pas » —
//  elles existaient, il ne les voyait plus. La portée du contrôle fait partie du
//  contrôle.
const pages = FICHIERS_PAGES.map((f) => readFileSync(f, 'utf8')).join('');
const nav = readFileSync(NAV, 'utf8');

const erreurs = [];
const PUBLICS = publicsDeclares();

// ── Les routes du site ──────────────────────────────────────────────────────
const routes = new Set([...pages.matchAll(/^\t\thref: '([^']+)',$/gm)].map((m) => m[1]));
//  🔴 CAS ZÉRO — sans routes, tout le reste serait vert sans rien lire.
if (routes.size < 10) {
	console.error(
		`✗ Cas zéro : ${routes.size} route(s) trouvée(s) dans pages.ts, 10 au minimum. ` +
			'La forme du fichier a changé — ce contrôle ne mesure plus rien.',
	);
	process.exit(1);
}

// ── Ce que le manuel annonce ────────────────────────────────────────────────
const cartes = new Map(
	[...manuel.matchAll(/data-page="([^"]+)"\s+data-acces="([^"]+)"/g)].map((m) => [m[1], m[2]]),
);
if (cartes.size === 0) {
	console.error(
		'✗ Cas zéro : aucune carte `data-page` dans le manuel. La section « Les écrans » ' +
			'a-t-elle été renommée ou retirée ? Ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

for (const route of routes) {
	if (!cartes.has(route)) {
		erreurs.push(`le menu ${route} existe dans pages.ts et le manuel ne le cite pas`);
		continue;
	}
	const attendu = PUBLICS.get(route);
	if (!attendu) {
		erreurs.push(`le menu ${route} : sa page ne déclare pas son public (\`acces\`)`);
	} else if (cartes.get(route) !== attendu) {
		erreurs.push(
			`le menu ${route} : le manuel annonce « ${cartes.get(route)} », ` +
				`sa page déclare « ${attendu} »`,
		);
	}
}
for (const [route] of cartes) {
	//  `profil` n'a pas de route de menu (href null) et c'est légitime : on y accède
	//  par l'avatar. Il est cité parce que le lecteur le cherche.
	if (route !== 'profil' && !routes.has(route)) {
		erreurs.push(`le manuel cite ${route}, qui n'existe pas dans pages.ts`);
	}
}

// ── Nav.svelte ne raisonne sur aucun rôle ni statut (#2969) ─────────────────
//  Le menu LIT `acces_menu` ; une branche `href === '/x'`, ou un rôle, ou un
//  statut écrit en littéral, referait la copie que les apps avaient recopiée.
const LITTERAUX_INTERDITS =
	/href === '|'(propriétaire|résident|externe|conseil_syndical|admin|operateur|syndic|mandataire|aidant|locataire|admin_technique)'/g;
for (const m of nav.matchAll(LITTERAUX_INTERDITS)) {
	erreurs.push(
		`Nav.svelte écrit « ${m[0]} » : qui voit quelle entrée se lit dans \`acces_menu\` ` +
			'(#lib/acces-menu), jamais dans un rôle ou un statut',
	);
}
if (!/pageAuMenu\(/.test(nav)) {
	erreurs.push(
		'Nav.svelte ne filtre plus le menu par `pageAuMenu` — le contrôle ne mesure plus rien',
	);
}

// ── Les DEUX MAQUETTES du menu (04/09/2026) ────────────────────────────────
//  Elles montrent le même menu à deux endroits : celui de l'ordinateur, toujours
//  affiché, et celui du téléphone, replié. C'est la COMPARAISON qui fait le
//  propos — si les deux listes divergent, le lecteur ne compare plus rien, il lit
//  deux menus dont l'un est faux, sans savoir lequel.
//
//  ⚠️ On ne vérifie PAS que les maquettes citent les mêmes routes que la grille :
//  une maquette est une illustration, elle peut légitimement s'arrêter avant la
//  fin. Ce qu'on exige, c'est qu'elles soient d'accord ENTRE ELLES.
/**
 *  L'ordre du menu PAR DÉFAUT, dérivé des deux tables du code.
 *
 *  `pages.ts` porte les écrans ouverts à tous, `pages-roles.ts` ceux réservés —
 *  et le menu les rend dans cet ordre-là quand aucun `pages_order` n'a été
 *  enregistré. Les maquettes du manuel annoncent ce même ordre : elles ne le
 *  recopient donc pas, elles s'y comparent.
 */
function ordreParDefaut() {
	const libelle = (bloc) => {
		const m = bloc.match(/navLabel: '([^']+)'/);
		return m ? m[1] : null;
	};
	const noms = [];
	for (const bloc of blocsDePages()) {
		//  Une page sans `href` ne paraît pas au menu (profil, notifications).
		if (/href: null/.test(bloc)) continue;
		const nom = libelle(bloc);
		if (nom) noms.push(nom);
	}
	return noms;
}

const duo = manuel.match(/<div class="maq-duo">([\s\S]*?)<\/div>\s*<p class="maq-note"/);
if (!duo) {
	erreurs.push('les deux maquettes du menu sont introuvables (`.maq-duo`)');
} else {
	const figures = duo[1].split('<figure class="maq">').slice(1);
	if (figures.length !== 2) {
		erreurs.push(`${figures.length} maquette(s) de menu au lieu de 2`);
	} else {
		const compte = (f) => (f.match(/class="maq-item/g) || []).length;
		const [bureau, mobile] = figures.map(compte);
		//  Cas zéro : deux listes vides seraient « d’accord », et ne montreraient rien.
		if (bureau < 5 || mobile < 5) {
			erreurs.push(`maquettes quasi vides (${bureau} et ${mobile} entrées) — rien à comparer`);
		} else if (bureau !== mobile) {
			erreurs.push(
				`les deux maquettes divergent : ${bureau} entrées sur ordinateur, ` +
					`${mobile} sur téléphone — c'est pourtant le même menu`,
			);
		}

		//  ════════════════════════════════════════════════════════════════════
		//  L'ORDRE DES ENTRÉES (22/09/2026, signalé à l'écran)
		//  ════════════════════════════════════════════════════════════════════
		//
		//  🔴 Les maquettes portaient un ordre écrit à la main, et il ne
		//  correspondait plus à rien : ni au menu en service, ni au défaut du
		//  code. L'en-tête de ce contrôle DÉCLARAIT ne pas vérifier l'ordre — au
		//  motif qu'il vit dans `pages_order`, une clé administrable. C'était
		//  vrai pour l'ordre SERVI ; ça ne l'était pas pour l'ordre PAR DÉFAUT,
		//  que le code porte et que les maquettes annoncent en toutes lettres.
		//
		//  Ce qui est comparé est donc exactement ce que le manuel promet : « le
		//  menu le plus complet, dans son ordre PAR DÉFAUT ».
		//
		//  ⚠️ Ce qui reste hors de portée : l'ordre réellement servi, s'il a été
		//  réordonné en administration (#1114). Une limite nommée vaut mieux
		//  qu'une limite tue.
		//  ⚠️ Les entités HTML se décodent avant de comparer : le manuel écrit
		//  « Mes lots &amp; accès », le code « Mes lots & accès ». Sans cela, une
		//  entrée correcte serait refusée pour une raison d'écriture.
		const libelles = (f) =>
			[...f.matchAll(/class="maq-item"><span>([^<]+)<\/span>/g)].map((m) =>
				m[1]
					.trim()
					.replace(/&amp;/g, '&')
					.replace(/&nbsp;/g, ' '),
			);
		const attendus = ordreParDefaut();
		for (const [nom, figure] of [
			['ordinateur', figures[0]],
			['téléphone', figures[1]],
		]) {
			const lus = libelles(figure);
			if (lus.length === 0) {
				erreurs.push(`maquette ${nom} : aucun libellé lisible — le motif a dérivé`);
			} else if (lus.join(' · ') !== attendus.join(' · ')) {
				erreurs.push(
					`maquette ${nom} — l'ordre du menu ne suit pas le code :\n` +
						`        manuel : ${lus.join(' · ')}\n` +
						`        code   : ${attendus.join(' · ')}`,
				);
			}
		}

		//  🔴 LE BOUTON DU TÉLÉPHONE DOIT ÊTRE DESSINÉ ET EXPLIQUÉ (04/09/2026).
		//  Il portait le caractère ☰, qui ne dit rien à qui n'a jamais fait le
		//  rapprochement — c'est-à-dire au lecteur de ce guide, qui n'est pas
		//  informaticien. Un symbole que le lecteur doit déjà connaître n'explique
		//  rien : il trie ceux qui savaient déjà.
		const tel = figures[1];
		if (!/class="maq-burger"[^>]*>\s*<svg/.test(tel)) {
			erreurs.push(
				"le bouton du menu téléphone n'est pas dessiné (un caractère ne s'imprime pas pareil, et ne s'explique pas)",
			);
		}
		//  ⚠️ L'attribut ENTIER, pas la sous-chaîne : `maq-explication-icone` la
		//  contient, et le contrôle restait vert sur une explication supprimée dont
		//  il ne subsistait que l'icône. Trouvé en éprouvant le contrôle, pas en le
		//  relisant.
		if (!tel.includes('class="maq-explication"')) {
			erreurs.push(
				'le bouton du menu téléphone est montré sans être expliqué (`.maq-explication` dans sa figure)',
			);
		}
	}
}

if (erreurs.length > 0) {
	console.error('✗ Le manuel et le code ne disent pas la même chose des menus :');
	for (const e of erreurs) console.error(`    ${e}`);
	console.error('');
	console.error("  Une table recopiée diverge, et deux listes d'accord entre elles ne");
	console.error('  prouvent rien. Corriger le manuel, ou déclarer la nouvelle règle.');
	process.exit(1);
}

console.log(
	`✓ Manuel : ${cartes.size} écran(s) annoncé(s), ${routes.size} route(s) du site — ` +
		'tous cités, et le public annoncé est celui que sa page déclare.',
);
