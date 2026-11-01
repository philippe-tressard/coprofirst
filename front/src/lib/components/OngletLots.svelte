<!--
  Admin › Copropriété › LOTS — le patrimoine selon le règlement (#2216).

  Ce qu'aucun écran ne montrait : ce qui dessert chaque lot, ses périmètres, et ce
  qui ne tombe pas juste (les CONSTATS, en tête). La liste vient de
  `/lots/admin/tous`, qui rend déjà la désignation ; les constats, la
  re-dérivation et les périmètres manuels de `routers/lots_admin.py`.

  - Un lot ne se CRÉE pas ici : il naît d'un acte, il entre par l'import.
  - Un périmètre DÉRIVÉ se recalcule (« Recalculer les périmètres »), il ne se
    retire pas ; un périmètre POSÉ À LA MAIN survit au recalcul et se retire.
  - Un seul lot déplié à la fois (`#lib/accordeon`).
  - Les clés de charges telles que le syndic les appelle : `ReglageDesCles` (#2252).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import Badge from '#lib/components/Badge.svelte';
	import ChampRecherche from '#lib/components/ChampRecherche.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import ConstatsLots from '#lib/components/ConstatsLots.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import ReglageDesCles from '#lib/components/ReglageDesCles.svelte';
	import ReglagesListe from '#lib/components/ReglagesListe.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		lots as lotsApi,
		lotsAdmin,
		perimetres as perimetresApi,
		type ConstatPatrimoine,
		type MonLot,
		type RelationLotPerimetre,
	} from '#lib/api/index.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import type { Perimetre } from '#lib/perimetres/index.ts';
	import { contientTousLesMots } from '#lib/texte.ts';
	import { etageLabel, lotTypeLabel } from '#lib/utils.ts';

	let lots: MonLot[] = [];
	let constats: ConstatPatrimoine[] = [];
	let arbre: Perimetre[] = [];
	let chargement = true;
	let erreur = '';
	let recherche = '';
	let nature = '';
	let deplie: number | null = null;
	let recalcul = false;
	/** La saisie d'un périmètre manuel, pour le lot déplié. */
	let ajoutPerimetre = '';
	let ajoutRelation: string = 'desservi_par';
	let ajout = false;

	const OPTIONS_RELATION = [
		{ val: 'desservi_par', label: 'Desservi par' },
		{ val: 'situe_dans', label: 'Situé dans' },
	];
	const RELATIONS = Object.fromEntries(OPTIONS_RELATION.map((o) => [o.val, o.label]));

	async function charger() {
		try {
			[lots, constats, arbre] = await Promise.all([
				lotsApi.tous(),
				lotsAdmin.constats(),
				perimetresApi.list(),
			]);
			erreur = '';
		} catch (e) {
			erreur = messageErreur(e, 'Impossible de lire les lots');
		} finally {
			chargement = false;
		}
	}
	onMount(charger);

	async function recalculer() {
		recalcul = true;
		try {
			const { modifies } = await lotsAdmin.rederiver();
			toast(
				'success',
				`${modifies} périmètre(s) recalculé(s) — les périmètres posés à la main restent`,
			);
			await charger();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			recalcul = false;
		}
	}

	function idDuCode(code: string): number | undefined {
		return arbre.find((p) => p.code === code)?.id;
	}

	async function poser(lot: MonLot) {
		const id = Number(ajoutPerimetre);
		if (!id) return;
		ajout = true;
		try {
			await lotsAdmin.poserPerimetre(lot.id, id, ajoutRelation as RelationLotPerimetre);
			ajoutPerimetre = '';
			await charger();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			ajout = false;
		}
	}

	async function retirer(lot: MonLot, code: string, relation: string) {
		const id = idDuCode(code);
		if (!id) return;
		try {
			await lotsAdmin.retirerPerimetre(lot.id, id, relation as RelationLotPerimetre);
			await charger();
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	$: natures = [...new Set(lots.map((l) => l.nature).filter((n): n is string => !!n))]
		.sort()
		.map((n) => ({ val: n, label: lotTypeLabel(n) }));
	$: affiches = lots
		.filter((l) => !nature || l.nature === nature)
		.filter((l) => contientTousLesMots([l.numero, l.numero_usage, l.batiment_nom], recherche))
		.sort((a, b) => a.numero.localeCompare(b.numero, 'fr', { numeric: true }));
	$: selectionnables = arbre.filter((p) => p.actif && p.selectionnable !== false);

	function desservi(l: MonLot): string {
		return (
			l.perimetres
				.filter((p) => p.relation === 'desservi_par')
				.map((p) => p.libelle)
				.join(', ') || '—'
		);
	}
</script>

<section class="card config-section">
	<div class="config-section-entete">
		<div>
			<h2 class="config-section-title"><Icon name="shield-check" size={17} />Constats</h2>
			<p class="config-section-intro muted">
				Ce qui ne tombe pas juste dans le patrimoine : un lot sans propriétaire, une place sans
				circulation, une clé de charges dont la somme diffère de son dénominateur…
			</p>
		</div>
		<button
			class="btn btn-outline btn-sm"
			on:click={recalculer}
			disabled={recalcul}
			aria-busy={recalcul}
		>
			<IconeAction icone="refresh-cw" />
			{recalcul ? 'Recalcul…' : 'Recalculer les périmètres'}
		</button>
	</div>
	<ConstatsLots {constats} videTexte="Aucun constat : le patrimoine tombe juste." />
</section>

<ReglageDesCles />

<ReglagesListe>
	<ChampRecherche
		id="lots-recherche"
		bind:valeur={recherche}
		placeholder="N° de lot, porte ou place, bâtiment…"
		dans="n° de lot, n° de porte ou de place, et bâtiment"
	/>
	{#if natures.length > 1}
		<ChoixPastilles
			options={natures}
			bind:valeur={nature}
			tous="Toutes"
			compte={affiches.length}
			libelle="Nature"
			libelleDevant
		/>
	{/if}
</ReglagesListe>

<EtatListe {chargement} {erreur} titreErreur="Impossible d’afficher les lots">
	{#if affiches.length === 0}
		<p class="muted">Aucun lot pour cette recherche.</p>
	{:else}
		<div class="card carte-lots">
			<table class="table imp-table-dense">
				<thead>
					<tr>
						<th>Lot</th><th>Bât.</th><th>Nature</th><th>Porte ou place</th><th>Niveau</th>
						<th>Desservi par</th><th><span class="sr-only">Détail</span></th>
					</tr>
				</thead>
				<tbody>
					{#each affiches as l (l.id)}
						<tr>
							<td class="numero-lot">{l.numero}</td>
							<td>{l.batiment_nom ?? '—'}</td>
							<td>{lotTypeLabel(l.nature ?? l.type)}</td>
							<td>{l.numero_usage ?? '—'}</td>
							<td>{l.etage === null ? '—' : etageLabel(l.etage)}</td>
							<td>{desservi(l)}</td>
							<td>
								<button
									class="btn-icon"
									aria-expanded={deplie === l.id}
									aria-label="Périmètres du lot {l.numero}"
									title="Périmètres du lot"
									on:click={() => (deplie = basculer(deplie, l.id))}
									><IconeAction icone="chevron-down" /></button
								>
							</td>
						</tr>
						{#if deplie === l.id}
							<tr>
								<td colspan="7">
									<div class="carte-corps">
										<ul class="perimetres">
											{#each l.perimetres as p (p.code + p.relation)}
												<li>
													<span class="relation">{RELATIONS[p.relation] ?? p.relation}</span>
													<span>{p.libelle}</span>
													<Badge teinte={p.derive ? 'badge-gray' : 'badge-blue'} compact
														>{p.derive ? 'dérivé' : 'posé à la main'}</Badge
													>
													{#if !p.derive}
														<button
															class="btn-icon-danger"
															aria-label="Retirer {p.libelle}"
															title="Retirer"
															on:click={() => retirer(l, p.code, p.relation)}
															><IconeAction icone="x" /></button
														>
													{/if}
												</li>
											{:else}
												<li class="muted">Aucun périmètre : recalculer les périmètres.</li>
											{/each}
										</ul>
										{#if l.quotes_parts?.length}
											<p class="aide">
												Tantièmes : {l.quotes_parts
													.map((q) => `${q.libelle} ${q.numerateur}/${q.denominateur}`)
													.join(' · ')}
											</p>
										{/if}
										<div class="ajout">
											<label class="field">
												Périmètre à poser
												<select bind:value={ajoutPerimetre}>
													<option value="">—</option>
													{#each selectionnables as p (p.id)}
														<option value={String(p.id)}>{p.libelle}</option>
													{/each}
												</select>
											</label>
											<ChoixPastilles
												options={OPTIONS_RELATION}
												bind:valeur={ajoutRelation}
												tous={false}
												radio="relation-{l.id}"
												libelle="Relation"
												libelleVisible
												defilante={false}
											/>
											<button
												class="btn btn-primary btn-sm"
												on:click={() => poser(l)}
												disabled={!ajoutPerimetre || ajout}
												aria-busy={ajout}
											>
												<IconeAction icone="plus" /> Poser
											</button>
										</div>
									</div>
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</EtatListe>

<style>
	/* Bloc conteneur du `.sr-only` de l'en-tête, qui sortirait sinon (#2437, `normes.css`). */
	.carte-lots {
		overflow-x: auto;
		position: relative;
	}
	.numero-lot {
		font-weight: 600;
	}
	.perimetres {
		list-style: none;
		margin: 0 0 0.75rem;
		padding: 0;
		display: grid;
		gap: 0.4rem;
	}
	.perimetres li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.relation {
		color: var(--color-text-muted);
		min-width: 7rem;
	}
	.ajout {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 0.75rem;
	}
</style>
