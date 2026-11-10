<!--
  EcheanceGouttiere.svelte — la VIGNETTE D'ÉCHÉANCE d'une affaire datée, sous
  le classement de la gouttière : le DÉLAI d'abord (« J-8 »), la ou les dates
  ensuite.

  ## Pourquoi (10/11/2026, maquette C « Échéance », choisie parmi cinq)

  Au fil, une affaire de nature Calendrier ne disait pas QUAND elle a lieu : sa
  gouttière portait l'heure de la dernière nouvelle, puis « CAL. », et le jour
  du rendez-vous se cherchait dans le texte. La colonne se lit désormais de haut
  en bas : quand on en a parlé · ce que c'est · quand ça se passe.

  🔴 Le délai n'est PAS compté ici : le serveur le dérive en jours civils de
  Paris et sert son libellé (`utils/echeance_affaire`, `meta.affaire.echeance`).
  Ce composant ne fait que le rendre — et formater les deux dates, valeurs
  typées que chaque client rend avec son formateur (`fmtJourCourt`).

  Une affaire CLOSE n'a plus de délai (`libelle` absent) : la date seule dit
  quand c'était prévu. Un rendez-vous passé perd la teinte de la carte.

  Rendu dans le créneau `gouttiere` de `CarteListe` : la teinte est celle du
  classement (`--nature-fort`). Au téléphone la gouttière est une LIGNE : la
  vignette s'y couche, délai puis dates.
-->
<script lang="ts">
	import type { EcheanceAffaire } from '#lib/api/index.ts';
	import { fmtDateLong, fmtJourCourt } from '#lib/date.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** L'échéance servie par le fil — sans elle, rien n'est rendu. */
	export let echeance: EcheanceAffaire | null | undefined = null;
	/** Les dates de l'affaire (ISO) : `debut`, et `fin` si elle tombe un autre jour. */
	export let debut: string | null | undefined = null;
	export let fin: string | null | undefined = null;

	$: plage = !!(echeance?.plusieurs_jours && fin);
	$: enClair = plage
		? `Du ${fmtDateLong(debut)} au ${fmtDateLong(fin)}`
		: `Le ${fmtDateLong(debut)}`;
</script>

{#if echeance && debut}
	<span class="echeance" data-etat={echeance.etat} title={enClair}>
		<span class="sr-only">Prévu : </span>
		{#if echeance.libelle}<strong class="e-delai">{echeance.libelle}</strong>{/if}
		<span class="e-dates">
			<time datetime={debut}>{fmtJourCourt(debut)}</time>
			{#if plage && fin}
				<time datetime={fin}>{SEPARATEUR.fleche}{fmtJourCourt(fin, false)}</time>
			{/if}
		</span>
	</span>
{/if}

<style>
	.echeance {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.15rem;
		text-align: center;
	}
	/*  Le délai prend la teinte du classement, juste au-dessus de lui : les deux
	    se lisent comme un seul repère. */
	.e-delai {
		font-size: var(--fs-xl);
		font-weight: 700;
		line-height: 1.1;
		color: var(--nature-fort, var(--color-primary));
		font-variant-numeric: lining-nums tabular-nums;
		white-space: nowrap;
	}
	/*  Passé : il ne reste qu'un fait, plus une attente — le texte discret. */
	[data-etat='passee'] .e-delai {
		color: var(--color-text-muted);
	}
	.e-dates {
		display: flex;
		flex-direction: column;
		font-size: var(--fs-xs);
		line-height: 1.25;
		color: var(--color-text-muted);
	}
	.e-dates time {
		white-space: nowrap;
	}

	/*  Au pouce, la gouttière est une ligne : délai, puis dates, sur la même. */
	@media (max-width: 480px) {
		.echeance {
			flex-direction: row;
			align-items: baseline;
			gap: 0.35rem;
		}
		.e-delai {
			font-size: var(--fs-sm);
		}
		.e-dates {
			flex-direction: row;
			gap: 0.3em;
			font-size: var(--fs-sm);
		}
	}
</style>
