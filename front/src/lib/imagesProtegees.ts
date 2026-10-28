/**
 * **Une image protégée qui échoue parce que la session a expiré (#996).**
 *
 * ## Le défaut, constaté en production le 17/09/2026
 *
 * Les vignettes et les photos d'un ticket s'affichaient cassées. Mesuré côté
 * serveur : `/uploads/tickets/…jpg` répondait **401**, et 200 dès la
 * reconnexion. Le serveur était sain, le fichier présent — seule la session
 * avait expiré. L'utilisateur, lui, voyait une panne du site.
 *
 * ## Pourquoi les images n'étaient pas couvertes
 *
 * `/uploads/*` passe par le `forward_auth` du Caddyfile, et le navigateur
 * charge ces fichiers **lui-même** : ils ne traversent pas le client
 * TypeScript. Le renouvellement silencieux sur 401 — écrit dans
 * `#lib/api/client.ts` et déployé sur tous les appels d'API depuis #379 —
 * n'avait donc aucune prise sur eux. L'access token vit 120 min, le refresh
 * token 7 jours : pendant cette fenêtre la session est parfaitement
 * renouvelable, et c'est exactement le cas qui s'est produit.
 *
 * ## Ce que fait ce module, et ce qu'il ne fait pas
 *
 * 🔴 **Un seul écouteur, aucune règle dans un écran.** Il est monté par le
 * layout racine et s'applique à toute image protégée, présente ou future.
 * C'est la contrainte du projet : la règle la plus déployée est enrichie pour
 * couvrir ses occurrences, elle n'est pas recopiée dans les composants qui
 * affichent des photos (`Vignette`, `PiecesJointes`, `FluxVignette`, et les
 * écrans qui écrivent un `<img>` à la main).
 *
 * La conduite à tenir n'est pas réécrite ici : `renouvelerSession()` est celle
 * du client, redirection vers la mire comprise quand la session est morte.
 *
 * ⚠️ **Une image absente reste silencieuse.** Un 404 n'est pas une affaire de
 * session ; annoncer une session expirée dans ce cas serait un faux message,
 * et l'utilisateur chercherait à se reconnecter pour rien.
 */
import { renouvelerSession } from '#lib/api/client.ts';

/**
 * Le préfixe des fichiers derrière `forward_auth` (Caddyfile).
 *
 * Tout `/uploads/` est derrière la session depuis le 30/09/2026 (#1494) :
 * `/uploads/publications/`, public pour un bridge WhatsApp qui reçoit les
 * images en base64 depuis le 10/08, suit la règle commune. Si un dossier
 * redevenait public, rien ne serait à changer ici : une image publique ne rend
 * jamais 401, et la sonde conclut « rien à faire » d'elle-même.
 */
const PROTEGEES = '/uploads/';

/**
 * Les images cassées depuis le dernier verdict, et celles déjà rejouées.
 *
 * ⚠️ `rejouees` est un `WeakSet` : sans lui, une image qui échouerait encore
 * après renouvellement relancerait une sonde, puis un renouvellement, sans fin.
 * Une image n'a droit qu'à une seule seconde chance.
 */
const cassees = new Set<HTMLImageElement>();
const rejouees = new WeakSet<HTMLImageElement>();
let minuteur: ReturnType<typeof setTimeout> | null = null;
let sondeEnCours = false;

/** Le délai de regroupement : une page de douze vignettes ne pose qu'UNE question. */
const REGROUPEMENT_MS = 200;

function estProtegee(img: HTMLImageElement): boolean {
	//  L'attribut, pas la propriété : `img.src` est résolu en URL absolue par le
	//  navigateur, et un `src` relatif deviendrait méconnaissable.
	const brut = img.getAttribute('src') ?? '';
	if (brut.startsWith(PROTEGEES)) return true;
	//  Une URL absolue vers notre propre origine compte aussi — c'est la forme
	//  que prennent les images passées au bridge WhatsApp.
	try {
		const url = new URL(brut, window.location.origin);
		return url.origin === window.location.origin && url.pathname.startsWith(PROTEGEES);
	} catch {
		return false;
	}
}

/** Redemande l'image, en contournant l'échec déjà mémorisé par le navigateur. */
function rejouer(img: HTMLImageElement): void {
	rejouees.add(img);
	try {
		const url = new URL(img.src, window.location.origin);
		//  Réaffecter le même `src` ne redemande rien : le navigateur a déjà son
		//  verdict. Le paramètre change l'URL sans changer le fichier — Caddy sert
		//  `file_server` sur le chemin, la chaîne de requête ne l'atteint pas.
		url.searchParams.set('r', String(Date.now()));
		img.src = url.pathname + url.search;
	} catch {
		//  URL illisible : rien à rejouer, et surtout pas de message à afficher.
	}
}

async function conclure(): Promise<void> {
	minuteur = null;
	const lot = [...cassees].filter((img) => !rejouees.has(img));
	cassees.clear();
	if (lot.length === 0 || sondeEnCours) return;

	sondeEnCours = true;
	try {
		//  🔴 UNE sonde pour tout le lot. L'événement `error` d'une image ne porte
		//  PAS le statut HTTP — c'est pour cela qu'il faut redemander le fichier
		//  pour savoir ce qui a échoué. Une sonde par vignette cassée ferait
		//  douze requêtes là où une seule répond à la question.
		const reponse = await fetch(lot[0].src, { credentials: 'include', cache: 'no-store' });
		if (reponse.status !== 401) return;
		if (!(await renouvelerSession())) return; // la mire prend le relais
		for (const img of lot) rejouer(img);
	} catch {
		//  Réseau coupé ou serveur injoignable : la page entière est concernée, et
		//  les appels d'API le diront mieux qu'une vignette.
	} finally {
		sondeEnCours = false;
	}
}

/**
 * Installe la surveillance. Rend la fonction qui la retire.
 *
 * 🔴 **En phase de CAPTURE**, et c'est le point technique du module :
 * l'événement `error` d'une `<img>` **ne remonte pas** l'arbre. Sans le
 * troisième argument, ce gestionnaire ne verrait jamais rien — et un
 * gestionnaire qui ne voit rien ressemble en tout point à un gestionnaire qui
 * n'a rien à signaler.
 */
export function surveillerImagesProtegees(): () => void {
	if (typeof document === 'undefined') return () => {};
	//  🔴 La surveillance se DÉCLARE sur la page, et pas pour décorer : un test
	//  de navigateur doit pouvoir attendre qu'elle soit en place. Sans ce
	//  marqueur, il injecte son image avant l'hydratation, ne voit rien partir,
	//  et mesure en réalité le moment de l'hydratation — pas la règle
	//  (`standards/04` : un contrôle doit mesurer ce qu'on croit).
	document.documentElement.dataset.imagesSurveillees = 'oui';

	const surErreur = (ev: Event) => {
		const cible = ev.target;
		if (!(cible instanceof HTMLImageElement)) return;
		if (rejouees.has(cible) || !estProtegee(cible)) return;
		cassees.add(cible);
		if (minuteur === null) minuteur = setTimeout(conclure, REGROUPEMENT_MS);
	};

	document.addEventListener('error', surErreur, true);
	return () => {
		document.removeEventListener('error', surErreur, true);
		delete document.documentElement.dataset.imagesSurveillees;
		if (minuteur !== null) {
			clearTimeout(minuteur);
			minuteur = null;
		}
		cassees.clear();
	};
}
