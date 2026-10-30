<!--
  Le tableau des affaires du « Suivi des affaires » — âge, date d'ouverture,
  affaire, catégorie — dans ses deux modes (#2035).

  - **Suivre** : le tableau de la maquette D2, tel quel.
  - **Relancer le syndic** (`relance`) : une case en tête de ligne, pour composer
    la relance, et en fin de ligne les relances déjà envoyées.

  - **Point CS / Syndic en cours** (`crs`, #2041) : sous l'aperçu, l'état du
    compte rendu de l'affaire et le geste qui l'ouvre ; la saisie (créneau
    `saisie`) s'ouvre dans une ligne pleine largeur, sous l'affaire. Une seule
    à la fois : `ouverte`, liée.

  Sorti de `VueSuiviAffaires` pour que les deux modes rendent la MÊME ligne : la
  relance avait sa propre carte, avec ses propres badges, et ne disait ni l'âge,
  ni la date d'ouverture, ni le résumé de l'affaire.

  - **#2089** : sous le titre, l'état de suivi (Chez le syndic, Résolu…) et
    « qui la lit » — la pastille de la page Affaires (`PastilleLecture`), à
    l'identique (la vignette Public / Privé de #2082 est retirée) ; en point, la ligne du CR dit aussi l'état décidé
    pour la validation (« → Résolu ») et « Modifié en révision N ». Chaque ligne
    est une cible de défilement (`cible-defilement`, `id="affaire-N"`) : après
    l'enregistrement d'un CR, la vue place l'affaire suivante en haut de l'écran.

  - **#2083** : les affaires LIÉES se suivent, rassemblées par le serveur
    (`groupe`) ; une ligne d'en-tête les annonce, avec **Fusionner** et **Ne pas
    fusionner** (hors relance), et la fusion s'ouvre sous elle (créneau
    `fusion`). Une affaire qui en a absorbé d'autres les cite sous son titre.

  Sous le titre, le PÉRIMÈTRE (`BadgePerimetre`, qui tait celui par défaut), puis
  l'APERÇU — le résumé de l'assistant (✨), sinon le descriptif —
  coupé à cinq lignes (`.clamp-rapport`). Le serveur décide lequel
  (`AffaireOuverte.apercu`) ; c'est du TEXTE, jamais un `{@html}`.
-->
<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import Badge from '#lib/components/Badge.svelte';
	import BadgeEtatAffaire from '#lib/components/BadgeEtatAffaire.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import PastillesRelances from './PastillesRelances.svelte';
	import PastilleLecture from '#lib/components/PastilleLecture.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import type { AffaireOuverte, CrAffaire } from '#lib/api/index.ts';
	import { etatCr } from '#lib/points-conseil.ts';
	import { ETATS_VISITE } from '#lib/entretien-periodique.ts';
	import { motifEvolution } from '#lib/reporting.ts';
	import { fmtDate } from '#lib/date.ts';
	import { categorieTicketLabel, lienTicket, statutTicketLabel } from '#lib/tickets.ts';

	export let affaires: AffaireOuverte[];
	/** Le mode « Relancer le syndic » : une case par ligne, et les relances envoyées. */
	export let relance = false;
	/**  Le mode « Suivi entretiens périodiques » (#2043) : l'état de la visite à la
	 *   place de la catégorie, toujours « Entretien » dans ce mode. */
	export let visites = false;
	/** Les affaires cochées — liées, lues par l'aperçu et l'envoi. */
	export let choisies: Set<number> = new Set();
	/**  Les comptes rendus d'un point CS / Syndic EN COURS, par affaire — `null`
	 *   hors d'un point : la ligne n'offre alors aucune saisie. */
	export let crs: Map<number, CrAffaire> | null = null;
	/** L'affaire dont le compte rendu est en saisie — une à la fois. */
	export let ouverte: number | null = null;
	/**  Le point accepte-t-il un compte rendu NOUVEAU ? Terminé, il n'offre que
	 *   la correction des comptes rendus saisis (#2042). */
	export let ajout = true;
	/** « Modifié en révision N », par affaire — lu dans le CR global (#2082). */
	export let marques: Map<number, string> = new Map();
	/** Le groupe dont la fusion est ouverte — un à la fois (#2083). */
	export let fusionOuverte: number | null = null;
	/** « Ne pas fusionner » : la vue demande confirmation, puis relit. */
	export let onEcarter: ((ids: number[]) => void) | null = null;

	/** Les membres de chaque groupe, dans l'ordre servi. */
	$: membres = affaires.reduce((m, a) => {
		if (a.groupe !== null) m.set(a.groupe, [...(m.get(a.groupe) ?? []), a]);
		return m;
	}, new Map<number, AffaireOuverte[]>());

	$: colonnes = relance ? 6 : 4;

	/** La teinte de l'âge — la tranche vient du serveur, qui garde les seuils. */
	const TEINTE_AGE: Record<AffaireOuverte['anciennete'], string> = {
		ancienne: 'badge-red',
		moyenne: 'badge-orange',
		recente: 'badge-gray',
	};

	function basculer(id: number) {
		const s = new Set(choisies);
		if (s.has(id)) s.delete(id);
		else s.add(id);
		choisies = s;
	}
</script>

<div class="table-wrap">
	<table class="report-table compact affaires">
		<thead>
			<tr>
				{#if relance}<th class="choix"><span class="sr-only">Relancer</span></th>{/if}
				<th>Âge</th><th>Ouverte le</th><th>Affaire</th><th>{visites ? 'Visite' : 'Catégorie'}</th>
				{#if relance}<th>Relances envoyées</th>{/if}
			</tr>
		</thead>
		<tbody>
			{#each affaires as a (a.id)}
				{#if a.groupe === a.id && !relance}
					<tr class="groupe-tete">
						<td colspan={colonnes}>
							<span class="groupe-titre">
								<Icon name="link" size={14} />
								{membres.get(a.id)?.length ?? 0} affaires liées
							</span>
							<button
								type="button"
								class="btn btn-sm btn-outline"
								aria-expanded={fusionOuverte === a.id}
								on:click={() => (fusionOuverte = fusionOuverte === a.id ? null : a.id)}
							>
								Fusionner
							</button>
							{#if onEcarter}
								<button
									type="button"
									class="btn btn-sm btn-outline"
									on:click={() => onEcarter?.((membres.get(a.id) ?? []).map((m) => m.id))}
								>
									Ne pas fusionner
								</button>
							{/if}
						</td>
					</tr>
					{#if fusionOuverte === a.id}
						<tr class="saisie">
							<td colspan={colonnes}><slot name="fusion" affaires={membres.get(a.id) ?? []} /></td>
						</tr>
					{/if}
				{/if}
				<tr id="affaire-{a.id}" class="cible-defilement" class:liee={a.groupe !== null}>
					{#if relance}
						<td class="choix">
							<input
								type="checkbox"
								checked={choisies.has(a.id)}
								aria-label="Relancer l’affaire {a.numero}"
								on:change={() => basculer(a.id)}
							/>
						</td>
					{/if}
					<td class="age">
						<Badge teinte={TEINTE_AGE[a.anciennete]} title="{fmtNombre(a.age_jours)} jours"
							>{fmtNombre(a.age_jours)} j</Badge
						>
					</td>
					<td class="date">{fmtDate(a.ouverte_le)}</td>
					<td class="affaire">
						<a href={lienTicket(a.id)} class="titre">{a.titre}</a>
						<span class="vignettes">
							<BadgeEtatAffaire statut={a.statut} compact />
							<PastilleLecture ticket={a} />
						</span>
						{#if a.fusionnees.length}
							<!--  L'historique de fusion, cité au point (#2083). -->
							<span class="fusionnees">🔀 Fusionne {a.fusionnees.join(' · ')}</span>
						{/if}
						{#if a.a_evolue && !visites}
							<!--  Le signal « a évolué » (#2044) : sous le titre, icône ET libellé. -->
							<span class="evolution"
								><Badge teinte="badge-orange" compact
									><Icon name="bell" size={12} /> {motifEvolution(a.motif_evolution)}</Badge
								></span
							>
						{/if}
						<!--  Le périmètre — tu quand c'est celui par défaut (règle 4). -->
						<BadgePerimetre perimetre={a.perimetre_cible} />
						{#if a.apercu}
							<p class="descriptif clamp-rapport">
								{#if a.apercu_ia}<span class="ia-signe" title="Résumé de l’assistant"
										>✨<span class="sr-only">Résumé de l’assistant :</span></span
									>{/if}{a.apercu}
							</p>
						{/if}
						{#if crs && (ajout || crs.has(a.id))}
							<p class="cr">
								{#if crs.get(a.id)}
									<Badge teinte={crs.get(a.id)?.brouillon ? 'badge-gray' : 'badge-green'} compact
										>{etatCr(crs.get(a.id))}</Badge
									>
									{#if crs.get(a.id)?.etat_cible && crs.get(a.id)?.etat_cible !== a.statut}
										<Badge
											teinte="badge-blue"
											compact
											title="État posé à la validation du compte rendu"
											>→ {statutTicketLabel(crs.get(a.id)?.etat_cible)}</Badge
										>
									{/if}
									{#if marques.get(a.id)}
										<Badge teinte="badge-orange" compact>{marques.get(a.id)}</Badge>
									{/if}
								{/if}
								<button
									type="button"
									class="btn btn-sm btn-outline"
									aria-expanded={ouverte === a.id}
									aria-controls="saisie-cr-{a.id}"
									on:click={() => (ouverte = ouverte === a.id ? null : a.id)}
								>
									<Icon name="file-text" size={14} />
									{ouverte === a.id ? 'Replier' : 'Compte rendu'}
								</button>
							</p>
						{/if}
					</td>
					<td class="categorie">
						{#if visites && a.etat_visite}
							<Badge teinte={ETATS_VISITE[a.etat_visite].teinte}
								>{ETATS_VISITE[a.etat_visite].libelle}</Badge
							>
						{:else}
							{categorieTicketLabel(a.categorie)}
						{/if}
					</td>
					{#if relance}
						<td class="relances"><PastillesRelances relances={a.relances} /></td>
					{/if}
				</tr>
				{#if crs && ouverte === a.id}
					<tr class="saisie" id="saisie-cr-{a.id}">
						<td colspan={colonnes}><slot name="saisie" affaire={a} cr={crs.get(a.id)} /></td>
					</tr>
				{/if}
			{/each}
		</tbody>
	</table>
</div>

<style>
	.affaires .date,
	.affaires .categorie,
	.affaires .age {
		white-space: nowrap;
	}
	.affaires .date,
	.affaires .categorie {
		color: var(--color-text-muted);
	}
	.affaires .choix {
		width: 2.5rem;
	}
	.affaires .choix input {
		width: 1.25rem;
		height: 1.25rem;
		accent-color: var(--color-primary);
	}
	.titre {
		font-weight: 700;
		color: var(--color-text);
	}
	.descriptif {
		margin: 0.2rem 0 0;
		white-space: pre-line;
	}
	.cr {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin: 0.35rem 0 0;
	}
	.evolution {
		display: block;
		margin: 0.15rem 0;
	}
	.groupe-tete td {
		background: var(--color-neutre-fond);
		padding: 0.35rem 0.5rem;
	}
	.groupe-titre {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		margin-right: 0.75rem;
		font-weight: 600;
		font-size: var(--fs-sm);
	}
	.groupe-tete .btn {
		margin-right: 0.4rem;
	}
	tr.liee td:first-child {
		box-shadow: inset 3px 0 0 var(--color-primary);
	}
	.vignettes {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin: 0.15rem 0;
	}
	.fusionnees {
		display: block;
		margin: 0.15rem 0;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.ia-signe {
		color: var(--color-violet);
		margin-right: 0.3rem;
	}

	/*  Au téléphone, chaque ligne devient une fiche : la case, l'âge, la date et
	    la catégorie sur une ligne, puis le titre et l'aperçu, puis les relances. */
	@media (max-width: 767px) {
		.affaires thead {
			display: none;
		}
		.affaires,
		.affaires tbody {
			display: block;
		}
		.affaires tr {
			display: flex;
			flex-wrap: wrap;
			gap: 0.25rem 0.6rem;
			align-items: center;
			padding: 0.6rem 0;
			border-bottom: 1px solid var(--color-border);
		}
		.affaires td {
			display: block;
			padding: 0;
			border: 0;
		}
		.affaires td.affaire {
			order: 4;
			flex-basis: 100%;
		}
		.affaires td.relances {
			order: 5;
			flex-basis: 100%;
		}
		.affaires tr.saisie td {
			flex-basis: 100%;
		}
	}
</style>
