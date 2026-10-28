<!--
  Un journal : des lignes, chacune avec son verdict, sa date et ce qu'elle dit.

  Né le 28/09/2026 (#1447) de `HistoriqueEnvoisWhatsApp`, quand la relève des
  réponses par courriel a demandé le même rendu — un message, son issue, sa
  raison. Le recopier aurait fait deux journaux qui divergent au premier
  changement ; les deux écrans ne font plus que DIRE ce qu'ils montrent
  (`EntreeJournal`), et c'est ici qu'on le rend.

  Le verdict est une pastille `.badge-*` de la charte — son contraste est
  mesuré par `lint:charte-valeurs` — et non plus une teinte écrite en ligne.

  `pliable` (05/10/2026, Espace CS › Courriels) : chaque ligne devient une
  pliure — objet, verdict et date en tête ; l'expéditeur, le motif et le lien
  dessous. C'est un `<details>` natif : le clavier, le lecteur d'écran et
  « un seul ouvert à la fois » (`unSeulDetailsOuvert`, posé par le layout) sont
  déjà là. Le même balisage sert les deux formes — une seule écriture des
  pastilles et du corps, jamais une seconde liste.
-->
<script context="module" lang="ts">
	export type TonVerdict = 'succes' | 'info' | 'attention' | 'danger' | 'neutre';

	/** Une ligne de journal, telle que l'écran appelant la décrit. */
	export interface EntreeJournal {
		/** Clé du `{#each}` — l'identifiant de la ligne côté serveur. */
		cle: number;
		titre: string;
		/** Sous le titre, en gris : qui, d'où. */
		sousTitre?: string;
		verdict: string;
		/** La gravité, jamais le nom : elle choisit la pastille de la charte. */
		ton: TonVerdict;
		date: string | null;
		texte: string;
		/** Une mise en garde, en rouge sous le texte. */
		alerte?: string;
		lien?: { href: string; libelle: string };
	}
</script>

<script lang="ts">
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { fmtDatetimeShort } from '#lib/date.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	export let entrees: EntreeJournal[] = [];
	/** Non vide = le journal n'a pas pu être lu : il ne se dit pas « vide » (#1459). */
	export let erreur = '';
	export let vide = 'Rien à afficher.';
	export let recharger: () => unknown = () => {};
	/** Ce que le bouton de rafraîchissement annonce aux lecteurs d'écran. */
	export let libelleRecharger = 'Rafraîchir';
	/** Une pliure par ligne : seul le titre, le verdict et la date restent visibles. */
	export let pliable = false;
</script>

<div class="largeur-saisie">
	<div class="jv-outils">
		<button class="btn btn-outline jv-rafraichir" on:click={recharger} aria-label={libelleRecharger}
			><IconeAction icone="refresh-cw" /></button
		>
	</div>
	{#if erreur}
		<EtatListe compact {erreur} />
	{:else if entrees.length === 0}
		<p class="jv-vide">{vide}</p>
	{:else}
		<ul class="jv-liste">
			{#each entrees as e (e.cle)}
				<li>
					<svelte:element this={pliable ? 'details' : 'div'} class="jv-ligne">
						<svelte:element this={pliable ? 'summary' : 'div'} class="jv-tete">
							<span class="jv-titre">{e.titre}</span>
							<span class="jv-meta">
								<span
									class="badge"
									class:badge-green={e.ton === 'succes'}
									class:badge-blue={e.ton === 'info'}
									class:badge-orange={e.ton === 'attention'}
									class:badge-red={e.ton === 'danger'}
									class:badge-gray={e.ton === 'neutre'}>{e.verdict}</span
								>
								{#if e.date}<time class="jv-date" datetime={e.date}>{fmtDatetimeShort(e.date)}</time
									>{/if}
								{#if pliable}<span class="jv-chevron" aria-hidden="true">&#x203A;</span>{/if}
							</span>
						</svelte:element>
						{#if e.sousTitre}<p class="jv-sous-titre">{e.sousTitre}</p>{/if}
						<p class="jv-texte">{e.texte}</p>
						{#if e.alerte}<p class="jv-alerte">&#x26A0;&#xFE0F; {e.alerte}</p>{/if}
						{#if e.lien}<a class="jv-lien" href={e.lien.href}>{e.lien.libelle}</a>{/if}
					</svelte:element>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.jv-outils {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.jv-rafraichir {
		font-size: var(--fs-2xs);
		padding: 0.1rem 0.4rem;
	}
	.jv-vide {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.jv-liste {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.jv-ligne {
		border: 1px solid var(--color-border);
		border-radius: 6px;
		padding: 0.5rem 0.75rem;
		font-size: var(--fs-sm);
		background: var(--color-surface);
		/*  Une adresse ou un objet sans espace ne doit pas élargir la page au
		    téléphone : il se coupe plutôt que de pousser le cadre. */
		overflow-wrap: anywhere;
	}
	.jv-tete {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.25rem 0.5rem;
		margin-bottom: 0.25rem;
	}
	/*  Une pliure : la tête est le bouton. Plus de marque native — le chevron
	    dit « ça se déplie », et il se retourne à l'ouverture. */
	summary.jv-tete {
		cursor: pointer;
		list-style: none;
		margin-bottom: 0;
	}
	summary.jv-tete::-webkit-details-marker {
		display: none;
	}
	/*  `[open]` est posé par le navigateur sur un élément dont la balise se choisit
	    à l'exécution (`svelte:element`) : Svelte ne peut pas le voir, d'où le
	    `:global` — borné à CETTE liste. */
	.jv-liste :global(.jv-ligne[open]) > :global(.jv-tete) {
		margin-bottom: 0.25rem;
	}
	.jv-chevron {
		display: inline-block;
		color: var(--color-text-muted);
		transition: transform var(--duree-geste) var(--ease-out);
	}
	.jv-liste :global(.jv-ligne[open]) :global(.jv-chevron) {
		transform: rotate(90deg);
	}
	/*  Au doigt, la tête fait 44 px (standards/11 §10). */
	@media (pointer: coarse) {
		summary.jv-tete {
			min-height: 2.75rem;
		}
	}
	.jv-titre {
		font-weight: 600;
		min-width: 0;
	}
	.jv-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-shrink: 0;
	}
	.jv-date {
		color: var(--color-text-muted);
		font-size: var(--fs-xs);
		font-variant-numeric: tabular-nums;
	}
	.jv-sous-titre {
		margin: 0 0 0.2rem;
		color: var(--color-text-muted);
		font-size: var(--fs-xs);
	}
	.jv-texte {
		margin: 0;
		white-space: pre-wrap;
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.jv-alerte {
		margin: 0.2rem 0 0;
		color: var(--color-danger);
		font-size: var(--fs-xs);
	}
	.jv-lien {
		/*  Une cible qu'on touche au pouce : la hauteur vient du cadre, pas du
		    texte en petit corps (standards/11 §10). */
		display: inline-flex;
		align-items: center;
		min-height: 1.75rem;
		margin-top: 0.1rem;
		font-size: var(--fs-xs);
	}
</style>
