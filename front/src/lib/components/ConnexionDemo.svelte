<!--
  La page de connexion de la DÉMO PUBLIQUE (spec `mode-demo.md` §5 et §8, #1906) :
  à la place du formulaire, un lien par personnage. Chaque lien est l'adresse
  d'entrée que la route du serveur sert (`/api/demo/entrer/{code}`) — la même que
  les boutons de la page d'accueil de CoproFirst.

  Les personnages se LISENT au serveur : libellés et descriptions n'ont qu'une
  écriture (`app/demo/personnages.py`).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { demo, type PersonnageDemo } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';

	let personnages: PersonnageDemo[] = [];
	let chargement = true;
	let erreur = '';

	onMount(async () => {
		try {
			personnages = await demo.personnages();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});
</script>

<p class="choix-intro">Choisissez qui vous êtes pour visiter la résidence :</p>
<EtatListe {chargement} {erreur} vide={personnages.length === 0}>
	<ul class="personnages">
		{#each personnages as p (p.code)}
			<li>
				<a class="personnage" href={demo.urlEntree(p.code)} data-sveltekit-reload>
					<span class="personnage-nom">{p.libelle}</span>
					<span class="personnage-description">{p.description}</span>
				</a>
			</li>
		{/each}
	</ul>
</EtatListe>

<style>
	.choix-intro {
		margin: 0 0 0.75rem;
		color: var(--color-text-muted);
		font-size: var(--fs-base);
	}
	.personnages {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.5rem;
	}
	.personnage {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-height: 44px;
		padding: 0.6rem 0.85rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		color: var(--color-text);
		text-decoration: none;
		transition:
			border-color var(--duree-geste),
			background-color var(--duree-geste);
	}
	.personnage:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	.personnage:active {
		transform: scale(0.97);
	}
	@media (hover: hover) and (pointer: fine) {
		.personnage:hover {
			border-color: var(--color-primary);
			background: var(--color-primary-light);
		}
	}
	.personnage-nom {
		font-weight: 600;
		color: var(--color-primary);
	}
	.personnage-description {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
</style>
