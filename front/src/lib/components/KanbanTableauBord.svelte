<script lang="ts">
	/**
	 * Le **kanban condensé du tableau de bord** — ses colonnes, ses vignettes, et
	 * sa vue étroite qui n'en montre qu'une à la fois.
	 *
	 * ## Pourquoi ce composant (18/09/2026, #779)
	 *
	 * `tableau-de-bord/+page.svelte` était à 1 090 lignes, et le garde-fou de
	 * modularité (rang 1) a refusé les DEUX lignes de commentaire qu'ajoutait la
	 * nouvelle forme des vignettes. Comme les refus précédents, il désignait moins
	 * la taille que le rangement : ces cent trente-sept lignes ne parlent que du
	 * kanban — ses colonnes, son année d'exercice, sa navigation au doigt — et
	 * n'ont rien à voir avec le fil d'activité ni avec les alertes qui les
	 * entourent.
	 *
	 * ⚠️ Les classes `kb-*` sont **globales** (`styles/composants.css`), comme
	 * pour `ItemKanban` : le balisage déménage sans emporter de style.
	 *
	 * La page garde ce qui lui appartient : le CHARGEMENT des affaires, et le
	 * contexte de droits qu'elle calcule déjà pour le fil.
	 *
	 * ## Il lit les AFFAIRES depuis le 23/09/2026 (#1092, lot 5)
	 *
	 * Les événements du calendrier sont devenus des affaires. Paraissent les
	 * affaires suivies, non archivées et non annulées, rangées par leur état
	 * (`colonneDuTicket`). Le filtre par exercice est parti avec eux : une
	 * affaire suivie en cours reste à l'accueil tant qu'elle n'est pas close,
	 * quelle que soit l'année ; la visibilité est celle du serveur.
	 */
	import ItemKanban from '#lib/components/ItemKanban.svelte';
	import { routeOnglet } from '#lib/routes-onglets.ts';
	import { basculer } from '#lib/accordeon.ts';
	import type { Ticket } from '#lib/api/index.ts';
	import {
		KANBAN_COLS_ACCUEIL,
		SEUIL_KANBAN_ETROIT,
		colonneDuTicket,
		kanbanColVisible,
		MAX_CARTES_ACCUEIL,
		MOT_COLONNE_VIDE,
		type KanbanCtx,
	} from '#lib/kanban.ts';

	/** Les affaires — la page les charge, ce composant les trie. */
	export let affaires: Ticket[] = [];
	/** Le contexte de droits, calculé UNE fois par la page (elle en a besoin pour le fil). */
	export let ctx: KanbanCtx;
	/** Le chargement est en cours : on ne dit pas « aucun dossier » avant d'avoir regardé. */
	export let loading = false;

	let mobileKanbanIdx = 0;

	/**  La colonne vide qu'on a dépliée d'un clic — UNE à la fois.
	 *
	 *   🔴 Révisé le 30/09/2026. C'était un `Set`, écrit exprès (« ce n'est pas
	 *   un accordéon, c'est un tableau ») ; arbitré depuis : l'accordéon vaut
	 *   partout, sans exception, et le kanban y entre (`#lib/accordeon`). */
	let videDepliee: string | null = null;

	const lienKanban = routeOnglet('mes-demandes', 'kanban');

	//  🔴 Cette table était RECOPIÉE ici jusqu'au 19/09/2026 (#1030) — mêmes
	//  identifiants, mêmes couleurs, mais cinq colonnes au lieu de six et des
	//  libellés plus courts, sans que rien ne dise si c'était voulu.
	//
	//  Les deux écarts l'étaient, et ils se déclarent maintenant DANS la table :
	//  `labelCourt` pour l'étroitesse de la brique, `masqueAccueil` pour « Annulé ».
	//  On dérive, on ne recopie pas : une colonne ajoutée apparaît des deux côtés.
	const DASH_KANBAN_COLS = KANBAN_COLS_ACCUEIL.map((col) => ({
		...col,
		label: col.labelCourt,
	}));

	//  🔴 Le rendu du périmètre a suivi le balisage dans `ItemKanban` : il n'était
	//  employé que là. Le garder ici aurait laissé une fonction sans appelant dans
	//  un fichier de mille lignes — exactement ce qui se recopie (13/09/2026).

	$: dashKanbanEvs = affaires.filter((t) => {
		const colonne = colonneDuTicket(t.statut);
		return t.suivi_kanban && !t.archivee && colonne !== null && colonne !== 'annule';
	});

	$: dashKanbanCols = DASH_KANBAN_COLS.filter((col) => kanbanColVisible(col.id, ctx)).map((col) => {
		//  🔴 Le rangement vit dans `#lib/kanban` : il était écrit ici ET dans le
		//  calendrier, et les deux ont divergé (signalé à l'écran, 02/09/2026).
		let items: Ticket[] = dashKanbanEvs.filter((t) => colonneDuTicket(t.statut) === col.id);
		if (col.id === 'termine') {
			items = [...items].sort(
				(a, b) =>
					new Date(b.mis_a_jour_le ?? b.cree_le).getTime() -
					new Date(a.mis_a_jour_le ?? a.cree_le).getTime(),
			);
		}
		return { ...col, total: items.length, items: items.slice(0, MAX_CARTES_ACCUEIL) };
	});

	$: mobileKanbanCols = dashKanbanCols.filter((col) => col.items.length > 0);
	$: {
		if (mobileKanbanIdx >= mobileKanbanCols.length)
			mobileKanbanIdx = Math.max(0, mobileKanbanCols.length - 1);
	}
	$: mobileKanbanCurrent = mobileKanbanCols[mobileKanbanIdx] ?? null;

	//  Bascule par rendu conditionnel, pas par CSS — le pourquoi est avec la
	//  constante (`#lib/kanban.ts`) : deux bascules CSS ont échoué le même soir.
	let largeurFenetre = 0;
	$: vueEtroite = largeurFenetre > 0 && largeurFenetre <= SEUIL_KANBAN_ETROIT;
