<!--
  Une carte du fil d'activité du tableau de bord.

  Ce composant existe parce que le fil rendait la MÊME carte à deux endroits —
  le bloc « récent » et l'accordéon « plus ancien » — dans deux blocs de balisage
  copiés puis modifiés séparément. Les deux avaient divergé : le bloc ancien
  avait perdu la date de tenue, l'auteur, l'état, la réaction du CS, les badges
  et le libellé de lien adapté au type. Toute évolution du fil devait par ailleurs
  être écrite deux fois (la vignette d'aperçu l'a été, le 01/08/2026).

  La fusion retient, pour chaque partie, la version la plus complète des deux —
  pas la première rencontrée. Le bloc « ancien » conserve sa seule distinction
  volontaire, l'atténuation (`.older-timeline { opacity }`), qui est du ressort
  du conteneur.

  Sert les trois registres du fil : urgences (via le bandeau dédié de la page),
  épinglé et chronologie. Une carte se rend de la même façon partout.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import BadgeNouveau from '#lib/components/BadgeNouveau.svelte';
	import { createEventDispatcher } from 'svelte';

	import { isAdmin } from '#lib/stores/auth.ts';
	import type { FluxItem, Ticket } from '#lib/api/index.ts';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import FluxVignette from '#lib/components/FluxVignette.svelte';
	import FluxCorps from '#lib/components/FluxCorps.svelte';
	import { chargerCorpsAffaire } from '#lib/affaire-au-fil.ts';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import PastillesAffaire from '#lib/components/PastillesAffaire.svelte';
	import AuteurCarte from '#lib/components/AuteurCarte.svelte';
	import MarqueIA from '#lib/components/MarqueIA.svelte';
	import BadgeVerdict from '#lib/components/BadgeVerdict.svelte';
	import { champDe, relire } from '#lib/utils.ts';
	import { equipementsStore } from '#lib/stores/equipements.ts';
	import {
		badgeClass,
		badgesDuFlux,
		classeFlux,
		estTicketUrgent,
		isNew,
		typeCouleur,
		typeLink,
	} from '#lib/flux.ts';

	export let item: FluxItem;
	export let expanded = false;
	/** Rendue aux Archives du fil : l'allure de toute carte archivée (`CarteListe`). */
	export let archive = false;
	/**  La gouttière dit l'HEURE — seulement quand un intitulé de groupe dit le
	 *   jour (`FriseDuFil`). Le bandeau Épinglé n'en a pas : l'heure seule n'y
	 *   situait rien, la carte y prend la date (12/10/2026). */
	export let heure = false;

	/**  🗑️ Retirer la carte du FIL — admin seulement, et sur les cartes d'ANNUAIRE
	 *   seulement. La carte n'agit pas, elle prévient — comme pour `toggle`. */
	const dispatch = createEventDispatcher<{ toggle: string; masquer: string }>();

	/**  Une carte ne se retire du fil que si son objet n'a pas d'archivage : ce
	 *   qui s'archive se retire EN S'ARCHIVANT, et poser un 🗑️ à côté offrirait
	 *   un second chemin pour la même intention (#367). Seul l'annuaire n'a pas
	 *   d'archivage. Le raisonnement complet est dans l'endpoint. */
	$: retirable = item.type === 'annuaire';
	function basculer() {
		dispatch('toggle', item.id);
	}

	$: typeColor = typeCouleur(item.type);
	$: nouveau = isNew(item);
	$: lien = typeLink(item);
	/**
	 *  L'extrait à montrer sous le libellé quand la carte est PLIÉE.
	 *
	 *  `evol_contenu` d'abord — c'est ce qui vient d'être dit, donc ce qu'on
	 *  cherche en parcourant le fil. `description` en repli, pour les cartes qui
	 *  n'annoncent pas une évolution.
	 *
	 *  ⚠️ Rien n'est affiché si l'extrait répète déjà `detail` : sur une carte
	 *  d'actualité, `detail` EST l'extrait, et l'afficher deux fois serait pire
	 *  que de ne rien ajouter. C'est la donnée qui tranche, pas le type de carte
	 *  — énumérer les types est exactement ce qui a coûté l'affichage du
	 *  commentaire d'un événement (cf. `flux/evenements.py`,(supprimé avec #1092)).
	 */
	$: extraitReplie = (() => {
		const brut = (item.meta?.evol_contenu ?? item.meta?.description) as string | undefined;
		const extrait = (brut ?? '').trim();
		if (!extrait) return '';
		const libelle = (item.detail ?? '').trim();
		if (!libelle) return extrait;
		return libelle.includes(extrait) || extrait.includes(libelle) ? '' : extrait;
	})();

	/**  La ligne de pastilles d'une affaire, telle que le serveur la rend
	 *   (`flux/commun.pastilles_affaire`) — absente sur les autres cartes. */
	$: affaire = item.meta?.affaire as Ticket | undefined;
	$: auteur = item.meta?.auteur as string | undefined;
	//  Le libellé d'un équipement vient d'un cache chargé après la page (#2442) :
	//  le citer repeint la pastille quand il arrive (`relire`).
	$: badges = relire($equipementsStore, () => badgesDuFlux(item));
	$: assisteIA = item.meta?.assiste_ia === true;
	$: photos = (item.meta?.photos_urls as string[] | undefined) ?? [];
	$: fichiers = (item.meta?.fichiers_urls as string[] | undefined) ?? [];

	//  🔴 Le serveur envoie désormais des CODES, plus un libellé (14/09/2026).
	//
	//  La ligne d'avant comparait `meta.perimetre` à la chaîne « Copropriété
	//  entière » — et le fichier le disait lui-même : *« comparaison de libellé en
	//  dur, et c'est une fragilité connue »*. Renommer le nœud racine depuis
	//  l'administration aurait fait réapparaître le badge sur CHAQUE ligne du fil.
	//
	//  Le remède annoncé était « côté API, ne pas envoyer le périmètre quand il
	//  vaut le défaut ». C'était encore mettre la règle au mauvais endroit : le
	//  serveur aurait décidé d'un rendu. Il envoie les codes, et la règle reste
	//  là où elle est déjà écrite — `BadgePerimetre`, qui ne rend rien quand il
	//  n'y a rien à dire. La ligne de méta est celle d'`EnteteCarte`, toujours
	//  posée : la carte n'a plus à décider si elle s'affiche.
	$: perimetreCodes = (item.meta?.perimetre_codes as string[] | undefined) ?? [];
