<!--
  La saisie d'une notation de prestataire — trois états, deux colonnes de motifs, un
  commentaire libre (14/11/2026, maquette N5c).

  Le commentaire enregistré se COMPOSE ici : la phrase générée par les cases cochées,
  puis le texte libre. Le parent ne reçoit que `commentaire` (lié), jamais les cases.

  Le parent porte le geste (`GesteEnPlace`, Annuler / Enregistrer) : ce composant ne
  rend que le corps, pour qu'une seule carte garde le cadre.
-->
<script lang="ts">
	import {
		ETATS,
		LIBELLE_ETAT,
		POINTS_FAIBLES,
		POINTS_FORTS,
		commentaireComplet,
		decomposerCommentaire,
		phraseGeneree,
		type Etat,
	} from '#lib/notations.ts';

	/** L'état choisi — `null` tant que personne n'a choisi. */
	export let etat: Etat | null = null;
	/** Le commentaire enregistré : phrase générée puis texte libre. Lié au parent. */
	export let commentaire = '';
	/** Identifiant préfixant les champs, pour que deux saisies ne se confondent pas. */
	export let id = 'notation';
	/** Le commentaire d'un avis qu'on corrige (15/11/2026) : ses cases se RECOCHENT, et
	 *  seul le texte libre revient dans la zone de saisie (`decomposerCommentaire`). */
	export let initial = '';

	let { forts, faibles, libre } = decomposerCommentaire(initial);

	$: genere = phraseGeneree(forts, faibles);
	$: commentaire = commentaireComplet(genere, libre);
</script>

<div class="notation">
	<div class="ligne-etats" role="group" aria-label="État de l'intervention">
		{#each ETATS as e (e)}
			<button
				type="button"
				class="etat"
				class:etat-mauvais={e === 'mauvais'}
				class:etat-neutre={e === 'neutre'}
				class:etat-excellent={e === 'excellent'}
				aria-pressed={etat === e}
				on:click={() => (etat = e)}
			>
				{LIBELLE_ETAT[e]}
			</button>
		{/each}
	</div>

	<div class="colonnes">
		<fieldset class="colonne forts">
			<legend>Points forts</legend>
			{#each POINTS_FORTS as motif (motif)}
				<label class="motif">
					<input type="checkbox" value={motif} bind:group={forts} />
					<span>{motif}</span>
				</label>
			{/each}
		</fieldset>
		<fieldset class="colonne faibles">
			<legend>Points faibles</legend>
			{#each POINTS_FAIBLES as motif (motif)}
				<label class="motif">
					<input type="checkbox" value={motif} bind:group={faibles} />
					<span>{motif}</span>
				</label>
			{/each}
		</fieldset>
	</div>

	<p class="genere" aria-live="polite">
		<span class="detail-label">Commentaire généré</span>
		{genere || 'Rien de coché pour l’instant.'}
	</p>

	<label class="field libre" for="{id}-libre">
		<span>Commentaire libre <span class="aide">(facultatif, sauf pour « Mauvais »)</span></span>
		<textarea id="{id}-libre" rows="3" bind:value={libre}></textarea>
	</label>
</div>

<style>
	.notation {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.ligne-etats {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.etat {
		flex: 1 1 6rem;
		min-height: 44px;
		border: 2px solid var(--color-border);
		border-radius: 0.5rem;
		background: var(--color-surface);
		font-weight: 600;
		cursor: pointer;
	}
	.etat[aria-pressed='true'] {
		color: var(--color-sur-plein);
	}
	.etat-mauvais[aria-pressed='true'] {
		background: var(--color-danger-plein);
		border-color: var(--color-danger-plein);
	}
	.etat-neutre[aria-pressed='true'] {
		background: var(--color-text-muted);
		border-color: var(--color-text-muted);
	}
	.etat-excellent[aria-pressed='true'] {
		background: var(--color-success-plein);
		border-color: var(--color-success-plein);
	}
	.colonnes {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}
	.colonne {
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		min-width: 0;
	}
	.colonne.forts {
		background: var(--color-success-fond);
	}
	.colonne.faibles {
		background: var(--color-danger-fond);
	}
	legend {
		font-size: var(--fs-sm);
		font-weight: 600;
		padding: 0 0.25rem;
	}
	.motif {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 36px;
	}
	.motif input {
		width: 18px;
		height: 18px;
		margin: 0;
	}
	.genere {
		margin: 0;
		line-height: 1.5;
	}
	.libre {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.libre textarea {
		resize: vertical;
	}
	@media (max-width: 480px) {
		.colonnes {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
