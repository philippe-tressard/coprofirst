<!--
  Le COMPTE RENDU GLOBAL d'un point CS / Syndic — maquette C1, deux parties
  (arbitrée le 17/10/2026, #2041) :

  1. **Le point** — Quand, Où, Qui (conseil, syndic, invités) ;
  2. **Les affaires abordées**, une par bloc, dans l'ordre d'ouverture ; puis
     les **non traitées**, numéro et titre seuls.

  Composé par le serveur (`GET /points-conseil/courant`) ; un brouillon s'y lit
  comme tel, et le texte riche passe par l'assainisseur. Chaque affaire porte
  « qui la lit » (`PastilleLecture`, #2089), « CS et présents », l'état décidé
  pour la validation et « Modifié en révision N » (#2082).
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import type { AffaireOuverte, CompteRenduPoint } from '#lib/api/index.ts';
	import { fmtDatetime, fmtTime } from '#lib/date.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import { lienTicket, statutTicketLabel } from '#lib/tickets.ts';
	import {
		ETATS_POINT,
		GROUPES_PRESENTS,
		LIBELLE_CS_ET_PRESENTS,
		nomPresent,
		precisionPresent,
	} from '#lib/points-conseil.ts';
	import PastilleLecture from '#lib/components/PastilleLecture.svelte';

	export let compteRendu: CompteRenduPoint;
	/** Les affaires du relevé, par identifiant — ce que lit leur pastille de lecture. */
	export let affaires: Map<number, AffaireOuverte> = new Map();

	$: point = compteRendu.point;
	$: groupes = GROUPES_PRESENTS.map((g) => ({
		...g,
		presents: compteRendu.presents.filter((p) => p.nature === g.nature),
	})).filter((g) => g.presents.length);
</script>

<section class="report-card" aria-labelledby="titre-cr-{point.id}">
	<div class="tete">
		<h3 id="titre-cr-{point.id}">Compte rendu du point</h3>
		<span class="badges">
			<Badge teinte={ETATS_POINT[point.etat].teinte}>{ETATS_POINT[point.etat].libelle}</Badge>
			{#if compteRendu.revision}
				<Badge teinte="badge-gray">Révision {compteRendu.revision}</Badge>
			{/if}
		</span>
	</div>

	<h4 class="partie">1 · Le point</h4>
	<p class="quand">
		{fmtDatetime(point.debut)}{#if point.fin}&nbsp;→ {fmtTime(point.fin)}{/if} · {point.ou}
	</p>
	{#each groupes as g (g.nature)}
		<p class="presents">
			<span class="groupe">{g.libelle} :</span>
			<!--  L'espace de tête vit DANS l'expression : un blanc en tête de balise se
			      perd au formatage, et « Paul Bernard(Gestionnaire) » se lisait collé
			      (17/10/2026). -->
			{#each g.presents as p, i (p.id)}{i ? ' · ' : ''}{nomPresent(p)}{#if precisionPresent(p)}<span
						class="precision">{` (${precisionPresent(p)})`}</span
					>{/if}{#if p.telephone || p.email}<span class="precision"
						>{` — ${[p.telephone, p.email].filter(Boolean).join(', ')}`}</span
					>{/if}{/each}
		</p>
	{:else}
		<p class="vide">Aucun présent indiqué.</p>
	{/each}

	<h4 class="partie">2 · Les affaires abordées · {compteRendu.abordees.length}</h4>
	{#each compteRendu.abordees as { affaire, cr, marque } (affaire.id)}
		<article class="abordee">
			<p class="titre">
				<a href={lienTicket(affaire.id)}>{affaire.numero} · {affaire.titre}</a>
				{#if affaires.has(affaire.id)}<PastilleLecture
						ticket={affaires.get(affaire.id) ?? null}
					/>{/if}
				{#if cr.brouillon}<Badge teinte="badge-gray" compact>Brouillon</Badge>{/if}
				{#if cr.conseil_seul}<Badge teinte="badge-purple" compact>{LIBELLE_CS_ET_PRESENTS}</Badge
					>{/if}
				{#if cr.etat_cible}<Badge teinte="badge-blue" compact title="À la validation"
						>→ {statutTicketLabel(cr.etat_cible)}</Badge
					>{/if}
				{#if marque}<Badge teinte="badge-orange" compact>{marque}</Badge>{/if}
			</p>
			<div class="contenu">{@html safeHtml(cr.contenu)}</div>
		</article>
	{:else}
		<p class="vide">Aucune affaire n’a encore de compte rendu.</p>
	{/each}

	{#if compteRendu.non_traitees.length}
		<h4 class="partie">Non traitées · {compteRendu.non_traitees.length}</h4>
		<p class="non-traitees">
			{#each compteRendu.non_traitees as a, i (a.id)}{i ? ' · ' : ''}<a href={lienTicket(a.id)}
					>{a.numero}</a
				>
				{a.titre}{/each}
		</p>
	{/if}
</section>

<style>
	.tete {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.tete h3 {
		margin: 0;
	}
	.badges {
		display: inline-flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
	.partie {
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin: 1rem 0 0.35rem;
	}
	.quand,
	.presents,
	.non-traitees,
	.vide {
		margin: 0 0 0.25rem;
		font-size: var(--fs-sm);
	}
	.groupe {
		font-weight: 600;
	}
	.precision,
	.vide {
		color: var(--color-text-muted);
	}
	.abordee {
		padding: 0.5rem 0;
		border-top: 1px solid var(--color-border);
	}
	.titre {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		margin: 0 0 0.25rem;
		font-weight: 600;
	}
	.titre a {
		color: var(--color-text);
	}
	.contenu {
		font-size: var(--fs-sm);
	}
	.contenu :global(p) {
		margin: 0 0 0.35rem;
	}
</style>
