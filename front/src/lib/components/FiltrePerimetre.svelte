<!--
  Le FILTRE PAR PÉRIMÈTRE — une rangée de pastilles « tout » + les périmètres de
  premier niveau, prise dans l'arborescence administrée.

  🔴 **Il est dynamique par construction** (arbitré le 10/09/2026). Un périmètre
  créé dans Admin → Patrimoine apparaît dans ce filtre sans qu'on y touche, et un
  périmètre désactivé en disparaît. C'est ce que ne savait pas faire le premier
  filtre du carnet d'entretien, qui listait les BÂTIMENTS : il ne pouvait ni
  proposer « Parking » ou « Caves » — qui n'en sont pas —, ni suivre l'arbre.

  La règle du premier niveau vient de `#lib/perimetres` (`perimetresNiveau1`),
  partagée avec `PerimetrePicker` : deux calculs auraient divergé au premier
  périmètre ajouté, c'est-à-dire précisément le jour où ce filtre doit servir.

  ⚠️ **Choix UNIQUE, là où le picker est multiple.** Filtrer, c'est se restreindre
  à une chose ; cibler, c'est en désigner plusieurs. Deux gestes, deux composants
  — les fondre aurait demandé une prop `multiple` et rendu chaque écran
  responsable de dire lequel des deux il fait.

  Usage :
      <FiltrePerimetre bind:choisi on:changer={recharger} />
-->
<script context="module" lang="ts">
	let compteur = 0;
</script>

<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { perimetresStore } from '#lib/stores/perimetres.ts';
	import {
		perimetreLabelUn,
		perimetresNiveau1,
		perimetreParDefaut,
	} from '#lib/perimetres/index.ts';
	import { relire } from '#lib/utils.ts';
	import Pastille from './Pastille.svelte';

	/**  Le code choisi, ou `null` pour « tout ». C'est un **code de périmètre**
	 *   (`'bat:3'`, `'parking'`), jamais un identifiant de bâtiment : c'est ce qui
	 *   permet au filtre de proposer des espaces qui n'ont pas de bâtiment. */
	export let choisi: string | null = null;

	/**  Le libellé de la pastille « aucun filtre ». Par défaut celui du périmètre
	 *   racine — « Toute la résidence » —, parce que ne pas filtrer revient
	 *   exactement à prendre le périmètre le plus large. */
	export let libelleTout = '';

	/**  Combien la liste filtrée montre — porté par la pastille retenue, comme
	 *   toute rangée de filtres (`ChoixPastilles.compte`). `null` : rien. */
	export let compte: number | null = null;
	/**  Le libellé « Périmètre » DEVANT la rangée, comme les rangées de
	 *   `ChoixPastilles libelleDevant` — pour la grille des réglages d'une liste
	 *   à gouttière (`ReglagesListe`, standard de la page Affaires). Sans lui, la
	 *   rangée se nomme par `aria-label`, comme avant. */
	export let libelleDevant = false;

	//  Un identifiant par instance, compteur de MODULE (même raison que
	//  `ChoixPastilles` : stable entre le rendu serveur et l'hydratation).
	const idTitre = `filtre-perimetre-${++compteur}`;

	const dispatch = createEventDispatcher<{ changer: string | null }>();

	//  ⚠️ Le magasin est cité EXPRÈS dans `relire` : `perimetreParDefaut()` lit un
	//  état de MODULE posé au chargement de l'arbre. Sans cette dépendance, ce
	//  `$:` ne se réexécute jamais et rend le `null` d'AVANT le chargement — le
	//  même piège que #549 sur le sélecteur.
	$: defaut = relire($perimetresStore, perimetreParDefaut);
	$: niveau1 = perimetresNiveau1($perimetresStore, defaut);
	//  ⚠️ Le magasin est cité ici AUSSI : `perimetreLabelUn` lit le même état de
	//  module que `perimetreParDefaut` juste au-dessus. La ligne précédente
	//  portait déjà `relire`, celle-ci l'avait oublié — et rendait le code brut
	//  quand l'arbre arrivait après le premier rendu (#947).
	$: libelleRacine =
		libelleTout || relire($perimetresStore, () => (defaut ? perimetreLabelUn(defaut) : 'Tout'));

	function choisir(code: string | null) {
		if (choisi === code) return;
		choisi = code;
		dispatch('changer', code);
	}
</script>

{#if niveau1.length > 0}
	<!--  `role="group"` et non `radiogroup` : `Pastille` rend un `<button>`, et un
	      `radiogroup` sans `<input type="radio">` promet une navigation par flèches
	      qui n'existe pas. Mieux vaut un groupe honnête (`ux-patterns`). -->
	<div class:choix-libelle-devant={libelleDevant}>
		{#if libelleDevant}
			<span class="libelle-groupe libelle-devant" id={idTitre}>Périmètre</span>
		{/if}
		<div
			class="filtre-perimetre"
			role="group"
			aria-label={libelleDevant ? undefined : 'Filtrer par périmètre'}
			aria-labelledby={libelleDevant ? idTitre : undefined}
		>
			<Pastille active={choisi === null} {compte} on:click={() => choisir(null)}>
				{libelleRacine}
			</Pastille>
			{#each niveau1 as noeud (noeud.code)}
				<Pastille
					active={choisi === noeud.code}
					{compte}
					icone={noeud.icone ?? ''}
					privatif={noeud.privatif}
					on:click={() => choisir(noeud.code)}
				>
					{noeud.libelle_court || noeud.libelle}
				</Pastille>
			{/each}
		</div>
	</div>
{/if}

<style>
	.filtre-perimetre {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
</style>
