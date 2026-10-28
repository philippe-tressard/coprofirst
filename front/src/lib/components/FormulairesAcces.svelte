<!--
  **Demander un nouvel accès, ou en déclarer un qu'on détient déjà.**

  ## Pourquoi séparé (12/09/2026, #928)

  `OngletAcces` est né au-dessus du plafond de modularité en extrayant l'écran
  `/acces-securite`. La coupe suit la nature : d'un côté **ce que je possède**
  (mes listes, leur historique), de l'autre **ce que je demande**.

  🔴 Les deux formulaires vont ensemble et ne vont qu'ensemble : ils remplissent
  la même table côté serveur, et l'utilisateur choisit entre eux — « je n'en ai
  pas, j'en veux un » contre « j'en ai un, il n'est pas chez vous ». Les séparer
  aurait donné deux composants dont chacun n'a de sens que si l'autre existe.

  ⚠️ Ils sont OUVERTS depuis l'en-tête de page, par deux boutons (#928), et non
  par des sections à faire défiler. Leur visibilité est donc une prop liée : un
  second état chez l'hôte finirait par se désaccorder de celui-ci.
-->
<script lang="ts">
	import type { MonLot } from '#lib/api/index.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { TYPES_ACCES } from '#lib/types-acces.ts';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';

	/** Les formulaires ouverts — liés à l'en-tête, qui porte les boutons. */
	export let showForm = false;
	export let showDeclareForm = false;

	/** Les lots de l'utilisateur, pour rattacher la demande. */
	export let mesLots: MonLot[] = [];

	/**  Ce que l'hôte sait faire : il tient les listes, donc il enregistre.
	 *   Ce composant ne parle qu'à l'utilisateur. */
	export let soumettreCommande: () => void;
	export let declarerBadge: () => void;

	export let formLotId = '';
	export let formType = 'vigik';
	export let formQuantite = 1;
	export let formMotif = '';
	export let submitting = false;
	/** L'enregistrement d'une DÉCLARATION est en cours (distinct de `submitting`,
	 *  qui porte la demande : les deux formulaires peuvent être ouverts). */
	export let declaring = false;
	export let declareType = 'telecommande';
	export let declareCode = '';
</script>

{#if showForm}
	<FormulaireCreation titre="Nouvelle demande d'accès">
		<!--  Le pied STANDARD (#1329) : ces deux formulaires ont quitté leur fenêtre
		      le 06/09 et en gardaient le corps et le pied (`.modal-body`,
		      `.modal-footer`), écrits à la main. -->
		<form on:submit|preventDefault={soumettreCommande}>
			<div>
				<div class="form-grid">
					<ChoixPastilles
						options={TYPES_ACCES}
						bind:valeur={formType}
						tous={false}
						libelle="Type d'accès"
						libelleVisible
						requis
						radio="commande-type"
						defilante={false}
					/>
					<label class="field">
						<span>Lot concerné<EtoileRequis vide={!formLotId} /></span>
						<select bind:value={formLotId} required>
							<option value="">— Sélectionner —</option>
							{#each mesLots as lot (lot.id)}
								<option value={lot.id}>Lot {lot.numero}</option>
							{/each}
						</select>
					</label>
					<label class="field">
						<span>Quantité<EtoileRequis vide={!formQuantite} /></span>
						<input type="number" bind:value={formQuantite} min="1" max="5" />
					</label>
					<label class="field">
						Motif
						<textarea bind:value={formMotif} rows="2" placeholder="Raison de la demande…"
						></textarea>
					</label>
				</div>
			</div>
			<PiedFormulaire enCours={submitting} on:annule={() => (showForm = false)} />
		</form>
	</FormulaireCreation>
{/if}

{#if showDeclareForm}
	<FormulaireCreation titre="Déclarer un accès existant">
		<form on:submit|preventDefault={declarerBadge}>
			<div>
				<div class="form-grid">
					<ChoixPastilles
						options={TYPES_ACCES}
						bind:valeur={declareType}
						tous={false}
						libelle="Type d'accès"
						libelleVisible
						requis
						radio="declare-type"
						defilante={false}
					/>
					<label class="field"
						><span>Code / référence<EtoileRequis vide={!declareCode.trim()} /></span>
						<input
							type="text"
							bind:value={declareCode}
							placeholder="Ex : 1234567890"
							class="texte-code"
							required
						/>
					</label>
				</div>
				<p class="effet-declaration">
					Si ce code figure dans nos imports, l'entrée sera automatiquement liée à votre compte.
				</p>
			</div>
			<PiedFormulaire enCours={declaring} on:annule={() => (showDeclareForm = false)} />
		</form>
	</FormulaireCreation>
{/if}

<style>
	.effet-declaration {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0.5rem 0 0;
	}
</style>
