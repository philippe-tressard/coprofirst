<!--
  ConciliationFusion.svelte — le plan pour AUTORISER la fusion d'une affaire refusée
  pour fuite de lecture (27/10/2026).

  La fusion verse les Suites de l'autre affaire dans la principale : toute personne
  qui lit la principale les lirait. Le refus (#1704) demeure — il devient une
  DÉCISION du conseil, prise devant :

  - l'ÉCART (périmètre, Destinataires, accès) entre les deux affaires ;
  - trois options, chacune avec ce qu'elle ferait lire et à qui :
    inverser (l'autre absorbe — hors clôture), restreindre (ce que les deux avaient
    en commun), élargir (l'union des deux) ;
  - pour toute option qui fait lire à quelqu'un ce qu'il ne lisait pas : sa liste
    NOMINATIVE, à confirmer. Les noms viennent du serveur, qui exige la même liste.

  Rien ne se décide ici : le serveur mesure avec la règle d'accès de la fiche
  (`utils/fusion_conciliation`) et l'écran montre. S'emploie dans `DialogueFusion`
  (clôture) et `FusionAffaires` (correction, Suivi).
-->
<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import type { CandidateFusion } from '#lib/api/index.ts';
	import type { DecisionConciliation } from '#lib/fusion-conciliation.ts';

	/** L'affaire refusée, avec son plan (`conciliation`). */
	export let candidate: CandidateFusion;
	/** Le numéro de l'affaire qui absorberait. */
	export let numeroPrincipale: string;
	/** Le choix du conseil — `null` : elle reste hors de la fusion. */
	export let decision: DecisionConciliation | null | undefined = null;
	/** Une autre affaire restreint ou élargit déjà : l'inversion n'est plus mesurée. */
	export let inversionInterdite = false;
	/** Une autre affaire inverse déjà les rôles : celle-ci ne peut que rester dehors. */
	export let bloque = false;

	$: conciliation = candidate.conciliation;
	$: nom = `conciliation-${candidate.id}`;

	function choisir(option: DecisionConciliation['option'] | null) {
		if (option === null) decision = null;
		else if (decision?.option !== option) decision = { option, confirme: false };
	}
</script>

{#if conciliation}
	<div class="conciliation">
		<p class="aide">
			{candidate.numero} n'est pas lue par les mêmes personnes que {numeroPrincipale} :
		</p>
		<ul class="ecarts">
			{#each conciliation.ecarts as e (e.champ)}
				<li>
					<strong>{e.libelle}</strong> — {numeroPrincipale} : {e.principale} · {candidate.numero} : {e.absorbee}
				</li>
			{/each}
		</ul>
		<div role="radiogroup" aria-label="Conciliation de {candidate.numero}" class="options">
			<label class="case">
				<input type="radio" name={nom} checked={!decision} on:change={() => choisir(null)} />
				<span>La laisser hors de la fusion</span>
			</label>
			{#each conciliation.options as o (o.code)}
				{@const indisponible =
					!o.disponible || bloque || (o.code === 'inverser' && inversionInterdite)}
				<div>
					<label class="case" class:attenue={indisponible}>
						<input
							type="radio"
							name={nom}
							disabled={indisponible}
							checked={decision?.option === o.code}
							on:change={() => choisir(o.code)}
						/>
						<span>{o.libelle}</span>
					</label>
					{#if !o.disponible}
						<p class="aide sous-case">Impossible : {o.pourquoi}</p>
					{:else if o.code === 'inverser'}
						<p class="aide sous-case">
							{candidate.numero} absorbe {numeroPrincipale} : plus personne ne lit ce qu'il ne lisait
							pas.
						</p>
					{:else if o.resultat}
						<p class="aide sous-case">
							{numeroPrincipale} serait lue ainsi — {o.resultat.perimetre} · {o.resultat
								.destinataires}
							· {o.resultat.acces}.
							{#if o.perdants}Perdent l'accès à un fil qu'elles lisaient : {fmtNombre(
									o.perdants,
								)}.{/if}
						</p>
					{/if}
					{#if decision?.option === o.code && o.consentement}
						<div class="consentement">
							<p class="aide sous-case">
								{o.exposes.length} personne{o.exposes.length > 1 ? 's' : ''} liront désormais ce qu'elles
								ne lisaient pas :
							</p>
							<ul class="noms">
								{#each o.exposes as p (p.id)}
									<li>{p.nom}</li>
								{/each}
							</ul>
							<label class="case sous-case">
								<input type="checkbox" bind:checked={decision.confirme} />
								<span>Je confirme que ces personnes liront désormais ce fil.</span>
							</label>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</div>
{/if}

<style>
	.conciliation {
		margin: 0.25rem 0 0.75rem;
		padding: 0.5rem 0.75rem;
		border-left: 3px solid var(--color-border);
	}
	.ecarts {
		margin: 0 0 0.5rem;
		padding-left: 1.1rem;
		font-size: var(--fs-sm);
	}
	.consentement {
		margin-top: 0.25rem;
		padding: 0.4rem 0.6rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		/* Le bloc se monte au choix de l'option : fondu seul (pas de déplacement, donc rien
		   à couper sous prefers-reduced-motion), comme l'entrée du corps d'une carte. */
		animation: fadeIn var(--duree-apparition) var(--ease-out);
	}
	.options {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.noms {
		margin: 0.25rem 0 0.4rem 1.6rem;
		padding-left: 1rem;
		max-height: 9rem;
		overflow-y: auto;
		font-size: var(--fs-sm);
		columns: 2 12rem;
	}
</style>
