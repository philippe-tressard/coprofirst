#!/usr/bin/env node
/**
 * Garde-fou : une prop de section lit LA section qu'elle active.
 *
 * ## Le défaut (#1095, relevé le 22/09/2026)
 *
 * `FormulaireTicket` écrivait :
 *
 *     avecSaisiPour={$estModerateur && sectionPresente(TICKET, etat, 'nature')}
 *     avecOptions={sectionPresente(TICKET, etat, 'nature')}
 *
 * — alors que ces deux props activent « Au nom de » (10) et « Mise en avant »
 * (11). C'est un reliquat de l'ancienne section « Champs spécifiques », qui
 * portait les trois notions avant la scission.
 *
 * 🔴 Ce que ça coûte : la déclaration de ces sections n'est **pas lue**. Leur
 * `absente`, leur motif, leur présence par état sont écrits dans
 * `lib/entites/*.ts` et ne gouvernent rien — l'écran suit une autre section.
 * Tant que les deux réponses coïncident, personne ne le voit ; le jour où elles
 * divergent, c'est la déclaration qui a tort à l'écran.
 *
 * ⚠️ C'est la limite que #1095 devait refermer : *« scinder l'ancienne section 2
 * rend déclarable ce qui ne peut aujourd'hui s'écrire qu'en commentaire »*. La
 * scission a eu lieu ; les lectures, elles, étaient restées sur l'ancien nom.
 *
 * ## Ce qui est vérifié
 *
 * Pour chaque `avecX={… sectionPresente(…, '<id>') …}` : `<id>` est bien la
 * section que `X` active, d'après la table ci-dessous — qui est celle du
 * composant, pas une seconde écriture de l'ordre.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**  La prop de `ChampsCommuns` et la section qu'elle rend.
 *
 *   ⚠️ `avecPhotos` et `avecDocuments` visent la même section depuis la fusion
 *   du 21/09/2026 : une seule « Pièces jointes ». */
const SECTION_DE_LA_PROP = {
	avecQuand: 'quand',
	avecPerimetre: 'perimetre',
	avecDescription: 'description',
	avecPhotos: 'pieces_jointes',
	avecDocuments: 'pieces_jointes',
	avecSaisiPour: 'au_nom_de',
	avecOptions: 'mise_en_avant',
	avecDestinataires: 'destinataires',
	avecDiffusion: 'diffusion',
};

function svelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...svelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

/**  Les lectures fautives d'une source. PURE : éprouvable sans arborescence. */
export function lecturesFautives(source) {
	const fautes = [];
	for (const [prop, attendue] of Object.entries(SECTION_DE_LA_PROP)) {
		//  `avecX={…}` jusqu'à l'accolade fermante de la même ligne : ces props
		//  tiennent sur une ligne, prettier les y garde.
		const re = new RegExp(
			`(?:^|[^A-Za-z])${prop}=[{]([^}]*sectionPresente[(][^)]*[)][^}]*)[}]`,
			'g',
		);
		let m;
		while ((m = re.exec(source))) {
			const lues = [...m[1].matchAll(/sectionPresente\([^,]+,\s*[^,]+,\s*'([a-z_]+)'\)/g)].map(
				(x) => x[1],
			);
			for (const lue of lues) {
				if (lue !== attendue) {
					fautes.push({ prop, attendue, lue, ligne: source.slice(0, m.index).split('\n').length });
				}
			}
		}
	}
	return fautes;
}

if (process.argv.includes('--selftest')) {
	//  🔴 Le cas fautif AVANT tout : un contrôle se prouve sur ce qu'il refuse.
	const cas = [
		["avecSaisiPour={$estModerateur && sectionPresente(TICKET, etat, 'nature')}", 1],
		["avecSaisiPour={$estModerateur && sectionPresente(TICKET, etat, 'au_nom_de')}", 0],
		["avecOptions={sectionPresente(TICKET, etat, 'nature')}", 1],
		["avecOptions={sectionPresente(PUBLICATION, etat, 'mise_en_avant')}", 0],
		//  Une prop qui ne lit aucune section n'est pas jugée : certains écrans
		//  activent une section par un booléen à eux (`avecSaisiPour` tout court).
		['avecDiffusion={$estModerateur}', 0],
		["avecPhotos={sectionPresente(TICKET, etat, 'pieces_jointes')}", 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = lecturesFautives(src).length;
		if (n !== attendu) {
			console.error(`  ✗ « ${src.slice(0, 60)} » → ${n} faute(s), attendu ${attendu}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.\n`);
		process.exit(1);
	}
	console.log(`✓ Auto-test : ${cas.length} cas, la mauvaise section est vue et la bonne passe.`);
	process.exit(0);
}

const fautifs = [];
let lues = 0;
for (const chemin of svelte(RACINE)) {
	const source = readFileSync(chemin, 'utf8');
	if (!source.includes('sectionPresente')) continue;
	lues++;
	for (const f of lecturesFautives(source)) {
		fautifs.push(
			`src/${relative(RACINE, chemin).split(sep).join('/')}:${f.ligne}  ` +
				`${f.prop} lit « ${f.lue} » au lieu de « ${f.attendue} »`,
		);
	}
}

//  Cas zéro : un relevé vide et une lecture ratée se ressemblent.
if (lues === 0) {
	console.error(
		"\n✗ Cas zéro : aucun écran n'appelle `sectionPresente` — le motif a dérivé.\n" +
			'  Ne pas lire ceci comme un succès.\n',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error(`\n✗ ${fautifs.length} prop(s) de section qui lisent la MAUVAISE section :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		"\n  La déclaration de la section rendue n'est alors pas lue : son `absente`," +
			'\n  son motif et sa présence par état ne gouvernent rien. Tant que les deux' +
			'\n  réponses coïncident personne ne le voit — le jour où elles divergent,' +
			"\n  c'est la déclaration qui a tort à l'écran.\n",
	);
	process.exit(1);
}

console.log(
	`✓ Sections lues : ${lues} écran(s) consultent la déclaration, chacun sur la section qu'il rend.`,
);
