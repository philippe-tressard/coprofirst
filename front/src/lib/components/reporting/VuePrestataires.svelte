<!--
  Reporting CS — **synthèse prestataires** : le tableau des prestataires actifs,
  et la fiche détaillée de celui qu'on ouvre (notations, contrats).

  Extrait d'`espace-cs/+page.svelte` avec #453. Seule vue à faire un appel réseau
  de son côté : la fiche de synthèse se charge à la demande, prestataire par
  prestataire — les charger toutes d'avance n'aurait aucun sens.
-->
<script lang="ts">
	import { nomAffiche } from '#lib/noms.ts';
	//  ⚠️ Cet écran affichait la valeur BRUTE — `chauffage_collectif` — parce que
	//  la table des libellés vivait dans `prestataires/+page.svelte` et qu'il n'y
	//  avait pas accès. Une table qui vit dans UN écran, les autres s'en passent.
	import { equipLabel, typePrestataireLabel } from '#lib/prestataires.ts';
	import { prestataires as prestApi, type SynthesePrestataire } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { fmtDate } from '#lib/date.ts';
	import NoteEtoiles from '#lib/components/NoteEtoiles.svelte';
	import { type ReportPrestataire } from '#lib/reporting.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	export let reportPrestataires: ReportPrestataire[] = [];

	let reportPrestSynth: SynthesePrestataire | null = null;
	let reportPrestSynthLoading = false;

	async function loadPrestSynthese(prestId: number) {
		reportPrestSynthLoading = true;
		try {
			reportPrestSynth = await prestApi.synthese(prestId);
		} catch {
			toast('error', 'Erreur chargement synthèse');
			reportPrestSynth = null;
		} finally {
			reportPrestSynthLoading = false;
		}
	}
</script>

<!-- ── Synthèse prestataires ─────────────────────────────────────────── -->
<div class="kpi-row bloc-espace">
	<div class="kpi-card">
		<div class="kpi-value">{reportPrestataires.length}</div>
		<div class="kpi-label">Prestataires actifs</div>
	</div>
</div>
<div class="report-table-wrap bloc-espace-large">
	<table class="report-table">
		<thead>
			<tr>
				<th>Prestataire</th>
				<th>Équipement</th>
				<th>Catégorie</th>
				<th>Actions</th>
			</tr>
		</thead>
		<tbody>
			{#each reportPrestataires as p (p.id)}
				<tr>
					<td><strong>{p.nom}</strong></td>
					<td>{equipLabel(p.specialite)}</td>
					<td>{typePrestataireLabel(p.type_prestataire)}</td>
					<td
						><button class="btn btn-sm btn-outline" on:click={() => loadPrestSynthese(p.id)}
							>Fiche synthèse</button
						></td
					>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<!-- Fiche synthèse prestataire (modale inline) -->
{#if reportPrestSynthLoading}
	<EtatListe chargement messageChargement="Chargement synthèse…" />
{:else if reportPrestSynth}
	<section class="report-card bloc-espace-large">
		<div class="entete-fiche">
			<h3 class="titre-fiche">&#x1F4C4; Fiche — {reportPrestSynth.nom}</h3>
			<button class="btn btn-sm btn-outline" on:click={() => (reportPrestSynth = null)}
				>✕ Fermer</button
			>
		</div>
		<div class="report-grid-2 bloc-espace">
			<div>
				<p><strong>Équipement :</strong> {equipLabel(reportPrestSynth.specialite)}</p>
				<p>
					<strong>Catégorie :</strong>
					{typePrestataireLabel(reportPrestSynth.type_prestataire)}
				</p>
				{#if reportPrestSynth.email}<p><strong>Email :</strong> {reportPrestSynth.email}</p>{/if}
				{#if reportPrestSynth.contacts && reportPrestSynth.contacts.length > 0}
					<p><strong>Contacts :</strong></p>
					{#each reportPrestSynth.contacts as c (c)}
						<p class="retrait">
							📞 {c.telephone ?? '—'}{#if c.prenom || c.nom}&nbsp;— {nomAffiche(
									c,
								)}{/if}{#if c.fonction}&nbsp;({c.fonction}){/if}{#if c.email}&nbsp;· {c.email}{/if}
						</p>
					{/each}
				{/if}
			</div>
			<div>
				<p><strong>Contrats actifs :</strong> {reportPrestSynth.nb_contrats}</p>
				<p>
					<strong>Note moyenne :</strong>
					{#if reportPrestSynth.note_moyenne != null}
						<NoteEtoiles
							note={reportPrestSynth.note_moyenne}
							nbAvis={reportPrestSynth.nb_notations}
							surCinq
						/>
						<span class="text-muted-sm">({reportPrestSynth.nb_notations} avis)</span>
					{:else}
						Aucune notation
					{/if}
				</p>
				{#if reportPrestSynth.prochaines_visites && reportPrestSynth.prochaines_visites.length > 0}
					<p><strong>Prochaines visites :</strong></p>
					{#each reportPrestSynth.prochaines_visites as v (v)}
						<p class="retrait">📅 {fmtDate(v.date)} — {v.contrat}</p>
					{/each}
				{/if}
			</div>
		</div>
		{#if reportPrestSynth.notations && reportPrestSynth.notations.length > 0}
			<h4 class="sous-titre-fiche">Historique des notations</h4>
			<div class="report-table-wrap">
				<table class="report-table compact">
					<thead><tr><th>Date</th><th>Note</th><th>Commentaire</th><th>Par</th></tr></thead>
					<tbody>
						{#each reportPrestSynth.notations as n (n)}
							<tr>
								<td>{fmtDate(n.cree_le)}</td>
								<!--  🔴 Cette cellule colorait TOUTE note en orange — un 1/5 y
								      paraissait comme un 3,5. La teinte est censée dire d’un coup
								      d’œil si l’on est content de quelqu’un ; là, elle mentait. -->
								<td><NoteEtoiles note={n.note} surCinq /></td>
								<td>{n.commentaire ?? '—'}</td>
								<td>{n.auteur_nom}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
		{#if reportPrestSynth.contrats && reportPrestSynth.contrats.length > 0}
			<h4 class="sous-titre-fiche">Contrats</h4>
			<div class="report-table-wrap">
				<table class="report-table compact">
					<thead
						><tr><th>Libellé</th><th>Équipement</th><th>Début</th><th>Prochaine visite</th></tr
						></thead
					>
					<tbody>
						{#each reportPrestSynth.contrats as c (c)}
							<tr>
								<td>{c.libelle}</td>
								<td>{equipLabel(c.type_equipement)}</td>
								<td>{fmtDate(c.date_debut)}</td>
								<td>{c.prochaine_visite ? fmtDate(c.prochaine_visite) : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>
{/if}

<style>
	.bloc-espace {
		margin-bottom: 1rem;
	}
	.bloc-espace-large {
		margin-bottom: 1.5rem;
	}
	.entete-fiche {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
	}
	.titre-fiche {
		margin: 0;
	}
	.retrait {
		margin-left: 1rem;
	}
	.sous-titre-fiche {
		font-size: var(--fs-base);
		font-weight: 600;
		margin: 1rem 0 0.5rem;
	}
</style>
