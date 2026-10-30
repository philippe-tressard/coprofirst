<!--
  L'HISTORIQUE DES COMPTES RENDUS du mode (#2082, demandé le 19/10/2026) : les
  points CS / Syndic validés, le plus récent en tête, chacun avec son PDF — celui
  qui a été rangé et envoyé aux présents.

  Entre les graphiques et le point, **plié par défaut** : un `<details>` natif,
  membre de l'accordéon de la page (`unSeulDetailsOuvert`, posé par le layout).
  Il se lit à l'ouverture seulement, et se relit quand un point vient d'être
  validé (`version`).
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { fmtNombre } from '#lib/utils.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { pointsConseil, type ModePoint, type PointHistorique } from '#lib/api/index.ts';
	import { fmtDate, fmtDatetime, jourIso } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { enregistrerFichier } from '#lib/fichiers.ts';

	export let mode: ModePoint;
	/** Change quand un point vient d'être validé : l'historique se relit. */
	export let version = 0;

	let ouvert = false;
	let points: PointHistorique[] | null = null;
	let chargement = false;
	let erreur = '';
	let enCours: number | null = null;

	async function charger() {
		chargement = true;
		erreur = '';
		try {
			points = await pointsConseil.historique(mode);
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			chargement = false;
		}
	}

	//  Lu à la première ouverture, puis à chaque validation (`version`).
	$: if (ouvert) {
		void version;
		charger();
	}

	async function pdf(p: PointHistorique) {
		enCours = p.id;
		try {
			enregistrerFichier(
				await pointsConseil.pdf(p.id),
				`compte-rendu-point-cs-syndic-${jourIso(p.debut)}.pdf`,
			);
		} catch (e) {
			toast('error', messageErreur(e, 'Export PDF impossible'));
		} finally {
			enCours = null;
		}
	}
</script>

<details class="report-card historique" bind:open={ouvert}>
	<summary>
		Historique des comptes rendus{#if points}{SEPARATEUR.point}{points.length}{/if}
	</summary>
	{#if chargement || erreur || !points || !points.length}
		<EtatListe
			{chargement}
			{erreur}
			vide={!!points && !points.length}
			titreErreur="Impossible d’afficher l’historique"
			titreVide="Aucun compte rendu validé"
			messageVide="Les comptes rendus validés des points CS / Syndic se rangent ici, avec leur PDF."
		/>
	{:else}
		<ul class="liste">
			{#each points as p (p.id)}
				<li>
					<span class="quand">{fmtDatetime(p.debut)}</span>
					<span class="muet">
						{p.ou} · {fmtNombre(p.abordees)} affaire{p.abordees > 1 ? 's' : ''}
						{#if p.valide_le}{SEPARATEUR.point}validé le {fmtDate(p.valide_le)}{/if}
					</span>
					<button
						type="button"
						class="btn btn-sm btn-outline"
						disabled={enCours === p.id}
						aria-busy={enCours === p.id}
						on:click={() => pdf(p)}
					>
						<IconeAction icone="file-text" /> PDF
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</details>

<style>
	.historique {
		margin-bottom: 0.75rem;
	}
	summary {
		cursor: pointer;
		font-weight: 600;
	}
	.liste {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
	}
	.liste li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem 0.75rem;
		padding: 0.4rem 0;
		border-top: 1px solid var(--color-border);
		font-size: var(--fs-sm);
	}
	.liste .btn {
		margin-left: auto;
	}
	.quand {
		font-weight: 600;
	}
	.muet {
		color: var(--color-text-muted);
	}
</style>
