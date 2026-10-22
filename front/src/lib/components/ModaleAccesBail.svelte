<!--
  **La modale d'accès d'un bail** : quels Vigik et quelles télécommandes sont
  confiés au locataire, et lesquels reviennent au bailleur.

  ## Pourquoi ce composant (#779, 08/09/2026)

  Extrait de `mon-lot/+page.svelte` quand le garde-fou de modularité a refusé de
  la laisser grossir (1 458 → 1 471 lignes). Le refus disait vrai : ces trois
  cent six lignes forment une **entité complète et close** — un appel réseau, six
  variables d'état, cinq dérivés, huit gestes — dont la page n'apprenait
  strictement rien. Elle en portait pourtant tout l'état.

  Deuxième extraction du même patron, après `InventaireBail` (#806).

  🔴 **L'interface est volontairement PLUS ÉTROITE que l'objet.** Le composant
  reçoit `bailId`, `titre` et `typeLot`, pas un `Bail` — dupliquer l'interface
  `Bail` dans deux fichiers aurait recréé, au nom du découpage, exactement la
  duplication que le découpage doit retirer. Il n'a besoin que de ces trois
  choses ; il ne demande que ces trois choses.

  ⚠️ `lotTypeLabel` est parti dans `$lib/utils` : il servait ICI et à la
  préparation de `FormulaireBail`, restée dans la page. L'emporter en aurait
  fait une deuxième écriture — c'est le défaut que `mon-lot` avait déjà nommé en
  commentaire, et qui se serait produit à cette extraction-ci.
-->
<script lang="ts">
	import { statutAccesLabel } from '$lib/types-acces';
	import { confirmer } from '$lib/confirmation';
	import { createEventDispatcher, onMount } from 'svelte';
	import { bailleur as bailApi, type AccesBail } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { lotTypeLabel } from '$lib/utils';
	import { toast } from '$lib/components/Toast.svelte';
	import EncartAvertissement from '$lib/components/EncartAvertissement.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';

	/** Le bail dont on gère les accès. */
	export let bailId: number;
	/** Titre de la modale — la page sait nommer le locataire, pas nous. */
	export let titre: string;
	/**  Type du lot du bail, quand il est connu : un parking ou une cave
	 *   n'accepte pas de Vigik, et l'écran le dit avant qu'on essaie. */
	export let typeLot: string | null = null;

	const dispatch = createEventDispatcher();
	const fermer = () => dispatch('fermer');

	let accesListe: AccesBail[] = [];
	let loadingAcces = true;
	/**  🔴 Non vide = on n'a PAS pu regarder (#816).
	 *
	 *   Ce `catch` se contentait d'un toast, et la liste restait vide : la modale
	 *   affirmait ensuite « Aucun Vigik ni télécommande rattaché à ce lot » — une
	 *   absence qu'elle n'avait pas constatée, sur l'écran d'où l'on décide de
	 *   confier ou de reprendre des accès physiques à un logement.
	 *
	 *   ⚠️ Trouvé en DÉPLAÇANT ce code, pas par le contrôle : `check-etat-liste`
	 *   ne reconnaît que `.empty-state`, et ce vide-ci s'écrit en `<p>`. Le motif
	 *   voit la forme, pas la faute. */
	let erreurAcces = '';
	let selectionVigik = new Set<number>();
	let selectionTc = new Set<number>();
	let filtreLotsAcces = new Set<number>();

	onMount(async () => {
		try {
			accesListe = await bailApi.accesBail(bailId);
			preselectionRecommandee();
		} catch (e) {
			erreurAcces = messageErreur(e, 'Impossible de charger les accès');
			toast('error', erreurAcces);
		} finally {
			loadingAcces = false;
		}
	});

	function isSelectable(acces: AccesBail): boolean {
		if (bailId == null) return false;
		if (!acces.eligible_transfert) return false;
		if (acces.chez_locataire && acces.bail_id !== bailId) return false;
		return true;
	}

	function clearSelection() {
		selectionVigik = new Set();
		selectionTc = new Set();
	}

	function preselectionRecommandee() {
		clearSelection();
		for (const a of accesListe) {
			if (!isSelectable(a) || !a.recommande) continue;
			if (a.type === 'vigik') selectionVigik.add(a.id);
			else selectionTc.add(a.id);
		}
		selectionVigik = new Set(selectionVigik);
		selectionTc = new Set(selectionTc);
	}

	function toggleFiltreLot(lotId: number) {
		if (filtreLotsAcces.has(lotId)) filtreLotsAcces.delete(lotId);
		else filtreLotsAcces.add(lotId);
		filtreLotsAcces = new Set(filtreLotsAcces);
	}

	async function transfererAcces() {
		const tVigik = [...selectionVigik].filter((id) => {
			const a = accesListe.find((x) => x.type === 'vigik' && x.id === id);
			return a && !a.chez_locataire;
		});
		const tTc = [...selectionTc].filter((id) => {
			const a = accesListe.find((x) => x.type === 'telecommande' && x.id === id);
			return a && !a.chez_locataire;
		});
		if (tVigik.length === 0 && tTc.length === 0) {
			toast('error', 'Sélectionnez au moins un accès à transférer');
			return;
		}
		try {
			const updated = await bailApi.transfererAcces(bailId, {
				vigik_ids: tVigik,
				tc_ids: tTc,
			});
			accesListe = accesListe.map((a) => {
				const u = updated.find((x: AccesBail) => x.id === a.id && x.type === a.type);
				return u ?? a;
			});
			selectionVigik = new Set();
			selectionTc = new Set();
			toast('success', 'Accès transférés au locataire');
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur lors du transfert'));
		}
	}

	async function recupererSelection() {
		const rVigik = [...selectionVigik].filter((id) => {
			const a = accesListe.find((x) => x.type === 'vigik' && x.id === id);
			return a?.chez_locataire;
		});
		const rTc = [...selectionTc].filter((id) => {
			const a = accesListe.find((x) => x.type === 'telecommande' && x.id === id);
			return a?.chez_locataire;
		});
		if (rVigik.length === 0 && rTc.length === 0) {
			toast('error', 'Sélectionnez au moins un accès à récupérer');
			return;
		}
		try {
			const updated = await bailApi.recupererAcces(bailId, {
				vigik_ids: rVigik,
				tc_ids: rTc,
			});
			accesListe = accesListe.map((a) => {
				const u = updated.find((x: AccesBail) => x.id === a.id && x.type === a.type);
				return u ?? a;
			});
			for (const id of rVigik) selectionVigik.delete(id);
			for (const id of rTc) selectionTc.delete(id);
			selectionVigik = new Set(selectionVigik);
			selectionTc = new Set(selectionTc);
			toast('success', 'Accès récupérés');
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function recupererAcces() {
		if (!(await confirmer('Récupérer tous les accès confiés au locataire pour ce bail ?'))) return;
		try {
			const updated = await bailApi.recupererAcces(bailId);
			accesListe = accesListe.map((a) => {
				const u = updated.find((x: AccesBail) => x.id === a.id && x.type === a.type);
				return u ?? a;
			});
			selectionVigik = new Set();
			selectionTc = new Set();
			toast('success', 'Accès récupérés');
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	function toggleAcces(type: 'vigik' | 'telecommande', id: number) {
		if (type === 'vigik') {
			if (selectionVigik.has(id)) selectionVigik.delete(id);
			else selectionVigik.add(id);
			selectionVigik = new Set(selectionVigik);
		} else {
			if (selectionTc.has(id)) selectionTc.delete(id);
			else selectionTc.add(id);
			selectionTc = new Set(selectionTc);
		}
	}

	$: lotsSourcesAcces = (() => {
		const map = new Map<number, string>();
		for (const a of accesListe) {
			if (a.lot_id == null) continue;
			if (!map.has(a.lot_id)) map.set(a.lot_id, a.lot_label ?? `Lot #${a.lot_id}`);
		}
		return [...map.entries()].map(([id, label]) => ({ id, label }));
	})();
	$: accesFiltres = accesListe.filter(
		(a) => filtreLotsAcces.size === 0 || (a.lot_id != null && filtreLotsAcces.has(a.lot_id)),
	);

	$: nTransfert =
		[...selectionVigik].filter((id) => {
			const a = accesListe.find((x) => x.type === 'vigik' && x.id === id);
			return a && !a.chez_locataire;
		}).length +
		[...selectionTc].filter((id) => {
			const a = accesListe.find((x) => x.type === 'telecommande' && x.id === id);
			return a && !a.chez_locataire;
		}).length;
	$: nRecuperation =
		[...selectionVigik].filter(
			(id) => accesListe.find((x) => x.type === 'vigik' && x.id === id)?.chez_locataire,
		).length +
		[...selectionTc].filter(
			(id) => accesListe.find((x) => x.type === 'telecommande' && x.id === id)?.chez_locataire,
		).length;
</script>

<!-- ── Modal : gestion des accès (Vigik / TC) ───────────────────────── -->
<Modale edition {titre} styleBoite="width:min(620px,95vw)" on:fermer={fermer}>
	<div class="modal-body">
		{#if loadingAcces}
			<EtatListe chargement />
		{:else if erreurAcces}
			<!--  L'échec AVANT le vide : « aucun accès » et « je n'ai pas pu lire les
			      accès » mènent à des décisions opposées. -->
			<p class="etat-erreur-acces">{erreurAcces}</p>
		{:else if typeLot === 'parking' || typeLot === 'cave'}
			<EncartAvertissement>
				Ce bail concerne un {typeLot}. <strong>TC uniquement</strong> : les Vigik ne sont pas autorisés.
			</EncartAvertissement>
		{:else if accesListe.length === 0}
			<p class="text-muted-base">Aucun Vigik ni télécommande rattaché à ce lot.</p>
		{:else}
			<p class="intro-selection">
				Sélection intelligente : utilisez un préréglage puis ajustez manuellement. Les règles de
				cohérence sont appliquées automatiquement (ex. pas de Vigik pour un bail parking seul).
			</p>
			<div class="acces-presets">
				<!--  Pas de ✨ : la présélection est une RÈGLE (le type du bail), pas
				      l'assistant — ✨ ne se dit que de l'IA, sur tout le site (`IconeIA`). -->
				<button class="btn btn-sm" on:click={preselectionRecommandee}
					>Présélection recommandée</button
				>
				<button class="btn btn-sm btn-outline" on:click={clearSelection}>Effacer</button>
			</div>
			{#if lotsSourcesAcces.length > 1}
				<div class="acces-filters">
					<span class="text-muted-sm">Filtrer lots source :</span>
					{#each lotsSourcesAcces as ls (ls.id)}
						<Pastille active={filtreLotsAcces.has(ls.id)} on:click={() => toggleFiltreLot(ls.id)}
							>{ls.label}</Pastille
						>
					{/each}
				</div>
			{/if}
			<div class="table-wrap">
				<table class="table table-transfert">
					<thead>
						<tr>
							<th class="col-case"></th>
							<th>Lot source</th>
							<th>Type</th>
							<th>Code</th>
							<th>Statut</th>
							<th>Localisation</th>
							<th>Info</th>
						</tr>
					</thead>
					<tbody>
						{#each accesFiltres as acces (acces.type + acces.id)}
							<tr>
								<td>
									{#if isSelectable(acces)}
										<input
											type="checkbox"
											checked={acces.type === 'vigik'
												? selectionVigik.has(acces.id)
												: selectionTc.has(acces.id)}
											on:change={() => toggleAcces(acces.type, acces.id)}
										/>
									{/if}
								</td>
								<td
									>{acces.lot_label ?? '—'}
									<span class="badge badge-gray type-lot">{lotTypeLabel(acces.lot_type)}</span></td
								>
								<td>{acces.type === 'vigik' ? '\u{1F3F7}️ Vigik' : '\u{1F4E1} Télécommande'}</td>
								<td class="texte-code">{acces.code}</td>
								<td>
									<!--  🔴 `class:` et non un ternaire INTERPOLÉ (#810) : devant
									      `class="badge {…}"`, Svelte cesse de déclarer les sélecteurs
									      inutilisés pour TOUT le fichier, et `lint:css-orphelin` y devient
									      aveugle sans le dire. Les deux valeurs sont connues ici. -->
									<span
										class="badge"
										class:badge-green={acces.statut === 'actif'}
										class:badge-gray={acces.statut !== 'actif'}
									>
										{statutAccesLabel(acces.statut)}
									</span>
								</td>
								<td>
									{#if acces.chez_locataire}
										<span class="badge badge-yellow">Chez locataire</span>
									{:else}
										<span class="badge badge-blue">Chez bailleur</span>
									{/if}
								</td>
								<td>
									{#if acces.recommande}
										<span class="badge badge-green">Recommandé</span>
									{:else if acces.motif_non_eligible}
										<span class="badge badge-gray" title={acces.motif_non_eligible}
											>{acces.motif_non_eligible}</span
										>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if accesListe.some((a) => a.chez_locataire)}
				<button class="btn btn-sm btn-tout" on:click={recupererAcces}> ↩ Tout récupérer </button>
			{/if}
		{/if}
	</div>
	<div class="modal-footer">
		<button class="btn" on:click={fermer}>Fermer</button>
		{#if nRecuperation > 0}
			<button class="btn btn-primary" on:click={recupererSelection}>
				↩ Récupérer ({nRecuperation})
			</button>
		{/if}
		{#if nTransfert > 0}
			<button class="btn btn-primary" on:click={transfererAcces}>
				Transférer ({nTransfert})
			</button>
		{/if}
	</div>
</Modale>

<style>
	.acces-presets {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin-bottom: 0.7rem;
	}
	/*  🔴 L'échec ne ressemble PAS au vide — même teinte d'alerte que `EtatListe`
	    en mode compact, d'où cette règle est reprise. */
	.etat-erreur-acces {
		font-size: var(--fs-base);
		color: var(--color-warning-texte);
		font-weight: 500;
		padding: 0.5rem 0;
	}
	.acces-filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		margin-bottom: 0.7rem;
	}
	.intro-selection {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-bottom: 0.6rem;
	}
	.table-transfert {
		font-size: var(--fs-md);
	}
	.col-case {
		width: 2rem;
	}
	.type-lot {
		margin-left: 0.25rem;
	}
	.btn-tout {
		margin-top: 0.75rem;
	}
</style>
