/**
 * Neutraliser les commentaires avant d'analyser un fichier — **une seule fois**.
 *
 * ## Pourquoi ce module existe
 *
 * Le 20/08/2026, **trois** garde-fous du front ont refusé un lot à cause d'un
 * COMMENTAIRE qui citait ce qu'ils interdisent :
 *
 * | Contrôle | Ce qu'il a refusé |
 * |---|---|
 * | `check-html` | un commentaire expliquant pourquoi le composant n'emploie PAS `{@html}` |
 * | `check-charge-utile` | une virgule dans une phrase, qui coupait son propre découpage |
 * | `check-libelles-taches` | un commentaire nommant « Sauvegarde quotidienne » |
 *
 * 🔴 **Un contrôle qui interdit d'en parler oblige à taire la raison — et c'est
 * la raison qui se perd en premier.** Le fichier qui explique une règle est
 * précisément celui qui la cite le plus.
 *
 * Chacun a d'abord été corrigé chez lui. Quatre copies de la même parade en ont
 * résulté, écrites dans la même journée : c'est la duplication que
 * `standards/02` interdit, commise en réparant des contrôles.
 *
 * ## 🔴 La détection LINE-LOCALE ne suffit pas
 *
 * La forme naïve — « la portion de ligne avant l'occurrence contient-elle `//`,
 * `*` ou `<!--` ? » — ne voit qu'un commentaire ouvert sur la MÊME ligne. Un
 * commentaire Svelte de plusieurs lignes la traverse sans être vu, et c'est
 * exactement ce qui s'est produit trois fois.
 *
 * ## Le contenu est remplacé par des ESPACES, jamais supprimé
 *
 * Les index et les numéros de ligne des occurrences RÉELLES doivent rester
 * justes : un contrôle qui désigne la mauvaise ligne se fait ignorer.
 *
 * Test : node front/scripts/lib-commentaires.mjs --selftest
 */
import { pathToFileURL } from 'node:url';

/** Blanchit un fragment en gardant sa longueur et ses sauts de ligne. */
const blanchir = (bloc) => bloc.replace(/[^\n]/g, ' ');

/**
 * Les commentaires de CODE — `/* … *\/` et `// …`.
 *
 * ⚠️ Le `//` d'une URL (`https://…`) n'est PAS un commentaire. Le motif exige
 * donc que le caractère précédent ne soit pas `:` — sans quoi une ligne
 * contenant une URL serait tronquée, et ce qui la suit deviendrait invisible.
 */
