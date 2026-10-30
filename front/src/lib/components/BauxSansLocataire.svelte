<!--
  **Les baux dont aucun compte locataire n'est rattaché** — le moyen d'observer.

  ## 🔴 Pourquoi ce relevé, et pourquoi PAS de bouton (#808, 07/09/2026)

  Le rattachement d'un compte locataire à son bail est automatique, et il se fait
  sur l'**e-mail exact** (`_auto_match_baux_locataire`). Il échoue dès que le bail
  porte une autre adresse, ou aucune — et surtout quand le bail est créé **après**
  l'inscription, puisque le rapprochement n'a lieu qu'à la validation du compte.

  ⚠️ Et il échoue **en silence**. Côté locataire, cela se voit ainsi : son compte
  est actif, mais il ne voit ni son lot, ni ses badges, ni sa fiche de location.

  Arbitrage du 06/09/2026, en réponse à « faut-il livrer un geste de rattachement
  manuel ? » : **garder et observer** — on ne sait pas si le cas se présente.

  🔴 **Ce relevé répond à cette question, et rien de plus.** Il n'y a
  volontairement **aucun bouton de rattachement**, alors que l'endpoint existe
  (`POST /admin/baux/{id}/lier-locataire/{user}`, retiré le 13/09/2026 après
  observation) et qu'il aurait coûté trois
  lignes. Livrer le geste ici aurait contourné la décision au motif que c'eût été
  plus pratique — or la décision portait exactement là-dessus. Si le relevé
  montre des cas, le bouton est à un lot de distance.

  ## Deux catégories, et les confondre ferait crier sur le cas normal

  | Catégorie | Ce que c'est |
  |---|---|
  | **rattachement manquant** | un compte existe au nom du locataire — c'est le cas rattrapable |
  | **pas de compte** | personne ne s'est inscrit sous ce nom : c'est **normal**, un locataire n'est pas tenu d'utiliser le site |

  Un relevé qui mêlerait les deux serait bruyant, donc désarmé en trois jours.
  La catégorie est calculée **côté serveur**, une fois : la laisser à l'écran en
  ferait une seconde règle, et deux vues du même relevé pourraient ranger le même
  bail dans deux cases.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { onMount } from 'svelte';
	import { admin as adminApi, type BailSansLocataire } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { fmtDate } from '#lib/date.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	let lignes: BailSansLocataire[] = [];
	let chargement = true;
	/**  Non vide = on n'a PAS pu regarder. Un relevé vide se lirait « tout est
	 *   rattaché », ce qui serait faux et rassurant (`standards/04`). */
	let erreur = '';

	onMount(async () => {
		try {
			lignes = await adminApi.bauxSansLocataire();
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			chargement = false;
		}
	});

	$: manquants = lignes.filter((l) => l.categorie === 'compte_probable');
	$: sansCompte = lignes.filter((l) => l.categorie === 'sans_compte');
</script>

<section class="card bsl-carte">
	<div class="section-header">
		<h2 class="section-title">Baux sans compte locataire rattaché</h2>
	</div>

	<p class="bsl-aide">
		Le rattachement se fait automatiquement sur l’<strong>adresse e-mail</strong> du bail. Il échoue quand
		le locataire s’inscrit avec une autre adresse, ou quand le bail est créé après son inscription — et
		il échoue sans rien dire. Ce relevé est là pour le voir.
	</p>

	<EtatListe
		{chargement}
		{erreur}
		vide={lignes.length === 0}
		titreErreur="Impossible d’afficher les baux"
		titreVide="Tous les baux en cours ont leur locataire rattaché"
		messageVide="Rien à signaler."
	>
		{#if manquants.length}
			<p class="bsl-titre-groupe">
				<strong
					>{manquants.length} rattachement{manquants.length > 1 ? 's' : ''} manquant{manquants.length >
					1
						? 's'
						: ''}</strong
				>
				— un compte existe à ce nom, mais il n’est pas lié au bail.
			</p>
			<div class="table-wrap">
				<table class="table bsl-table">
					<thead>
						<tr>
							<th>Locataire du bail</th>
							<th>Lot</th>
							<th>Entrée</th>
							<th>Compte trouvé</th>
						</tr>
					</thead>
					<tbody>
						{#each manquants as l (l.bail_id)}
							<tr>
								<td>
									{l.locataire_nom}
									{#if l.locataire_email}<br /><span class="bsl-mail">{l.locataire_email}</span
										>{/if}
								</td>
								<td
									>{l.lot}{#if l.batiment !== '—'}{SEPARATEUR.point}{l.batiment}{/if}</td
								>
								<td>{fmtDate(l.date_entree)}</td>
								<td>
									{#each l.candidats as c (c.id)}
										<div>{c.nom} <span class="bsl-mail">{c.email}</span></div>
									{/each}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

		{#if sansCompte.length}
			<p class="bsl-titre-groupe bsl-normal">
				<strong>{sansCompte.length} locataire{sansCompte.length > 1 ? 's' : ''} sans compte</strong>
				— personne ne s’est inscrit sous ce nom. C’est la situation ordinaire, rien à corriger.
			</p>
			<div class="table-wrap">
				<table class="table bsl-table">
					<thead>
						<tr><th>Locataire du bail</th><th>Lot</th><th>Entrée</th></tr>
					</thead>
					<tbody>
						{#each sansCompte as l (l.bail_id)}
							<tr>
								<td>{l.locataire_nom}</td>
								<td
									>{l.lot}{#if l.batiment !== '—'}{SEPARATEUR.point}{l.batiment}{/if}</td
								>
								<td>{fmtDate(l.date_entree)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</EtatListe>
</section>

<style>
	/*  `.section` n'est pas globale : elle vit dans les écrans qui la définissent,
	    scopée à eux. Le padding est donc posé ici, avec la carte qui le porte
	    (`standards/02` §4 ter). */
	.bsl-carte {
		padding: 1.25rem;
		margin-top: 1.5rem;
	}
	.bsl-aide {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0 0 1rem;
	}
	.bsl-titre-groupe {
		font-size: var(--fs-base);
		margin: 1rem 0 0.5rem;
	}
	/*  Le groupe « normal » est atténué : il ne demande aucune action, et le
	    présenter comme le premier ferait lire un relevé de 12 lignes là où il n'y
	    a qu'un cas à traiter. */
	.bsl-normal {
		color: var(--color-text-muted);
	}
	.bsl-table {
		font-size: var(--fs-md);
	}
	.bsl-mail {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
</style>
