<!--
  **Mes badges** — une section de l'écran Accès & sécurité, rendue deux fois :
  une pour les vigiks, une pour les télécommandes.

  ## 🔴 Pourquoi ce composant (#805, 06/09/2026)

  Les deux sections étaient écrites **à l'identique**, à quatre mots près : le
  titre, le nom du tableau, le libellé du vide, et le `'vigik'` / `'tc'` passé
  aux deux gestes. Quarante lignes en double — table, colonnes, en-têtes, bouton
  « Signaler perdu » conditionné au statut, bouton de suppression conditionné au
  droit.

  ⚠️ Elles n'avaient PAS encore divergé, et c'est justement le moment où l'on
  factorise : après, il faut d'abord décider laquelle des deux a raison. C'est ce
  qui a coûté deux jours sur les libellés de rôles, le matin même (#801).

  ## Ce qui reste chez le parent, et pourquoi

  Le geste — signaler perdu — parle à l'API et recharge la liste. Il reste un
  callback : un seul endroit parle au serveur, et le composant ne connaît ni les
  routes ni le type d'objet qu'il rend. C'est le même contrat que
  `ListeAnnonces` et `ListeIdees`.

  ## 🔴 La poubelle est partie le 15/09/2026, et c'est de fond

  > « sur la page Mes lots & accès : enlève la poubelle. Un résident ne peut pas
  >   supprimer un accès, il peut juste signaler qu'il a perdu. »

  Le geste détruisait la ligne. Or **le badge existe toujours** — il est dans une
  poche, un tiroir, ou perdu : le parc cessait de pouvoir dire qu'il circule.
  C'est la règle déjà déployée partout (`ux-patterns` §8) : archiver sur la vue
  principale, supprimer réservé à l'admin — qui le fait, lui, sur l'écran du parc.

  ⚠️ Les **routes** ont été retirées avec le bouton (`routers/acces/resident`) :
  masquer un geste sans le fermer le laisse accessible à qui appelle l'API.

  ## La colonne « Accès », demandée le même jour

  > « ajouter la colonne Accès, de celle du CS / Badges & télécommandes »

  Le même `BadgePerimetre` que l'écran du conseil syndical, sur la même donnée :
  un porteur voit désormais ce que son badge ouvre. Une seconde mise en forme du
  même objet aurait été la divergence de demain.

  ## La condition d'affichage vient du parent, elle aussi

  `{#if vigiks.length > 0 || statut !== 'locataire'}` — un locataire qui n'a
  aucun badge ne voit pas la section vide, un copropriétaire si (il peut en
  déclarer un). Cette règle est écrite **une fois** dans le parent, pour les deux
  sections : la porter ici obligerait à lui passer le statut, alors qu'elle ne
  parle pas du tableau mais de la place qu'il occupe dans l'écran.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import { statutAccesBadge, statutAccesLabel } from '#lib/types-acces.ts';

	/** « Badges d'accès (Vigik) » ou « Télécommandes de parking ». */
	export let titre: string;
	/** Ce qu'on affiche quand la personne n'en a aucun. */
	export let messageVide: string;
	export let items: {
		id: number;
		code: string;
		statut: string;
		perimetre_cible?: string[];
	}[] = [];

	export let onSignalerPerdu: (id: number) => void;
</script>

<section class="card mes-acces-carte">
	<div class="section-header">
		<h2 class="section-title">{titre}</h2>
	</div>
	{#if items.length === 0}
		<p class="mes-acces-vide">{messageVide}</p>
	{:else}
		<div class="table-wrap">
			<table class="table table-acces">
				<colgroup><col class="col-1" /><col class="col-2" /><col /><col class="col-4" /></colgroup>
				<thead><tr><th>Code</th><th>Statut</th><th>Accès</th><th>Actions</th></tr></thead>
				<tbody>
					{#each items as item (item.id)}
						<tr>
							<td class="mes-acces-code">{item.code}</td>
							<td
								><Badge teinte={statutAccesBadge(item.statut)}
									>{statutAccesLabel(item.statut)}</Badge
								></td
							>
							<!--  🔹 Le MÊME composant que l'écran du conseil syndical : ce que
							      le badge ouvre se lit d'une seule façon sur tout le site. -->
							<td>
								<BadgePerimetre perimetre={item.perimetre_cible ?? []}>
									<span class="mes-acces-vide">—</span>
								</BadgePerimetre>
							</td>
							<td class="mes-acces-actions">
								{#if item.statut === 'actif'}
									<button class="btn btn-sm btn-outline" on:click={() => onSignalerPerdu(item.id)}>
										Signaler perdu
									</button>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</section>

<style>
	/*  `.section` n'est pas globale : elle vit dans l'écran hôte, scopée à lui.
	    L'employer ici aurait rendu la carte sans son cadre (`standards/02` §4 ter,
	    et `lint:classes-nues` le refuse). */
	.mes-acces-carte {
		padding: 1.25rem;
	}
	.mes-acces-carte + :global(.mes-acces-carte) {
		margin-top: 1rem;
	}
	.mes-acces-vide {
		color: var(--color-text-muted);
		font-size: var(--fs-base);
	}
	.mes-acces-code {
		font-family: monospace;
	}
	.mes-acces-actions {
		display: flex;
		gap: 0.35rem;
		flex-wrap: wrap;
	}
	.table-acces {
		table-layout: fixed;
		width: 100%;
	}
	.col-1 {
		width: 28%;
	}
	.col-2 {
		width: 8rem;
	}
	.col-4 {
		width: 9rem;
	}
</style>
