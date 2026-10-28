<script lang="ts">
	import { onMount } from 'svelte';
	import { afterNavigate, beforeNavigate } from '$app/navigation';
	import { navigating, updated } from '$app/state';

	// Mise à jour de l'application — appliquée d'elle-même, sans rien demander.
	//
	// POURQUOI CE MÉCANISME EXISTE (26/07/2026) : l'application est une PWA dont le
	// service worker met l'app shell en cache et ne cherche une nouvelle version
	// qu'au chargement de la page. Un onglet resté ouvert sert donc indéfiniment la
	// version chargée le matin — constaté le jour de la MEP v2.23.0, un correctif de
	// SÉCURITÉ : le navigateur exécutait toujours le code d'avant, une heure après le
	// déploiement.
	//
	// POURQUOI PAS `registerType: 'autoUpdate'`, qui ferait tout seul : parce qu'il
	// recharge la page à l'instant où il trouve la version, sans regarder ce que
	// l'utilisateur est en train de faire — un ticket à moitié rédigé disparaît. On
	// garde donc la main sur le MOMENT, et on choisit ceux où un rechargement ne
	// coûte rien :
	//
	//   1. onglet en arrière-plan  → personne ne regarde, on applique ;
	//   2. changement de page      → l'utilisateur quitte l'écran de toute façon,
	//                                le rechargement se confond avec la navigation ;
	//   3. sinon, après 15 min sur le même écran → et seulement là, on propose le
	//      bandeau. C'est le cas rare (page laissée ouverte, onglet au premier plan)
	//      où appliquer d'autorité risquerait d'effacer une saisie en cours.
	//
	// Appliquer = activer le service worker en attente ; le plugin recharge alors la
	// page courante lui-même (écouteur `controlling` de `virtual:pwa-register`).
	const INTERVALLE_MS = 30 * 60 * 1000;
	const DELAI_BANDEAU_MS = 15 * 60 * 1000;

	// ⏱ L'enregistrement attend que l'écran ait ses données (#1839). Il précache
	// tout le build — environ 776 Ko, 333 fichiers — et partait à l'hydratation :
	// à la première visite et après chaque MEP, ces requêtes disputaient le lien
	// aux données de l'écran et aux morceaux chargés au geste. Le précache ne
	// change pas (le hors-ligne non plus) ; il part après la page chargée, ce
	// délai, puis un moment d'inactivité du navigateur.
	const DELAI_ENREGISTREMENT_MS = 3000;
	const INACTIVITE_MAX_MS = 5000;

	function apresOuverture(action: () => void): () => void {
		let minuteur: ReturnType<typeof setTimeout> | undefined;
		const attendreInactivite = () => {
			if ('requestIdleCallback' in window)
				requestIdleCallback(action, { timeout: INACTIVITE_MAX_MS });
			else action();
		};
		const differer = () => (minuteur = setTimeout(attendreInactivite, DELAI_ENREGISTREMENT_MS));
		if (document.readyState === 'complete') differer();
		else window.addEventListener('load', differer, { once: true });
		return () => {
			clearTimeout(minuteur);
			window.removeEventListener('load', differer);
		};
	}

	// Garde-fou anti-boucle : si une nouvelle version ne parvenait pas à prendre la
	// main, on rechargerait sans fin. Au-delà de ce nombre d'applications
	// automatiques dans le même onglet, on repasse en mode « bandeau », qui laisse
	// l'utilisateur maître du rechargement plutôt que de boucler devant lui.
	const MAX_AUTO = 3;
	const CLE_COMPTEUR = 'maj-auto-appliquees';

	let disponible = false;
	let rechargement = false;
	let majPrete = false;
	let appliquer: ((reloadPage?: boolean) => Promise<void>) | null = null;
	let minuteurBandeau: ReturnType<typeof setTimeout> | undefined;

	function autoRestantes(): number {
		if (typeof sessionStorage === 'undefined') return 0;
		return MAX_AUTO - Number(sessionStorage.getItem(CLE_COMPTEUR) ?? 0);
	}

	/** Une application automatique de plus est-elle permise ? La compte si oui. */
	function consommerAuto(): boolean {
		if (autoRestantes() <= 0) {
			disponible = true; // dernier recours : on laisse la main à l'utilisateur
			return false;
		}
		try {
			sessionStorage.setItem(CLE_COMPTEUR, String(MAX_AUTO - autoRestantes() + 1));
		} catch {
			/* mode privé : le garde-fou saute, pas la mise à jour */
		}
		return true;
	}

	function appliquerAutomatiquement() {
		if (!majPrete || !appliquer) return;
		if (!consommerAuto()) return;
		majPrete = false;
		clearTimeout(minuteurBandeau);
		void appliquer();
	}

	// ── L'onglet tourne sur une version RETIRÉE (04/10/2026) ──────────────────
	//
	// Un déploiement remplace les morceaux de code (`/_app/immutable/…`, noms
	// hachés) : un onglet ouvert avant ne retrouve plus ceux qu'il charge à la
	// demande. Pendant une NAVIGATION, SvelteKit s'en charge seul — il relit
	// `version.json` et recharge vers la page visée. Mais un import lancé par un
	// composant (DOMPurify dans `$lib/sanitize`, l'éditeur riche…) échouait sans
	// recours : « Importing a module script failed. » relevé trois fois par la
	// télémétrie le 03/10, après les déploiements de 15:00 et 17:20.
	//
	// Vite signale chacun de ces échecs (`vite:preloadError`). Si le site a bien
	// changé, on applique aux moments sans risque, comme pour une mise à jour :
	// onglet caché, ou prochaine navigation (chargée en entier) — et le bandeau
	// tout de suite, l'écran étant déjà amputé. Jamais de rechargement d'autorité
	// devant l'utilisateur : une saisie en cours disparaîtrait. Un échec sans
	// nouvelle version (réseau) ne déclenche rien.
	let perimee = false;

	function surImportEchoue() {
		if (navigating.to) return;
		updated
			.check()
			.then((nouvelle) => {
				if (!nouvelle) return;
				perimee = true;
				if (document.visibilityState === 'hidden') rechargerSiPermis();
				else disponible = true;
			})
			.catch(() => {
				/* `version.json` injoignable : rien n'est établi, rien ne se fait */
			});
	}

	function rechargerSiPermis() {
		if (consommerAuto()) location.reload();
	}

	function recharger() {
		rechargement = true;
		//  Version retirée sans service worker en attente : `appliquer()` ne
		//  ferait rien, et le bouton resterait sur « Rechargement… ».
		if (perimee && !majPrete) {
			location.reload();
			return;
		}
		if (!appliquer) {
			rechargement = false;
			return;
		}
		void appliquer();
	}

	// Version retirée : la page visée se charge en entier, sur la nouvelle.
	beforeNavigate(({ willUnload, to, cancel }) => {
		if (!perimee || willUnload || !to?.url) return;
		cancel();
		location.href = to.url.href;
	});

	// Cas 2 : on vient de changer d'écran — l'ancien contenu est déjà perdu, un
	// rechargement ici se confond avec la navigation.
	afterNavigate(() => {
		if (majPrete) appliquerAutomatiquement();
	});

	onMount(() => {
		let annule = false;
		let arreter: (() => void) | undefined;

		//  Indépendants du service worker : une version retirée se constate aussi
		//  sans lui (premier passage, navigateur qui le refuse).
		const surPerimeeCachee = () => {
			if (perimee && document.visibilityState === 'hidden') rechargerSiPermis();
		};
		window.addEventListener('vite:preloadError', surImportEchoue);
		document.addEventListener('visibilitychange', surPerimeeCachee);

		// Import dynamique : le module virtuel n'existe qu'au build (stub inerte en
		// `vite dev`), et rien ne doit s'exécuter côté serveur au rendu SSR.
		const renoncer = apresOuverture(() =>
			import('virtual:pwa-register').then(({ registerSW }) => {
				if (annule) return;

				appliquer = registerSW({
					immediate: true,
					onNeedRefresh() {
						majPrete = true;
						// Cas 1 : onglet en arrière-plan, rien à interrompre.
						if (document.visibilityState === 'hidden') {
							appliquerAutomatiquement();
							return;
						}
						// Cas 3 : l'utilisateur est devant cet écran — on attend qu'il en
						// change ou qu'il s'en aille ; passé ce délai, on propose.
						minuteurBandeau = setTimeout(() => {
							if (majPrete) disponible = true;
						}, DELAI_BANDEAU_MS);
					},
					// Un enregistrement qui échoue supprime le cache hors ligne ET les mises
					// à jour, sans rien afficher : le 26/07/2026 l'URL relative du service
					// worker renvoyait 404 sur toute route imbriquée, en silence complet.
					onRegisterError(erreur) {
						console.error('[PWA] enregistrement du service worker échoué', erreur);
					},
					onRegisteredSW(_url, registration) {
						if (!registration) return;

						const verifier = () => {
							// Hors ligne, `update()` échoue sans rien apprendre
							if (navigator.onLine) void registration.update();
						};
						const minuteur = setInterval(verifier, INTERVALLE_MS);

						// L'onglet passe en arrière-plan : moment idéal pour appliquer une
						// version déjà prête. Il en revient : on en profite pour vérifier —
						// c'est le cas d'une page ouverte toute la nuit.
						const surVisibilite = () => {
							if (document.visibilityState === 'hidden') appliquerAutomatiquement();
							else verifier();
						};
						document.addEventListener('visibilitychange', surVisibilite);

						arreter = () => {
							clearInterval(minuteur);
							document.removeEventListener('visibilitychange', surVisibilite);
						};
					},
				});
			}),
		);

		return () => {
			renoncer();
			window.removeEventListener('vite:preloadError', surImportEchoue);
			document.removeEventListener('visibilitychange', surPerimeeCachee);
			annule = true;
			clearTimeout(minuteurBandeau);
			arreter?.();
		};
	});
</script>

{#if disponible}
	<div class="maj-bandeau" role="status" aria-live="polite">
		<span class="maj-texte">Une nouvelle version de l'application est disponible.</span>
		<div class="maj-actions">
			<button type="button" class="btn btn-sm btn-outline" on:click={() => (disponible = false)}>
				Plus tard
			</button>
			<button
				type="button"
				class="btn btn-sm btn-primary"
				disabled={rechargement}
				on:click={recharger}
			>
				{rechargement ? 'Rechargement…' : 'Recharger'}
			</button>
		</div>
	</div>
{/if}

<style>
	.maj-bandeau {
		position: fixed;
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		z-index: 9998; /* juste sous les toasts (9999) */
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
		justify-content: center;
		max-width: min(560px, calc(100vw - 2rem));
		padding: 0.75rem 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-left: 4px solid var(--color-primary);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		font-size: var(--fs-base);
		color: var(--color-text);
	}

	.maj-texte {
		flex: 1 1 auto;
	}

	.maj-actions {
		display: flex;
		gap: 0.5rem;
		flex: 0 0 auto;
	}
</style>
