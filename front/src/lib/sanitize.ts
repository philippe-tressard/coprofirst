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
	//  Rattrapé (#2683) : sous WebKit, une navigation pendant le chargement le fait
	//  échouer, et le rejet devenait une exception non rattrapée de la page. En
	//  échec, le repli à liste blanche reste en service — celui du rendu serveur,
	//  le même qu'avant l'arrivée de DOMPurify ; l'API assainit de son côté (#2150).
	import('dompurify').then(
		(mod) => {
			_purify = mod.default;
		},
		() => {
			/* le repli reste en service */
		},
	);
}

//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const ALLOWED_TAGS = [
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

//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const ALLOWED_ATTR = ['href', 'src', 'alt', 'title', 'class', 'target', 'rel'];

const _allowedTagSet = new Set(ALLOWED_TAGS);
//  Les débuts d'URL admis par l'assainisseur de SECOURS (rendu serveur, premier
//  rendu) — absolue web, courriel, chemin relatif, ancre ; une image, absolue web
//  ou chemin (`/uploads/…`). Ni data-URI ni `//hote` (protocole implicite).
const URL_HREF_ADMISE = /^(?:https?:\/\/|mailto:|\/(?!\/)|#|\.{1,2}\/)/i;
const URL_SRC_ADMISE = /^(?:https?:\/\/|\/(?!\/))/i;
const _allowedAttrSet = new Set(ALLOWED_ATTR);

//  L'assainisseur de SECOURS : rendu serveur, et premier rendu du navigateur tant
//  que DOMPurify n'est pas chargé (son import est asynchrone, ci-dessus).
//
//  🔴 Il LIT l'entrée en jetons, il ne RETIRE pas des motifs (#2882). L'ancienne
//  version enchaînait des `replace` : retirer `on…=` pouvait en RECOLLER un
//  (`oonclick=""nerror=` → `onerror=`), et une valeur entre guillemets qui
//  contenait `>` coupait la balise — le reste, gestionnaire compris, passait tel
//  quel. Seule la CSP (`script-src` sans `unsafe-inline`) arrêtait encore le script.
//
//  Ce qui sort est une GRAMMAIRE fermée, éprouvée par `npm run lint:html`
//  (`scripts/check-html.mjs` §5, corpus hostile et fuzz) :
//    - du texte sans `<` ni `>` (ceux de l'entrée sortent en `&lt;` / `&gt;`) ;
//    - `<balise attr="valeur">` ou `</balise>`, balise de `ALLOWED_TAGS`, attribut
//      de `ALLOWED_ATTR`, valeur toujours entre `"` et sans `"`, `<` ni `>`.
//  Ce que la grammaire n'admet pas ne sort pas : rien n'est « réparé ».
//
//  ⚠️ Les deux motifs sont LINÉAIRES : le nom de balise se clôt par une
//  anticipation (sans elle, `<aaaa…` sans `>` coûtait n² au rendu serveur), et
//  les trois formes d'un attribut commencent par des caractères disjoints.
const _JETON =
	/<!--[\s\S]*?(?:--!?>|$)|<(\/?)([a-zA-Z][a-zA-Z0-9]*)(?![a-zA-Z0-9])((?:[^<>"']|"[^"]*"|'[^']*')*)>|[<>]/g;
const _ATTRIBUT = /([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'<>=`]+)))?/g;
//  Balises dont le CONTENU tombe avec elles (il sortirait en texte inerte, mais
//  illisible) — le reste d'une balise refusée garde son texte.
const _CONTENU_RETIRE = new Set(['script', 'style']);

const _echapperValeur = (v: string) =>
	v.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function _attributs(brut: string): string {
	let sortie = '';
	for (const a of brut.matchAll(_ATTRIBUT)) {
		const nom = a[1].toLowerCase();
		if (!_allowedAttrSet.has(nom)) continue;
		const valeur = a[2] ?? a[3] ?? a[4] ?? '';
		//  🔴 Une URL n'est admise que par son DÉBUT (#2159) : la liste blanche
		//  gardait `href="javascript:…"`, que seule la CSP arrêtait encore.
		//  Ni décodage ni liste noire : un schéma déguisé (entités, blancs)
		//  ne commence par aucun des débuts admis, donc il tombe.
		if (nom === 'href' || nom === 'src') {
			const admis = nom === 'src' ? URL_SRC_ADMISE : URL_HREF_ADMISE;
			if (!admis.test(valeur.trim())) continue;
		}
		sortie += ` ${nom}="${_echapperValeur(valeur)}"`;
	}
	return sortie;
}

/** Éprouvé par `npm run lint:html` (`scripts/check-html.mjs` §5), par `safeHtml` hors navigateur. */
function _serverSanitize(input: string): string {
	let sortie = '';
	let retire: string | null = null; //  la balise dont on saute le contenu
	let depuis = 0;
	for (const m of input.matchAll(_JETON)) {
		if (retire === null) sortie += input.slice(depuis, m.index);
		depuis = (m.index ?? 0) + m[0].length;
		const [jeton, fermante, nomBrut, attrs] = m;
		if (!nomBrut) {
			//  Un commentaire tombe ; un `<` ou un `>` isolé devient du texte.
			if (retire === null && !jeton.startsWith('<!--')) sortie += jeton === '<' ? '&lt;' : '&gt;';
			continue;
		}
		const nom = nomBrut.toLowerCase();
		if (retire !== null) {
			if (fermante && nom === retire) retire = null;
			continue;
		}
		if (!fermante && _CONTENU_RETIRE.has(nom)) {
			retire = nom;
			continue;
		}
		if (!_allowedTagSet.has(nom)) continue;
		sortie += fermante ? `</${nom}>` : `<${nom}${_attributs(attrs)}>`;
	}
	if (retire === null) sortie += input.slice(depuis);
	return sortie;
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
