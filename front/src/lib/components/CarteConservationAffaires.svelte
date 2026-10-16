<!--
  **Conservation des affaires** (#2014), dans Administration › Maintenance — le
  CONSTAT de ce qui partira, et quand (lot L1).

  Une affaire close est gardée un nombre d'exercices complets selon sa catégorie
  (10 pour les travaux et sinistres, 5 pour les pannes et l'entretien, 2 pour les
  actualités et les questions) ; à l'échéance, elle perdra ses pièces jointes,
  archivées sur le PC, et ses auteurs, et gardera son texte. La règle vit au
  serveur (`utils/conservation_affaires`) ; cet écran ne recalcule rien.

  Rien n'est retiré tant que le lot suivant n'est pas livré et que
  l'administrateur n'a pas coché la case qui l'applique : l'écran le dit.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import EtatListe from './EtatListe.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { conservation, type ConstatConservation } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { fmtDate } from '$lib/date';
	import { fmtNombre, fmtOctets } from '$lib/utils';

	let constat: ConstatConservation | null = null;
	let chargement = true;
	let erreur = '';

	onMount(async () => {
		try {
			constat = await conservation.constat();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});

	$: echeances = constat?.echeances ?? [];

	/** « (1 absente du disque) » — une référence en base sans fichier, dite et non pesée. */
	function absentes(n: number): string {
		return n ? ` (${fmtNombre(n)} ${n > 1 ? 'absentes' : 'absente'} du disque)` : '';
	}
	/** Les durées et leur fondement, une ligne par type rencontré. */
	$: fondements = [...new Map(echeances.map((e) => [e.type, e])).values()];
</script>

<section class="card config-section" id="conservation-affaires">
	<SectionFormulaire titre="Conservation des affaires" icone="archive" />
	<p class="muted">
		Une affaire close est gardée un nombre d’exercices complets selon sa catégorie. À l’échéance,
		elle perdra ses pièces jointes, archivées sur le PC, et ses auteurs&nbsp;; son texte restera, et
		le carnet d’entretien avec lui.
	</p>
	{#if constat && !constat.application_active}
		<p class="aide">
			Constat seul&nbsp;: rien n’est archivé ni retiré pour l’instant. L’exercice
			{constat.mois_debut_exercice
				? 'suit le mois de début de la fiche copropriété'
				: 'est l’année civile'}.
		</p>
	{/if}

	<EtatListe
		{chargement}
		{erreur}
		vide={echeances.length === 0}
		titreVide="Aucune affaire close"
		messageVide="Aucune affaire close n’a encore d’échéance."
	>
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr>
						<th>Échéance</th>
						<th>Type</th>
						<th>Closes en</th>
						<th class="nombre">Affaires</th>
						<th class="nombre">Pièces jointes</th>
					</tr>
				</thead>
				<tbody>
					{#each echeances as e (e.type + e.exercice_cloture)}
						<tr>
							<td>{fmtDate(e.echoit_le)}</td>
							<td>{e.libelle}</td>
							<td>{e.exercice_cloture}</td>
							<td class="nombre">{fmtNombre(e.affaires)}</td>
							<td class="nombre">
								{fmtNombre(e.fichiers)} · {fmtOctets(e.octets)}<span class="muted"
									>{absentes(e.absents)}</span
								>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<ul class="aide fondements">
			{#each fondements as f (f.type)}
				<li>
					<strong>{f.libelle}</strong>&nbsp;: {f.exercices} exercices après la clôture —
					{f.fondement}.
				</li>
			{/each}
		</ul>
	</EtatListe>
</section>

<style>
	.nombre {
		text-align: right;
		white-space: nowrap;
	}
	.fondements {
		padding-left: 1.1rem;
	}
</style>