</script>

<!--  🗂️ LA CARTE DU SITE (10/10/2026, maquette B du fil, choisie à l'écran) :
      `CarteListe` porte le conteneur, le geste et les états, `EnteteCarte`
      l'en-tête. La gouttière dit l'HEURE quand le jour est l'intitulé du groupe
      (`FriseDuFil`), la date sinon — puis la RUBRIQUE (`classeFlux`), dans sa teinte. La frise
      (trait vertical, puces) est partie avec elle : la gouttière la remplace.

      🔴 Le geste devient celui du site : repliée, toute la carte ouvre ;
      dépliée, seul le titre referme. Le fil se refermait au moindre clic dans
      son corps — il était la seule liste à le faire, alors que `ux-patterns` §3
      le donnait pour référence de ce geste. -->
<CarteListe
	quand={item.date}
	{heure}
	classe={classeFlux(item.type)}
	{expanded}
	urgent={estTicketUrgent(item)}
	{archive}
	onDeplier={basculer}
	onApprocher={affaire ? chargerCorpsAffaire : null}
	style="--nature-fort: {typeColor}"
>
	<EnteteCarte titre={item.titre} basculable on:toggle={basculer}>
		<svelte:fragment slot="titre-suffixe"><BadgeNouveau si={nouveau} /></svelte:fragment>
		<svelte:fragment slot="actions">
			{#if $isAdmin && retirable}
				<button
					class="btn-icon-danger"
					title="Retirer du fil (l'élément reste à son origine)"
					aria-label="Retirer cette carte du fil"
					on:click|stopPropagation={() => dispatch('masquer', item.id)}
					on:keydown|stopPropagation><IconeAction icone="trash-2" /></button
				>
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="apercu">
			<!--  Plié : le libellé, l'extrait et la vignette. Déplié, le corps prend
			      le relais — inutile de montrer deux fois la même image. -->
			{#if !expanded}
				<div class="flux-apercu">
					{#if item.detail || extraitReplie}
						<!--  🔴 Le LIBELLÉ et l'EXTRAIT, pas seulement le libellé (#531) :
						      « Mise à jour » ou « Pris en charge » disent qu'il s'est passé
						      quelque chose sans dire quoi. -->
						<p class="flux-detail clamp-3">
							{#if item.detail}<span class="flux-detail-libelle">{item.detail}</span
								>{/if}{#if item.detail && extraitReplie}&#8201;—&#8201;{/if}{extraitReplie}
						</p>
					{/if}
					<FluxVignette
						{photos}
						{fichiers}
						nbPieces={(item.meta?.pj_compte as number | undefined) ?? 0}
					/>
				</div>
			{/if}
		</svelte:fragment>
		<!--  🔴 LA DERNIÈRE LIGNE (27/09/2026, arbitré à l'écran) : une affaire ou une
		      actualité y porte la ligne de sa carte, À L'IDENTIQUE — `PastillesAffaire`,
		      sans 📌 (le fil a son bandeau « Épinglé »). Les autres cartes suivent le
		      même ORDRE : état, 🔹 périmètre, ✍️ auteur, ✨ IA. 🔒 `npm run lint:pastilles`. -->
		<svelte:fragment slot="tags">
			{#if affaire}
				<PastillesAffaire {affaire} {auteur} dansLeFil />
			{:else}
				{#each badges as b (b)}
					<!--  Un verdict garde la teinte qu'il a dans l'onglet Règlement. -->
					{#if item.type === 'question_reglement'}
						<BadgeVerdict verdict={String(champDe(item.meta, 'verdict') ?? '')} libelle={b} />
					{:else}
						<Badge teinte={badgeClass(item.type, b)}>{b}</Badge>
					{/if}
				{/each}
				<!--  `BadgePerimetre` ne rend RIEN quand le périmètre vaut le défaut. -->
				<BadgePerimetre perimetre={perimetreCodes} />
				<AuteurCarte nom={auteur} />
				<MarqueIA assiste={assisteIA} />
			{/if}
		</svelte:fragment>
	</EnteteCarte>
	{#if expanded}
		<!--  Le corps ne referme pas la carte (`ux-patterns` §3) : on y lit, on y
		      sélectionne, on y suit un lien. -->
		<div
			class="carte-corps flux-corps-carte"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			<FluxCorps {item} {lien} />
		</div>
	{/if}
</CarteListe>

<style>
	/*  Conteneur, survol, liseré, urgence, archive et gouttière : `CarteListe`
	    (`normes.css`). L'en-tête, ses actions, sa ligne de méta : `EnteteCarte`.
	    Ne reste ici que l'aperçu du fil — sa typographie est la référence des
	    aperçus de carte (`ApercuCarte`) — et le retrait de son corps. */
	.flux-apercu {
		display: flex;
		align-items: flex-start;
		gap: 0.85rem;
		margin-top: 0.1rem;
	}
	.flux-detail {
		flex: 1;
		min-width: 0;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0;
		line-height: 1.4;
	}
	/*  Le libellé garde le poids qu'il avait quand il était seul : c'est lui qui
	    dit la NATURE de la mise à jour, l'extrait n'en donne que la teneur. */
	.flux-detail-libelle {
		font-weight: 600;
	}
	/*  Le retrait latéral de l'en-tête (`EnteteCarte`) : le corps s'aligne sur le titre. */
	.flux-corps-carte {
		padding: 0 1.1rem 0.9rem;
	}
</style>
