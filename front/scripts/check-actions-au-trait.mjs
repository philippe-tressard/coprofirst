/**
 * Garde-fou : un bouton d'ACTION se dessine au trait, jamais en émoji.
 *
 * ## Pourquoi (10/10/2026, #1819)
 *
 * La page Affaires a reçu ses actions au trait (maquette B, choisie à l'écran) :
 * six émojis de six couleurs sur une carte, la couleur ne hiérarchisait plus
 * rien. Le soir même, l'utilisateur en a fait le STANDARD du site — « l'UX de la
 * page Affaires (icônes, cartes, tout l'UX) est le standard ; applique-le à
 * toutes les pages ». Une centaine de boutons ✏️ 🗑️ 📦 ↩️ … ont été redessinés
 * par `IconeAction`. Rien n'empêchait le suivant de revenir en émoji : la règle
 * se recopie au premier bouton écrit de mémoire, et l'écran est derrière une
 * connexion qu'aucun contrôle n'ouvre.
 *
 * ## Ce qu'il lit
 *
 * Tout `<button>` de `src/` dont le contenu visible est un ÉMOJI sans aucun mot
 * — un bouton icône-seule dessiné en couleur. Le pictogramme passe par
 * `<IconeAction icone="…" />` (`#lib/icones-svg.json`).
 *
 * Ce qu'il ne juge PAS, et pourquoi :
 *  - un bouton qui PARLE (« 🚩 Signaler l'annonce ») : l'émoji y décore un mot,
 *    ce n'est pas une icône d'action ;
 *  - un contenu calculé (`{g.glyphe}`) : on ne peut pas savoir ici ce qu'il
 *    rendra — le crier ferait un contrôle qui ment ;
 *  - les zones de code (`<script>`, `<style>`).
 *
 * Usage : node scripts/check-actions-au-trait.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { balisageSeul } from './lib-analyse-styles.mjs';
import { balisesOuvrantes, contenuDe, ligneDe, porteUnMot } from './lib-balises.mjs';
import { fichiersSources } from './lib-source-unique.mjs';

const RACINE = fileURLToPath(new URL('../src', import.meta.url)).replaceAll('\\', '/');

/**
 * Les exceptions, NOMMÉES avec leur raison (`chemin` → raison) — et le contrôle
 * échoue si l'une cesse de servir. Une exception non écrite n'est pas une
 * exception.
 */
//  `BoutonAssistant` en était une (son ✨ émoji qui pulsait) jusqu'au 17/10/2026 :
//  tout geste qui lance l'assistant se dessine désormais par `IconeIA`, au trait.
const EXCEPTIONS = Object.assign(Object.create(null), {});

const EMOJI = /\p{Extended_Pictographic}/u;

/** Le contenu est-il un émoji SEUL — sans mot, sans expression calculée ? */
export function emojiSeul(contenu) {
	if (porteUnMot(contenu)) return false;
	//  Le texte que le bouton affiche en dur : hors balises, blocs et expressions.
	const texte = contenu
		.replace(/\{[^}]*\}/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		//  Une entité numérique (`&#x1F5D1;`) rend un émoji comme un autre.
		.replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
		.replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)));
	return EMOJI.test(texte);
}

/** Les boutons en émoji d'une source. PURE : éprouvable sans arborescence. */
export function boutonsEnEmoji(source) {
	const nu = balisageSeul(source);
	const fautes = [];
	for (const ouvrante of balisesOuvrantes(nu, 'button')) {
		if (emojiSeul(contenuDe(nu, 'button', ouvrante))) {
			fautes.push({ ligne: ligneDe(nu, ouvrante.index) });
		}
	}
	return fautes;
}

if (process.argv.includes('--selftest')) {
	const cas = [
		//  🔴 LE CAS : une action dessinée en émoji.
		['<button class="btn-icon-edit" aria-label="Modifier">✏️</button>', 1],
		['<button class="btn-icon-danger" aria-label="Supprimer">\n\t🗑️\n</button>', 1],
		//  La fermeture que Prettier écrit sur deux lignes (le faux vert de #1819).
		['<button aria-label="Modifier">✏️</button\n\t>\n<p>Un texte qui parle</p>', 1],
		//  Une entité numérique est un émoji comme un autre.
		['<button aria-label="Supprimer">&#x1F5D1;️</button>', 1],
		//  Au trait, il passe.
		['<button aria-label="Modifier"><IconeAction icone="pencil" /></button>', 0],
		//  Un bouton qui PARLE n'est pas une icône d'action.
		["<button>🚩 Signaler l'annonce</button>", 0],
		//  Un contenu calculé ne se juge pas.
		['<button aria-label={g.libelle}>{g.glyphe}</button>', 0],
		//  Un émoji dans une condition reste un émoji en dur.
		['<button aria-label="Voter">{#if vote}❤️{:else}🤍{/if}</button>', 1],
		//  Une chaîne JS dans un `<script>` n'est pas du balisage.
		['<script>const s = "<button>✏️</button>";</script>', 0],
		//  Un glyphe typographique n'est pas un émoji : ce contrôle ne le juge pas.
		['<button aria-label="Fermer">×</button>', 0],
		//  Aucun bouton : rien à dire.
		['<div>✏️</div>', 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = boutonsEnEmoji(src).length;
		if (n !== attendu) {
			console.error(`  ✗ « ${src.slice(0, 70)} » → ${n}, attendu ${attendu}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.\n`);
		process.exit(1);
	}
	console.log(`✓ Auto-test : ${cas.length} cas — l'action en émoji est vue, le reste passe.`);
	process.exit(0);
}

const fichiers = fichiersSources(RACINE, ['.svelte']);
//  🔴 CAS ZÉRO. Zéro fichier n'est pas « zéro faute » : c'est une lecture qui
//  n'a pas eu lieu (`standards/04` §1).
if (fichiers.length === 0) {
	console.error('\n✗ Aucun .svelte lu — le contrôle ne mesure RIEN.\n');
	process.exit(1);
}

const fautes = [];
const restantes = new Set(Object.keys(EXCEPTIONS));
for (const fichier of fichiers.sort()) {
	const chemin = `src/${fichier.slice(RACINE.length + 1)}`;
	const trouvees = boutonsEnEmoji(readFileSync(fichier, 'utf8'));
	if (trouvees.length && chemin in EXCEPTIONS) {
		restantes.delete(chemin);
		continue;
	}
	for (const { ligne } of trouvees) fautes.push(`${chemin}:${ligne}`);
}

if (restantes.size > 0) {
	console.error(
		`\n✗ Exception(s) à retirer, le défaut n'existe plus : ${[...restantes].join(', ')}\n`,
	);
	process.exit(1);
}

if (fautes.length > 0) {
	console.error(`\n✗ ${fautes.length} bouton(s) d'action dessiné(s) en émoji :\n`);
	for (const f of fautes) console.error(`  ${f}`);
	console.error(
		'\n  Le standard du site (page Affaires, 10/10/2026) dessine les actions AU\n' +
			'  TRAIT : gris au repos, Bleu Seine au survol.\n' +
			'  → <IconeAction icone="pencil" /> (noms : `#lib/icones-svg.json`),\n' +
			'    en gardant l’aria-label du bouton.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Actions au trait : ${fichiers.length} fichier(s) lus, aucun bouton d'action en émoji.`,
);
