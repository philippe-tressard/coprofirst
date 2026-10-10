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
	import IconeAction from '$lib/components/IconeAction.svelte';
	import BadgeNouveau from '$lib/components/BadgeNouveau.svelte';
	import { createEventDispatcher } from 'svelte';

	import { isAdmin } from '$lib/stores/auth';
	import type { FluxItem, Ticket } from '$lib/api';
	import { fmtDatetimeShort } from '$lib/date';
	import FluxVignette from '$lib/components/FluxVignette.svelte';
	import FluxCorps from '$lib/components/FluxCorps.svelte';
	import BadgePerimetre from '$lib/components/BadgePerimetre.svelte';
	import PastillesAffaire from '$lib/components/PastillesAffaire.svelte';
	import AuteurCarte from '$lib/components/AuteurCarte.svelte';
	import MarqueIA from '$lib/components/MarqueIA.svelte';
	import { estPerimetreParDefaut } from '$lib/perimetres';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { relire } from '$lib/utils';
	import {
		badgeClass,
		badgesDuFlux,
		estTicketUrgent,
		isNew,
		typeCouleur,
		typeFond,
		typeLibelle,
		typeLink,
	} from '$lib/flux';

	export let item: FluxItem;
	export let expanded = false;

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
	//  là où elle est déjà écrite — `estPerimetreParDefaut`, puis
	//  `BadgePerimetre`, qui ne rend rien quand il n'y a rien à dire.
	//
	//  ⚠️ `relire($perimetresStore, …)` : ces deux fonctions lisent l'arbre dans un
	//  état de MODULE, que Svelte ne surveille pas (#947). Sans cette dépendance,
	//  une carte rendue avant l'arrivée de l'arbre garderait son verdict.
	$: perimetreCodes = (item.meta?.perimetre_codes as string[] | undefined) ?? [];
	$: aPerimetre = relire(
		$perimetresStore,
		() => perimetreCodes.length > 0 && !estPerimetreParDefaut(perimetreCodes),
	);
</script>

