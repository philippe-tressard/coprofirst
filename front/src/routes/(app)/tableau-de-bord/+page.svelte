<script lang="ts">
	import { messageErreur } from '#lib/erreurs.ts';
	import { onMount } from 'svelte';
	import { marquerDonneesAffichees } from '#lib/telemetry.ts';
	import { relire } from '#lib/utils.ts';
	import KanbanTableauBord from '#lib/components/KanbanTableauBord.svelte';
	import UrgencesAccueil from '#lib/components/UrgencesAccueil.svelte';
	import { salutation } from '#lib/date.ts';
	import { seuilRecentMs } from '#lib/archivage.ts';
	import ArchivesDuFil from '#lib/components/ArchivesDuFil.svelte';
	import {
		authResolue,
		currentUser,
		isAdmin,
		isAdminOnly,
		isCS,
		isLocataire,
		isProprioOuCS,
	} from '#lib/stores/auth.ts';
	import { goto } from '$app/navigation';
	import {
		flux,
		lots,
		tickets as ticketsApi,
		type FluxItem,
		type FluxResponse,
		type MonLot,
		type Ticket,
	} from '#lib/api/index.ts';
	import {
		getPageConfig,
		configStore,
		siteNomStore,
		defautsDePage,
	} from '#lib/stores/pageConfig.ts';
	import Icon from '#lib/components/Icon.svelte';
	import EnteteAccueil from '#lib/components/EnteteAccueil.svelte';
	import FriseDuFil from '#lib/components/FriseDuFil.svelte';
	import RaccourcisRapides from '#lib/components/RaccourcisRapides.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import ReglagesListe from '#lib/components/ReglagesListe.svelte';
	import { OPTIONS_PORTEE, offrirLaPastille, selonPortee } from '#lib/me-concerne.ts';
	// Toutes les règles du fil (apparence, liens, appartenance aux trois
	// registres) vivent dans ce module — cf. `#lib/flux.ts`.
	import {
		dateDeReference,
		estEpingle,
		estNonResolu,
		estUrgent,
		grouperParJour,
	} from '#lib/flux.ts';

	$: _pc = getPageConfig($configStore, 'tableau-de-bord', defautsDePage('tableau-de-bord'));
	$: _siteNom = $siteNomStore;

	//  L'admin seul — le compte technique créé à l'installation, sans lot ni
	//  conseil syndical — n'a au menu que l'administration (`Nav.svelte`) :
	//  le Kanban, le fil et les raccourcis d'un résident ne le concernent pas.
	//  Demandé à l'écran le 14/10/2026. Le même garde que l'Espace CS, inversé.
	$: if ($authResolue && $isAdminOnly) goto('/admin', { replaceState: true });

	let data: FluxResponse | null = null;
	let userLots: MonLot[] = [];
	let loading = true;
	let ready = false;
	let kanbanAffaires: Ticket[] = [];
	//  « Ce qui me concerne » (#2215) : filtre la chronologie du fil, offerte s'il
	//  y a de quoi filtrer. Urgences et épinglés restent : ils ne se trient pas.
	let offrirMeConcerne = false;
	let portee = '';

	onMount(async () => {
		offrirMeConcerne = await offrirLaPastille();
	});

	onMount(async () => {
		try {
			const [fluxRes, lotsRes, calRes] = await Promise.allSettled([
				flux.get(),
				lots.mesList(),
				ticketsApi.list(),
			]);
			if (fluxRes.status === 'fulfilled') data = fluxRes.value;
			else toast('error', 'Erreur chargement du flux');
			if (lotsRes.status === 'fulfilled') userLots = lotsRes.value;
			if (calRes.status === 'fulfilled') kanbanAffaires = calRes.value;
		} catch (e) {
			toast('error', 'Erreur chargement : ' + messageErreur(e));
		} finally {
			loading = false;
			marquerDonneesAffichees();
			setTimeout(() => {
				ready = true;
			}, 50);
		}
	});

	// ── Rôles & filtrage ───────────────────────────────────────────────────

	//  Ce filtre réimplémentait la règle du serveur : un motif `bat:(\d+)` analysé à
	//  la main et la liste des périmètres transverses écrite en dur — troisième
	//  copie de la même énumération. Il s'appuie désormais sur l'arborescence, comme
	//  `api/app/utils/visibility.py`. Ce n'est qu'un filtre d'AFFICHAGE : le serveur
	//  a déjà écarté ce que l'utilisateur n'a pas le droit de voir.

	//  ⚠️ Dépend de l'HEURE : sans dépendance citée, ce `$:` restait au montage et
	//  disait « Bonjour » à 20 h (`utils.relire`). `salutation` vit dans
	//  `#lib/date` — c'est une notion de date, pas de cet écran.
	$: greeting = relire(data, salutation);

	// ── Expand state (unique entre prochaines échéances et fil d'activité) ─
	let expandedItem: string | null = null;
	/**  Retirer une carte du fil. Le droit est vérifié côté SERVEUR
	 *   (`require_admin`) : le bouton n'est qu'une commodité.
	 *
	 *   La carte part tout de suite, sans attendre la réponse — le geste est
	 *   idempotent, et une carte qui reste une seconde se relit comme un clic
	 *   manqué. En cas d'échec, la liste est rétablie à l'identique. */
	async function masquerItem(id: string) {
		if (!data) return;
		const avant = data.items;
		data = { ...data, items: data.items.filter((i) => i.id !== id) };
		try {
			await flux.masquer(id);
		} catch (e) {
			//  Rétabli à l'identique : un fil amputé sans que rien ne soit
			//  enregistré serait un mensonge qui disparaît au rechargement.
			data = { ...data, items: avant };
			toast('error', messageErreur(e, 'Retrait impossible'));
		}
	}

	function toggleItem(id: string) {
		expandedItem = expandedItem === id ? null : id;
	}

	// ── Filtrage rôle/périmètre sur items ──────────────────────────────────
	$: filteredItems = (data?.items ?? []).filter((item) => {
		// AG invisible pour les locataires / non-proprios
		if (item.type === 'evenement' && item.meta?.type === 'ag' && !$isProprioOuCS) return false;
		// Filtrage périmètre (backend le fait déjà, mais sécurité côté client)
		return true;
	});

	// ── Fil et agenda ne racontent pas la même chose ───────────────────────
	// Un événement à venir était écarté du fil deux fois : parce qu'il figurait
	// déjà dans « Prochaines échéances », et parce que sa date était future. Un
	// nettoyage programmé restait donc introuvable dans le fil (01/08/2026),
	// alors qu'il venait d'être créé — c'est-à-dire qu'il s'était bien passé
	// quelque chose.
	// Le fil répond à « quoi de neuf ? » et date la ligne à l'ANNONCE (le
	// backend renvoie `date = cree_le`) ; l'agenda répond à « quoi ensuite ? »
	// et affiche la date de tenue. Les deux vues coexistent sans doublon de
	// sens : ce n'est pas la même information.
	$: filItems = selonPortee(filteredItems, portee);

	// ── Classement du fil : récent / ancien / masqué ───────────────────────
	//  🔴 UN SEUL délai, pour tout le site (#513 puis #515) — voir `#lib/archivage`.
	//  `PLAFOND_CHARGEMENT` est une borne de CHARGEMENT, pas un second seuil de
	//  visibilité : les Archives couvrent tout l'intervalle.
	$: SEUIL_RECENT = seuilRecentMs(data?.delai_recent_jours);
	const PLAFOND_CHARGEMENT = 377 * 86400000;

	let recentItems: FluxItem[] = [];
	let olderItems: FluxItem[] = [];
	$: {
		const _recent: FluxItem[] = [];
		const _older: FluxItem[] = [];
		const now = Date.now();
		for (const item of filItems) {
			// Un élément épinglé a son propre bandeau : le laisser aussi dans la
			// chronologie le ferait lire deux fois. C'est également ce qui le rend
			// insensible au vieillissement — un élément qu'on a explicitement voulu
			// garder en vue ne doit pas s'effacer au bout de 30 jours.
			if (estEpingle(item)) continue;
			const age = now - dateDeReference(item);
			if (estNonResolu(item)) {
				_recent.push(item);
				continue;
			}
			if (age > PLAFOND_CHARGEMENT) continue;
			if (age < SEUIL_RECENT) _recent.push(item);
			else _older.push(item);
		}
		recentItems = _recent;
		olderItems = _older;
	}

	// ── Groupement par jour : `grouperParJour` (`#lib/flux`), rendu par `FriseDuFil`.
	$: recentDayGroups = grouperParJour(recentItems);
	$: olderDayGroups = grouperParJour(olderItems);
	let olderOpen = false;

	// ── Kanban widget ──────────────────────────────────────────────────────
	//  Le widget vit dans `KanbanTableauBord` depuis le 18/09/2026 (#779) : ses
	//  colonnes, son année d'exercice et sa navigation au doigt ne parlaient que
	//  de lui. La page garde ce qui lui appartient — le CHARGEMENT des
	//  événements, et le contexte de droits, qu'elle calcule déjà pour le fil.
	$: _dashKanbanCtx = {
		isCS: $isCS,
		isAdmin: $isAdmin,
		canSeeAG: $isProprioOuCS,
		statut: $currentUser?.statut ?? '',
	};

	// ── Les trois registres du fil ─────────────────────────────────────────
	// 1. 🔴 Urgences  — « qu'est-ce qui brûle ? »        (plafonné à 3, s'auto-périme)
	// 2. 📌 Épinglé   — « qu'est-ce qu'il ne faut pas perdre de vue ? »
	// 3. Chronologie  — « quoi de neuf ? »               (recentItems / olderItems)
	// Les filtres sont dans `#lib/flux.ts` et sont mutuellement exclusifs : un
	// élément urgent ET épinglé ne paraît qu'en urgence, la gravité primant.
	$: urgentItems = filteredItems.filter(estUrgent);
	$: pinnedItems = filteredItems.filter(estEpingle);

	//  `countByType` vivait ici et n'alimentait qu'une chose : la pastille
	//  Tickets. Elle comptait donc les tickets ouverts **du fil affiché**, après
	//  les filtres de l'utilisateur — la seule de la rangée à bouger avec eux,
	//  sans que rien à l'écran ne le laisse deviner. Le nombre vient désormais du
	//  serveur, comme ses voisines (#399).
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

