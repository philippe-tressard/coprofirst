<!--
  Le corps déplié d'une AFFAIRE au fil : trois rubriques, chacune avec SES pièces
  (maquette A, arbitrée à l'écran le 15/10/2026).

  Signalé sur TK-109008 : la carte d'une affaire résolue montrait le texte de la
  demande et, dessous, les photos de la clôture — rien ne disait d'où elles
  venaient, et le texte de clôture manquait. L'ordre est celui du fil, qui date
  du dernier fait (#531) :

  1. **Dernière mise à jour** — ce qui vient d'arriver : qui, quoi, ses pièces ;
  2. **Synthèse** — seulement si le serveur l'envoie (affaire close, synthèse
     lisible : validée, ou brouillon pour le conseil) ; elle enrichit la carte
     sans la dater, la carte ne remonte pas à sa validation (arbitré le 15/10) ;
  3. **Demande initiale** — le contexte, PLIÉ derrière un `<details>` : un seul
     ouvert à la fois sur la page (`unSeulDetailsOuvert`, `$lib/accordeon`).

  Une affaire sans suite (carte « nouveau ») n'a que sa demande, dépliée : elle
  EST la nouvelle. La donnée décide — `evol_pieces`, posé par la seule carte
  d'une suite (`flux/tickets._derniere_suite`) —, jamais une liste de types.
-->
<script lang="ts">
	import type { FluxItem } from '$lib/api';
	import { fmtDate } from '$lib/date';
	import PiecesJointes from './PiecesJointes.svelte';

	export let item: FluxItem;

	type Pieces = { photos_urls?: string[]; fichiers_urls?: string[] };
	type Demande = Pieces & { le?: string };
	type Synthese = { texte?: string; validee?: boolean };

	const toutes = (p: Pieces | undefined) => [
		...(p?.photos_urls ?? []),
		...(p?.fichiers_urls ?? []),
	];

	$: suite = item.meta?.evol_pieces as Pieces | undefined;
	$: demande = item.meta?.demande as Demande | undefined;
	$: synthese = item.meta?.synthese as Synthese | undefined;
	$: piecesSuite = toutes(suite);
	$: piecesDemande = toutes(demande);
	$: texteDemande = (item.meta?.description as string | undefined) ?? '';
	//  Ce qui suit l'intitulé, séparé par « · » — composé ici : écrit dans le
	//  balisage, chaque `{#if}` mangeait l'espace qui le précédait.
	const suivi = (...parts: (string | null | undefined | false)[]) =>
		parts
			.filter(Boolean)
			.map((p) => ` · ${p}`)
			.join('');
	$: suiviSuite = suivi(item.meta?.evol_auteur as string | undefined, item.detail);
	$: suiviDemande = suivi(
		demande?.le && fmtDate(demande.le),
		piecesDemande.length > 0 && `📎 ${piecesDemande.length}`,
	);
</script>

{#if suite}
	<section class="rubrique rubrique-suite" aria-label="Dernière mise à jour">
		<p class="rubrique-titre">
			<span aria-hidden="true">{item.icon}</span>
			<strong>Dernière mise à jour</strong>{suiviSuite}
		</p>
		{#if item.meta?.evol_contenu}<p class="rubrique-texte">{item.meta.evol_contenu}</p>{/if}
		{#if piecesSuite.length}<PiecesJointes urls={piecesSuite} format="grand" />{/if}
	</section>
{/if}

{#if synthese?.texte}
	<section class="rubrique rubrique-synthese" aria-label="Synthèse">
		<p class="rubrique-titre">
			<span aria-hidden="true">✨</span>
			<strong>Synthèse</strong>{suivi(
				synthese.validee ? 'validée par le conseil' : 'brouillon à valider',
			)}
		</p>
		<p class="rubrique-texte">{synthese.texte}</p>
	</section>
{/if}

{#if suite}
	{#if texteDemande || piecesDemande.length}
		<details class="rubrique-demande">
			<summary>
				<strong>Demande initiale</strong>{suiviDemande}
			</summary>
			{#if texteDemande}<p class="rubrique-texte">{texteDemande}</p>{/if}
			{#if piecesDemande.length}<PiecesJointes urls={piecesDemande} format="grand" />{/if}
		</details>
	{/if}
{:else}
	{#if texteDemande}<p class="rubrique-texte">{texteDemande}</p>{/if}
	{#if piecesDemande.length}<PiecesJointes urls={piecesDemande} format="grand" />{/if}
{/if}

<style>
	.rubrique {
		margin: 0.6rem 0;
		padding: 0.5rem 0.75rem;
		border-left: 3px solid;
		font-size: var(--fs-md);
	}
	.rubrique-suite {
		background: var(--color-primary-light);
		border-left-color: var(--color-primary);
	}
	.rubrique-synthese {
		background: var(--color-success-fond);
		border-left-color: var(--color-success-bordure);
		color: var(--color-success-texte);
	}
	.rubrique-titre {
		margin: 0 0 0.25rem;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.rubrique-synthese .rubrique-titre {
		color: inherit;
	}
	.rubrique-titre strong {
		color: var(--color-text);
		font-weight: 600;
	}
	.rubrique-synthese .rubrique-titre strong {
		color: inherit;
	}
	.rubrique-texte {
		margin: 0 0 0.4rem;
		font-size: var(--fs-md);
		line-height: 1.5;
	}
	.rubrique-synthese .rubrique-texte {
		color: var(--color-text);
	}
	/*  Le contexte, en retrait : un filet neutre, le texte gris. Pas de fond —
	    il ne concurrence pas la mise à jour. */
	.rubrique-demande {
		margin: 0.6rem 0;
		padding: 0.25rem 0.75rem;
		border-left: 3px solid var(--color-border);
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	.rubrique-demande summary {
		cursor: pointer;
		font-size: var(--fs-xs);
		/*  Pas de `flex` : il retire le marqueur ▸ natif, le seul signe que la
		    ligne se déplie. La hauteur vient du rembourrage (cible tactile). */
		padding: 0.5rem 0;
	}
	.rubrique-demande summary strong {
		color: var(--color-text);
		font-weight: 600;
	}
</style>
