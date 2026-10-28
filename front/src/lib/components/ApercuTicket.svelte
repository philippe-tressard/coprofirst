<!--
  ApercuTicket.svelte — ce qu'une carte de TICKET repliée montre, écrit une fois.

  ## Pourquoi ce composant (18/08/2026)

  Trois écrans rendent l'aperçu replié d'un ticket : le fil et les archives
  (`CarteTicket`), et **deux fois** l'espace CS, qui recompose ses propres cartes
  au lieu d'utiliser `CarteTicket` (dette suivie à part, #453). Les trois
  appelaient `ApercuCarte` à la main avec la même liste d'arguments — et les trois
  ont **oublié les documents** de la même façon : un ticket dont la seule pièce
  jointe était un devis PDF ne le signalait nulle part, alors qu'un ticket
  illustré montrait sa photo d'un coup d'œil.

  🔴 **Le garde-fou de modularité a dit où était le problème.** Ajouter l'argument
  manquant faisait grossir `espace-cs/+page.svelte` — 3 341 lignes, très au-dessus
  du plafond de rang 1 —, et le refus ne portait pas sur la taille : il disait que
  cette règle n'a rien à faire dans un écran. Trois réponses possibles, une seule
  juste ici — *remonter la règle d'un cran*, parce que « un aperçu de ticket montre
  sa description, ses photos ET ses documents » est une phrase sur le **ticket**,
  pas sur l'espace CS. Les deux écrans y perdent des lignes.

  ⚠️ Ce composant ne remplace pas le découpage de `CarteTicket` dans l'espace CS,
  qui reste à faire : il enlève seulement à cet écran une décision qui ne lui
  appartenait pas.
-->
<script lang="ts">
	import type { Ticket } from '#lib/api/index.ts';
	import ApercuCarte from './ApercuCarte.svelte';
	import { separerFichiers } from '#lib/fichiers.ts';

	/** Le ticket, tel que l'API le renvoie (`apercu_pieces` compris). */
	export let ticket: Ticket;
	/**  L'aperçu est rendu DANS l'en-tête de la carte (`slot="apercu"`), qui porte
	 *   déjà son retrait : sans cela, le texte serait décalé de deux fois la marge.
	 *   Relayé et non redécidé — c'est `ApercuCarte` qui sait ce que ça change. */
	export let dansLigne = false;

	//  `separerFichiers` refait le tri photos / documents : `apercu_pieces` est une
	//  liste unique, et la vignette pose `photos[0]` dans un `<img>` — les verser
	//  ensemble ferait sortir un devis PDF en image cassée.
	$: pieces = separerFichiers(ticket.apercu_pieces ?? []);
</script>

<!--  Les documents sont passés, à la différence des ACTUALITÉS : ceux d'un ticket
      voyagent dans la charge utile (`fichiers_urls`), là où ceux d'une
      publication sont des entités `Document` chargées au dépliage — les compter
      en liste y coûterait une requête par carte pour afficher un trombone. -->
<!--  🔴 `apercu_pieces` REMPLACE les deux listes du ticket (#464, 18/08/2026) :
      c'est le serveur qui décide quoi montrer, en repliant sur l'entrée
      d'Historique la plus récente quand le ticket lui-même ne porte rien.

      Un ticket dont les photos arrivent par le suivi — « voici ce qu'a constaté
      le plombier » — n'affichait aucune vignette, là où le même dossier saisi
      avec ses photos dès l'ouverture en affichait une. Deux tickets, même contenu
      visible, deux apparences dans la liste.

      ⚠️ Le repli se calcule côté SERVEUR et non ici : la page des tickets charge ses évolutions
      à la demande, et les réclamer en liste coûterait une requête par carte.
      Le serveur, lui, ne transporte que les URLs affichées.

      ⚠️ Le tri photos / documents se fait dans le `<script>` : `{@const}` n'est
      permis qu'à l'intérieur d'un bloc, jamais à la racine d'un composant. -->
<ApercuCarte
	contenu={ticket.description}
	photos={pieces.photos}
	fichiers={pieces.documents}
	{dansLigne}
/>
