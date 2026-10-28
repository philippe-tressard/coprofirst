<!--
  Les RÉPONSES DU SYNDIC aux relances groupées, conservées et relues ici
  (04/09/2026) — en mode « Relancer le syndic » du Suivi des affaires depuis
  #2035 ; elles vivaient dans l'ancienne vue « Relance syndic », retirée.

  Elles étaient captées et notifiées, jamais consultables : une notification se
  lit une fois puis descend dans la pile. Passé quelques jours, la réponse du
  syndic était en base et introuvable.

  ⚠️ Elles s'affichent sous la relance, jamais dans les fils : « pour le TK-123 on
  intervient jeudi, le TK-456 est clos » recopié dans quatre fils serait faux dans
  trois. Le conseil reporte là où c'est juste.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { tickets as ticketsApi, type ReponseRelance } from '#lib/api/index.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { essayer } from '#lib/chargement.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	let reponses: ReponseRelance[] = [];
	//  Une ligne discrète, pas un second bandeau : l'écran reste juste sans cet
	//  historique, mais ne doit pas le dire vide (#1459).
	let erreur = '';

	export async function recharger() {
		const [r, e] = await essayer(ticketsApi.relanceReponses(), { reponses: [] });
		[reponses, erreur] = [r.reponses, e];
	}

	onMount(recharger);
</script>

{#if erreur}
	<EtatListe compact {erreur} />
{:else if reponses.length}
	<section class="report-card">
		<h3 class="rep-titre">&#x1F4E8; Réponses du syndic aux relances</h3>
		<p class="rep-aide">
			Ces réponses portent sur <strong>plusieurs dossiers à la fois</strong> : elles ne sont volontairement
			ajoutées à aucun fil. À reporter dans les affaires concernées.
		</p>
		{#each reponses as rep (rep.id)}
			<article class="rep-carte">
				<header class="rep-entete">
					<span class="rep-de">{rep.expediteur}</span>
					<span class="rep-quand">{fmtDatetime(rep.recue_le)}</span>
				</header>
				{#if rep.tickets.length}
					<p class="rep-tickets">
						Relance portant sur&nbsp;: {#each rep.tickets as num, i (num)}<span
								class="badge badge-gray">#{num}</span
							>{#if i < rep.tickets.length - 1}&nbsp;{/if}{/each}
					</p>
				{/if}
				<p class="rep-texte">{rep.contenu || '(message sans texte lisible)'}</p>
			</article>
		{/each}
	</section>
{/if}

<style>
	.rep-titre {
		margin-bottom: 0.35rem;
	}
	.rep-aide {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-bottom: 0.75rem;
	}
	.rep-carte {
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-primary);
		border-radius: 0 var(--radius) var(--radius) 0;
		padding: 0.6rem 0.8rem;
		margin-bottom: 0.6rem;
		background: var(--color-bg);
	}
	.rep-entete {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.3rem;
	}
	.rep-de {
		font-weight: 600;
		font-size: var(--fs-base);
	}
	.rep-quand {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.rep-tickets {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-bottom: 0.4rem;
	}
	/*  `pre-wrap` : une réponse de courriel porte ses propres retours à la ligne,
	    et les écraser collerait des paragraphes que le syndic a séparés. */
	.rep-texte {
		white-space: pre-wrap;
		font-size: var(--fs-base);
		margin: 0;
	}
</style>
