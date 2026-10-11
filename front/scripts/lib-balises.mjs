/**
 * Lire une balise Svelte — l'automate, écrit UNE fois.
 *
 * ## Pourquoi ce module (22/09/2026, `standards/04` §48)
 *
 * Un contrôle qui vérifie les attributs d'une balise commence par l'isoler, et
 * le motif qui vient sous la main est toujours le même :
 *
 *     /<MaBalise\b[^>]*>/
 *
 * Il est faux dès qu'un attribut contient un `>`, un `=>` ou une accolade —
 * c'est-à-dire dès qu'une valeur est une **expression** et non une chaîne :
 *
 *     <Section rempli={liste.length > 0} pliable={p}>
 *
 * Le motif s'arrête au `>` de la comparaison. La balise paraît finir là, et
 * tout ce qui suit lui échappe.
 *
 * 🔴 **Le faux verdict va dans les deux sens, et le plus coûteux n'est pas
 * celui qu'on croit.** Manquer un attribut qui devait être là donne un faux
 * vert, qu'on finit par voir. Ne pas voir un attribut **déjà présent** donne un
 * faux ROUGE, et un faux rouge se « corrige » : j'ai ajouté une seconde fois un
 * `pliable` que la balise portait quatre lignes plus bas.
 *
 * ⚠️ C'était la **troisième** fois dans ce dépôt — un `=>` avait déjà coupé
 * `check-ordre-sections`, un `>` `check-libelles-soumission`. Trois contrôles
 * écrits à des mois d'intervalle, trois fois le même motif recopié de tête.
 * D'où ce module : la quatrième recopie manquerait le cas suivant.
 *
 * ⚠️ `check-ordre-sections` et `check-libelles-soumission` portent encore leur
 * propre automate, chacun corrigé dans son coin. Ils migrent ici au fil de
 * l'eau (#1145) — les déplacer tous d'un coup dans un lot qui parle d'autre
 * chose est exactement ce qui rend une PR irrelisible.
 */

/**
 * Les balises ouvrantes de `nom` dans `source`.
 *
 * Rend `[{ balise, index, fin }]` — `fin` est l'index du `>` fermant, ce qui
 * permet à l'appelant de lire le CONTENU sans refaire l'analyse.
 *
 * Suit les guillemets (`"`, `'`, `` ` ``) et compte les accolades : un `>` ne
 * ferme la balise que lorsque la profondeur est nulle et qu'on n'est pas dans
 * une chaîne.
 */
export function balisesOuvrantes(source, nom) {
	const trouvees = [];
	//  `(?=[^A-Za-z])` et non `\b` : `<Section` ne doit pas matcher `<Sections`,
	//  et le motif doit tenir aussi pour `<button>` sans attribut.
	const ouvertures = new RegExp(`<${nom}(?=[^A-Za-z0-9_-])`, 'g');
	let ouverture;
	while ((ouverture = ouvertures.exec(source))) {
		let i = ouverture.index + 1;
		let guillemet = '';
		let accolades = 0;
		while (i < source.length) {
			const c = source[i];
			if (guillemet) {
				if (c === guillemet) guillemet = '';
			} else if (c === '"' || c === "'" || c === '`') {
				guillemet = c;
			} else if (c === '{') {
				accolades += 1;
			} else if (c === '}') {
				accolades = Math.max(0, accolades - 1);
			} else if (c === '>' && accolades === 0) {
				break;
			}
			i += 1;
		}
		trouvees.push({
			balise: source.slice(ouverture.index, i + 1),
			index: ouverture.index,
			fin: i,
		});
	}
	return trouvees;
}

/** Le numéro de ligne d'un index, 1-based. */
export function ligneDe(source, index) {
	return source.slice(0, index).split(String.fromCharCode(10)).length;
}

/**
 * Le contenu d'un élément, depuis la fin de sa balise ouvrante jusqu'à sa
 * fermeture — imbrications comprises.
 *
 * Rend `''` pour un élément auto-fermant (`<X … />`).
 */
export function contenuDe(source, nom, ouvrante) {
	if (ouvrante.balise.endsWith('/>')) return '';
	const ouvre = new RegExp(`<${nom}(?=[^A-Za-z0-9_-])`, 'g');
	//  Des blancs, retours à la ligne compris, et non `[ ]*` : Prettier ferme un
	//  bloc long par `</button` puis `>` à la ligne suivante, et la lecture
	//  prenait alors le contenu des éléments suivants pour le sien — un bouton
	//  en émoji passait pour un bouton qui parle (#1819).
	const ferme = new RegExp(`</${nom}\\s*>`, 'g');
	let profondeur = 1;
	let i = ouvrante.fin + 1;
	while (i < source.length) {
		ouvre.lastIndex = i;
		ferme.lastIndex = i;
		const o = ouvre.exec(source);
		const f = ferme.exec(source);
		if (!f) return source.slice(ouvrante.fin + 1);
		if (o && o.index < f.index) {
			profondeur += 1;
			i = o.index + 1;
			continue;
		}
		profondeur -= 1;
		if (profondeur === 0) return source.slice(ouvrante.fin + 1, f.index);
		i = f.index + 1;
	}
	return source.slice(ouvrante.fin + 1);
}

