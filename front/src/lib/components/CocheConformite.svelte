<!--
  **La coche de conformité** — un point mesuré (posture d'une installation, copie
  de sauvegarde hors machine) : conforme, à corriger, ou INCONNU.

  ## Pourquoi (15/10/2026)

  La fiche d'une installation disait « documentation d’API coupée : oui » : un
  « oui » sur un mot de panne se lisait comme une panne, alors que c'était l'état
  sain. Arbitré par l'utilisateur : une coche, et une phrase qui dit le FAIT.

  - **Trois états, trois formes** — ✓ dans un rond plein, ✗ dans un rond plein, ?
    dans un rond en pointillés —, pas trois couleurs seulement : la teinte double
    la forme, elle ne la remplace pas.
  - **INCONNU n'est jamais ✓** (`standards/04`) : une mesure qui n'a pas pu se
    faire (`null`) n'atteste rien. Son libellé est le seul NOM du point, sans
    adjectif : on ne sait pas.
  - **La phrase change avec l'état** (`PointConformite`, `#lib/registre-installations`) :
    la coche confirme le fait, elle ne le porte pas.
  - **L'explication s'ouvre au toucher, au clic et au clavier** (`Infobulle`) ; à
    la souris, elle est aussi au survol.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import Infobulle from '#lib/components/Infobulle.svelte';
	import type { PointConformite } from '#lib/registre-installations.ts';

	export let point: PointConformite;
	/** `true` conforme, `false` à corriger, `null` : la mesure n'a pas pu se faire. */
	export let conforme: boolean | null;

	$: etat = conforme === null ? 'inconnu' : conforme ? 'conforme' : 'a-corriger';
	$: fait = conforme === null ? point.inconnu : conforme ? point.conforme : point.aCorriger;
	$: verdict = conforme === null ? 'Inconnu' : conforme ? 'Conforme' : 'À corriger';
	$: precision =
		conforme === null
			? 'La mesure n’a pas pu se faire au dernier rapport : rien n’atteste ce point.'
			: '';
</script>

<Infobulle libelle="{fait} — {verdict}" titre="{verdict} — {point.explication}">
	<span class="coche" data-etat={etat}>
		<span
			class="marque"
			class:marque-conforme={etat === 'conforme'}
			class:marque-a-corriger={etat === 'a-corriger'}
			class:marque-inconnu={etat === 'inconnu'}
			aria-hidden="true"
		>
			{#if etat === 'conforme'}<Icon name="check" size={11} />{:else if etat === 'a-corriger'}<Icon
					name="x"
					size={11}
				/>{:else}?{/if}
		</span>
		<span class="fait">{fait}</span>
	</span>
	<svelte:fragment slot="bulle">
		<strong>{verdict}</strong>
		{point.explication}
		{precision}
	</svelte:fragment>
</Infobulle>

<style>
	.coche {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
	}
	/*  Le texte du fait porte un souligné en pointillés : il se touche pour en
	    savoir plus, comme une abréviation. */
	.fait {
		text-decoration: underline dotted var(--color-text-muted);
		text-underline-offset: 0.2em;
	}
	.marque {
		flex: none;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.1rem;
		height: 1.1rem;
		border-radius: 50%;
		border: 1px solid transparent;
		font-size: var(--fs-xs);
		font-weight: 700;
		line-height: 1;
	}
	.marque-conforme {
		background: var(--color-success-fond);
		border-color: var(--color-success-bordure);
		color: var(--color-success-texte);
	}
	.marque-a-corriger {
		background: var(--color-danger-fond);
		border-color: var(--color-danger-bordure);
		color: var(--color-danger);
	}
	.marque-inconnu {
		border: 1px dashed var(--color-text-muted);
		color: var(--color-text-muted);
	}
</style>
