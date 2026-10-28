<!--
  Une liste de petites annonces — le `{#each}`, la carte et son formulaire de
  correction, écrits **une seule fois**.

  ## Pourquoi ce composant existe (18/08/2026)

  L'onglet en rend maintenant **deux** : les annonces courantes, et l'Historique
  replié des annonces conclues depuis plus d'un mois. Le premier réflexe est de
  recopier le bloc `{#each}` — une quinzaine de lignes de câblage — sous la
  section repliée.

  🔴 **Ce réflexe est exactement ce que le rang 1 interdit**, et l'histoire du
  projet dit pourquoi : le fil des tickets a été rendu à la main six fois, et les
  copies avaient divergé sur les pièces jointes, la marge et jusqu'au libellé des
  boutons (#431). Deux listes qui se ressemblent aujourd'hui divergent au premier
  correctif appliqué à une seule.

  Ici, la seule différence entre les deux listes est **la liste elle-même** —
  l'atténuation des cartes archivées vient de `annonce.archivee`, que le serveur
  calcule. Rien d'autre ne change, donc rien d'autre ne se paramètre.
-->
<script lang="ts">
	import type { PetiteAnnonce } from '#lib/api/index.ts';
	import AnnonceCard from './AnnonceCard.svelte';

	/** Les annonces à rendre, déjà filtrées et triées par l'appelant. */
	export let liste: PetiteAnnonce[] = [];
	/**  L'annonce dépliée — tenue par l'onglet (un lien profond la désigne).
	 *
	 *   ⚠️ `editAnnonce` N'EST PLUS ICI depuis le 02/09/2026 : l'ONGLET tient
	 *   quelle annonce est en cours de correction, et ne fait que la désigner par
	 *   `editId`. Ce composant est rendu DEUX fois — les annonces courantes et les
	 *   Archives — et y loger cet état en aurait donné deux versions sur la même
	 *   annonce. Le formulaire, lui, vit dans la carte (#787). */
	export let expandedId: number | null = null;
	export let gestionPhotosId: number | null = null;

	export let estCS = false;
	export let estAdmin = false;
	export let currentUserId: number | undefined = undefined;

	export let onToggle: (a: PetiteAnnonce) => void;
	export let onToggleGestion: (a: PetiteAnnonce) => void;
	export let onModifier: (a: PetiteAnnonce) => void;
	export let onUpload: (id: number, f: File) => Promise<string>;
	export let onRemove: (id: number, url: string) => Promise<string[] | void>;
	export let onStatut: (id: number, statut: string) => void;
	export let onSupprimer: (id: number) => void;
	export let onRepondre: (id: number, contenu: string) => Promise<void>;
	export let onSupprimerReponse: (id: number, repId: number) => void;
	export let onSignaler: (cibleType: string, cibleId: number) => void;
	/**  L'identifiant de l'annonce en cours de correction, ou `null` (#787).
	 *
	 *   🔴 Le formulaire s'ouvrait EN BAS DE PAGE : « c'est tout en bas, et on ne
	 *   voit pas ». Il s'ouvre désormais DANS la carte, à la place de son corps —
	 *   ce que la carte d'actualité fait depuis longtemps (`slot="formulaire"`).
	 *   Rien à inventer : le pattern existait, cette carte ne l'avait pas. */
	export let editId: number | null = null;
</script>

{#each liste as annonce (annonce.id)}
	<AnnonceCard
		{annonce}
		expanded={expandedId === annonce.id}
		gestionOuverte={gestionPhotosId === annonce.id}
		{estCS}
		{estAdmin}
		{currentUserId}
		onToggle={() => onToggle(annonce)}
		onToggleGestion={() => onToggleGestion(annonce)}
		onModifier={() => onModifier(annonce)}
		onUpload={(f) => onUpload(annonce.id, f)}
		onRemove={(url) => onRemove(annonce.id, url)}
		onStatut={(statut) => onStatut(annonce.id, statut)}
		onSupprimer={() => onSupprimer(annonce.id)}
		onRepondre={(c) => onRepondre(annonce.id, c)}
		onSupprimerReponse={(rid) => onSupprimerReponse(annonce.id, rid)}
		onSignalerAnnonce={() => onSignaler('annonce', annonce.id)}
		onSignalerReponse={(rid) => onSignaler('reponse', rid)}
		formulaireOuvert={editId === annonce.id}
	>
		<svelte:fragment slot="formulaire">
			<!--  Relayé jusqu'ici : la liste ne sait pas construire le formulaire, elle
			      sait seulement OÙ il va. L'appelant le fournit, comme pour les
			      actualités. -->
			<slot name="formulaire" {annonce} />
		</svelte:fragment>
	</AnnonceCard>
{/each}
