<script lang="ts">
	import { page } from '$app/stores';
	import {
		currentUser,
		isCS,
		isAdminOuOperateur,
		hasResidentRole,
		isAdminOnly,
	} from '$lib/stores/auth';
	import { locale, NAV_LABELS } from '$lib/stores/locale';
	import { auth as authApi } from '$lib/api';
	import { CHEMIN_CONNEXION } from '$lib/redirection';
	import { configStore, getPageConfig } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';
	import LiensGuide from '$lib/components/LiensGuide.svelte';
	import MarqueResidence from '$lib/components/MarqueResidence.svelte';
	import {
		HREFS_DEFAUT,
		HREF_VERS_PAGE,
		ID_VERS_HREF,
		PAGES_MENU,
		identifiantsRepetes,
		ordonnerPages,
	} from '$lib/pages';

	// Les valeurs par défaut, l'ordre et la correspondance identifiant → route
	// viennent tous de `$lib/pages.ts` — voir l'en-tête de ce fichier pour les trois
	// divergences qu'entretenaient les deux tables d'avant (#401).

	function navItem(href: string, raw: Record<string, string>) {
		const def = HREF_VERS_PAGE[href];
		if (!def) return { href, icon: 'help-circle', label: href };
		const cfg = getPageConfig(raw, def.id, {
			titre: def.titre,
			descriptif: def.descriptif,
			navLabel: def.navLabel,
			icone: def.icone,
		});
		return { href, icon: cfg.icone ?? def.icone, label: cfg.navLabel ?? def.navLabel };
	}

	let menuOpen = false;

	function toggleMenu() {
		menuOpen = !menuOpen;
	}
	function closeMenu() {
		menuOpen = false;
	}

	/** Au-delà, on part sans attendre la révocation : les cookies sont `HttpOnly`,
	 *  le navigateur ne peut pas les effacer lui-même, et rester bloqué sur un
	 *  réseau perdu serait pire qu'une session qui expirera d'elle-même. */
	const ATTENTE_REVOCATION_MS = 3000;
	let deconnexionEnCours = false;

	//  🔴 Révoquer D'ABORD, puis quitter par une navigation COMPLÈTE (29/09/2026).
	//
	//  L'ancien geste vidait l'utilisateur (`setUser(null)`) puis appelait `goto` :
	//  pendant que la mire se chargeait, le tableau de bord se re-rendait SANS
	//  utilisateur — « Bonsoir » sans prénom, menu vide, kanban et fil toujours
	//  affichés. Sur un réseau lent, c'est ce qu'on voyait en se déconnectant.
	//
	//  La navigation complète vide aussi tout ce que l'onglet tenait de la
	//  session : utilisateur, listes chargées. Une navigation interne les
	//  laissait en mémoire.
	//
	//  Rien à conserver : on se déconnecte volontairement, d'où `CHEMIN_CONNEXION`
	//  et non `urlDeConnexion()`.
	async function logout() {
		if (deconnexionEnCours) return;
		deconnexionEnCours = true;
		await Promise.race([
			authApi.logout().catch(() => {}),
			new Promise((fin) => setTimeout(fin, ATTENTE_REVOCATION_MS)),
		]);
		window.location.assign(CHEMIN_CONNEXION);
	}

	$: t = NAV_LABELS[$locale];

	function computeOrderedHrefs(orderJson: string | undefined): string[] {
		if (!orderJson) return HREFS_DEFAUT;
		try {
			const ids: string[] = JSON.parse(orderJson);
			// Un identifiant sans route est une INCOHÉRENCE DE DONNÉES, pas un cas
			// normal : l'ordre enregistré nomme une page que le menu ne connaît pas.
			// L'ancien `.filter()` les jetait sans un mot — il masquait précisément le
			// défaut qu'on cherchait quand l'ordre ne semblait pas appliqué (#401).
			const inconnus = ids.filter((id) => !(id in ID_VERS_HREF));
			if (inconnus.length)
				console.warn(
					`[Nav] pages_order contient ${inconnus.length} identifiant(s) sans entrée de menu, ignoré(s) : ${inconnus.join(', ')}`,
				);
			//  Même raison, autre incohérence : un identifiant RÉPÉTÉ affichait la page
			//  deux fois dans le menu, et faisait bien pire dans « Descriptif pages »
			//  (`each_key_duplicate`, erreur fatale de Svelte — cf. `ordonnerPages`).
			const repetes = identifiantsRepetes(ids);
			if (repetes.length)
				console.warn(
					`[Nav] pages_order répète ${repetes.length} identifiant(s), dédoublonné(s) : ${repetes.join(', ')}`,
				);
			//  🔴 L'ordre se calcule à UN seul endroit. Ces quatre lignes réimplémentaient
			//  `ordonnerPages` — même notion, deux écritures — et elles ont divergé sur le
			//  cas limite qui compte : celle-ci dédoublonnait par accident (`remaining`
			//  filtre sur `ordered`), l'autre non, et c'est l'autre qui rendait l'écran.
			return ordonnerPages(PAGES_MENU, ids).map((p) => p.href as string);
		} catch {
			console.warn('[Nav] pages_order illisible (JSON invalide) — ordre par défaut appliqué');
			return HREFS_DEFAUT;
		}
	}

	// Ordre lu depuis le backend (pages_order), repli sur l'ordre par défaut
	$: _pagesOrderJson = $configStore['pages_order'];
	$: orderedHrefs = computeOrderedHrefs(_pagesOrderJson);

	//  Les outils du conseil — Prestataires, Espace CS, Délégations. `$isCS` inclut l'admin ;
	//  le compte technique créé à l'installation (admin seul, sans lot ni CS)
	//  n'a pas à les voir. Prestataires et Délégations ne l'excluaient pas,
	//  l'Espace CS si : une seule règle, posée ici, pour les trois.
	$: outilDuConseil = $isCS && !$isAdminOnly;

	$: allNav = orderedHrefs
		.filter((href) => {
			const statut = $currentUser?.statut;
			if (
				href === '/sondages' &&
				(statut === 'syndic' || statut === 'mandataire' || statut === 'aidant')
			)
				return false;
			if (href === '/prestataires') return outilDuConseil;
			if (href === '/espace-cs') return outilDuConseil;
			if (href === '/delegations')
				return (
					outilDuConseil ||
					($currentUser?.delegations_aidant?.length ?? 0) > 0 ||
					statut === 'aidant'
				);
			if (href === '/admin') return $isAdminOuOperateur;
			return $hasResidentRole;
		})
		.map((href) => navItem(href, $configStore));

	function isActive(href: string) {
		return $page.url.pathname.startsWith(href);
	}

	//  Fermer le menu lors d'un changement de page.
	//
	//  ⚠️ La dépendance passe en ARGUMENT plutôt qu'en expression séquentielle
	//  (`$: $page.url.pathname, closeMenu()`). Les deux formes ont le même effet,
	//  mais la seconde se lit comme une valeur calculée puis jetée — ce qui est
	//  presque toujours un `=` oublié, et ce qu'ESLint signale à raison. Ici
	//  l'argument DIT ce qui déclenche : le chemin change, le menu se ferme.
	function fermerAuChangementDePage(_chemin: string) {
		closeMenu();
	}
	$: fermerAuChangementDePage($page.url.pathname);
