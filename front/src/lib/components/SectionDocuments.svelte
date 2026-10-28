<!--
  **Une section de documents de la page Résidence** — son titre, son bouton
  d'ajout, ses trois états et ses lignes téléchargeables.

  ## Pourquoi ce composant (#522)

  La page Résidence portait **trois fois** la même section, à quarante lignes
  d'intervalle : Plans, Règlement de copropriété, Comptes-rendus d'AG. Même
  en-tête, même bouton « + Ajouter », même `doc-row`, mêmes gestes (télécharger,
  modifier, supprimer). Seuls les **badges** d'une ligne changeaient.

  Le garde-fou de modularité a refusé que la page grossisse en recevant les états
  d'erreur de #522, et il disait vrai : une page de 1 350 lignes qui rend trois
  fois la même chose n'a pas un problème de taille, elle a un problème de
  découpage (#453).

  ## Ce qui varie, et comment

  Le **badge** d'une ligne, par le `slot` nommé `badges` — c'est la seule
  différence réelle entre les trois sections :

  | Section | Badge |
  |---|---|
  | Plans | le bâtiment, ou « Copropriété » |
  | Règlement | aucun |
  | Comptes-rendus d'AG | l'année, la date d'AG, les bâtiments concernés |

  ## La CARTE au standard de la page Affaires (10/10/2026)

  La page Affaires est devenue le standard du site : un document se rend donc en
  `.carte-liste` à gouttière — la date à gauche (`quandDe`), puis ce qui le
  classe (`classe`, la rubrique : plan, règlement, AG), le titre et les actions
  au trait sur la première ligne, la description en aperçu, les pastilles en
  dernière ligne (slot `badges`). C'était une ligne `doc-row` à part, la seule
  forme de liste du site à ne pas passer par `EnteteCarte`.

  La carte ne se DÉPLIE que si elle a quelque chose à montrer de plus : une
  description. Repliée, elle en montre trois lignes (`ApercuCarte`) ; dépliée,
  le texte entier. Sans description, le titre reste un simple texte — une
  fiche qui n'a rien à replier ne propose pas un bouton inerte (`EnteteCarte`).

  ## 🔴 Les styles voyagent avec le balisage

  `.doc-list`, `.doc-row`, `.doc-info`… vivaient dans le `<style>` de la page.
  Svelte scope les styles au composant qui rend l'élément : les y laisser aurait
  livré les lignes **nues** en production — c'est la panne des pastilles de la
  v2.67.11, refaite deux fois depuis. Depuis le passage aux cartes, ce composant
  ne garde que sa section : le conteneur est `.carte-liste` (`normes.css`),
  l'en-tête `EnteteCarte`, la colonne `Gouttiere`, le texte déplié
  `TexteDeplie` — chacun avec ses règles.
-->
<script lang="ts">
	import type { ClasseGouttiere } from '#lib/gouttiere.ts';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import BoutonLien from '#lib/components/BoutonLien.svelte';
	import ApercuCarte from '#lib/components/ApercuCarte.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import LienAction from '#lib/components/LienAction.svelte';
	import TexteDeplie from '#lib/components/TexteDeplie.svelte';
	import ListeDocuments from '#lib/components/ListeDocuments.svelte';
	import { basculer } from '#lib/accordeon.ts';
	import type { Document } from '#lib/api/index.ts';

	/** Le titre affiché, emoji compris — la page reste maîtresse de son vocabulaire. */
	export let titre: string;
	export let documents: Document[] = [];
	/**  Non vide = on n'a PAS pu charger. Distinct de « chargé et vide » : c'est
	 *   toute la raison de ce lot (#522). */
	export let erreur = '';
	export let messageVide = 'Aucun document ajouté.';
	/** Le lecteur peut-il ajouter, corriger et supprimer ? (conseil syndical) */
	export let peutModifier = false;
	/** L'URL de téléchargement — construite par la page, qui connaît son client API. */
	export let urlTelechargement: (doc: Document) => string;
	export let onAjouter: () => void;
	export let onModifier: (doc: Document) => void;
	export let onSupprimer: (id: number) => void;
	/**  L'instant qui SITUE un document (ISO), rendu par la gouttière ; rien = la
	 *   gouttière ne porte que le classement. La date de publication pour un plan,
	 *   celle de l'assemblée pour un compte-rendu : c'est l'appelant qui le sait. */
	export let quandDe: (doc: Document) => string | null | undefined = () => null;
	/**  Ce qui classe les documents de la section — la rubrique —, ou rien. Le type
	 *   est celui de `Gouttiere`, lu et non recopié. */
	export let classe: ClasseGouttiere | null = null;
	/**  Les annexes d'un document (migration 0278) : elles se lisent carte
	 *   dépliée, et une carte qui en porte se déplie même sans description. */
	export let annexesDe: (doc: Document) => Document[] = () => [];

	//  UNE description dépliée à la fois (`#lib/accordeon`).
	let deplie: number | null = null;
</script>

<section class="section-documents">
	<div class="section-header">
		<!--  Texte, jamais `{@html}` : Svelte décode déjà les entités HTML dans
		      une valeur d'attribut, donc `titre="&#x1F5FA;️ Plans"` arrive ici en
		      emoji. Passer par `{@html}` aurait exigé un assainisseur pour un
		      titre que la page écrit elle-même — une exception de plus à la
		      règle XSS, pour rien. -->
		<h2 class="section-title">{titre}</h2>
		{#if peutModifier}
			<button class="btn btn-sm" on:click={onAjouter}>+ Ajouter</button>
		{/if}
	</div>

	<!--  🔴 LE FORMULAIRE EST DANS SA SECTION (#852, 08/09/2026).
	      Signalé à l'écran : *« l'édition est en bas de page et non dans la
	      section sélectionnée […] quand on édite on ne se retrouve pas en bas de
	      page mais à l'endroit où on édite (faire de même que la référence
	      Actualité ou ticket) »*.

	      Les sept formulaires de Résidence étaient rendus à la FIN du fichier,
	      après toutes les sections. Cliquer « + Ajouter » dans « Plans » ouvrait
	      donc une boîte quatre cents pixels plus bas, sous les diagnostics —
	      hors de l'écran, et sans rapport visible avec le geste qu'on venait de
	      faire.

	      ⚠️ Ce n'est pas un défaut de style, c'est un défaut de PLACE : le
	      balisage était juste, et posé au mauvais endroit du document. Aucun
	      contrôle ne peut voir ça — `lint:formulaires` vérifie le cadre, pas sa
	      position dans la page. -->
	<slot name="formulaire" />

	<EtatListe compact {erreur} vide={documents.length === 0} {messageVide}>
		{#each documents as doc (doc.id)}
			{@const pieces = annexesDe(doc)}
			{@const depliable = !!doc.description || pieces.length > 0}
			<!--  Repliée, toute la carte déplie ; dépliée, seul le titre replie
			      (`ux-patterns` §3). L'`id` est la cible des liens profonds
			      (`#doc-<id>`, fil d'activité et 🔗). -->
			<CarteListe
				id="doc-{doc.id}"
				quand={quandDe(doc)}
				{classe}
				expanded={deplie === doc.id}
				onDeplier={depliable ? () => (deplie = doc.id) : null}
			>
				<EnteteCarte
					titre={doc.titre}
					basculable={depliable}
					on:toggle={() => (deplie = basculer(deplie, doc.id))}
				>
					<svelte:fragment slot="actions">
						<BoutonLien ancre="doc-{doc.id}" quoi="le document" />
						<LienAction
							href={urlTelechargement(doc)}
							icone="arrow-down"
							mot="Télécharger"
							titre="Télécharger"
							libelle="Télécharger le document"
							telecharger
						/>
						{#if peutModifier}
							<button
								class="btn-icon-edit"
								aria-label="Modifier"
								title="Modifier"
								on:click|stopPropagation={() => onModifier(doc)}
								><IconeAction icone="pencil" /></button
							>
							<button
								class="btn-icon-danger"
								aria-label="Supprimer"
								title="Supprimer"
								on:click|stopPropagation={() => onSupprimer(doc.id)}
								><IconeAction icone="trash-2" /></button
							>
						{/if}
					</svelte:fragment>
					<!--  La DESCRIPTION (#852) : le titre NOMME le document, elle dit ce
					      qu'il couvre. Trois lignes en aperçu, comme toute carte
					      (`ux-patterns` §7) — le texte entier quand on déplie. -->
					<svelte:fragment slot="apercu">
						{#if doc.description && deplie !== doc.id}
							<ApercuCarte contenu={doc.description} dansLigne />
						{/if}
					</svelte:fragment>
					<svelte:fragment slot="tags">
						<slot name="badges" {doc} />
					</svelte:fragment>
				</EnteteCarte>
				{#if deplie === doc.id}
					<!--  Le corps ne replie pas la carte : on lit, on sélectionne. -->
					<div class="carte-corps" role="presentation" on:click|stopPropagation>
						{#if doc.description}<TexteDeplie contenu={doc.description} />{/if}
						{#if pieces.length}<ListeDocuments documents={pieces} />{/if}
					</div>
				{/if}
			</CarteListe>
		{/each}
	</EtatListe>
</section>

<style>
	.section-documents {
		margin-bottom: 2.5rem;
	}
	/*  Seul `margin: 0` differe : la charte pose `margin-bottom` (#607, 28/08/2026). */
	.section-title {
		margin: 0;
	}
</style>
