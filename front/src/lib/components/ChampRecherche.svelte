<!--
  ChampRecherche.svelte — LE champ de RECHERCHE du site, et le seul (#2308) :
  libellé « Recherche » devant, saisie blanche avec sa loupe et sa croix pour
  effacer, et dessous la phrase qui dit OÙ l'on cherche.

  ## Pourquoi (28/09/2026)

  Sorti de `FiltresAffaires` le jour où l'annuaire des prestataires a reçu sa
  recherche « comme pour les affaires » : recopier le balisage et ses quarante
  lignes de style aurait fait la deuxième écriture d'un même objet (`standards/02`).
  Il ne cherche RIEN — il expose la saisie liée ; la règle de correspondance
  reste à qui la connaît (le serveur pour les affaires, `contientTousLesMots`
  de `#lib/texte` pour une liste déjà reçue).

  ## Le standard (maquette B, 29/10/2026)

  Demandé : « standardisée sur tous les champs de saisie RECHERCHE », puis « le
  champ est de la même couleur que le fond ; mets-le en blanc ». Cinq maquettes,
  la B retenue : fond `--color-surface` (blanc, et la surface du thème sombre),
  loupe à gauche, ✕ qui vide le champ dès qu'il a du texte.

  - `dans` : OBLIGATOIRE — ce que la recherche fouille (« n°, titre, auteur »).
    L'aide est composée ICI, pour que toutes disent la même chose de la même
    façon ; trois recherches n'en avaient aucune.
  - `sansAccents` : la règle ignore-t-elle les accents ? Vrai par défaut — c'est
    celle de `contientTousLesMots` et du serveur des affaires. Une recherche
    dont la règle ne les ignore pas le dit (`false`) : l'aide ne promet que ce
    qui est vrai.
  - le slot par défaut se pose à droite de la saisie (le bouton « Chercher »
    d'une recherche au serveur).
  - `on:keydown` est relayé (Entrée lance une recherche au serveur).

  🔒 `npm run lint:recherche` refuse un champ de recherche écrit sans lui.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Unique sur la page : relie le libellé et l'aide à la saisie. */
	export let id: string;
	export let valeur = '';
	export let placeholder = '';
	/** Ce que la recherche fouille — la phrase d'aide le dit. */
	export let dans: string;
	export let sansAccents = true;

	let saisie: HTMLInputElement;

	function effacer() {
		valeur = '';
		saisie.focus();
	}
</script>

<div class="field champ-en-ligne champ-recherche">
	<label class="libelle-groupe libelle-devant" for={id}>Recherche</label>
	<div class="recherche-saisie">
		<div class="recherche-cadre">
			<span class="loupe" aria-hidden="true"><Icon name="search" size={16} /></span>
			<input
				{id}
				type="search"
				{placeholder}
				autocomplete="off"
				aria-describedby="{id}-aide"
				bind:value={valeur}
				bind:this={saisie}
				on:keydown
			/>
			{#if valeur}
				<button type="button" class="effacer" aria-label="Effacer la saisie" on:click={effacer}>
					<Icon name="x" size={16} />
				</button>
			{/if}
		</div>
		<slot />
	</div>
	<p class="aide" id="{id}-aide">
		Cherche dans : {dans}{SEPARATEUR.tiret}sans tenir compte {sansAccents
			? 'des accents ni des majuscules'
			: 'des majuscules'}.
	</p>
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
	/*  Le CADRE porte ce que `.field input` donne d'ordinaire à la saisie —
	    bordure, rayon, fond, anneau de focus —, pour que loupe et croix soient
	    dedans. Fond BLANC : la saisie ressort sur la pierre de la page. */
	.recherche-cadre {
		flex: 1;
		min-width: 12rem;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0 0.3rem 0 0.6rem;
		border: 1px solid var(--color-border-champ);
		border-radius: var(--radius);
		background: var(--color-surface);
		transition:
			border-color var(--duree-geste),
			box-shadow var(--duree-geste);
	}
	.recherche-cadre:focus-within {
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px var(--color-primary-light);
	}
	.loupe {
		display: inline-flex;
		color: var(--color-text-muted);
	}
	.recherche-cadre input[type='search'] {
		flex: 1;
		min-width: 0;
		padding: 0.45rem 0;
		border: none;
		background: transparent;
		box-shadow: none;
	}
	/*  La croix du navigateur (Chrome, Safari) ferait double emploi avec la
	    nôtre, et Firefox n'en a pas : une seule, la même partout. */
	.recherche-cadre input[type='search']::-webkit-search-cancel-button {
		appearance: none;
	}
	.effacer {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 2rem;
		min-height: 2rem;
		padding: 0;
		border: none;
		border-radius: var(--radius);
		background: none;
		color: var(--color-text-muted);
		cursor: pointer;
	}
	.effacer:focus-visible {
		outline: 2px solid var(--color-primary);
	}
	@media (hover: hover) and (pointer: fine) {
		.effacer:hover {
			color: var(--color-text);
			background: var(--color-neutre-fond);
		}
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
		/*  Cible tactile (`e2e` cibles tactiles) : 44 px au doigt. */
		.effacer {
			min-width: 2.75rem;
			min-height: 2.75rem;
		}
	}
</style>
