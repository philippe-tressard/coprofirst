<!--
  L'APERÇU de la relance du syndic, sous le tableau (#2035, maquette 3b) : ce que
  le courriel dira de chaque affaire cochée, avant qu'il parte.

  Les affaires déjà relancées viennent en tête, avec leurs relances précédentes ;
  puis les premières relances. Pour chacune, le numéro de la relance qui part et
  son aperçu — le résumé de l'assistant, que le courriel reprend sous « Point de
  situation », sinon le descriptif (`relance_syndic`, migration 0288).

  ⚠️ C'est l'aperçu des AFFAIRES, pas du courriel entier : le préambule, la
  formule d'appel et l'historique de chaque affaire sont composés au serveur
  (`routers/tickets/relance`), et les recopier ici les ferait diverger.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import PastillesRelances from './PastillesRelances.svelte';
	import type { AffaireOuverte } from '#lib/api/index.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Les affaires cochées, dans l'ordre du tableau. */
	export let affaires: AffaireOuverte[];
	/** L'envoi est en cours. */
	export let envoi = false;
	export let onEnvoyer: () => void;

	$: dejaRelancees = affaires.filter((a) => a.relances.length > 0);
	$: premieres = affaires.filter((a) => a.relances.length === 0);
	$: groupes = [
		{ titre: 'Déjà relancées', liste: dejaRelancees },
		{ titre: 'Première relance', liste: premieres },
	].filter((g) => g.liste.length);

	function numero(a: AffaireOuverte): string {
		return a.relances.length ? `Relance n°${a.relances.length + 1}` : '1ʳᵉ relance';
	}
</script>

<section class="apercu" aria-labelledby="titre-apercu-relance">
	<h3 id="titre-apercu-relance" class="intitule">Aperçu de la relance</h3>
	<dl class="entete">
		<dt>À</dt>
		<dd>le syndic principal</dd>
		<dt>Copie</dt>
		<dd>les membres du conseil syndical</dd>
	</dl>

	{#if affaires.length === 0}
		<p class="vide">Cochez au moins une affaire pour composer la relance.</p>
	{:else}
		{#each groupes as g (g.titre)}
			<p class="groupe">{g.titre}{SEPARATEUR.tiret}{g.liste.length}</p>
			<ul class="liste">
				{#each g.liste as a (a.id)}
					<li class="item" class:deja={a.relances.length > 0}>
						<div class="item-tete">
							<strong>{a.numero}{SEPARATEUR.tiret}{a.titre}</strong>
							<Badge teinte={a.relances.length ? 'badge-red' : 'badge-orange'}>{numero(a)}</Badge>
							<BadgePerimetre perimetre={a.perimetre_cible} />
						</div>
						{#if a.relances.length}<PastillesRelances relances={a.relances} />{/if}
						{#if a.apercu}<p class="texte clamp-rapport">{a.apercu}</p>{/if}
					</li>
				{/each}
			</ul>
		{/each}
	{/if}

	<div class="pied">
		<button
			type="button"
			class="btn btn-primary"
			disabled={envoi || affaires.length === 0}
			on:click={onEnvoyer}
		>
			{envoi
				? 'Envoi…'
				: `Envoyer la relance (${affaires.length} affaire${affaires.length > 1 ? 's' : ''})`}
		</button>
	</div>
</section>

<style>
	.apercu {
		border: 1px solid var(--color-primary);
		border-radius: var(--radius);
		background: var(--color-surface);
		padding: 1rem 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.intitule {
		font-family: inherit;
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin: 0;
	}
	.entete {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.2rem 0.75rem;
		margin: 0;
		padding-bottom: 0.6rem;
		border-bottom: 1px solid var(--color-border);
		font-size: var(--fs-base);
	}
	.entete dt {
		color: var(--color-text-muted);
		font-weight: 600;
	}
	.entete dd {
		margin: 0;
	}
	.groupe {
		margin: 0.4rem 0 0;
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		font-weight: 700;
	}
	.liste {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.6rem 1rem;
	}
	.item {
		border-left: 3px solid var(--color-border);
		padding: 0.15rem 0 0.15rem 0.7rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: var(--fs-base);
	}
	.item.deja {
		border-left-color: var(--color-danger);
	}
	.item-tete {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 0.5rem;
		align-items: baseline;
	}
	.texte {
		margin: 0;
		white-space: pre-line;
	}
	.vide {
		margin: 0;
		color: var(--color-text-muted);
	}
	.pied {
		display: flex;
		justify-content: flex-end;
		border-top: 1px solid var(--color-border);
		padding-top: 0.75rem;
	}
	@media (max-width: 767px) {
		.liste {
			grid-template-columns: minmax(0, 1fr);
		}
		.pied .btn {
			width: 100%;
			justify-content: center;
		}
	}
</style>
