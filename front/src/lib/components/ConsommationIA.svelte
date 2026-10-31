<!--
  Ce que l'assistant IA a **consommé** — jetons, appels, échecs, refus, coût
  estimé — par mois, usage et modèle (#1383).

  🔴 Pourquoi. L'assistant a un usage AUTOMATIQUE (les réponses du syndic par
  courriel, relevées toutes les dix minutes) et rien ne comptait ses appels. Une
  boucle aurait facturé en silence jusqu'à la facture du fournisseur.

  ⚠️ Le coût est une ESTIMATION au tarif saisi dans Administration › Assistant IA,
  en DOLLARS comme les grilles des fournisseurs (30/09/2026), et il se tait sans
  tarif — un « 0 $ » se lirait « gratuit ». Les réglages
  (prix, limites d'appels) restent dans l'onglet de l'assistant ; cette carte ne fait que
  montrer, là où l'on vient surveiller.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { onMount } from 'svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import EtatListe from './EtatListe.svelte';
	import {
		config as configApi,
		type ConsommationIA,
		type LigneConsommationIA,
	} from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { fmtMonthYear } from '#lib/date.ts';
	import { fmtMontant, fmtNombre } from '#lib/utils.ts';

	let donnees: ConsommationIA | null = null;
	let chargement = true;
	let erreur = '';

	const jetons = (l: LigneConsommationIA) => l.jetons_entree + l.jetons_sortie;
	//  Le coût d'un mois n'existe que si CHAQUE ligne en a un : additionner les
	//  lignes chiffrées en taisant les autres afficherait un total faux.
	function coutDuMois(lignes: LigneConsommationIA[]): number | null {
		if (!lignes.length || lignes.some((l) => l.cout_usd === null)) return null;
		return lignes.reduce((s, l) => s + Number(l.cout_usd), 0);
	}
	const dollars = (v: number) => fmtMontant(v, 'USD');
	const part = (appels: number, limite: number) =>
		Math.min(100, Math.round((appels / limite) * 100));

	onMount(async () => {
		try {
			donnees = await configApi.llmConsommation();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});
</script>

<section class="card config-section">
	<SectionFormulaire titre="Consommation de l’assistant IA" icone="bar-chart-3" />
	<p class="muted config-section-intro">
		Chaque appel au fournisseur, compté en jetons{SEPARATEUR.tiret}la question envoyée et la réponse
		produite. Le coût est estimé au tarif saisi pour chaque usage dans
		<strong>Assistant IA</strong>, où se règlent aussi ses <strong>limites d’appels</strong>, par
		mois et par heure&nbsp;: atteintes, l’appel est refusé avant tout envoi, et le contrôle de
		6&nbsp;h signale la limite du mois. Aucune question ni réponse n’est conservée.
	</p>

	<EtatListe
		{chargement}
		{erreur}
		vide={!donnees?.mois.length}
		titreErreur="Impossible d’afficher la consommation"
		titreVide="Aucun appel enregistré"
		messageVide="Le compte commence au premier appel à l’assistant après cette mise à jour."
	>
		{#if donnees}
			{@const limitees = donnees.limites.filter((l) => l.appels_mois > 0)}
			{#if limitees.length}
				<h4 class="sous-titre">Limites de {fmtMonthYear(donnees.mois_courant)}</h4>
				<ul class="limites">
					{#each limitees as l (l.usage)}
						<li>
							<span>{l.libelle}</span>
							<span class="muted"
								>{fmtNombre(l.appels)} / {fmtNombre(l.appels_mois)} appels ({part(
									l.appels,
									l.appels_mois,
								)}&nbsp;%)</span
							>
							<span
								class="jauge"
								role="progressbar"
								aria-label="Limite du mois de {l.libelle}"
								aria-valuemin="0"
								aria-valuemax="100"
								aria-valuenow={part(l.appels, l.appels_mois)}
							>
								<span
									class="jauge-plein"
									class:jauge-alerte={part(l.appels, l.appels_mois) >= 80}
									style="width:{part(l.appels, l.appels_mois)}%"
								></span>
							</span>
						</li>
					{/each}
				</ul>
			{/if}

			{#each donnees.mois as m (m.mois)}
				{@const cout = coutDuMois(m.usages)}
				<div class="mois">
					<h4 class="sous-titre">
						<span class="mois-libelle">{fmtMonthYear(m.mois)}</span>
						<span class="muted total"
							>{cout === null ? 'coût non renseigné' : `${dollars(cout)} estimés`}</span
						>
					</h4>
					<ul class="lignes">
						{#each m.usages as l (l.usage + l.modele)}
							<li>
								<strong>{l.libelle}</strong>
								<span class="muted">{l.modele}</span>
								<span>
									{fmtNombre(l.appels)} appel{l.appels > 1 ? 's' : ''}{SEPARATEUR.point}{fmtNombre(
										jetons(l),
									)} jetons
									<span class="muted"
										>({fmtNombre(l.jetons_entree)} envoyés{l.jetons_cache
											? ` dont ${fmtNombre(l.jetons_cache)} en cache`
											: ''}, {fmtNombre(l.jetons_sortie)} produits)</span
									>
									{#if l.cout_usd !== null}{SEPARATEUR.point}{dollars(Number(l.cout_usd))}{/if}
								</span>
								{#if l.erreurs}<span class="badge badge-red">{fmtNombre(l.erreurs)} en échec</span
									>{/if}
								{#if l.refus}<span class="badge badge-orange"
										>{fmtNombre(l.refus)} refusé{l.refus > 1 ? 's' : ''} à la limite</span
									>{/if}
							</li>
						{/each}
					</ul>
				</div>
			{/each}
		{/if}
	</EtatListe>
</section>

<style>
	.sous-titre {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.25rem 0.6rem;
		margin: 0 0 0.4rem;
		font-size: var(--fs-base);
	}
	/*  « septembre 2026 » → « Septembre 2026 » en tête de mois seulement : un
	    `capitalize` sur le titre mettait une capitale à chaque mot. */
	.mois-libelle {
		display: inline-block;
	}
	.mois-libelle::first-letter {
		text-transform: uppercase;
	}
	.total {
		font-weight: 400;
		font-size: var(--fs-sm);
	}
	.mois + .mois,
	.limites + .mois {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}
	.limites,
	.lignes {
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--fs-md);
	}
	.limites li,
	.lignes li {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.2rem 0.6rem;
		margin-bottom: 0.5rem;
		overflow-wrap: anywhere;
	}
	.jauge {
		flex-basis: 100%;
		height: 6px;
		border-radius: 3px;
		background: var(--color-border);
		overflow: hidden;
	}
	.jauge-plein {
		display: block;
		height: 100%;
		background: var(--color-primary);
	}
	.jauge-alerte {
		background: var(--color-warning);
	}
</style>