<div class="flux-item" class:flux-urgent={estTicketUrgent(item)} class:flux-expanded={expanded}>
	<div class="flux-dot" style="background:{typeColor}"></div>
	{#if nouveau}<div class="flux-new-dot"></div>{/if}
	<div
		class="flux-card card"
		style="border-left-color:{typeColor}"
		role="button"
		tabindex="0"
		on:click={basculer}
		on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && basculer()}
	>
		<div class="flux-card-top">
			<div class="flux-card-top-left">
				<span class="flux-type-chip" style="background:{typeFond(item.type)};color:{typeColor}"
					>{typeLibelle(item.type)}</span
				>
				<BadgeNouveau si={nouveau} />
			</div>
			<div class="flux-card-top-right">
				<span class="flux-heure">{fmtDatetimeShort(item.date)}</span>
				{#if $isAdmin && retirable}
					<!--  `stopPropagation` : la carte entière bascule au clic. Sans lui,
					      retirer une carte la déplierait au passage. -->
					<button
						class="btn-icon-danger"
						title="Retirer du fil (l'élément reste à son origine)"
						aria-label="Retirer cette carte du fil"
						on:click|stopPropagation={() => dispatch('masquer', item.id)}
						on:keydown|stopPropagation><IconeAction icone="trash-2" /></button
					>
				{/if}
				<span class="chevron" class:open={expanded}>›</span>
			</div>
		</div>
		<div class="flux-card-body">
			<span class="flux-icon">{item.icon}</span>
			<div class="flux-card-text">
				<span class="flux-titre">{item.titre}</span>
				{#if !expanded && (item.detail || extraitReplie)}
					<!--  🔴 Le LIBELLÉ et l'EXTRAIT, pas seulement le libellé (#531).
					      Signalé à l'écran, capture à l'appui : une carte « ticket mis à
					      jour » n'affichait que « Mise à jour » ou « Pris en charge » —
					      deux mots qui disent qu'il s'est passé quelque chose sans dire
					      quoi. À côté, une carte d'actualité remplissait deux lignes.

					      L'asymétrie ne venait pas des données : `evol_contenu` (300
					      caractères) était déjà transporté et déjà rendu par la carte
					      DÉPLIÉE. Seule la carte pliée l'ignorait. -->
					<p class="flux-detail clamp-3">
						{#if item.detail}<span class="flux-detail-libelle">{item.detail}</span
							>{/if}{#if item.detail && extraitReplie}&#8201;—&#8201;{/if}{extraitReplie}
					</p>
				{/if}
			</div>
			<!-- Plié : aperçu. Déplié : la galerie plus bas prend le relais,
			     inutile de montrer deux fois la même image. -->
			{#if !expanded}
				<FluxVignette
					{photos}
					{fichiers}
					nbPieces={(item.meta?.pj_compte as number | undefined) ?? 0}
				/>
			{/if}
		</div>
		<!--  🔴 LA DERNIÈRE LIGNE (27/09/2026, arbitré à l'écran) : une affaire ou une
		      actualité y porte la ligne de sa carte, À L'IDENTIQUE — `PastillesAffaire`,
		      sans 📌 (le fil a son bandeau « Épinglé »). Elle différait sur neuf
		      points : catégorie en texte, état absent, « urgent » rouge, numéro en
		      badge, lecteurs et ✨ absents…
		      Les autres cartes suivent le même ORDRE : état, 🔹 périmètre, ✍️ auteur,
		      ✨ IA. 🔒 `npm run lint:pastilles`. -->
		{#if affaire}
			<div class="flux-badges">
				<PastillesAffaire {affaire} {auteur} dansLeFil />
			</div>
		{:else if badgesDuFlux(item).length > 0 || aPerimetre || auteur || assisteIA}
			<div class="flux-badges">
				{#each badgesDuFlux(item) as b (b)}
					<span class="badge {badgeClass(item.type, b)}">{b}</span>
				{/each}
				<!--  `BadgePerimetre` ne rend RIEN quand le périmètre vaut le défaut. -->
				<BadgePerimetre perimetre={perimetreCodes} />
				<AuteurCarte nom={auteur} />
				<MarqueIA assiste={assisteIA} />
			</div>
		{/if}
		{#if expanded}
			<FluxCorps {item} {lien} />
		{/if}
	</div>
</div>

<style>
	.flux-item {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		color: inherit;
		position: relative;
		margin-bottom: 0.5rem;
	}
	.flux-card {
		flex: 1;
		padding: 0.7rem 0.9rem;
		transition:
			box-shadow var(--duree-geste),
			border-left-color var(--duree-geste),
			background var(--duree-geste);
		border-left: 4px solid var(--color-border);
		cursor: pointer;
	}
	.flux-card:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	/*  Le fond change au survol, comme sur toutes les listes dépliables du site
	    (#362). La carte ne renforçait que son OMBRE — trop discret pour annoncer
	    « ceci s'ouvre », et l'utilisateur l'a signalé deux fois : une carte du fil
	    restait blanche là où une actualité se teintait. La même valeur que
	    `.pub-row:hover` et `.tk-row:hover`, pas une nuance de plus. */
	/*  🔴 Le survol colore le TITRE, pas le bloc — la règle du site depuis le
	    18/08/2026, et le fil est le dernier à l'avoir reçue alors qu'il en est
	    la référence : « quand tout l'article change de couleur c'est moche ».

	    Un aplat sur toute la carte fait bouger la page à chaque passage de souris
	    dans une liste longue. Le titre qui change de teinte dit la même chose —
	    « ceci répond » — sans repeindre l'écran.

	    ⚠️ Le titre change **où que soit la souris sur le bloc** : c'est bien le
	    survol de `.flux-item` qui déclenche, pas celui du titre. Toute la carte
	    reste la cible du clic.

	    ⚠️ Pas de soulignement : le titre n'est pas un lien, c'est une zone
	    cliquable — le souligner le ferait passer pour une navigation. */
	@media (hover: hover) and (pointer: fine) {
		.flux-item:hover .flux-card {
			box-shadow: var(--shadow);
		}
	}
	@media (hover: hover) and (pointer: fine) {
		.flux-item:hover .flux-titre {
			color: var(--color-primary);
		}
	}
	.flux-titre {
		transition: color var(--duree-geste);
	}
	.flux-item.flux-urgent .flux-card {
		border-left-color: var(--color-danger) !important;
	}
	.flux-item.flux-expanded .flux-card {
		box-shadow: var(--shadow);
	}

	.flux-card-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.35rem;
	}
	.flux-card-top-left {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.flux-card-top-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.flux-heure {
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
		white-space: nowrap;
	}
	.flux-card-body {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
	}
	.flux-icon {
		font-size: 1.05rem;
		flex-shrink: 0;
		line-height: 1;
		margin-top: 0.1rem;
	}
	.flux-card-text {
		flex: 1;
		min-width: 0;
	}
	.flux-titre {
		font-size: var(--fs-base);
		font-weight: 500;
		line-height: 1.35;
		display: block;
	}
	.flux-detail {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0.15rem 0 0;
		line-height: 1.4;
	}
	/*  Le libellé garde le poids qu'il avait quand il était seul : c'est lui qui
	    dit la NATURE de la mise à jour, l'extrait n'en donne que la teneur. */
	.flux-detail-libelle {
		font-weight: 600;
	}
	/*  🔴 `.clamp-3` est parti dans `normes.css` (18/09/2026) : le fil tronquait
	    à trois lignes depuis toujours, et c'est ce choix qui a été retenu pour
	    TOUTES les cartes de liste. Une notion, une écriture — la classe globale
	    s'applique ici sans rien d'autre à faire. */
	/*  Le nom en texte discret, jamais en badge : même taille et même teinte que
	    `.tk-auteur` sur la carte du ticket, à dessein. */
	/*  La MÊME ligne que celle d'une carte (`.ec-tags` d'`EnteteCarte`) : même
	    taille de texte, même alignement, même espacement (27/09/2026) — sans quoi
	    le numéro et l'auteur y paraissaient plus gros que les pastilles. Seul le
	    retour à la ligne diffère : le fil n'a pas d'actions à côté. */
	.flux-badges {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		flex-wrap: wrap;
		font-size: var(--fs-xs);
		margin-top: 0.35rem;
	}

	/*  Le badge NEW vit dans `BadgeNouveau`, le même sur tout le site (26/09/2026). */

	/* ═══ CHEVRON ═══════════════════════════════════════════════════════ */
	/*  Écart assumé : chevron en gras, non sélectionnable, dans un flex. */
	.chevron {
		font-weight: 700;
		flex-shrink: 0;
		user-select: none;
	}

	/* ═══ CORPS DÉPLIÉ ══════════════════════════════════════════════════ */
	@media (hover: hover) and (pointer: fine) {
		.flux-link:hover {
			text-decoration: underline;
		}
	}

	/* Galerie dépliée — les styles étaient écrits en `style=` sur chaque balise,
	   donc quatre fois pour deux blocs.
	   La règle `.flux-photos img` qui bornait les images à 120×90 en `cover` a été
	   retirée : le format des photos appartient désormais à `PiecesJointes`, qui
	   les rend en grand une fois la carte dépliée. Deux endroits pour décider de
	   la même taille, c'est un endroit de trop — et celui-ci était devenu mort. */

	/* ═══ RÉACTION INLINE (ticket_mis_a_jour) ═══════════════════════════ */

	@media (max-width: 767px) {
		.flux-dot {
			left: -1.1rem;
			width: 8px;
			height: 8px;
		}
		.flux-new-dot {
			left: -1.4rem;
			width: 14px;
			height: 14px;
		}
	}
</style>
