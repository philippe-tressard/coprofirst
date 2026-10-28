<!--
  La PASTILLE d'un fichier joint — « TYPE: nom », et la croix qui le retire.

  ## Pourquoi ce composant (11/09/2026)

  Deux rendus coexistaient pour la même chose, et l'utilisateur a désigné le bon :

  | Écran | Ce qu'il rendait |
  |---|---|
  | Tickets (`FichiersUpload`) | des pastilles **horizontales**, une croix rouge |
  | Actualités (`DocumentsPublication`) | une **liste verticale**, un 🗑️ par ligne |

  *« Adopter celui de Tickets, qui est très beau »* — et surtout : le même objet
  ne peut pas avoir deux formes selon l'écran qui le montre (R3 du cadre). La
  pastille vit donc ici, et les deux appelants la reçoivent.

  ## Le format « TYPE: nom »

  Demandé le même jour : *« PDF: MON NOM »*. Le type est l'information la plus
  utile d'une liste de pièces jointes — on cherche « le PDF », pas « le
  cinquième ». Il se calcule dans `#lib/fichiers` (`typeFichier`), jamais ici :
  quatre rendus l'affichent, un format recopié aurait divergé au premier
  ajustement.

  ⚠️ L'extension ne s'affiche PAS dans le nom : elle est déjà dite par le type,
  et « PDF: contrat.pdf » allonge la pastille pour ne rien apprendre.
-->
<script lang="ts">
	import PastilleRetirable from '#lib/components/PastilleRetirable.svelte';
	import { typeFichier, nomSansExtension } from '#lib/fichiers.ts';

	/**  Le nom du fichier, ou son URL — `typeFichier` accepte les deux. */
	export let nom: string;
	/**  Un nom d'affichage qui prime sur celui du fichier (le `titre` d'un
	 *   `Document`, par exemple). L'extension reste tirée de `nom`. */
	export let libelle: string | null = null;
	export let readonly = false;

	$: type = typeFichier(nom);
	$: affiche = libelle?.trim() || nomSansExtension(nom);
</script>

<!--  La forme vit dans `PastilleRetirable` (#1342) : la section « Affaires
      liées » porte la même. Ici ne reste que ce qui est propre à un FICHIER. -->
<PastilleRetirable
	prefixe={type}
	nom={affiche}
	{readonly}
	aideRetirer="Retirer ce document"
	on:click
/>
