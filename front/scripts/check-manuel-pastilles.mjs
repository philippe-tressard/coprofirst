#!/usr/bin/env node
/**
 *  Les pastilles « qui la lit » du manuel disent ce que le site dit (27/09/2026).
 *
 *  ## Pourquoi
 *
 *  Arbitré à l'écran : le manuel nommait « la pastille bleue » en texte brut,
 *  et survoler le mot ne montrait rien. Il montre désormais la VRAIE pastille,
 *  avec sa phrase au survol. Mais une phrase recopiée dans un document diverge
 *  au premier changement de `#lib/lecture` — et le manuel mentirait alors en
 *  toute confiance.
 *
 *  ## Ce qu'il vérifie
 *
 *  Chaque `<span … data-lecture="cas" title="…">` du manuel : son texte et sa
 *  phrase sont RECALCULÉS avec `lectureDe` et `titreLecture` (le module exécuté,
 *  pas relu — `standards/04` §22), sur la nature déclarée ci-dessous. Un cas du
 *  manuel inconnu d'ici, ou un cas d'ici absent du manuel, échoue aussi.
 *
 *  Lancer : node scripts/check-manuel-pastilles.mjs
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { chargerModule } from './lib/charger-module.mjs';

const MANUEL = '../docs/manuel-utilisateur.html';
const NATURE = {
	actualite: false,
	categorie: 'etude_travaux',
	confidentiel: false,
	publicCible: null,
	perimetreRestreint: false,
	reservePerimetre: false,
};
/** Le cas du manuel → la nature d'objet qui produit sa pastille. */
const CAS = {
	//  Une Étude & travaux dont le conseil a CHOISI les copropriétaires : sans
	//  choix, elle est au conseil seul depuis le 29/09/2026 — le cas `cs` le dit.
	copro: { ...NATURE, publicCible: ['copropriétaires_occupants', 'bailleurs'] },
	occ: {
		...NATURE,
		actualite: true,
		categorie: 'actualite',
		publicCible: ['copropriétaires_occupants'],
	},
	cad: {
		...NATURE,
		actualite: true,
		categorie: 'actualite',
		publicCible: ['résidents'],
		perimetreRestreint: true,
		reservePerimetre: true,
	},
	//  Une Étude & travaux sans choix : le conseil seul. Entretien l'illustrait
	//  jusqu'au 30/09/2026, où il est passé aux copropriétaires.
	cs: { ...NATURE, categorie: 'etude_travaux' },
	//  Une Nuisance sans choix du conseil : « Résident concerné » (#1436).
	concerne: { ...NATURE, categorie: 'nuisance' },
	//  Une Panne sans choix, sur un bâtiment : les copropriétaires partout, les
	//  locataires du périmètre (standard du 30/09/2026).
	panne: { ...NATURE, categorie: 'panne', perimetreRestreint: true },
};

const echouer = (m) => {
	console.error(`\n✗ ${m}\n`);
	process.exit(2);
};
const { lectureDe, titreLecture } = await chargerModule(resolve('src/lib/lecture.ts'), echouer);

const manuel = readFileSync(MANUEL, 'utf8');
const pastilles = [
	...manuel.matchAll(
		/<span class="pastille-lecture-ex" data-lecture="(\w+)"[^>]*title="([^"]*)">[\s\S]*?<span>([^<]*)<\/span>/g,
	),
];
if (!pastilles.length) echouer('INCONNU : aucune pastille `data-lecture` dans le manuel.');

const ecarts = [];
const vus = new Set();
for (const [, cas, titre, texte] of pastilles) {
	vus.add(cas);
	if (!CAS[cas]) {
		ecarts.push(`cas « ${cas} » inconnu du contrôle — le déclarer dans CAS`);
		continue;
	}
	const l = lectureDe(CAS[cas]);
	const attendu = `${titreLecture(l)} — ${l.phrase} ${l.exclus}`.trim();
	if (titre !== attendu)
		ecarts.push(`${cas} : survol\n      manuel : ${titre}\n      site   : ${attendu}`);
	if (texte !== l.court) ecarts.push(`${cas} : texte « ${texte} », le site dit « ${l.court} »`);
}
for (const cas of Object.keys(CAS))
	if (!vus.has(cas)) ecarts.push(`cas « ${cas} » absent du manuel`);

if (ecarts.length) {
	console.error(`\n✗ Pastilles du manuel ≠ site :\n\n  ${ecarts.join('\n  ')}\n`);
	process.exit(1);
}
console.log(
	`✓ Manuel : ${pastilles.length} pastille(s) « qui la lit », phrases recalculées par le site.`,
);
