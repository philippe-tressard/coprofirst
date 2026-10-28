<!--
  **Reprendre une annonce de hall en actualité** — le raccourci, et lui seul.

  Extrait de `FormulaireActualite.svelte` le 20/09/2026 (#1092), au titre du
  découpage au fil de l'eau : l'écran passait 500 lignes en recevant la section
  « Quand », et la règle est qu'on découpe le fichier quand on y touche.

  🔴 **Ce n'est PAS une section du cadre #430**, et c'est ce que disait déjà le
  commentaire laissé sur place : *« un raccourci qui REMPLIT le formulaire, pas
  une section de l'entité »*. D'où sa place **avant** le titre, hors de la
  déclaration de `#lib/entites/publication` — et d'où le fait qu'il se sorte
  proprement : une notion qui n'est pas une section n'a rien à faire dans un
  écran qui, lui, rend des sections.

  ⚠️ Il ne s'affiche **qu'en création** : reprendre une annonce dans une
  publication existante écraserait ce qu'on est en train de corriger. Le
  composant le sait tout seul — l'appelant n'a pas à y repenser.
-->
<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { annoncesProposables, reprendreAnnonce } from '#lib/actualite-prefill.ts';
	import type { PrefillActualite } from '#lib/actualite-prefill.ts';
	import { annoncesHall, tickets } from '#lib/api/index.ts';
	import { perimetreDefautListe } from '#lib/perimetres/index.ts';
	import { fmtDateShort } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import type { AnnonceHall } from '#lib/api/types.ts';

	/** En édition, le raccourci ne s'affiche pas — voir l'en-tête. */
	export let modeEdition = false;

	const dispatch = createEventDispatcher<{ reprise: PrefillActualite }>();

	let annonces: AnnonceHall[] = [];
	let annonceSourceId: number | '' = '';

	onMount(async () => {
		if (modeEdition) return;
		annonces = await annoncesProposables(() => annoncesHall.list(true));
	});

	async function choisir(annonceId: number | '') {
		annonceSourceId = annonceId;
		if (annonceId === '') return;
		try {
			const p = await reprendreAnnonce(
				() => tickets.depuisAnnonceHall(annonceId),
				perimetreDefautListe,
			);
			toast('info', p.message);
			dispatch('reprise', p);
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur lors du pré-remplissage'));
		}
	}
</script>

{#if !modeEdition && annonces.length}
	<div class="field">
		<label for="pub-source-hall">Pré-remplir depuis une annonce de hall</label>
		<select
			id="pub-source-hall"
			value={annonceSourceId}
			on:change={(e) =>
				choisir(
					(e.currentTarget as HTMLSelectElement).value === ''
						? ''
						: Number((e.currentTarget as HTMLSelectElement).value),
				)}
		>
			<option value="">— Saisie libre —</option>
			{#each annonces as annonce (annonce.id)}
				<option value={annonce.id}>{fmtDateShort(annonce.cree_le)} · {annonce.titre}</option>
			{/each}
		</select>
	</div>
	<p class="aide">
		Reprend le titre, le message, le périmètre et les images de l'affiche. Tout reste modifiable
		ci-dessous : l'actualité est indépendante de l'annonce d'origine.
	</p>
	<hr class="separateur-prefill" />
{/if}