function neutraliserCodeur(source) {
	return source
		.replace(/\/\*[\s\S]*?\*\//g, blanchir)
		.replace(
			/(^|[^:])\/\/[^\n]*/g,
			(bloc, avant) => avant + ' '.repeat(bloc.length - avant.length),
		);
}

/**
 * Remplace le contenu des commentaires par des espaces, en conservant la
 * longueur du fichier.
 *
 * Trois formes, dont deux peuvent s'étendre sur plusieurs lignes : le
 * commentaire HTML/Svelte `<!-- … -->`, le commentaire de bloc `/* … *\/`, et le
 * commentaire de fin de ligne `// …`.
 *
 * ## 🔴 `/*` et `//` ne sont des commentaires QUE dans `<script>` et `<style>`
 *
 * Corrigé le 29/08/2026. Dans le BALISAGE d'un composant Svelte, ces deux
 * suites de caractères sont du texte ordinaire — et il y en a :
 *
 *     <input type="file" accept="image/*" … />      residence/+page.svelte:599
 *
 * Ce seul `/*` ouvrait un faux commentaire de bloc que rien ne fermait avant le
 * premier `*\/` du `<style>`, **721 lignes plus bas**. Le fichier le plus
 * fourni en modales du site — sept — était donc **blanchi de moitié** pour tous
 * les contrôles qui passent par ici, et pour les huit qui recopiaient cette
 * fonction chez eux.
 *
 * ⚠️ Aucun ne s'en plaignait, et c'est le pire : un contrôle qui ne voit pas la
 * moitié d'un fichier ne dit pas « je n'ai pas regardé », il dit ✓
 * (`standards/04-fiabilite-des-controles.md` §2). Trouvé en comptant les
 * `<Modale>` que `check-modales` recensait — 20 là où le dépôt en porte 27.
 *
 * Un fichier SANS `<script>` ni `<style>` (un `.ts`, un `.mjs`) est du code de
 * bout en bout : les deux formes y valent partout.
 */
export function neutraliserCommentaires(source) {
	//  Les commentaires HTML d'abord : ils peuvent en contenir d'autres, et ils
	//  sont les seuls valables dans le balisage.
	const sansHtml = source.replace(/<!--[\s\S]*?-->/g, blanchir);

	const zones = [...sansHtml.matchAll(/<(script|style)\b[^>]*>([\s\S]*?)<\/\1>/g)];
	if (zones.length === 0) return neutraliserCodeur(sansHtml);

	//  Reconstruit à l'identique : hors zone, le texte est intact ; dans la zone,
	//  seuls les commentaires sont blanchis. Les longueurs sont donc conservées.
	let sortie = '';
	let curseur = 0;
	for (const z of zones) {
		const debut = z.index + z[0].length - z[2].length - `</${z[1]}>`.length;
		sortie += sansHtml.slice(curseur, debut) + neutraliserCodeur(z[2]);
		curseur = debut + z[2].length;
	}
	return sortie + sansHtml.slice(curseur);
}

function selftest() {
	let ko = 0;

	//  🔴 On éprouve des PROPRIÉTÉS, pas des chaînes recopiées.
	//
	//  La première version de ce self-test comparait le résultat à un attendu
	//  écrit à la main — et deux cas sur sept échouaient, à UN espace près. La
	//  fonction était juste, mes attendus étaient faux. Un test qu'on ajuste
	//  jusqu'à ce qu'il passe ne prouve plus rien : il finit par décrire le
	//  comportement observé, quel qu'il soit.
	//
	//  Les trois propriétés ci-dessous sont, elles, indiscutables — et ce sont
	//  exactement celles dont dépendent les contrôles qui emploient ce module.
	const t = (libelle, source, marqueur) => {
		const obtenu = neutraliserCommentaires(source);
		const soucis = [];
		if (obtenu.length !== source.length) {
			soucis.push(
				`longueur ${obtenu.length} au lieu de ${source.length} — les positions se décalent`,
			);
		}
		if ((obtenu.match(/\n/g) || []).length !== (source.match(/\n/g) || []).length) {
			soucis.push('sauts de ligne perdus — les numéros de ligne deviennent faux');
		}
		if (marqueur !== null && obtenu.includes(marqueur)) {
			soucis.push(`« ${marqueur} » subsiste alors qu'il est en commentaire`);
		}
		if (marqueur === null && obtenu !== source) {
			soucis.push('le contenu HORS commentaire a été modifié');
		}
		if (!soucis.length) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — ${soucis.join(' ; ')}`);
			ko = 1;
		}
	};

	t('commentaire de ligne', 'const a = 1; // interdit', 'interdit');
	t('commentaire de bloc', 'const a = 1; /* interdit */ const b = 2;', 'interdit');
	t('commentaire Svelte', '<!-- interdit -->\n<p>ok</p>', 'interdit');
	//  🔴 Le cas que la détection line-locale ne voit pas — celui qui a fait
	//  refuser trois lots le 20/08/2026.
	t(
		'commentaire Svelte multi-lignes',
		'<!--  ligne un\n      ligne deux : interdit\n-->\n<p>ok</p>',
		'interdit',
	);
	t('commentaire de bloc multi-lignes', '/*\n interdit\n*/\nconst a = 1;', 'interdit');
	//  ⚠️ Ce qui n'est PAS un commentaire doit rester intact, au caractère près.
	t('URL avec double barre', "const u = 'https://exemple.test/a';", null);
	t('code sans commentaire', 'const a = 1;\nconst b = 2;', null);
	t('barre oblique simple', 'const r = a / b;', null);

	//  🔴 Le cas du 29/08/2026 : un `/*` dans le BALISAGE n'ouvre rien. Sans
	//  cette règle, tout ce qui suit est blanchi jusqu'à la première fermeture de bloc du
	//  `<style>` — 721 lignes dans `residence`, ses sept modales comprises.
	//
	//  ⚠️ Ce cas éprouve les DEUX moitiés à la fois : ce qui suit l'attribut
	//  survit, ET le vrai commentaire du `<style>` disparaît quand même. Vérifier
	//  la première seule laisserait passer une fonction qui ne neutralise plus rien.
	{
		const source =
			'<input accept="image/*" />\n<Modale titre="Ajouter" />\n<style>\n\t/* interdit */\n\t.a {\n\t\tcolor: red;\n\t}\n</style>';
		const obtenu = neutraliserCommentaires(source);
		const soucis = [];
		if (!obtenu.includes('<Modale titre="Ajouter" />')) {
			soucis.push('le balisage qui suit `accept="image/*"` a été blanchi');
		}
		if (obtenu.includes('interdit'))
			soucis.push("le commentaire du `<style>` n'a pas été neutralisé");
		if (obtenu.length !== source.length) soucis.push('les positions se décalent');
		if (!soucis.length)
			console.log('PASS  attribut contenant /* — le balisage suivant reste intact');
		else {
			console.log(`FAIL  attribut contenant /* — ${soucis.join(' ; ')}`);
			ko = 1;
		}
	}
	//  Le commentaire d'un `<style>` sans attribut piégeux avant lui.
	t(
		'commentaire de bloc dans <style>',
		'<div />\n<style>\n\t/* interdit */\n\t.a {\n\t\tcolor: red;\n\t}\n</style>',
		'interdit',
	);
	t(
		'commentaire de ligne dans <script>',
		'<script>\n\tconst a = 1; // interdit\n</' + 'script>\n<p>ok</p>',
		'interdit',
	);

	console.log(
		ko === 0
			? '\n✓ Autotest : commentaires neutralisés, longueurs et lignes conservées, code intact.'
			: '\n✗ Autotest en échec',
	);
	return ko;
}

//  Ne s'exécute QUE si le fichier est lancé, jamais s'il est importé — sans quoi
//  un module qu'on ne peut pas importer est un module qu'on ne peut pas éprouver.
const _lance = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === _lance) process.exit(selftest());
