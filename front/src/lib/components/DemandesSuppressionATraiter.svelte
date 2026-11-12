<!--
  La file des **demandes de suppression de compte** (#2699), dans l'onglet « À
  traiter » de l'administration.

  Traiter, c'est effacer le compte par la purge de l'administration — le geste de
  `DELETE /admin/utilisateurs/{id}`, définitif : il se confirme. En démonstration,
  l'API traite la demande sans effacer, et l'annonce le dit.

  La liste arrive liée depuis la page (`bind:demandes`) : la pastille de l'onglet
  l'additionne dès l'ouverture de l'administration, comme les trois autres files.
-->
<script lang="ts">
	import { suppressionCompte, type DemandeSuppressionEnAttente } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { fmtDatetimeShort as fmt } from '#lib/date.ts';

	export let demandes: DemandeSuppressionEnAttente[] = [];

	async function traiter(d: DemandeSuppressionEnAttente) {
		const ok = await confirmer({
			titre: 'Supprimer le compte',
			message:
				`Le compte de ${d.utilisateur_nom} et ses données personnelles seront effacés ` +
				'définitivement ; ses contributions collectives restent, sans son nom.',
			libelleConfirmer: 'Supprimer le compte',
			danger: true,
		});
		if (!ok) return;
		try {
			const { annonce } = await suppressionCompte.traiter(d.id);
			toast(annonce.ton, annonce.texte);
			demandes = demandes.filter((x) => x.id !== d.id);
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}
</script>

<div class="card">
	<table class="table">
		<thead>
			<tr><th>Résident</th><th>Motif</th><th>Demandée le</th><th>Actions</th></tr>
		</thead>
		<tbody>
			{#each demandes as d (d.id)}
				<tr>
					<td>
						<div class="demandeur">{d.utilisateur_nom}</div>
						<div class="text-muted-sm">{d.utilisateur_email ?? ''}</div>
					</td>
					<td class="motif-demande">{d.motif ?? '—'}</td>
					<td class="text-muted-md">{fmt(d.cree_le)}</td>
					<td>
						<button type="button" class="btn btn-sm btn-danger" on:click={() => traiter(d)}>
							Supprimer le compte
						</button>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.demandeur {
		font-weight: 600;
	}
	.motif-demande {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		max-width: 180px;
		white-space: pre-wrap;
	}
</style>
