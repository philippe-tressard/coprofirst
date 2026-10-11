/**
 * Garde-fou : un bouton qui ne montre qu'une ICÔNE doit dire ce qu'il fait.
 *
 * ## Pourquoi (22/09/2026)
 *
 * `CLAUDE.md` l'exige — *« `aria-label` sur les boutons icône-seule »* —,
 * `ux-patterns` §3 aussi, et `standards/11` §2 une troisième fois. **Aucun
 * contrôle ne le tenait.**
 *
 * 🔴 Mesuré : en retirant l'`aria-label` d'un bouton icône fraîchement écrit,
 * `npm run lint:a11y` est resté **vert**. Il relaie les avertissements de
 * `svelte-check`, et svelte-check n'a pas de règle pour « bouton sans nom
 * accessible » — il ne la trouve donc jamais. Une règle écrite trois fois et
 * appliquée zéro : c'est exactement le motif de #561, où quarante-cinq défauts
 * d'accessibilité avaient défilé sans que rien ne les arrête.
 *
 * ## Ce qu'il lit
 *
 * Tout `<button>` de `src/` dont le contenu visible ne porte **aucun mot**  :
 * un glyphe, un emoji, un `<Icon …/>`, une entité, ou rien. Un tel bouton n'a
 * de nom accessible que par `aria-label` / `aria-labelledby`.
 *
 * ⚠️ `title` NE COMPTE PAS comme nom accessible de secours ici, bien que les
 * navigateurs l'utilisent en dernier ressort : il ne s'affiche qu'au survol,
 * donc jamais au doigt ni au clavier. Le porter en plus de l'`aria-label` est
 * une bonne chose ; le porter seul laisse le bouton muet là où il compte.
 *
 * ⚠️ Il ne lit PAS les zones de code (`<script>`, `<style>`) : une chaîne
 * JavaScript qui contient `<button>` n'est pas du balisage rendu.
 *
 * Usage : node scripts/check-bouton-icone.mjs [--selftest]
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep as sepOS } from 'node:path';

import { balisesOuvrantes, contenuDe, ligneDe, porteUnMot } from './lib-balises.mjs';

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

/**
 * Les exceptions, NOMMÉES avec leur raison — et le contrôle échoue si l'une
 * cesse de servir. Une exception non écrite n'est pas une exception.
 */
const EXCEPTIONS = Object.create(null);

/** Retire les zones qui ne sont pas du balisage rendu. */
function baliseSeul(source) {
	return source.replace(/<(script|style)\b[\s\S]*?<\/\1\s*>/g, (bloc) =>
		bloc.replace(/[^\n]/g, ' '),
	);
}

/** Le nom accessible est-il porté par la balise ? */
export function aUnNomAccessible(balise) {
	//  Un bouton RETIRÉ de l'arbre d'accessibilité (`aria-hidden="true"`) n'a
	//  pas de nom à porter : c'est un doublon pour la souris d'un geste qui a
	//  son chemin clavier ailleurs (les flèches de `PiecesJointes`). Le contrôle
	//  ne le voyait pas avant #1819 — la lecture des fermetures sur deux lignes
	//  avalait son contenu.
	if (/\saria-hidden="true"/.test(balise)) return true;
	return /\saria-label(ledby)?[=\s]/.test(balise);
}

/** Les manquements d'une source. PURE : éprouvable sans arborescence. */
export function boutonsMuets(source) {
	const nu = baliseSeul(source);
	const manques = [];
	for (const ouvrante of balisesOuvrantes(nu, 'button')) {
		if (aUnNomAccessible(ouvrante.balise)) continue;
		if (porteUnMot(contenuDe(nu, 'button', ouvrante))) continue;
		manques.push({ ligne: ligneDe(nu, ouvrante.index) });
	}
	return manques;
}

if (process.argv.includes('--selftest')) {
	const cas = [
		//  🔴 LE CAS VÉCU : l'icône seule, sans nom accessible.
		['<button on:click={f}>✨</button>', 1],
		//  Avec le libellé, il passe.
		['<button aria-label="Retravailler" on:click={f}>✨</button>', 0],
		//  `aria-labelledby` compte aussi.
		['<button aria-labelledby="t">✨</button>', 0],
		//  Retiré de l'arbre d'accessibilité : rien à nommer.
		['<button aria-hidden="true" tabindex="-1">&#x2039;</button>', 0],
		//  ⚠️ `title` SEUL ne suffit pas : il n'existe pas au doigt ni au clavier.
		['<button title="Gras"><b>B</b></button>', 1],
		//  Un bouton qui PARLE n'a besoin de rien.
		['<button on:click={f}>Enregistrer</button>', 0],
		//  Le texte peut venir après des balises imbriquées.
		['<button><span class="x">Appliquer</span></button>', 0],
		//  Un `>` dans une expression ne doit pas couper la lecture de la balise.
		['<button disabled={n > 0} aria-label="Ajouter">＋</button>', 0],
		//  …et il ne doit pas non plus masquer un manque réel.
		['<button disabled={n > 0}>＋</button>', 1],
		//  Une chaîne JS dans un `<script>` n'est pas du balisage.
		['<script>const s = "<button>✕</button>";</script>', 0],
		//  ⚠️ Un `<slot>` porte le texte de l'appelant : on ne juge pas.
		['<button><slot /></button>', 0],
		//  Aucun bouton : rien à dire.
		['<div>rien</div>', 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = boutonsMuets(src).length;
		if (n !== attendu) {
			console.error(`  ✗ « ${src.slice(0, 70)} » → ${n}, attendu ${attendu}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.\n`);
		process.exit(1);
	}
	console.log(`✓ Auto-test : ${cas.length} cas — le bouton muet est vu, le reste passe.`);
	process.exit(0);
}

const fichiers = svelte(RACINE);
//  🔴 CAS ZÉRO. Zéro fichier n'est pas « zéro faute » : c'est une lecture qui
//  n'a pas eu lieu (`standards/04` §1).
if (fichiers.length === 0) {
	console.error('\n✗ Aucun .svelte lu — le contrôle ne mesure RIEN.\n');
	process.exit(1);
}

const fautes = [];
const restantes = new Set(Object.keys(EXCEPTIONS));
for (const fichier of fichiers.sort()) {
	const chemin = `src/${relative(RACINE, fichier).split(sepOS).join('/')}`;
	const source = readFileSync(fichier, 'utf8');
	for (const { ligne } of boutonsMuets(source)) {
		const cle = `${chemin}:${ligne}`;
		if (cle in EXCEPTIONS) {
			restantes.delete(cle);
			continue;
		}
		fautes.push(`${chemin}:${ligne}`);
	}
}

if (restantes.size > 0) {
	console.error(
		`\n✗ Exception(s) à retirer, le défaut n'existe plus : ${[...restantes].join(', ')}\n`,
	);
	process.exit(1);
}

if (fautes.length > 0) {
	console.error(`\n✗ ${fautes.length} bouton(s) icône-seule sans nom accessible :\n`);
	for (const f of fautes) console.error(`  ${f}`);
	console.error(
		'\n  Un lecteur d’écran annonce « bouton », et rien d’autre. Au doigt, le\n' +
			'  `title` ne s’affiche jamais.\n' +
			'  → aria-label="Ce que fait le bouton" (le GESTE, ou l’ÉTAT quand les\n' +
			'    glyphes en montrent un — cf. `BoutonOptions`).\n',
	);
	process.exit(1);
}

console.log(
	`✓ Boutons icône : ${fichiers.length} fichier(s) lus, tous les boutons sans texte ont un nom accessible.`,
);
