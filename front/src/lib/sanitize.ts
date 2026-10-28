/**
 * Sanitisation HTML — défense contre les attaques XSS.
 * Client : DOMPurify (DOM natif du navigateur — gold standard).
 * Serveur : nettoyage regex allow-list (pas de jsdom, léger et compatible Node 22).
 */

// Chargement async fire-and-forget côté client uniquement.
// SSR et premier rendu client utilisent le fallback regex.
// Dès que DOMPurify est chargé (quelques ms), il prend le relais.
let _purify: { sanitize: (html: string, cfg: object) => string } | null = null;

if (typeof window !== 'undefined') {
	import('dompurify').then((mod) => {
		_purify = mod.default;
	});
}

const ALLOWED_TAGS = [
	'p',
	'br',
	'b',
	'i',
	'u',
	's',
	'strong',
	'em',
	'ul',
	'ol',
	'li',
	'blockquote',
	'pre',
	'code',
	'h1',
	'h2',
	'h3',
	'h4',
	'h5',
	'h6',
	'a',
	'img',
	'hr',
	'span',
	'div',
	//  🔴 LE BLOC DÉPLIABLE (#992, 17/09/2026) — les extraits d'articles que la
	//  synthèse d'un contrat joint en fin de texte : onze extraits de trente
	//  lignes, dépliés, noieraient la synthèse qu'ils éclairent.
	//
	//  ⚠️ `open` n'est PAS ajouté à `ALLOWED_ATTR`, et c'est ce qui rend le repli
	//  fiable : l'attribut est retiré quoi que le modèle écrive, donc un bloc
	//  arrive toujours fermé. Le repli n'est pas une consigne qu'on espère
	//  respectée, c'est une propriété du rendu.
	//
	//  📖 Les nœuds qui les font survivre à l'éditeur : `#lib/blocDepliable`.
	//  Ces trois listes — celle-ci, celle du schéma Tiptap et celle de la
	//  consigne donnée au modèle — sont tenues d'accord par
	//  `api/tests/test_consigne_balises.py`.
	'details',
	'summary',
];

const ALLOWED_ATTR = ['href', 'src', 'alt', 'title', 'class', 'target', 'rel'];

const _allowedTagSet = new Set(ALLOWED_TAGS);
//  Les débuts d'URL admis par l'assainisseur de SECOURS (rendu serveur, premier
//  rendu) — absolue web, courriel, chemin relatif, ancre ; une image, absolue web
//  ou chemin (`/uploads/…`). Ni data-URI ni `//hote` (protocole implicite).
const URL_HREF_ADMISE = /^(?:https?:\/\/|mailto:|\/(?!\/)|#|\.{1,2}\/)/i;
const URL_SRC_ADMISE = /^(?:https?:\/\/|\/(?!\/))/i;
const _allowedAttrSet = new Set(ALLOWED_ATTR);

/** Nettoyage regex basique pour le SSR (les clients ré-hydrateront avec DOMPurify). */
function _serverSanitize(input: string): string {
	return input
		.replace(/<script[\s>][\s\S]*?<\/script>/gi, '')
		.replace(/<style[\s>][\s\S]*?<\/style>/gi, '')
		.replace(/on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '')
		.replace(/<\/?([a-z][a-z0-9]*)\b([^>]*)>/gi, (match, tag, attrs) => {
			const tagLower = tag.toLowerCase();
			if (!_allowedTagSet.has(tagLower)) return '';
			const cleanAttrs = (attrs || '').replace(
				/\s([a-z][a-z-]*)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]*))?/gi,
				(_: string, attrName: string, valeur: string) => {
					const nom = attrName.toLowerCase();
					if (!_allowedAttrSet.has(nom)) return '';
					//  🔴 Une URL n'est admise que par son DÉBUT (#2159) : la liste blanche
					//  gardait `href="javascript:…"`, que seule la CSP arrêtait encore.
					//  Ni décodage ni liste noire : un schéma déguisé (entités, blancs)
					//  ne commence par aucun des débuts admis, donc il tombe.
					if (nom === 'href' || nom === 'src') {
						const url = (valeur || '').replace(/^["']|["']$/g, '').trim();
						const admis = nom === 'src' ? URL_SRC_ADMISE : URL_HREF_ADMISE;
						if (!admis.test(url)) return '';
					}
					return _;
				},
			);
			return match.startsWith('</') ? `</${tagLower}>` : `<${tagLower}${cleanAttrs}>`;
		});
}

/**
 * Sanitise une chaîne HTML et retourne la version sûre.
 * Si l'entrée est vide/nulle, retourne ''.
 */
export function safeHtml(input: string | null | undefined): string {
	if (!input) return '';
	if (_purify) {
		return _purify.sanitize(input, {
			ALLOWED_TAGS,
			ALLOWED_ATTR,
			ALLOW_DATA_ATTR: false,
		});
	}
	return _serverSanitize(input);
}

/**
 * Rend un contenu stocké soit en HTML riche, soit en texte simple.
 * - HTML : sanitise et conserve la structure.
 * - Texte : sanitise puis remplace les retours ligne par des <br>.
 */
export function safeRichContent(input: string | null | undefined): string {
	if (!input) return '';
	const value = input.trim();
	const looksLikeHtml = /<\/?[a-z][\s\S]*>/i.test(value);
	if (looksLikeHtml) return safeHtml(value);
	return safeHtml(value).replace(/\n/g, '<br>');
}

/**
 * Comme `safeRichContent`, mais enveloppe le texte simple dans un `<p>`.
 *
 * Pourquoi deux fonctions plutôt qu'un paramètre : `safeRichContent` est appelée
 * à l'intérieur d'un `<p>` existant (page Notifications), où produire un second
 * `<p>` donnerait un HTML invalide. La différence est donc structurelle, pas une
 * option — chaque appelant choisit celle qui correspond à son contexte.
 *
 * Cette variante était écrite en double sous le nom `renderDesc`, dans
 * `tickets/+page.svelte` et `espace-cs/+page.svelte`, alors qu'elle ne diffère
 * de `safeRichContent` que par cette enveloppe. Les descriptions de tickets et
 * d'évolutions en ont besoin : elles sont rendues dans `.rich-content`, dont les
 * styles (interlignage, marges) s'appliquent aux blocs.
 */
export function safeDescription(input: string | null | undefined): string {
	if (!input) return '';
	if (input.trimStart().startsWith('<')) return safeHtml(input);
	return safeHtml(`<p>${input.replace(/\n/g, '<br>')}</p>`);
}