</script>

<!-- ─── Sidebar desktop ─────────────────────────────────────────────────── -->
<nav class="sidebar">
	<MarqueResidence variante="barre" />

	<div class="nav-section">
		{#each allNav as item (item.href)}
			<a href={item.href} class="nav-item" class:active={isActive(item.href)}>
				<span class="nav-icon"><Icon name={item.icon} size={18} /></span>
				<span class="nav-label">{item.label}</span>
			</a>
		{/each}
	</div>

	<div class="nav-footer">
		<a href="/profil" class="nav-item" class:active={isActive('/profil')}>
			<span class="nav-icon"><Icon name="user" size={18} /></span>
			<span class="nav-label">{$currentUser?.prenom ?? t['/profil']}</span>
		</a>
		<!--  ⚠️ Le menu principal ne porte QUE le guide en ligne (04/09/2026,
		      arbitré à l'écran). Le PDF reste atteignable depuis le manuel et
		      depuis la FAQ : deux entrées « Guide » côte à côte encombraient un
		      menu déjà long, pour un document qu'on télécharge une fois. -->
		<div class="enveloppe-guide">
			<LiensGuide taille={18} avecPdf={false} />
		</div>
		<button class="nav-item nav-logout" on:click={logout} type="button">
			<span class="nav-icon"><Icon name="log-out" size={18} /></span>
			<span class="nav-label">{t['deconnexion']}</span>
		</button>
	</div>
</nav>

<!-- ─── Topbar mobile (hamburger) ──────────────────────────────────────── -->
<header class="mobile-topbar">
	<MarqueResidence variante="entete" />
	<button class="hamburger" on:click={toggleMenu} aria-label="Menu" aria-expanded={menuOpen}>
		{#if menuOpen}
			<span class="hb-line hb-close-1"></span>
			<span class="hb-line hb-close-2"></span>
		{:else}
			<span class="hb-line"></span>
			<span class="hb-line"></span>
			<span class="hb-line"></span>
		{/if}
	</button>
</header>

<!-- ─── Overlay menu mobile ────────────────────────────────────────────── -->
{#if menuOpen}
	<!--  Le fond de `Modale` : `role="presentation"`, rien à activer au clavier —
	      le menu se ferme par le bouton ☰, qui porte `aria-expanded` (#1045). -->
	<div class="overlay-backdrop" role="presentation" on:click={closeMenu}></div>
	<div class="overlay-menu">
		<div class="overlay-nav">
			{#each allNav as item (item.href)}
				<a href={item.href} class="overlay-item" class:active={isActive(item.href)}>
					<span class="nav-icon"><Icon name={item.icon} size={20} /></span>
					<span>{item.label}</span>
				</a>
			{/each}
		</div>
		<div class="overlay-footer">
			<a href="/profil" class="overlay-item" class:active={isActive('/profil')}>
				<span class="nav-icon"><Icon name="user" size={20} /></span>
				<span>{$currentUser?.prenom ?? t['/profil']}</span>
			</a>
			<div class="enveloppe-guide">
				<LiensGuide mobile taille={20} />
			</div>
			<button class="overlay-item nav-logout" on:click={logout} type="button">
				<span class="nav-icon"><Icon name="log-out" size={20} /></span>
				<span>{t['deconnexion']}</span>
			</button>
		</div>
	</div>
{/if}

<style>
	/* ── Desktop sidebar ───────────────────────────────────────────────────── */
	.sidebar {
		position: fixed;
		top: 0;
		left: 0;
		width: 185px;
		height: 100vh;
		background: var(--color-surface);
		border-right: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		/*  Le haut est réduit de moitié avec la marque (arbitré à l'écran, 08/10/2026) :
		    le logo, à 64 px, porte déjà son propre blanc. */
		padding: 0.5rem 0 1rem;
		z-index: 100;
	}

	.nav-section {
		flex: 1;
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
		padding: 0 0.5rem;
	}

	.nav-item {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.55rem 0.75rem;
		border-radius: var(--radius);
		color: var(--color-text);
		font-size: var(--fs-base);
		text-decoration: none;
		transition: background var(--duree-geste);
		border: none;
		background: transparent;
		width: 100%;
		cursor: pointer;
		margin-bottom: 0.15rem;
		touch-action: manipulation;
		-webkit-tap-highlight-color: transparent;
	}

	@media (hover: hover) and (pointer: fine) {
		.nav-item:hover {
			background: var(--color-bg);
		}
	}
	.nav-item.active {
		background: var(--color-primary-light);
		color: var(--color-primary);
		font-weight: 600;
	}

	.nav-footer {
		padding: 0.5rem;
		border-top: 1px solid var(--color-border);
		margin-top: 0.5rem;
	}

	.nav-logout {
		color: var(--color-text-muted);
	}
	@media (hover: hover) and (pointer: fine) {
		.nav-logout:hover {
			color: var(--color-danger);
			background: var(--color-danger-fond);
		}
	}
	/* ── Mobile topbar ─────────────────────────────────────────────────────── */
	.mobile-topbar {
		display: none;
	}

	/* ── Overlay menu ──────────────────────────────────────────────────────── */
	.overlay-backdrop {
		display: none;
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		left: 0;
		background: rgba(0, 0, 0, 0.35);
		z-index: 199;
	}

	.overlay-menu {
		display: none;
		position: fixed;
		top: 3.25rem;
		left: 0;
		right: 0;
		bottom: 0;
		background: var(--color-surface);
		z-index: 200;
		flex-direction: column;
		overflow-y: auto;
	}

	.overlay-nav {
		flex: 1;
		padding: 0.5rem;
		overflow-y: auto;
	}

	.overlay-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		border-radius: var(--radius);
		color: var(--color-text);
		font-size: 1rem;
		text-decoration: none;
		border: none;
		background: transparent;
		width: 100%;
		cursor: pointer;
		margin-bottom: 0.1rem;
		touch-action: manipulation;
		-webkit-tap-highlight-color: transparent;
	}

	@media (hover: hover) and (pointer: fine) {
		.overlay-item:hover {
			background: var(--color-bg);
		}
	}
	.overlay-item.active {
		background: var(--color-primary-light);
		color: var(--color-primary);
		font-weight: 600;
	}

	.overlay-footer {
		padding: 0.5rem;
		border-top: 1px solid var(--color-border);
	}

	/* ── Hamburger button ──────────────────────────────────────────────────── */
	.hamburger {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 5px;
		width: 2.25rem;
		height: 2.25rem;
		background: transparent;
		border: none;
		cursor: pointer;
		padding: 0.3rem;
		border-radius: var(--radius);
	}

	@media (hover: hover) and (pointer: fine) {
		.hamburger:hover {
			background: var(--color-bg);
		}
	}

	.hb-line {
		display: block;
		width: 100%;
		height: 2px;
		background: var(--color-text);
		border-radius: 2px;
		transition:
			transform var(--duree-apparition) var(--ease-out),
			opacity var(--duree-apparition) var(--ease-out);
	}

	.hb-close-1 {
		transform: translateY(7px) rotate(45deg);
	}

	.hb-close-2 {
		transform: translateY(-7px) rotate(-45deg);
	}

	/* ── Responsive ────────────────────────────────────────────────────────── */
	@media (max-width: 767px) {
		.sidebar {
			display: none;
		}

		.mobile-topbar {
			display: flex;
			align-items: center;
			gap: 0.6rem;
			position: fixed;
			top: 0;
			left: 0;
			right: 0;
			height: 3.25rem;
			background: var(--color-surface);
			border-bottom: 1px solid var(--color-border);
			padding: 0 1rem;
			z-index: 100;
		}

		.overlay-backdrop {
			display: block;
		}
		.overlay-menu {
			display: flex;
		}
	}

	/*  Les deux règles ci-dessous ne sont PAS des redéfinitions : elles rendent
	    applicables au composant enfant celles que la page porte déjà. Bornées à
	    l'enveloppe, elles ne fuient nulle part. */
	.enveloppe-guide :global(.nav-item),
	.enveloppe-guide :global(.overlay-item) {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.55rem 0.7rem;
		border-radius: var(--radius);
		color: var(--color-text);
		text-decoration: none;
	}
</style>
