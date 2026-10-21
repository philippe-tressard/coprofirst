/**
 * Télémétrie — collecte des pages visitées et des erreurs vues à l'écran.
 *
 * Utilise `navigator.sendBeacon` pour un envoi non-bloquant (fire-and-forget).
 * Les événements sont accumulés en mémoire et envoyés en batch toutes les 30 s
 * ou au moment du déchargement de la page (beforeunload / visibilitychange).
 *
 * Aucun impact sur la latence utilisateur.
 *
 * Ce que le serveur fait de ces lots — rattachés au compte s'il y en a un, refus
 * du profil honoré une seconde fois — se lit dans `api/app/routers/telemetry_collecte.py`,
 * pas ici. 🔴 Cet en-tête l'a décrit « anonyme » après la migration 0247, qui
 * rattachait de nouveau la mesure au compte (#1635) : un commentaire qui
 * raconte un autre fichier diverge sans bruit. Ce qui est vrai ICI : le refus
 * du profil s'applique aussi dans le navigateur — qui refuse n'envoie plus rien.
 */

const FLUSH_INTERVAL = 30_000; // 30 secondes
const ENDPOINT = '/api/telemetry/collect';
/** Au-delà, le serveur refuse le lot (`EVENEMENTS_PAR_LOT` de
 *  `telemetry_collecte.py`, #1597) : la file part dès qu'elle l'atteint. ⚠️ Les
 *  deux valeurs se tiennent à la main — le front et l'API ne partagent aucun
 *  fichier. */
const EVENEMENTS_PAR_LOT = 20;
/** L'action d'un signalement d'erreur (#1631). ⚠️ Tenue à la main avec
 *  `ACTION_ERREUR` de `api/app/utils/erreurs_navigateur.py`. */
const ACTION_ERREUR = 'erreur';
/** Au plus tant de signalements par onglet ouvert : une boucle d'erreurs ne doit
 *  ni épuiser la limite de collecte du serveur ni noyer les vues du même lot. */
const SIGNALEMENTS_PAR_ONGLET = 10;
/** Le `max_length` du `detail` côté serveur (`EvenementAudience`) : au-delà, le
 *  lot entier serait refusé, vues comprises. */
const LONGUEUR_DETAIL = 100;
/** L'action d'une durée d'affichage (#1632). ⚠️ Tenue à la main, avec la durée
 *  maximale, avec `ACTION_MESURE` et `DUREE_MAX_MS` de
 *  `api/app/utils/mesures_affichage.py`. */
const ACTION_MESURE = 'perf';
const DUREE_MAX_MS = 60_000;
/** Les indicateurs d'une durée d'affichage. ⚠️ Tenus avec `INDICATEURS` de
 *  `api/app/utils/mesures_affichage.py` — `test_mesures_affichage.py` les compare. */
export const INDICATEURS = ['chargement', 'navigation', 'donnees'] as const;

const buffer: { page: string; action: string; detail?: string }[] = [];
let timer: ReturnType<typeof setInterval> | null = null;
let disabled = false;
/** Les couples (page, code) déjà signalés par cet onglet. */
const signales = new Set<string>();

/** Refus de la mesure d'audience — appliqué ici, seul endroit qui le peut. */
export function setTelemetryOptOut(optOut: boolean) {
	disabled = optOut;
	if (optOut) buffer.length = 0;
}

/** Enregistre un événement de télémétrie (non-bloquant). */
export function trackEvent(page: string, action = 'view', detail?: string) {
	if (disabled) return;
	buffer.push({ page, action, ...(detail ? { detail } : {}) });
	if (buffer.length >= EVENEMENTS_PAR_LOT) flush();
}

/** Enregistre une vue de page — avec, à l'arrivée, la notification qui y a mené (#1634). */
export function trackPageView(path: string, source?: string) {
	trackEvent(path, 'view', source);
}

/** Enregistre une vue d'onglet (page#tab). */
export function trackTabView(tab: string) {
	if (typeof window === 'undefined') return;
	trackEvent(`${window.location.pathname}#${tab}`, 'view');
}

