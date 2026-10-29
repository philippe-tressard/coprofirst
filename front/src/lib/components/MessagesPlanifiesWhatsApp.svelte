<!--
  Les messages WhatsApp planifiés — leur liste éditable, un par carte.

  Extrait de `OngletWhatsApp.svelte` le 28/09/2026 (#1329) : l'onglet était
  entièrement composé d'attributs `style`, quarante, et n'avait aucune feuille.
  Le bloc part avec ses règles, à l'identique : même rendu, mais des styles qui
  se lisent, se réemploient et se surchargent. La section (`SectionFormulaire`)
  reste dans l'onglet, qui en tient l'ordre.

  Les messages sont des objets PARTAGÉS avec l'onglet : les cases et les champs
  les modifient en place, et `enregistrer` reçoit l'objet tel qu'il est saisi.
-->
<script lang="ts">
	import type { MessagePlanifieWhatsApp } from '#lib/api/index.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	export let messages: MessagePlanifieWhatsApp[] = [];
	/** Non vide = la liste n'a pas pu être lue : elle ne se dit pas « vide » (#1459). */
	export let erreur = '';
	/** Enregistrement en cours, par identifiant de message. */
	export let enregistrement: Record<number, boolean> = {};
	export let enregistrer: (m: MessagePlanifieWhatsApp) => unknown = () => {};

	const REGLES: Record<string, string> = {
		'3eme_samedi': 'Vendredi avant le 3ᵉ samedi',
		'4eme_samedi': 'Vendredi avant le 4ᵉ samedi',
	};
</script>

<div class="largeur-saisie">
	<p class="wa-aide">
		&#x1F4A1; Markdown WhatsApp : <strong>*gras*</strong> | <em>_italique_</em> | <s>~barré~</s> | Sauts
		de ligne (Enter)
	</p>
	{#if erreur}
		<EtatListe compact {erreur} />
	{:else if messages.length === 0}
		<p class="wa-vide">Aucun message planifié.</p>
	{/if}
	{#each messages as item (item.id)}
		<div class="wa-message">
			<div class="wa-message-tete">
				<input type="checkbox" bind:checked={item.enabled} class="wa-case" />
				<div class="field champ-en-ligne wa-titre">
					<input
						type="text"
						bind:value={item.label}
						class="wa-titre-champ"
						placeholder="Titre du message"
					/>
				</div>
				<span class="wa-regle">{REGLES[item.cron_rule] ?? item.cron_rule}</span>
			</div>
			<div class="field champ-en-ligne">
				<textarea
					bind:value={item.message}
					rows="4"
					class="wa-contenu"
					placeholder="Contenu du message (markdown WhatsApp autorisé)"></textarea>
			</div>
			<div class="wa-apercu">
				{item.message || '— Aperçu du message'}
			</div>
			<div class="form-actions">
				<button
					class="btn btn-primary"
					on:click={() => enregistrer(item)}
					disabled={enregistrement[item.id]}
				>
					{enregistrement[item.id] ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</div>
	{/each}
</div>

<style>
	.wa-aide {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-bottom: 1rem;
		line-height: 1.5;
	}
	.wa-vide {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.wa-message {
		border: 1px solid var(--color-border);
		border-radius: 8px;
		padding: 0.75rem;
		margin-bottom: 0.75rem;
		background: var(--color-surface);
	}
	.wa-message-tete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.wa-case {
		width: 1rem;
		height: 1rem;
	}
	.wa-titre {
		flex: 1;
	}
	.wa-titre-champ {
		font-weight: 600;
	}
	.wa-regle {
		font-size: var(--fs-xs);
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
		background: var(--color-info-fond);
		color: var(--color-info);
	}
	.wa-contenu {
		resize: vertical;
		font-size: var(--fs-md);
		font-family: monospace;
	}
	.wa-apercu {
		margin-top: 0.4rem;
		padding: 0.5rem;
		background: var(--color-bg);
		border-left: 3px solid var(--color-border);
		border-radius: 4px;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		line-height: 1.6;
		white-space: pre-wrap;
		word-wrap: break-word;
	}
</style>
