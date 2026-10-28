<!--
  ModaleFusionAffaires.svelte — fusionner les affaires liées DEPUIS la correction
  d'une affaire (#2173, 23/10/2026).

  Le geste est celui du Suivi des affaires (#2083), et il n'est PAS récrit : la
  fenêtre monte `FusionAffaires` tel quel — l'assistant propose titre et
  description, le conseil relit, la plus ancienne absorbe et reste ouverte, même
  route, mêmes refus. Elle n'ajoute que ce que la correction rend nécessaire :

  - que la fusion s'enregistre seule : ce que la correction n'a pas enregistré
    est abandonné, le serveur ayant réécrit titre et description.

  Une liée que la fusion ferait lire à qui ne la lisait pas n'est plus écartée
  ici : `FusionAffaires` vérifie qui lirait quoi, montre l'écart et propose de
  concilier (inverser, restreindre, élargir — confirmé par les noms).

  ## Pourquoi une fenêtre, et pas la section elle-même

  La section « Affaires liées » vit dans le `<form>` de la correction, et
  `FusionAffaires` est un `<form>` : deux formulaires imbriqués sont invalides
  (le second `submit` enverrait le premier). La fenêtre est montée hors de la
  page (`modaleImperative`). C'est la forme que `ux-patterns` §14 bis admet pour
  une saisie qui ACCOMPAGNE un geste — déclarée dans `lint:formulaires`.

  Le fond ne ferme pas — `Modale` le déduit du champ qu'elle contient : un titre
  et une description relus se perdraient d'un clic à côté. `Échap` et
  « Annuler » restent.

  ⚠️ S'emploie par `fusionnerLiees()` (`$lib/fusion-affaires`), jamais
  directement — comme `DialogueFusion` par `demanderFusion()`.
-->
<script lang="ts">
	import Modale from './Modale.svelte';
	import FusionAffaires from './reporting/FusionAffaires.svelte';
	import type { AffaireAFusionner, FusionFaite } from '$lib/fusion-affaires';

	/** Le groupe, la plus ancienne en tête : elle absorbe. */
	export let affaires: AffaireAFusionner[];
	/** `null` : on renonce ; sinon ce que la fusion a fait. */
	export let onReponse: (r: FusionFaite | null) => void;
</script>

<Modale titre="Fusionner les affaires liées" on:fermer={() => onReponse(null)}>
	<div class="modal-body">
		<p class="aide">
			La fusion s’enregistre seule : ce que vous n’avez pas enregistré dans la correction est
			abandonné.
		</p>
		<FusionAffaires {affaires} onFusionne={(r) => onReponse(r)} onAnnule={() => onReponse(null)} />
	</div>
</Modale>
