<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { confirmer, SUPPRESSION } from '#lib/confirmation.ts';
	import { onMount } from 'svelte';
	import { admin as adminApi, type LienCompteLot } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { siteNomStore } from '#lib/stores/pageConfig.ts';
	import BauxSansLocataire from '#lib/components/BauxSansLocataire.svelte';
	import ReclassementTickets from '#lib/components/ReclassementTickets.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import ChampRecherche from '#lib/components/ChampRecherche.svelte';
	import { contientTousLesMots } from '#lib/texte.ts';

	$: _siteNom = $siteNomStore;

	let rows: LienCompteLot[] = [];
	let loading = true;
	let filtre = '';
	let deletingUserId: number | null = null;

	async function charger() {
		loading = true;
		try {
			rows = await adminApi.auditUserLots();
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur chargement'));
		} finally {
			loading = false;
		}
	}

	async function supprimer(ul: LienCompteLot) {
		if (
			!(await confirmer(
				SUPPRESSION(
					`L'association de « ${ul.user_nom} » au lot ${ul.lot_numero} (${ul.batiment}).`,
				),
			))
		)
			return;
		try {
			await adminApi.supprimerUserLot(ul.user_lot_id);
			toast('success', 'Association supprimée');
			rows = rows.filter((r) => r.user_lot_id !== ul.user_lot_id);
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur suppression'));
		}
	}

	async function supprimerToutesPourUtilisateur(g: {
		user_id: number;
		user_nom: string;
		lots: LienCompteLot[];
	}) {
		if (!g.lots.length) return;
		if (
			!(await confirmer(
				SUPPRESSION(`${g.lots.length} association(s) de « ${g.user_nom} » à ses lots.`),
			))
		)
			return;
		deletingUserId = g.user_id;
		try {
			const results = await Promise.allSettled(
				g.lots.map((ul) => adminApi.supprimerUserLot(ul.user_lot_id)),
			);
			const ok = results.filter((r) => r.status === 'fulfilled').length;
			const ko = results.length - ok;
			if (ok > 0) {
				const idsToDelete = new Set<number>();
				results.forEach((r, idx) => {
					if (r.status === 'fulfilled') idsToDelete.add(g.lots[idx].user_lot_id);
				});
				rows = rows.filter((r) => !idsToDelete.has(r.user_lot_id));
			}
			if (ko === 0) {
				toast('success', `${ok} association(s) supprimée(s)`);
			} else {
				// Rechargement pour garder un état cohérent si suppression partielle.
				await charger();
				toast('error', `${ko} suppression(s) en échec (${ok} réussie(s))`);
			}
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur suppression en masse'));
		} finally {
			deletingUserId = null;
		}
	}

	$: grouped = (() => {
		const map = new Map<
			number,
			{ user_id: number; user_nom: string; user_statut: string; lots: LienCompteLot[] }
		>();
		for (const r of filtered) {
			if (!map.has(r.user_id))
				map.set(r.user_id, {
					user_id: r.user_id,
					user_nom: r.user_nom,
					user_statut: r.user_statut,
					lots: [],
				});
			map.get(r.user_id)!.lots.push(r);
		}
		return [...map.values()].sort((a, b) => a.user_nom.localeCompare(b.user_nom));
	})();

	$: filtered = rows.filter((r) =>
		contientTousLesMots([r.user_nom, r.lot_numero, r.batiment], filtre),
	);

	onMount(charger);
</script>

<svelte:head><title>Audit associations lots — {_siteNom}</title></svelte:head>

<p class="intro">
	Liste toutes les associations utilisateur ↔ lot actives. Permet de repérer et supprimer les
	affectations erronées (faux positifs de l'auto-match).
</p>

<div class="barre-filtre">
	<ChampRecherche
		id="audit-lots-recherche"
		bind:valeur={filtre}
		placeholder="Nom, lot ou bâtiment…"
		dans="nom du compte, n° de lot et bâtiment"
	>
		<span class="compte"
			>{filtered.length} association{filtered.length > 1 ? 's' : ''} — {grouped.length} utilisateur{grouped.length >
			1
				? 's'
				: ''}</span
		>
	</ChampRecherche>
</div>

{#if loading}
	<EtatListe chargement />
{:else if grouped.length === 0}
	<p class="muted">Aucune association trouvée.</p>
{:else}
	{#each grouped as g (g.user_id)}
		<div class="card carte-compte">
			<div class="entete-compte">
				<strong>{g.user_nom}</strong>
				<span class="badge badge-gray statut-compte">{g.user_statut}</span>
				<span class="nb-lots"
					>{SEPARATEUR.tiret}{g.lots.length} lot{g.lots.length > 1 ? 's' : ''}</span
				>
				<button
					class="btn btn-sm btn-outline suppr-tout"
					disabled={deletingUserId === g.user_id}
					on:click={() => supprimerToutesPourUtilisateur(g)}
				>
					{deletingUserId === g.user_id
						? 'Suppression…'
						: `Supprimer les ${g.lots.length} associations`}
				</button>
			</div>
			<table class="table table-lots">
				<colgroup
					><col class="col-25" /><col class="col-20" /><col class="col-20" /><col
						class="col-20"
					/><col class="col-15" /></colgroup
				>
				<thead><tr><th>Lot</th><th>Type lot</th><th>Bâtiment</th><th>Lien</th><th></th></tr></thead>
				<tbody>
					{#each g.lots as ul (ul.user_lot_id)}
						<tr>
							<td class="texte-code">{ul.lot_numero}</td>
							<td>{ul.lot_type}</td>
							<td>{ul.batiment}</td>
							<td><span class="badge badge-blue">{ul.type_lien}</span></td>
							<td class="cellule-action">
								<button
									class="btn-icon-danger"
									aria-label="Supprimer cette association"
									title="Supprimer cette association"
									on:click={() => supprimer(ul)}><IconeAction icone="trash-2" /></button
								>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/each}
{/if}

<!--  🔴 Le relevé des baux non rattachés vient APRÈS les associations user↔lot
      (#808) : les deux disent « qui est relié à quoi », et cet onglet est
      l'endroit où l'on vient poser cette question. En faire un onglet séparé
      aurait dispersé la même intention sur deux écrans.

      ⚠️ Ce sont bien DEUX notions : `UserLot` relie un compte à un LOT, le bail
      relie un compte à un CONTRAT. Un locataire peut avoir l'un sans l'autre —
      c'est justement ce que ce relevé donne à voir. -->
<BauxSansLocataire />

<!--  Le second relevé de cet onglet, et le même parti pris : il PROPOSE, il
      n'écrit rien. Voir son en-tête pour le pourquoi. -->
<ReclassementTickets />

<style>
	.intro {
		color: var(--color-text-muted);
		font-size: var(--fs-base);
		margin: 0 0 1rem;
	}
	.barre-filtre {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}
	.compte {
		color: var(--color-text-muted);
		font-size: var(--fs-md);
	}
	.carte-compte {
		margin-bottom: 0.75rem;
		padding: 0.75rem 1rem;
	}
	.entete-compte {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.4rem;
	}
	.statut-compte {
		font-size: var(--fs-xs);
	}
	.nb-lots {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.suppr-tout {
		margin-left: auto;
	}
	.table-lots {
		table-layout: fixed;
		width: 100%;
		margin: 0;
	}
	.col-25 {
		width: 25%;
	}
	.col-20 {
		width: 20%;
	}
	.col-15 {
		width: 15%;
	}
	.cellule-action {
		text-align: right;
	}
</style>