/**
 * **Le CODE d'une erreur — ce qu'on en garde, jamais son message brut** (#1631).
 *
 * Un message peut porter une saisie de l'utilisateur ; une pile d'appels, des
 * chemins de fichiers. On garde donc, dans cet ordre :
 * - le code d'une erreur Svelte (`svelte:each_key_duplicate`), lu dans le lien
 *   que Svelte 5 met dans chaque message ;
 * - le statut et le chemin d'une réponse en échec (`ApiError`, reconnue à ses
 *   champs : l'importer ferait boucler ce module et le client d'API) ;
 * - sinon le nom de l'erreur et la PREMIÈRE ligne du message, sans ce qui est
 *   entre guillemets ou chevrons et sans les nombres.
 */
export function codeErreur(e: unknown): string {
	const brut = e instanceof Error ? e.message : String(e ?? '');
	const svelte = /svelte\.dev\/e\/(\w+)/.exec(brut);
	if (svelte) return `svelte:${svelte[1]}`;
	const reponse = e as { status?: unknown; chemin?: unknown } | null;
	if (typeof reponse?.status === 'number') {
		return codeHttp(reponse.status, typeof reponse.chemin === 'string' ? reponse.chemin : '?');
	}
	const nom = e instanceof Error ? e.name : typeof e;
	const signature = (brut.split('\n')[0] ?? '')
		.replace(/(["'`])[^"'`]*\1|«[^»]*»/g, '…')
		.replace(/\d+/g, '#')
		.replace(/\s+/g, ' ')
		.trim();
	return (signature ? `${nom}: ${signature}` : nom).slice(0, LONGUEUR_DETAIL);
}

/** Un chemin aux identifiants masqués, sans sa requête (`/tickets/#`) — mille
 *  affaires ne font pas mille lignes. */
function sansIdentifiants(chemin: string): string {
	return chemin.split('?')[0].replace(/\d+/g, '#');
}

/** Le code d'une réponse en échec : statut et chemin (`HTTP 502 /tickets/#`). */
export function codeHttp(status: number, chemin: string): string {
	return `HTTP ${status} ${sansIdentifiants(chemin)}`.slice(0, LONGUEUR_DETAIL);
}

/** Le début de la navigation en cours — `performance.now()`, ou `null`. */
let debutNavigation: number | null = null;
/** Le début de l'écran affiché, pour `donnees` — `null` une fois mesuré. Le
 *  premier écran commence à l'ouverture de l'onglet (`0`, l'origine de
 *  `performance.now()`), les suivants à `commencerNavigation`. */
let debutEcran: number | null = 0;

/** À appeler par `beforeNavigate` : une navigation commence. */
export function commencerNavigation() {
	if (typeof performance === 'undefined') return;
	debutNavigation = debutEcran = performance.now();
}

/** Envoie une durée depuis `debut` — rien hors de `[0, DUREE_MAX_MS]`. */
function envoyerDuree(indicateur: (typeof INDICATEURS)[number], debut: number) {
	const duree = Math.round(performance.now() - debut);
	if (duree < 0 || duree > DUREE_MAX_MS) return;
	trackEvent(sansIdentifiants(window.location.pathname), ACTION_MESURE, `${indicateur}:${duree}`);
}

/**
 * **La durée d'affichage d'un écran** (#1632) — à appeler par `afterNavigate`.
 *
 * - `enter` (la première page de l'onglet) : `chargement`, de l'ouverture de
 *   l'onglet à l'application prête — `performance.now()` part de là ;
 * - toute autre navigation : `navigation`, depuis `commencerNavigation`.
 *
 * Mesurée de la même façon dans tous les navigateurs (le LCP n'existe pas sous
 * Safari). ⚠️ Ni l'une ni l'autre ne compte le temps qu'un écran passe ensuite à
 * lire ses données : l'écran de télémétrie le dit.
 */
export function mesurerNavigation(type: string) {
	if (typeof window === 'undefined' || typeof performance === 'undefined') return;
	const indicateur = type === 'enter' ? 'chargement' : 'navigation';
	const debut = type === 'enter' ? 0 : debutNavigation;
	debutNavigation = null;
	if (debut !== null) envoyerDuree(indicateur, debut);
}

/**
 * **Les données principales de l'écran sont affichées** (#1846) — à appeler par
 * l'écran, une fois ce qu'il montre d'abord arrivé et posé.
 *
 * `chargement` et `navigation` s'arrêtent à l'hydratation : la moitié de
 * l'attente, celle des données, leur échappait (Affaires à chaud : 430 ms
 * hydratée, 861 ms affichée). Cette durée part du même début et s'arrête au
 * rendu suivant (`requestAnimationFrame`, puis la fin de la tâche : le dessin
 * de la liste compte, #1840). Une fois par écran ; un écran qui ne l'appelle
 * pas ne produit RIEN, jamais 0. 🔒 `npm run lint:donnees-affichees` exige
 * l'appel des écrans de premier niveau.
 */
export function marquerDonneesAffichees() {
	if (typeof window === 'undefined' || typeof performance === 'undefined') return;
	const debut = debutEcran;
	debutEcran = null;
	if (debut === null) return;
	requestAnimationFrame(() => setTimeout(() => envoyerDuree('donnees', debut)));
}

/** Signale une erreur vue à l'écran — une fois par page et par code, pour cet onglet. */
export function signalerErreur(code: string) {
	if (typeof window === 'undefined') return;
	const page = window.location.pathname;
	const cle = `${page}|${code}`;
	if (signales.has(cle) || signales.size >= SIGNALEMENTS_PAR_ONGLET) return;
	signales.add(cle);
	trackEvent(page, ACTION_ERREUR, code);
}

function flush() {
	if (buffer.length === 0) return;
	const events = buffer.splice(0);
	const payload = JSON.stringify({ events });
	try {
		if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
			navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: 'application/json' }));
		} else {
			// Fallback pour les navigateurs sans sendBeacon
			fetch(ENDPOINT, {
				method: 'POST',
				body: payload,
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				keepalive: true,
			}).catch(() => {});
		}
	} catch {
		// Silencieux — ne jamais impacter l'UX
	}
}