//  🔴 « Ce fichier est-il EXECUTE ? », et pas seulement « voit-il l'argument ? ».
//
//  Un module importe partage `process.argv` avec son importateur : sans cette
//  garde, `node check-bouton-icone.mjs --selftest` declenchait l'auto-test de CE
//  fichier, puis son `process.exit(0)` — et l'auto-test de l'appelant ne tournait
//  jamais. Mesure le 22/09/2026, une heure apres avoir corrige le meme defaut
//  cote bash (`lib-modules-sources.sh`) : le piege est le meme dans les deux
//  langages, et je l'ai refait dans le second.
//  ⚠️ Pas de `\` litteral dans ce fichier : il traverse des heredocs et des
//  outils qui en mangent un sur deux, en silence. `String.fromCharCode(92)` dit
//  la meme chose et survit a tout.
const SEP_WINDOWS = String.fromCharCode(92);
const EXECUTE =
	!!process.argv[1] && import.meta.url.endsWith(process.argv[1].split(SEP_WINDOWS).join('/'));

if (EXECUTE && process.argv.includes('--selftest')) {
	const cas = [
		//  🔴 LE CAS VÉCU : un `>` dans une expression ne ferme pas la balise.
		['<S rempli={n > 0} pliable={p}>x</S>', 'S', '<S rempli={n > 0} pliable={p}>', 'x'],
		//  Et celui qui l'avait précédé : une flèche dans une prop.
		['<S on:x={() => f()} a={1}>y</S>', 'S', '<S on:x={() => f()} a={1}>', 'y'],
		//  Un `>` dans une CHAÎNE ne ferme pas davantage.
		['<S t="a > b">z</S>', 'S', '<S t="a > b">', 'z'],
		//  Auto-fermante : pas de contenu.
		['<S a={1} />', 'S', '<S a={1} />', ''],
		//  Imbrication du même nom : la bonne fermeture est comptée.
		['<b><b>i</b>o</b>', 'b', '<b>', '<b>i</b>o'],
		//  Un nom plus long ne doit pas matcher.
		['<Sections a={1}>q</Sections>', 'S', null, null],
	];
	let ko = 0;
	for (const [src, nom, balise, contenu] of cas) {
		const trouvees = balisesOuvrantes(src, nom);
		if (balise === null) {
			if (trouvees.length !== 0) {
				console.error(`  ✗ « ${src} » → ${trouvees.length} balise(s), attendu 0`);
				ko++;
			}
			continue;
		}
		if (trouvees.length === 0) {
			console.error(`  ✗ « ${src} » → aucune balise trouvée`);
			ko++;
			continue;
		}
		if (trouvees[0].balise !== balise) {
			console.error(`  ✗ « ${src} » → balise « ${trouvees[0].balise} », attendu « ${balise} »`);
			ko++;
		}
		const obtenu = contenuDe(src, nom, trouvees[0]);
		if (obtenu !== contenu) {
			console.error(`  ✗ « ${src} » → contenu « ${obtenu} », attendu « ${contenu} »`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ lib-balises : ${ko} cas en échec.\n`);
		process.exit(1);
	}
	console.log(
		`✓ lib-balises : ${cas.length} cas — le \`>\` d'une expression ne ferme pas la balise.`,
	);
	process.exit(0);
}

/**
 * Le contenu porte-t-il un MOT lisible (deux lettres à la suite) ?
 *
 * Partagé par `check-bouton-icone` (un bouton sans mot doit se nommer) et
 * `check-actions-au-trait` (un bouton sans mot ne se dessine pas en émoji).
 */
export function porteUnMot(contenu) {
	//  ⚠️ Un `<slot>` porte le texte de l'APPELANT : on ne peut pas savoir ici
	//  ce qu'il rendra, et `Pastille` le prouve — son libellé vient toujours de
	//  l'écran qui l'emploie. Crier dessus ferait exiger un `aria-label` qui
	//  MASQUERAIT ce libellé, c'est-à-dire un défaut pour corriger une absence
	//  de défaut. Un contrôle qui crie sur du légitime finit désarmé.
	const sansBalises = contenu
		//  Un bloc Svelte (`{#if …}`) n'est pas du texte rendu ; son contenu, si.
		.replace(/\{[#:/@][^}]*\}/g, ' ')
		//  Une expression `{x}` peut rendre du texte : on ne peut pas trancher,
		//  et on la traite comme du texte — ne pas crier sur du légitime.
		.replace(/<[^>]*>/g, ' ');
	if (contenu.includes('<slot')) return true;
	return /\p{Letter}\p{Letter}/u.test(sansBalises);
}