</script>

<svelte:window bind:innerWidth={largeurFenetre} />

<div class="kb-header">
	<h2 class="section-title titre-kanban">&#x1F4CB; Kanban</h2>
	<a href={lienKanban} class="kb-voir-lien">Voir le Kanban complet →</a>
</div>

{#if dashKanbanEvs.length === 0 && !loading}
	<p class="kb-vide">Aucun dossier actif.</p>
{:else}
	{#if !vueEtroite}
		<div class="kb-grid">
			{#each dashKanbanCols as col (col.id)}
				{@const vide = col.items.length === 0}
				{@const repliee = vide && videDepliee !== col.id}
				<!--  🔴 Une colonne VIDE se replie sur son titre, à la verticale, et se
				      DÉPLIE d'un clic (19/09/2026, demandé à l'écran). Elle reste donc
				      visible et consultable — savoir qu'une étape est vide fait partie
				      de la lecture d'un kanban — sans prendre la largeur d'une colonne
				      qui, elle, a quelque chose à montrer.

				      ⚠️ L'en-tête est un `<button>` et non une `<div role="button">` :
				      un titre qui bascule quelque chose EST un bouton, il porte le
				      clavier sans qu'on ait à le lui ajouter. C'est la même décision
				      que le titre d'`EnteteCarte`. -->
				<div class="kb-col" class:kb-col-vide={repliee}>
					<button
						type="button"
						class="kb-col-head"
						class:kb-col-head--inerte={!vide}
						style="border-top-color:{col.color}"
						aria-expanded={vide ? !repliee : undefined}
						title={vide ? (repliee ? 'Déplier cette étape' : 'Replier cette étape') : undefined}
						on:click={() => vide && (videDepliee = basculer(videDepliee, col.id))}
					>
						<span class="kb-col-label" style="color:{col.color}">{col.label}</span>
						<!--  🔴 Le mot est lisible DANS le pli (20/09/2026, demandé à
						      l'écran) : une colonne repliée disait son titre, et il
						      fallait la déplier pour apprendre qu'elle est vide — donc
						      cliquer pour lire ce que le pli pouvait dire. Le
						      `writing-mode` de l'en-tête l'oriente avec le titre. -->
						{#if repliee}
							<span class="kb-col-vide-mot">{MOT_COLONNE_VIDE}</span>
						{/if}
						{#if col.total > 0}
							<span class="kb-col-count" style="--kb-teinte:{col.color}">
								{col.total > MAX_CARTES_ACCUEIL
									? `+${col.total - MAX_CARTES_ACCUEIL} / ${col.total}`
									: col.total}
							</span>
						{/if}
					</button>
					{#if vide && !repliee}
						<p class="kanban-empty">{MOT_COLONNE_VIDE}</p>
					{/if}
					<!--  🔴 Une colonne VIDE n'a plus de corps (18/09/2026, demandé à
					      l'écran) : elle se réduit à son titre, tourné à la verticale,
					      et rend sa largeur à celles qui portent quelque chose. Elle
					      reste VISIBLE — savoir qu'une étape est vide fait partie de la
					      lecture d'un kanban ; c'est le tiret qui ne disait rien en
					      occupant la place d'une colonne pleine. -->
					{#each col.items as item (item.id)}
						<ItemKanban {item} />
					{/each}
				</div>
			{/each}
		</div>
	{/if}

	{#if vueEtroite && mobileKanbanCols.length > 0}
		<div>
			<div class="kb-mobile-nav">
				<button
					class="kb-nav-btn"
					disabled={mobileKanbanIdx === 0}
					on:click={() => mobileKanbanIdx--}
					aria-label="Colonne précédente">‹</button
				>
				<div class="kb-mobile-nav-center">
					<span class="kb-mobile-col-label" style="color:{mobileKanbanCurrent?.color}">
						{mobileKanbanCurrent?.label}
					</span>
					<span class="kb-mobile-pos">{mobileKanbanIdx + 1} / {mobileKanbanCols.length}</span>
				</div>
				<button
					class="kb-nav-btn"
					disabled={mobileKanbanIdx >= mobileKanbanCols.length - 1}
					on:click={() => mobileKanbanIdx++}
					aria-label="Colonne suivante">›</button
				>
			</div>
			{#if mobileKanbanCurrent}
				<div class="kb-mobile-items">
					{#each mobileKanbanCurrent.items as item (item.id)}
						<ItemKanban {item} />
					{/each}
					{#if mobileKanbanCurrent.total > 5}
						<p class="kb-mobile-plus">
							+{mobileKanbanCurrent.total - 5} élément{mobileKanbanCurrent.total - 5 > 1 ? 's' : ''} —
							<a href={lienKanban} class="kb-mobile-plus-lien">voir tout</a>
						</p>
					{/if}
				</div>
			{/if}
			<a href={lienKanban} class="kb-mobile-lien">Voir le Kanban complet →</a>
		</div>
	{/if}
{/if}

<style>
	.titre-kanban {
		margin: 0;
	}
</style>