/**
 * Envoie la file tout de suite, sans attendre les 30 s du minuteur — pour le
 * signalement d'un rechargement de secours (#1993), qui se lit aussitôt.
 */
export function envoyerMaintenant() {
	flush();
}

/** Initialise la télémétrie — une fois, par le layout RACINE : toutes les pages,
 *  `/auth/*` compris (#2066). */
export function initTelemetry() {
	if (typeof window === 'undefined') return;
	if (timer) return; // Déjà initialisé

	timer = setInterval(flush, FLUSH_INTERVAL);

	// Flush au déchargement de la page
	window.addEventListener('visibilitychange', () => {
		if (document.visibilityState === 'hidden') flush();
	});
	window.addEventListener('beforeunload', flush);

	//  Ce que rien n'a rattrapé (#1631). Les erreurs d'un chargement ou d'une
	//  navigation n'arrivent pas jusqu'ici : `hooks.client.ts` les prend.
	window.addEventListener('error', (ev) => {
		if (erreurDuSite(ev.error, ev.filename)) signalerErreur(codeErreur(ev.error ?? ev.message));
	});
	window.addEventListener('unhandledrejection', (ev) => {
		if (erreurDuSite(ev.reason)) signalerErreur(codeErreur(ev.reason));
	});
}

/** Scripts de NOTRE origine qui ne sont pas les nôtres : l'arête Cloudflare y
 *  sert les siens (détection des robots, préchargement). */
const SCRIPTS_DE_L_ARETE = '/cdn-cgi/';

/**
 * **Une erreur levée par ce site — et non par un script étranger** (04/10/2026).
 *
 * L'écran « Erreurs vues par les résidents » a relevé, le 03/10, un
 * `t().filter is not a function` sur `/annonces` et `/tickets` : du code ES5
 * transpilé (`function(e){var t=s({},e).type…`) qu'aucun des fichiers servis
 * ne contient — vérifié sur les 152 morceaux de la production et sur les
 * scripts de l'arête. Une extension ou le navigateur intégré d'une application
 * l'avait injecté dans la page ; il était imputé au site.
 *
 * - un fichier d'une autre origine, ou masqué par le navigateur
 *   (`webkit-masked-url://`, `chrome-extension://`…), n'est pas le nôtre ;
 * - une `Error` venue d'un AUTRE contexte JavaScript (le `object:` du relevé :
 *   une erreur, mais pas une `Error` d'ici) non plus — le site n'en crée aucun
 *   qui fasse remonter ses erreurs jusqu'à cette fenêtre.
 */
export function erreurDuSite(erreur: unknown, fichier?: string): boolean {
	if (fichier) {
		try {
			const url = new URL(fichier);
			if (url.origin !== window.location.origin) return false;
			if (url.pathname.startsWith(SCRIPTS_DE_L_ARETE)) return false;
		} catch {
			return false;
		}
	}
	const autreContexte =
		Object.prototype.toString.call(erreur) === '[object Error]' && !(erreur instanceof Error);
	return !autreContexte;
}