{#if loading}
	<div class="skeleton-wrap">
		<div class="skel skel-header"></div>
		<div class="skel skel-subtitle"></div>
		<div class="skel-row">
			<div class="skel skel-kpi"></div>
			<div class="skel skel-kpi"></div>
			<div class="skel skel-kpi"></div>
		</div>
		<div class="skel skel-card"></div>
		<div class="skel skel-card"></div>
		<div class="skel skel-card short"></div>
	</div>
{:else if !data}
	<div class="empty-state">
		<Icon name="wifi-off" size={32} />
		<h3>Impossible de charger le flux</h3>
		<p>Vérifiez votre connexion et réessayez.</p>
	</div>
{:else}
	<EnteteAccueil salutation={greeting} lots={userLots} visible={ready} />

	<!-- ═══ RACCOURCIS RAPIDES ═════════════════════════════════════════════ -->
	<!-- Qui voit quelle pastille, et d'où vient chaque nombre : `#lib/raccourcis.ts`,
	     et nulle part ailleurs. La page recomposait ici la règle d'accès à
	     l'Espace CS, que le serveur écrivait déjà de son côté (#399). -->
	<RaccourcisRapides sante={data.sante} {ready} --delay=".08s" />

	<!-- ═══ ALERTES URGENTES ══════════════════════════════════════════════
	     🔴 Deux bandeaux pleine largeur sont partis le 31/10/2026 (#2397,
	     maquette A2) : « Consignes de la copropriété » est une pastille au bout
	     de la rangée ci-dessus, et « N affaires syndic à relancer » redisait le
	     compteur « N relances » de la pastille Espace CS, qui mène au même
	     endroit. Les urgences restent : elles NOMMENT les affaires. -->
	{#if urgentItems.length > 0}
		<div class="section-reveal delai-3" class:section-visible={ready}>
			<UrgencesAccueil items={urgentItems.slice(0, 3)} />
		</div>
	{/if}

	<!-- ═══ ÉPINGLÉ ═══════════════════════════════════════════════════════
	     Registre volontairement CALME : ni rouge ni alerte. Les urgences
	     au-dessus signalent ce qui brûle ; ce bandeau-ci répond à « qu'est-ce
	     qu'il ne faut pas perdre de vue ? ». Le fondre dans les urgences les
	     userait : un épinglé ne s'auto-périme pas, il resterait indéfiniment
	     dans un bandeau d'alerte, et le plafond de 3 des urgences finirait par
	     évincer une urgence réelle. -->
	{#if pinnedItems.length > 0}
		<div class="section-reveal delai-4" class:section-visible={ready}>
			<div class="epingle-bloc">
				<h2 class="epingle-titre">📌 Épinglé</h2>
				<FriseDuFil
					groupes={[{ label: null, items: pinnedItems }]}
					variante="epingle"
					itemDeplie={expandedItem}
					onBasculer={toggleItem}
					onMasquer={masquerItem}
				/>
			</div>
		</div>
	{/if}

	<!-- ═══ KANBAN (masqué pour les locataires) ═════════════════════════════ -->
	{#if !$isLocataire}
		<div class="section-reveal delai-5" class:section-visible={ready}>
			<KanbanTableauBord affaires={kanbanAffaires} ctx={_dashKanbanCtx} {loading} />
		</div>
	{/if}

	<!-- ═══ FIL D'ACTIVITÉ ════════════════════════════════════════════════ -->
	<div class="section-reveal delai-6" class:section-visible={ready}>
		<h2 class="section-title titre-fil">
			<Icon name="newspaper" size={16} /> Fil d'activité
		</h2>
		{#if offrirMeConcerne}
			<ReglagesListe>
				<ChoixPastilles
					options={[...OPTIONS_PORTEE]}
					bind:valeur={portee}
					tous="Tout"
					compte={filItems.length}
					libelle="Portée"
					libelleDevant
				/>
			</ReglagesListe>
		{/if}
	</div>

	{#if recentItems.length === 0 && olderItems.length === 0}
		<div class="empty-state">
			<Icon name="inbox" size={32} />
			<h3>{portee ? 'Rien de récent qui vous concerne' : 'Aucune activité récente'}</h3>
			<p>Les mouvements de la résidence apparaîtront ici.</p>
		</div>
	{:else}
		<!-- Fil récent (<30 jours) -->
		<div class="section-reveal delai-7" class:section-visible={ready}>
			<FriseDuFil
				groupes={recentDayGroups}
				itemDeplie={expandedItem}
				onBasculer={toggleItem}
				onMasquer={masquerItem}
			/>
		</div>

		<!-- Accordéon : anciens (>30 jours) -->
		{#if olderItems.length > 0}
			<div class="section-reveal delai-8" class:section-visible={ready}>
				<ArchivesDuFil
					groupesParJour={olderDayGroups}
					compte={olderItems.length}
					bind:ouvert={olderOpen}
					itemDeplie={expandedItem}
					onBasculer={toggleItem}
					onMasquer={masquerItem}
				/>
			</div>
		{/if}
	{/if}
{/if}

<style>
	/* ═══ SKELETON LOADING ═══════════════════════════════════════════════ */
	@keyframes shimmer {
		0% {
			background-position: -400px 0;
		}
		100% {
			background-position: 400px 0;
		}
	}
	.skeleton-wrap {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.skel {
		border-radius: var(--radius);
		background: linear-gradient(
			90deg,
			var(--color-border) 25%,
			var(--color-neutre-bordure) 37%,
			var(--color-border) 63%
		);
		background-size: 800px 100%;
		animation: shimmer 1.4s ease infinite;
	}
	.skel-header {
		height: 2rem;
		width: 60%;
	}
	.skel-subtitle {
		height: 1rem;
		width: 40%;
	}
	.skel-row {
		display: flex;
		gap: 0.75rem;
	}
	.skel-kpi {
		height: 5rem;
		flex: 1;
	}
	.skel-card {
		height: 4.5rem;
	}
	.skel-card.short {
		width: 70%;
	}

	/* La carte des consignes est `LienConsignes` (#779) : ses styles l'ont suivie. */

	/* Les styles de la rangée de raccourcis sont partis avec leur balisage dans
	   `RaccourcisRapides.svelte` — Svelte scope les styles au composant. */

	/* ═══ ANIMATIONS SECTIONS ═══════════════════════════════════════════
	   `.section-reveal` vit dans `styles/socle.css` : les raccourcis la
	   recopiaient (27/09/2026). */

	/* ═══ KPI CARDS ═════════════════════════════════════════════════════ */

	/* ═══ KANBAN WIDGET ═════════════════════════════════════════════════ */

	/* Grille desktop */

	/* Item commun desktop + mobile */ /* troncature : `.clamp-2` (#561) */

	/* Mobile */

	/* ═══ FLUX TIMELINE ═════════════════════════════════════════════════ */
	/* ═══ ÉPINGLÉ ═══════════════════════════════════════════════════════
	   Délibérément sobre : gris et bleu de la charte, aucun rouge, aucune
	   animation. Ce bandeau doit se distinguer de la chronologie sans entrer
	   en concurrence avec les urgences au-dessus — c'est un pense-bête, pas
	   une alerte. */
	.epingle-bloc {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-left: 4px solid var(--color-primary);
		border-radius: var(--radius);
		padding: 0.75rem 1rem 1rem;
		margin-bottom: 1rem;
	}
	.epingle-titre {
		font-size: var(--fs-2xs);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-muted);
		margin: 0 0 0.25rem;
	}
	/*  La frise elle-même — celle du bandeau comme celle du fil et des Archives —
	    est `FriseDuFil` (#779), variante `epingle` ici. */
	.delai-3 {
		--delay: 0.1s;
	}
	.delai-4 {
		--delay: 0.15s;
	}
	.delai-5 {
		--delay: 0.2s;
	}
	.delai-6 {
		--delay: 0.25s;
	}
	.titre-fil {
		margin-top: 1.5rem;
	}
	.delai-7 {
		--delay: 0.3s;
	}
	.delai-8 {
		--delay: 0.35s;
	}
</style>
