<!--
  ChampRecherche.svelte — le champ de RECHERCHE libre d'une barre de filtres :
  libellé « Recherche » devant, saisie, et ce que l'appelant y ajoute.

  ## Pourquoi (28/09/2026)

  Sorti de `FiltresAffaires` le jour où l'annuaire des prestataires a reçu sa
  recherche « comme pour les affaires » : recopier le balisage et ses quarante
  lignes de style aurait fait la deuxième écriture d'un même objet (`standards/02`).
  Il ne cherche RIEN — il expose la saisie liée ; la règle de correspondance
  reste à qui la connaît (le serveur pour les affaires, `#lib/prestataires`
  pour l'annuaire).

  - `aide` : la phrase grise sous le champ — facultative, un annuaire dont la
    règle tient dans le placeholder n'en a pas besoin.
  - le slot par défaut se pose à droite de la saisie — une option de la
    recherche (la case « Inclure les Archives » l'a occupé jusqu'au 28/09/2026).
-->
<script lang="ts">
	/** Unique sur la page : relie le libellé et l'aide à la saisie. */
	export let id: string;
	export let valeur = '';
	export let placeholder = '';
	export let aide = '';
</script>

<div class="field champ-en-ligne champ-recherche">
	<label class="libelle-groupe libelle-devant" for={id}>Recherche</label>
	<div class="recherche-saisie">
		<input
			{id}
			type="search"
			{placeholder}
			aria-describedby={aide ? `${id}-aide` : undefined}
			bind:value={valeur}
		/>
		<slot />
	</div>
	{#if aide}
		<p class="aide" id="{id}-aide">{aide}</p>
	{/if}
</div>

<style>
	/*  Le libellé DEVANT, comme ceux des rangées de pastilles : `.field` est une
	    colonne, la recherche est une ligne. L'aide passe dessous, alignée sur le
	    champ. */
	.champ-recherche {
		flex: 1;
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		column-gap: 0.5rem;
		row-gap: 0.25rem;
		align-items: center;
		max-width: 52rem;
	}
	.recherche-saisie {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1rem;
		align-items: center;
	}
	.recherche-saisie input[type='search'] {
		flex: 1;
		min-width: 12rem;
	}
	.champ-recherche .aide {
		grid-column: 2;
		margin: 0;
	}
	@media (max-width: 767px) {
		.champ-recherche {
			grid-template-columns: minmax(0, 1fr);
		}
		.champ-recherche .aide {
			grid-column: 1;
		}
	}
</style>
