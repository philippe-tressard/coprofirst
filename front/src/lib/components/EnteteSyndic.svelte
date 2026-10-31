<!--
  EnteteSyndic.svelte — l'en-tête « Syndic » de l'annuaire : nom, adresse, site.

  Extrait d'`espace-cs/+page.svelte` le 29/08/2026 (#535). Le fichier dépassait
  déjà 1 150 lignes, et le contrôle de modularité a refusé qu'il grossisse —
  à raison : la page porte quatre onglets, dont sept blocs déjà sortis en
  composants (`OngletAnnoncesHall`, `OngletReporting`…). Celui-ci suit le motif.

  🔴 CE QU'IL PORTE, et qui n'est pas cosmétique : le champ « Nom du syndic »
  n'est plus la source de vérité. Le CONTRAT désigné fait foi ; cette saisie est
  un repli pour les copropriétés qui n'en ont pas désigné (#535).

  ⚠️ Le champ est DÉSACTIVÉ quand le contrat fait foi, et `AideSource` dit
  pourquoi. Dire sans empêcher laisserait corriger dans le vide ; empêcher sans
  dire se lirait comme un bug. Les deux vont ensemble.

  ⚠️ Et le serveur ne se fie pas à ce `disabled` : `routers/admin/annuaire.py`
  refuse d'écrire `nom_syndic` quand le contrat fait foi. Un garde posé côté
  écran seul serait contourné par un second écran ou un appel direct.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import AideSource from '#lib/components/AideSource.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';

	export let nom = '';
	export let adresse = '';
	export let siteWeb = '';
	/** D'où vient `nom` — `contrat` désactive la saisie (`utils/syndic.py`). */
	export let source: 'contrat' | 'saisie' | 'aucune' = 'aucune';
	export let edition = false;
	export let enregistrement = false;
	/** Appelée à l'enregistrement. Le composant ne connaît pas l'API. */
	export let onEnregistrer: () => void = () => {};
</script>

{#if edition}
	<div class="form-grid largeur-saisie grille-syndic">
		<label class="field champ-large">
			Nom du syndic
			<input
				type="text"
				bind:value={nom}
				placeholder="ex. Cabinet Bertrand"
				disabled={source === 'contrat'}
			/>
			<AideSource
				active={source === 'contrat'}
				origine="contrat de syndic"
				ou="Prestataires → Contrats"
				repli="Aucun contrat désigné : cette saisie s'affiche."
			/>
		</label>
		<label class="field champ-large">
			Adresse
			<textarea rows="2" bind:value={adresse} placeholder="ex. 12 rue des Lilas, 75015 Paris"
			></textarea>
		</label>
		<label class="field champ-large">
			Espace client (site web)
			<input type="url" bind:value={siteWeb} placeholder="https://..." />
		</label>
		<!--  🔴 `PiedFormulaire` (12/09/2026) : cette rangée était une copie du pied
		      commun sous une autre classe, et elle avait divergé comme les neuf
		      d'origine — « Enregistrer » AVANT « Annuler », un emoji 💾 dans le
		      libellé, « … » au lieu de « Enregistrement… », et aucun `type` sur les
		      boutons. Elle échappait au contrôle parce qu'il n'ouvrait que les
		      rangées `.form-actions` ; il cherche désormais la paire quelle que
		      soit la classe. -->
		<div class="pied-syndic">
			<PiedFormulaire
				enCours={enregistrement}
				soumission={false}
				petit
				on:enregistre={onEnregistrer}
				on:annule={() => (edition = false)}
			/>
		</div>
	</div>
{:else}
	<div class="header-summary">
		<span>{nom || 'Nom du syndic non renseigné'}{adresse ? ` · ${adresse}` : ''}</span>
		{#if siteWeb}<span class="site-syndic"
				>{SEPARATEUR.point}<a href={siteWeb} target="_blank" rel="noopener">Espace client</a></span
			>{/if}
		<button
			type="button"
			class="btn-icon btn-icon-edit"
			aria-label="Modifier"
			title="Modifier"
			on:click={() => (edition = true)}><IconeAction icone="pencil" /></button
		>
	</div>
{/if}

<style>
	.grille-syndic {
		margin-bottom: 1rem;
	}
	.pied-syndic {
		grid-column: 1/-1;
	}
	.site-syndic {
		margin-left: 0.5rem;
	}
</style>
