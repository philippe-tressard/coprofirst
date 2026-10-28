<!--
  **Un composant chargé quand il s'affiche, pas à l'ouverture de l'écran** (11/10/2026).

  La télémétrie (Admin › Télémétrie › Durées d'affichage) donnait plus d'une
  seconde à l'« Ouverture du site » sur `/admin` et `/espace-cs`. Ces écrans
  importaient TOUS leurs onglets en tête de fichier : ouvrir « À traiter »
  téléchargeait aussi la télémétrie, les imports de lots, l'assistant IA… — le
  nœud d'`/admin` pesait 78 Ko compressés à lui seul, pour un onglet affiché.

  L'appelant passe l'`import()` ; le composant chargé revient en paramètre du
  snippet `contenu`, TYPÉ d'après l'import — props et `bind:` restent vérifiés
  par svelte-check (une prop de slot, `let:`, le perdait : `never`) :

  ```svelte
  <ChargementDiffere charger={() => import('#lib/components/OngletSmtp.svelte')}>
  	{#snippet contenu(OngletSmtp)}
  		<OngletSmtp bind:emailFooter={…} />
  	{/snippet}
  </ChargementDiffere>
  ```

  ⚠️ Chaque branche d'un `{#if onglet === …}` est une instance à part : le
  chargement part au montage, une fois. Le service worker garde ensuite le
  fichier : le passage suivant à l'onglet n'attend plus le réseau.

  🔴 Le parent ne s'adresse au composant qu'à travers des props liées, jamais
  seulement par une méthode (`bind:this`) : tant que le morceau n'est pas arrivé,
  la référence vaut `null` et l'appel se perd sans un mot. « Nouveau contrat »
  cliqué tôt ne faisait rien (12/10/2026, trouvé par le rejeu sous charge) — le
  repli passe par la prop que le composant lit à son montage.

  🔴 Un échec se DIT (`EtatListe`) : le cas réel est une version publiée entre
  l'ouverture de la page et le clic — le fichier d'avant n'existe plus.
-->
<script lang="ts" generics="T">
	import { onMount } from 'svelte';
	import type { Snippet } from 'svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';

	/** L'`import()` du composant — appelé une fois, au montage. */
	export let charger: () => Promise<{ default: T }>;
	/** Le rendu, une fois le composant chargé — il le reçoit en paramètre. */
	export let contenu: Snippet<[T]>;

	let composant: T | null = null;
	let erreur = '';

	onMount(() => {
		let actif = true;
		charger().then(
			(module) => {
				if (actif) composant = module.default;
			},
			() => {
				if (actif)
					erreur =
						'Rechargez la page : une nouvelle version du site a peut-être été publiée entre-temps.';
			},
		);
		return () => {
			actif = false;
		};
	});
</script>

{#if composant}
	{@render contenu(composant)}
{:else if erreur}
	<EtatListe {erreur} titreErreur="Cette partie de l’écran n’a pas pu se charger" />
{:else}
	<!--  ⏱ L'attente ne s'annonce qu'au-delà de `--delai-annonce` (12/10/2026) : le morceau
	      est le plus souvent déjà en cache, et « Chargement… » clignotait une
	      fraction de seconde à chaque onglet. Fondu seul — rien ne bouge, donc
	      rien à retirer sous `prefers-reduced-motion` (`emil-design-eng`). -->
	<div class="attente-differee"><EtatListe chargement /></div>
{/if}

<style>
	.attente-differee {
		animation: attente-annoncee var(--duree-apparition) var(--ease-out) var(--delai-annonce) both;
	}
	@keyframes attente-annoncee {
		from {
			opacity: 0;
		}
	}
</style>
