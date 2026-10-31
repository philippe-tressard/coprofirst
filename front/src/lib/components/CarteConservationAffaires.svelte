<!--
  **Conservation des affaires** (#2014), dans Administration › Maintenance — le
  CONSTAT de ce qui partira, et quand (lot L1), et ce qui est parti (L2, L3).

  Une affaire close est gardée un nombre d'exercices complets selon sa catégorie
  (10 pour les travaux et sinistres, 5 pour les pannes et l'entretien, 2 pour les
  actualités et les questions) ; à l'échéance, elle perdra ses pièces jointes,
  archivées sur le PC, et ses auteurs, et gardera son texte. La règle vit au
  serveur (`utils/conservation_affaires`) ; cet écran ne recalcule rien.

  Rien n'est retiré tant que l'administrateur n'a pas coché « Conservation des
  affaires » dans Administration › Services (lot L2) — la case ne se coche que
  là, l'écran le dit et y renvoie. Les archives produites sont listées avec leur
  copie sur le PC (lot L3) : le serveur retire la sienne 30 jours après.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import EtatListe from './EtatListe.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { conservation, type ConstatConservation } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { fmtDate, fmtDatetime } from '#lib/date.ts';
	import { fmtNombre, fmtOctets } from '#lib/utils.ts';
	import { LIBELLE_TACHE } from '#lib/taches.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

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
	$: archives = constat?.archives ?? [];

	/** « (1 absente du disque) » — une référence en base sans fichier, dite et non pesée. */
	function absentes(n: number): string {
		return n ? ` (${fmtNombre(n)} ${n > 1 ? 'absentes' : 'absente'} du disque)` : '';
	}
	/** Les durées et leur fondement, une ligne par type rencontré. */
	$: fondements = [...new Map(echeances.map((e) => [e.type, e])).values()];
</script>

<section class="card config-section" id="conservation-affaires">
	<SectionFormulaire titre={LIBELLE_TACHE.conservation_affaires} icone="archive" />
	<p class="muted">
		Une affaire close est gardée un nombre d’exercices complets selon sa catégorie. À l’échéance,
		elle perdra ses pièces jointes, archivées sur le PC, et ses auteurs&nbsp;; son texte restera, et
		le carnet d’entretien avec lui.
	</p>
	{#if constat}
		<p class="aide">
			{#if constat.application_active}
				Appliquée chaque nuit&nbsp;: une affaire échue perd ses pièces jointes, archivées puis
				copiées sur le PC par la sauvegarde hors site, et ses auteurs.
			{:else}
				Constat seul&nbsp;: rien n’est archivé ni retiré tant que «&nbsp;Conservation des
				affaires&nbsp;» n’est pas activée dans
				<a href="/admin?onglet=services">Administration › Services</a>.
			{/if}
			L’exercice {constat.mois_debut_exercice
				? 'suit le mois de début de la fiche copropriété'
				: 'est l’année civile'}.
		</p>
		{#if constat.application_active}
			{#if constat.politique_annonce}
				<p class="aide">La politique de confidentialité annonce ces durées.</p>
			{:else}
				<div class="alert alert-error" role="alert">
					La politique de confidentialité n’annonce pas ces durées&nbsp;: son texte a été modifié.
					Ajoutez la phrase à la rubrique «&nbsp;Durée de conservation&nbsp;» avant la première
					échéance.
				</div>
			{/if}
		{/if}
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
								{fmtNombre(e.fichiers)}{SEPARATEUR.point}{fmtOctets(e.octets)}<span class="muted"
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
					<strong>{f.libelle}</strong>&nbsp;: {fmtNombre(f.exercices)} exercices après la clôture{SEPARATEUR.tiret}{f.fondement}.
				</li>
			{/each}
		</ul>
	</EtatListe>

	{#if archives.length}
		<SectionFormulaire titre="Archives produites" icone="archive" />
		<p class="aide">
			Le serveur garde une archive {fmtNombre(constat?.delai_retrait_jours)} jours après sa copie sur
			le PC, puis la retire&nbsp;; le PC les garde toutes.
		</p>
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr>
						<th>Archive</th>
						<th class="nombre">Affaires</th>
						<th class="nombre">Pièces jointes</th>
						<th>Produite le</th>
						<th>Sur le PC</th>
					</tr>
				</thead>
				<tbody>
					{#each archives as a (a.id)}
						<tr>
							<td>
								{a.libelle}{SEPARATEUR.point}{a.exercice}
								{#if !a.retiree_le}
									<a class="telecharger" href={conservation.archiveUrl(a.id)} download={a.nom}
										>Télécharger</a
									>
								{/if}
							</td>
							<td class="nombre">{fmtNombre(a.affaires)}</td>
							<td class="nombre">{fmtNombre(a.fichiers)}{SEPARATEUR.point}{fmtOctets(a.octets)}</td>
							<td>{fmtDatetime(a.cree_le)}</td>
							<td>
								{#if a.copiee_le}
									Copiée le {fmtDate(a.copiee_le)}{#if a.retiree_le}<span class="muted"
											>{SEPARATEUR.point}retirée du serveur</span
										>{/if}
								{:else}
									<span class="muted">En attente de la sauvegarde hors site</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</section>

<style>
	.nombre {
		text-align: right;
		white-space: nowrap;
	}
	.fondements {
		padding-left: 1.1rem;
	}
	.telecharger {
		margin-left: 0.4rem;
	}
</style>
