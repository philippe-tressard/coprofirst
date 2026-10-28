<!--
  La liste des documents attachés à un objet, **en lecture** — pastilles
  « TYPE: nom », le rendu des tickets.

  ## Pourquoi ce composant (12/09/2026)

  La même liste était écrite **trois fois** : dans `CarteContrat` (la lecture),
  dans `DocumentsRattaches` (l'édition), et sous une autre forme encore dans
  `FichiersUpload` (les tickets). Les deux premières portaient les mêmes styles en
  ligne au caractère près — une duplication qu'aucun contrôle inter-fichiers ne
  voit, chacune vivant dans son fichier.

  🔴 Signalé à l'écran : *« la section document n'est pas standard ⇒ adopte le
  même rendu que Tickets : je n'accepte pas de différence »*. La pastille est
  cette forme, et elle vit déjà dans `PastilleFichier` (11/09) — ce composant-ci
  ne fait que la poser sur des entités `Document`, avec leur titre.

  ⚠️ **Lecture seulement.** L'édition passe par `FichiersUpload`, qui rend les
  mêmes pastilles ET porte le dépôt. Deux composants pour deux états, une seule
  pastille : c'est R3 du cadre — un objet a plusieurs rendus, pas plusieurs
  formes.
-->
<script lang="ts">
	import PastilleFichier from './PastilleFichier.svelte';
	import { documents as docsApi, type Document } from '#lib/api/index.ts';

	/** Les documents attachés — entités `Document` de l'API. */
	export let documents: Document[] = [];
	/** Le lecteur peut-il retirer une pièce ? La croix n'apparaît que si oui. */
	export let peutSupprimer = false;
	/** Qui sait supprimer — l'écran, qui tient la table. */
	export let onSupprimer: (docId: number) => void = () => {};

	/**  ⚠️ Le `titre` prime sur le nom du fichier, mais l'EXTENSION reste tirée du
	 *   nom : c'est elle qui donne le type de la pastille, et un titre saisi à la
	 *   main ne la porte pas toujours. `PastilleFichier` fait exactement cette
	 *   distinction (`nom` pour le type, `libelle` pour l'affichage). */
</script>

{#if documents?.length}
	<div class="docs-liste">
		{#each documents as doc (doc.id)}
			<a
				class="docs-lien"
				href={docsApi.downloadUrl(doc.id)}
				target="_blank"
				rel="noopener"
				on:click|stopPropagation
			>
				<PastilleFichier
					nom={doc.fichier_nom}
					libelle={doc.titre}
					readonly={!peutSupprimer}
					on:click={(e) => {
						//  🔴 La croix est DANS le lien de téléchargement : sans ces deux
						//  lignes, retirer un document l'ouvrirait dans un onglet au
						//  passage. `PastilleFichier` remonte l'événement natif tel quel,
						//  c'est donc à l'appelant de le borner.
						e.preventDefault();
						e.stopPropagation();
						onSupprimer(doc.id);
					}}
				/>
			</a>
		{/each}
	</div>
{:else}
	<p class="docs-vide">Aucun document.</p>
{/if}

<style>
	/*  La même rangée horizontale que `FichiersUpload` : c'est ce qui fait que
	    lecture et édition se ressemblent, et la valeur vient de la charte. */
	.docs-liste {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	/*  Le lien enveloppe la pastille sans la redessiner : la croix reste un
	    bouton à l'intérieur, et son `stopPropagation` empêche le téléchargement. */
	.docs-lien {
		text-decoration: none;
		color: inherit;
	}
	.docs-vide {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0;
	}
</style>
