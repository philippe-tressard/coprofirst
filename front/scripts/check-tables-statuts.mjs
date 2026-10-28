/**
 * Garde-fou — **deux tables ne se partagent pas le même ensemble de clés.**
 *
 * ## Pourquoi (15/09/2026, #779)
 *
 * Un relevé a comparé, fichier par fichier, les `Record<string, string>` dont
 * les clés se recouvrent. **Dix fichiers** énuméraient le même ensemble d'états
 * deux ou trois fois : un libellé ici, une classe de pastille là, parfois une
 * forme abrégée ou une aide contextuelle en troisième.
 *
 * Ce n'est pas la même ligne recopiée, c'est le même **ensemble de clés**.
 * Ajouter un état demande alors de le poser dans chaque table, et rien ne
 * signale l'oubli : la table incomplète rend `undefined`, donc un badge sans
 * couleur ou un libellé vide. Les deux passent la compilation et la relecture.
 *
 * ⚠️ **Au moment d'écrire ce contrôle, aucune divergence n'existait** : les dix
 * fichiers étaient d'accord avec eux-mêmes. C'est exactement l'état des quatre
 * copies des statuts de ticket avant #415 — « chacune était cohérente avec
 * elle-même ; c'est ce qui les rendait invisibles à la relecture ». Ce contrôle
 * ne répare donc rien : il ferme l'endroit d'où le défaut sort.
 *
 * ## Ce qu'il refuse, et ce qu'il laisse passer
 *
 * Refusé : deux littéraux d'objet, dans le même fichier, dont les clés se
 * recouvrent à **60 % ou plus**. La réponse est `parAttribut()`
 * (`#lib/table-statuts`) : un état, une entrée, tous ses attributs — et le
 * compilateur refuse alors l'entrée incomplète.
 *
 * Laissé passer : deux tables aux clés franchement différentes. Le seuil de
 * 60 % est là pour ça — `LIBELLES_HERITES` (`#lib/roles`) porte d'anciennes
 * clés, volontairement à part des énumérations du serveur, et ne doit pas
 * fondre dans elles.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
//: Le module qui porte la solution parle forcément du problème.
const SOURCE = 'src/lib/table-statuts.ts';
//: En deçà, deux tables décrivent des choses différentes qui se ressemblent.
const RECOUVREMENT = 0.6;
//: Sous ce nombre de clés, « le même ensemble » ne veut plus dire grand-chose :
//: deux tables de deux entrées se recouvrent par accident.
const MINIMUM = 3;

/** Les littéraux d'objet d'un fichier, réduits à leurs clés. */
export function tables(source) {
	const lignes = source.split('\n');
	const trouvees = [];
	//  🔴 LA PORTÉE FAIT PARTIE DU CONTRÔLE — seules les tables annotées
	//  `Record<…>` sont regardées, et c'est un choix, pas un raccourci.
	//
	//  Un `Record` est précisément ce qu'on interroge AVEC UNE VARIABLE
	//  (`LABEL[statut]`) : la clé manquante y rend `undefined`, en silence. Un
	//  objet nommé — deux clients d'API, deux instances d'une interface — se lit
	//  par ses propriétés littérales, et le compilateur refuse celle qui manque.
	//  Sans ce resserrement, le contrôle criait sur `IMPORT_VIGIK` /
	//  `IMPORT_TELECOMMANDES`, deux instances d'un `ModeleImportAcces` dont
	//  l'interface porte DÉJÀ la garantie qu'on cherche ici — deux dérogations
	//  pour zéro défaut réel, et un contrôle qu'on finit par désarmer.
	const ouverture = /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*:\s*Record<[^>]*>\s*=\s*\{\s*$/;
	const cle = /^\s*([A-Za-z_$][\w$]*|'[^']+'|"[^"]+"|[^\s:]+)\s*:/;
	for (let i = 0; i < lignes.length; i++) {
		const m = ouverture.exec(lignes[i]);
		if (!m) continue;
		const cles = new Set();
		//  Le niveau des états : un cran de plus que la ligne d'ouverture.
		const attendue = /^\t*/.exec(lignes[i])[0].length + 1;
		let j = i + 1;
		for (; j < lignes.length; j++) {
			const nue = lignes[j].trim();
			const profondeur = /^\t*/.exec(lignes[j])[0].length;
			//  ⚠️ On ferme sur l'accolade de la TABLE, pas sur celle d'une entrée :
			//  une entrée répartie sur plusieurs lignes en referme une avant. Sans
			//  cette condition de niveau, la lecture s'arrêtait au premier état et
			//  la table entière tombait sous le minimum — donc invisible.
			if (nue.startsWith('}') && profondeur < attendue) break;
			if (nue.startsWith('//') || nue.startsWith('*')) continue;
			const c = cle.exec(lignes[j]);
			//  Une clé est au premier niveau : plus profond, c'est un attribut et
			//  non un état. C'est ce qui distingue la table plate (le défaut) de la
			//  table fondue (la solution).
			if (c && profondeur === attendue) cles.add(c[1].replace(/['"]/g, ''));
		}
		if (cles.size >= MINIMUM) trouvees.push({ nom: m[1], ligne: i + 1, cles });
		i = j;
	}
	return trouvees;
}

/** Les couples de tables d'un fichier qui décrivent le même ensemble. */
export function paires(source) {
	const t = tables(source);
	const fautes = [];
	for (let a = 0; a < t.length; a++) {
		for (let b = a + 1; b < t.length; b++) {
			const communes = [...t[a].cles].filter((c) => t[b].cles.has(c)).length;
			const taille = Math.max(t[a].cles.size, t[b].cles.size);
			if (communes / taille >= RECOUVREMENT) {
				fautes.push(`${t[a].nom} (l.${t[a].ligne}) / ${t[b].nom} (l.${t[b].ligne})`);
			}
		}
	}
	return fautes;
}

function fichiers(dir) {
	const sortie = [];
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) sortie.push(...fichiers(p));
		else if (/\.(ts|svelte)$/.test(e)) sortie.push(p);
	}
	return sortie;
}

function selftest() {
	const cas = [
		//  🔴 Le défaut : deux tables plates, mêmes clés.
		[
			"const LABEL: Record<string, string> = {\n\ta: 'A',\n\tb: 'B',\n\tc: 'C',\n};\n" +
				"const BADGE: Record<string, string> = {\n\ta: 'x',\n\tb: 'y',\n\tc: 'z',\n};\n",
			1,
		],
		//  🔴 Une table IMBRIQUÉE face à une table plate, mêmes états : le même
		//  défaut, et c'est ici que le contrôle de profondeur se joue.
		//
		//  ⚠️ L'entrée est écrite sur PLUSIEURS lignes, et ce n'est pas un détail
		//  de présentation : sur une entrée d'une seule ligne, la regex ne voit
		//  que la première clé et la profondeur ne déciderait de rien. C'est la
		//  forme que Prettier produit dès qu'une entrée dépasse cent colonnes —
		//  celle de `#lib/roles`. Sans le contrôle de profondeur, les trois
		//  attributs comptent pour des états : 3 clés communes sur 6, sous le
		//  seuil, et le couple passe inaperçu.
		//
		//  🔒 Vérifié en retirant `profondeur === attendue` : l'auto-test échoue
		//  alors sur ce cas précis. Un premier cas, écrit sur une seule ligne,
		//  passait des deux façons — il donnait à croire que la ligne servait.
		[
			'const T: Record<string, Attributs> = {\n' +
				'\ta: {\n' +
				"\t\tlibelle: 'A',\n\t\tabrege: 'A',\n\t\tbadge: 'x',\n" +
				'\t},\n' +
				'\tb: {\n' +
				"\t\tlibelle: 'B',\n\t\tabrege: 'B',\n\t\tbadge: 'y',\n" +
				'\t},\n' +
				'\tc: {\n' +
				"\t\tlibelle: 'C',\n\t\tabrege: 'C',\n\t\tbadge: 'z',\n" +
				'\t},\n' +
				'};\n' +
				"const AIDE: Record<string, string> = {\n\ta: 'A',\n\tb: 'B',\n\tc: 'C',\n};\n",
			1,
		],
		//  ✅ La forme fondue telle qu'on l'écrit vraiment : `parAttribut()` ne
		//  porte pas d'annotation `Record<…>`, donc elle sort de la portée — la
		//  solution ne peut pas être refusée comme le problème.
		[
			'const T = parAttribut({\n' +
				"\ta: { libelle: 'A', badge: 'x' },\n" +
				"\tb: { libelle: 'B', badge: 'y' },\n" +
				"\tc: { libelle: 'C', badge: 'z' },\n" +
				'});\n',
			0,
		],
		//  ✅ Deux tables qui ne parlent pas de la même chose.
		[
			"const UN: Record<string, string> = {\n\ta: 'A',\n\tb: 'B',\n\tc: 'C',\n};\n" +
				"const DEUX: Record<string, string> = {\n\tx: '1',\n\ty: '2',\n\tz: '3',\n};\n",
			0,
		],
		//  ✅ Deux clés en commun sur cinq : en dessous du seuil.
		[
			"const UN: Record<string, string> = {\n\ta: 'A',\n\tb: 'B',\n\tc: 'C',\n};\n" +
				"const DEUX: Record<string, string> = {\n\ta: '1',\n\tb: '2',\n\tw: '3',\n\tx: '4',\n\ty: '5',\n};\n",
			0,
		],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = paires(src).length;
		if (n !== attendu) {
			console.error(`  ✗ ${n} au lieu de ${attendu} pour :\n${src}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : le défaut est reconnu, et la forme fondue ne l’est pas.');
}

selftest();
if (process.argv.includes('--selftest')) process.exit(0);

const fautifs = [];
for (const p of fichiers(RACINE)) {
	const chemin = p.split(sep).join('/');
	if (chemin === SOURCE) continue;
	for (const f of paires(readFileSync(p, 'utf8'))) fautifs.push(`${chemin} — ${f}`);
}

if (fautifs.length) {
	console.error(`\n✗ ${fautifs.length} couple(s) de tables partagent leur ensemble de clés :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  Ajouter un état demande alors de le poser dans chaque table, et un oubli\n' +
			'  ne lève rien : la table incomplète rend `undefined`, donc un badge sans\n' +
			'  couleur ou un libellé vide.\n' +
			'  → `parAttribut({ etat: { libelle, badge } })` de `#lib/table-statuts` :\n' +
			'    une entrée par état, et le compilateur refuse celle qui est incomplète.\n',
	);
	process.exit(1);
}
console.log("✓ Aucune table d'états n'est énumérée deux fois.");
