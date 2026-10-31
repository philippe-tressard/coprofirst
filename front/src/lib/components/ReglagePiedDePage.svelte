<!--
  Le réglage du PIED DE PAGE, dans Admin › Présentation › Connexion et pied de page.

  La marque — logo et nom de la résidence — est fixe, au cadenas : elle signe
  la carte (maquette A, 15/10/2026). Puis une liste par place de la carte,
  « Sous le nom » et « Liens, à droite », chacune dans son ordre d'affichage :
  chaque élément monte ou descend (↑ ↓) dans sa place, les facultatifs
  s'affichent ou se masquent (leur pastille), les trois que la loi ou la
  licence imposent restent — mais se déplacent comme les autres (arbitré à
  l'écran, 09/10/2026). Dessous, l'année de création, le préfixe du nom et le
  texte libre. La règle vit dans `#lib/piedDePage`.

  L'aperçu est le VRAI composant du squelette : il ne peut pas montrer autre
  chose que le site.

  ⚠️ Pas de texte d'exemple dans l'année ni dans le préfixe : « 2026 » et
  « Résidence », grisés, se lisaient comme des valeurs saisies — l'année n'a
  pas été enregistrée en production pour cette raison (09/10/2026). L'aide
  sous le champ porte l'exemple.
-->
<script lang="ts">
	import IconeAction from '#lib/components/IconeAction.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import LibelleGroupe from '#lib/components/LibelleGroupe.svelte';
	import Pastille from '#lib/components/Pastille.svelte';
	import PiedDePage from '#lib/components/PiedDePage.svelte';
	import {
		dansLaPlace,
		deplacer,
		ELEMENT_PIED,
		ELEMENTS_PIED,
		PLACES_REGLABLES,
		PREFIXE_NOM_MAX,
		TEXTE_PIED_MAX,
		type ReglagePied,
	} from '#lib/piedDePage.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Lié : la page porte l'état et l'enregistre. */
	export let reglage: ReglagePied;
	export let siteSaving = false;
	export let saveSiteConfig: () => void;

	/** La marque ne se règle pas ici : elle se montre, au cadenas. */
	const marque = ELEMENTS_PIED.find((e) => e.place === 'marque');

	/** Affiche ou masque un élément — l'aperçu suit aussitôt. */
	function basculer(code: string) {
		const masques = reglage.masques;
		reglage.masques = masques.includes(code)
			? masques.filter((c) => c !== code)
			: [...masques, code];
	}

	function bouger(code: string, sens: -1 | 1) {
		reglage.ordre = deplacer(reglage.ordre, code, sens);
	}
</script>

<section class="card config-section">
	<h2 class="config-section-title"><Icon name="pencil" size={17} />Pied de page</h2>
	<div class="largeur-saisie">
		<div class="groupes-pied">
			{#if marque}
				<p class="fixe" title="Toujours affichés : {marque.verrouille}">
					<Icon name="lock" size={13} />{marque.libelle}
				</p>
			{/if}
			{#each PLACES_REGLABLES as { place, titre } (place)}
				{@const codes = dansLaPlace(reglage.ordre, place)}
				<LibelleGroupe {titre} id="pied-{place}">
					<ol class="liste-pied">
						{#each codes as code, i (code)}
							{@const e = ELEMENT_PIED.get(code)}
							{#if e}
								<li>
									<button
										type="button"
										class="btn-icon deplacer"
										aria-label="Monter « {e.libelle} »"
										title="Monter"
										disabled={i === 0}
										on:click={() => bouger(code, -1)}><IconeAction icone="arrow-up" /></button
									>
									<button
										type="button"
										class="btn-icon deplacer"
										aria-label="Descendre « {e.libelle} »"
										title="Descendre"
										disabled={i === codes.length - 1}
										on:click={() => bouger(code, 1)}><IconeAction icone="arrow-down" /></button
									>
									{#if e.verrouille}
										<span class="fixe" title="Toujours affiché : {e.verrouille}"
											><Icon name="lock" size={13} />{e.libelle}</span
										>
									{:else}
										<Pastille
											petite
											bascule
											active={!reglage.masques.includes(code)}
											on:click={() => basculer(code)}>{e.libelle}</Pastille
										>
									{/if}
								</li>
							{/if}
						{/each}
					</ol>
				</LibelleGroupe>
			{/each}
		</div>
		<p class="aide">
			Une pastille pleine est affichée, une pastille vide masquée. Les éléments au cadenas restent
			toujours : le logo et le nom signent le pied de page, la licence du logiciel et la loi
			imposent que les trois liens soient accessibles depuis chaque page{SEPARATEUR.tiret}ils se
			déplacent comme les autres. Le logo et le nom se règlent plus haut, dans l’identité du site.
		</p>
		<div class="champs-pied">
			<label class="field">
				Année de création
				<input type="number" bind:value={reglage.anneeDebut} min="1900" max="9999" />
				<span class="aide"
					>« © 2026 » cette année, « © 2026–2027 » l’an prochain. Vide : l’année en cours seule.</span
				>
			</label>
			<label class="field">
				Texte avant le nom
				<input type="text" bind:value={reglage.prefixeNom} maxlength={PREFIXE_NOM_MAX} />
				<span class="aide">Écrit devant le nom de la résidence, sans séparateur.</span>
			</label>
			<label class="field champ-large">
				Texte libre
				<input
					type="text"
					bind:value={reglage.texte}
					maxlength={TEXTE_PIED_MAX}
					placeholder="Un texte court, placé sous le nom comme les autres mentions"
				/>
			</label>
		</div>
		<div class="apercu-pied" role="group" aria-label="Aperçu du pied de page">
			<PiedDePage {reglage} apercu />
		</div>
	</div>
	<div class="form-actions largeur-saisie">
		<button class="btn btn-primary" on:click={saveSiteConfig} disabled={siteSaving}>
			{siteSaving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</section>

<style>
	.liste-pied {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.3rem;
	}
	.liste-pied li {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}
	.deplacer:disabled {
		opacity: 0.25;
		cursor: not-allowed;
	}
	.groupes-pied {
		display: grid;
		gap: 0.75rem;
	}
	.groupes-pied > .fixe {
		margin: 0;
	}
	.fixe {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		margin-left: 0.3rem;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.champs-pied {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		margin-top: 0.75rem;
	}
	.champs-pied .champ-large {
		grid-column: 1 / -1;
	}
	@media (max-width: 767px) {
		.champs-pied {
			grid-template-columns: 1fr;
		}
	}
	.apercu-pied {
		margin-top: 0.75rem;
		border: 1px dashed var(--color-border);
		border-radius: var(--radius);
	}
</style>
