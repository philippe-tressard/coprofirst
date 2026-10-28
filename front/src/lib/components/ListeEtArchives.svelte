<!--
  **Une liste et ses Archives** — le même rendu, appelé deux fois, écrit une fois.

  ## Pourquoi ce composant (#803, 06/09/2026)

  Les trois onglets de la Communauté portaient exactement le même motif :

      $: courants = liste.filter((x) => !x.archivee);
      $: archives = liste.filter((x) => x.archivee);
      {#if courants.length === 0 && archives.length}  …aucun en cours…  {/if}
      <ListeXxx items={courants} …vingt props… />
      {#if archives.length}
        <SectionRepliee titre={TITRE_ARCHIVES} compte={archives.length}>
          <ListeXxx items={archives} …LES MÊMES vingt props… />
        </SectionRepliee>
      {/if}

  🔴 **Et les deux appels de liste étaient recopiés à l'identique** : dix-neuf
  propriétés pour les annonces, douze pour les idées, chacune écrite deux fois,
  slot `formulaire` et commentaire compris. C'est la duplication que
  `ListeAnnonces` et `ListeIdees` avaient justement été extraits pour supprimer —
  leurs en-têtes disent tous deux qu'un `{#each}` recopié diverge au premier
  correctif appliqué d'un seul côté. L'extraction avait déplacé le problème d'un
  cran : ce n'était plus la carte qui était en double, c'était son câblage.

  ⚠️ **Les trois copies avaient déjà divergé**, et de la façon la plus discrète —
  la condition du bloc « aucun en cours » : `courantes.length === 0` seul pour les
  annonces, `&& archivees.length > 0` pour les idées et les sondages. Les trois
  donnent le même résultat *aujourd'hui*, parce qu'`EtatListe` ne rend pas son
  contenu quand tout est vide. Aucune n'est fausse, et c'est bien le problème :
  rien ne dit laquelle fait foi.

  ## Comment il évite de connaître les objets

  Il n'en connaît qu'une chose : le champ **`archivee`**, que le serveur calcule
  (`app/utils/archivage.py`). Le contenu, lui, vient du slot — **rendu deux fois**,
  avec `items` pour seule différence. L'appelant écrit donc son appel de liste
  **une seule fois** :

      <ListeEtArchives liste={idees} titreVideCourant="Aucune idée en cours" …>
        <svelte:fragment let:items>
          <ListeIdees idees={items} …ses props… />
        </svelte:fragment>
      </ListeEtArchives>

  🔴 **Ne PAS recalculer `archivee` ici** ni ailleurs dans un écran : le délai se
  règle en administration, et une seconde règle côté client trancherait autrement
  le jour où il change. C'est le bug du 17/07/2026 sur les actualités — un élément
  visible dans une vue et pas dans l'autre.

  ## Ce qu'il ne fait pas

  Il ne rend ni le chargement, ni l'échec, ni le vide **global** : c'est
  `EtatListe` qui les porte, et il l'enveloppe (l'échec avant le vide, `standards/04`).
  Ce composant traite le cas d'après — « chargé, non vide, mais plus rien en cours ».

  Il ne groupe pas non plus par année : c'est `ArchivesParAnnee`, et c'est une
  autre question. Les trois onglets de la Communauté rendent leurs archives avec
  les **mêmes cartes** que les courants, simplement atténuées.
-->
<script lang="ts" generics="T extends { archivee?: boolean }">
	import SectionRepliee from '#lib/components/SectionRepliee.svelte';
	import { TITRE_ARCHIVES, enCours } from '#lib/archives.ts';

	/** La liste complète, courants et archivés mêlés, déjà triée par l'appelant. */
	export let liste: T[] = [];
	/**  Le titre du bloc « il n'y a plus rien en cours, mais il y a des archives ».
	 *   Vide = pas de bloc : tous les écrans n'ont pas cette nuance à dire. */
	export let titreVideCourant = '';
	/**  ⚠️ Ne CITE PAS le délai d'archivage. Il vaut 30 jours par défaut mais se
	 *   règle en administration : l'écrire en dur ferait mentir l'écran au premier
	 *   ajustement. Formulation tranchée le 18/08/2026 sur les annonces. */
	export let messageVideCourant = '';

	$: courants = enCours(liste);
	$: archives = (liste ?? []).filter((x) => x.archivee);
</script>

{#if titreVideCourant && courants.length === 0 && archives.length > 0}
	<div class="empty-state">
		<h3>{titreVideCourant}</h3>
		{#if messageVideCourant}<p>{messageVideCourant}</p>{/if}
	</div>
{/if}

<slot items={courants} />

<!--  Le bandeau vient de `SectionRepliee` et son intitulé de `#lib/archives` : il
      était en dur dans cinq écrans (#516, point 4). -->
{#if archives.length}
	<SectionRepliee titre={TITRE_ARCHIVES} compte={archives.length}>
		<slot items={archives} />
	</SectionRepliee>
{/if}
