<!--
  SectionTitre.svelte — la section 1 d'un formulaire : le titre de l'objet.

  ## Pourquoi (23/09/2026, signalé à l'écran)

  Demandé : *« normalise les polices / styles / positionnement des titres des
  sections, qui ne semblent pas normalisés »*, capture à l'appui — TITRE ne
  ressemblait pas à CATÉGORIE, SUIVI, QUAND, PÉRIMÈTRE juste en dessous.

  Mesuré : les sections nommées passent par `SectionFormulaire` (`.section-titre` :
  0,72 rem, gras, capitales espacées), et la section 1 écrivait à la place un
  **libellé de champ** (`.field label`, 0,875 rem, graisse moyenne). Deux règles
  pour un même rôle. Le bloc était recopié dans **sept** formulaires — affaire,
  actualité, événement, sondage, petite annonce, contrat, prestataire —, et
  aucun n'appliquait la règle de `SectionFormulaire` : *une section à un seul
  champ, le titre EST le libellé*.

  Il n'en reste qu'une écriture : l'intitulé vient de `SectionFormulaire`
  (`pour` relie le libellé au champ), l'astérisque suit son état, et le champ ne
  porte plus de `<label>` à lui.
-->
<script lang="ts">
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';

	/** `id` du champ — le titre de section s'y relie (`for`). */
	export let id: string;
	export let valeur = '';
	/** « Titre » par défaut, lu dans la table ; « Nom », « Question » ailleurs. */
	export let libelle: string = SECTIONS_LIBELLE.titre;
	export let placeholder = '';
	export let maxlength: number | undefined = undefined;
</script>

<SectionFormulaire premiere titre={libelle} requis rempli={!!valeur.trim()} pour={id}>
	<div class="field champ-large">
		<input {id} type="text" bind:value={valeur} required {placeholder} {maxlength} />
	</div>
</SectionFormulaire>
