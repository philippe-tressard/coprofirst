<!--
  L'atelier de l'ÉTAT DESCRIPTIF du règlement — Admin › Imports, source « État descriptif » (#2213).

  La liste du syndic dit qui possède quoi ; l'état descriptif dit ce qu'est chaque
  lot : sa nature, sa porte ou sa place, son niveau, la circulation qui le dessert
  et ses tantièmes (spec `specs/architecture/lots-et-perimetres.md`). Le fichier
  entre dans une table de passage et ne touche au patrimoine qu'au geste
  « Appliquer », une fois TOUS les contrôles passés — la règle vit côté serveur
  (`utils/etat_descriptif`), l'écran ne fait que la montrer.

  ## L'ordre de l'écran suit l'ordre du travail

  1. téléverser (le gabarit vide se télécharge à côté) ;
  2. dire la lettre de l'acte de chaque bâtiment — une correspondance SAISIE,
     jamais déduite de l'ordre ;
  3. lire les contrôles : un seul bloquant, et rien ne s'applique ;
  4. relire les lignes, puis appliquer.

  🔴 Le fichier d'une copropriété réelle ne s'enregistre nulle part ailleurs que
  dans sa table de passage : le dépôt est public.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import Badge from '$lib/components/Badge.svelte';
	import BarreImport from '$lib/components/BarreImport.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { lots as lotsApi, type EtatDescriptif, type LigneEtatDescriptif } from '$lib/api';
	import { confirmer } from '$lib/confirmation';
	import { fmtDatetime } from '$lib/date';
	import { messageErreur } from '$lib/erreurs';
	import { parAttribut } from '$lib/table-statuts';
	import { contientTousLesMots } from '$lib/texte';

	let etat: EtatDescriptif | null = null;
	let chargement = true;
	let televersement = false;
	let enregistrement = false;
	let application = false;
	let recherche = '';
	/** La lettre saisie pour chaque bâtiment, par identifiant. */
	let lettres: Record<number, string> = {};

	const { libelle: GRAVITE, badge: TEINTE } = parAttribut({
		bloquant: { libelle: 'Bloquant', badge: 'badge-red' },
		inconnu: { libelle: 'Inconnu', badge: 'badge-gray' },
		avertissement: { libelle: 'À savoir', badge: 'badge-orange' },
	});
	const { libelle: NATURE } = parAttribut({
		logement: { libelle: 'Logement' },
		commerce: { libelle: 'Commerce' },
		cave: { libelle: 'Cave' },
		parking: { libelle: 'Parking' },
		divers: { libelle: 'Divers' },
	});
	/** Au-delà, la liste des lots d'un constat se résume : le compte suffit à agir. */
	const LOTS_MONTRES = 12;

	function recevoir(lu: EtatDescriptif) {
		etat = lu;
		lettres = Object.fromEntries(lu.batiments.map((b) => [b.id, b.lettre_rcp ?? '']));
	}

	async function charger() {
		try {
			recevoir(await lotsApi.etatDescriptif());
		} catch (e) {
			toast('error', messageErreur(e, "Lecture de l'état descriptif impossible"));
		} finally {
			chargement = false;
		}
	}
	onMount(charger);

	async function televerser(fichier: File) {
		televersement = true;
		try {
			recevoir(await lotsApi.televerserEtatDescriptif(fichier));
			toast('success', `${etat?.lignes.length ?? 0} lot(s) lu(s) — rien n'est encore appliqué`);
		} catch (e) {
			toast('error', messageErreur(e, 'Import refusé'));
		} finally {
			televersement = false;
		}
	}

	async function enregistrerLettres() {
		if (!etat) return;
		enregistrement = true;
		try {
			recevoir(
				await lotsApi.saisirLettres(
					etat.batiments.map((b) => ({
						batiment_id: b.id,
						lettre_rcp: lettres[b.id]?.trim() || null,
					})),
				),
			);
			toast('success', 'Correspondance enregistrée');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enregistrement = false;
		}
	}

	async function appliquer() {
		if (!etat?.applicable) return;
		const ok = await confirmer({
			titre: 'Appliquer au patrimoine',
			message:
				`${etat.lignes.length} lot(s) recevront leur nature, leur circulation et leurs ` +
				'tantièmes ; les caves et les places seront situées dans le bâtiment que dit le ' +
				'règlement. Rejouer le même fichier ensuite ne change rien.',
			libelleConfirmer: 'Appliquer',
		});
		if (!ok) return;
		application = true;
		try {
			const bilan = await lotsApi.appliquerEtatDescriptif();
			toast(
				'success',
				`${bilan.lots} lot(s) désigné(s), ${bilan.quotes_modifiees} tantième(s) posé(s) ou ` +
					`modifié(s), ${bilan.perimetres_modifies} périmètre(s) recalculé(s)`,
			);
			await charger();
		} catch (e) {
			toast('error', messageErreur(e, 'Application refusée'));
		} finally {
			application = false;
		}
	}

	function ligneLue(l: LigneEtatDescriptif): (string | null)[] {
		return [l.lot, l.batiment, l.nature, l.numero_usage, l.niveau, l.circulation, l.lot_origine];
	}

	$: bloquants = etat?.constats.filter((c) => c.gravite !== 'avertissement') ?? [];
	$: avertissements = etat?.constats.filter((c) => c.gravite === 'avertissement') ?? [];
	$: affichees = (etat?.lignes ?? []).filter((l) => contientTousLesMots(ligneLue(l), recherche));
	$: lettresSaisies = new Set(Object.values(lettres).map((l) => l.trim().toUpperCase()));
	$: lettresManquantes = (etat?.lettres_citees ?? []).filter((l) => !lettresSaisies.has(l));
</script>

<BarreImport
	tuiles={etat?.importe_le
		? [
				{ valeur: etat.lignes.length, libelle: 'Lots lus' },
				{ valeur: etat.cles.length, libelle: 'Clés de charges' },
				{ valeur: bloquants.length, libelle: 'Bloquants', couleur: 'var(--color-danger)' },
				{
					valeur: avertissements.length,
					libelle: 'À savoir',
					couleur: 'var(--color-warning-texte)',
				},
			]
		: []}
	colonnesAttendues="lot | batiment | nature | numero_usage | niveau | circulation | lot_origine | source | <clé> /<dénominateur>…"
	libelleRemplacer=""
	enCours={televersement}
	bind:recherche
	idRecherche="etat-descriptif-recherche"
	exempleRecherche="N° de lot, bâtiment, nature, porte ou place…"
	compte={affichees.length}
	on:importer={(e) => televerser(e.detail.fichier)}
>
	<p slot="preparer" class="aide gabarit">
		<a href={lotsApi.gabaritEtatDescriptifUrl()} download>Télécharger le gabarit vide</a> — les en-têtes
		seuls, une colonne par clé de charges à ajouter sur le modèle de la dernière.
	</p>
</BarreImport>

{#if chargement}
	<EtatListe chargement />
{:else if etat}
	<section class="card config-section">
		<h2 class="config-section-title"><Icon name="building-2" size={17} />Lettres de l'acte</h2>
		<p class="config-section-intro muted">
			Le règlement nomme les bâtiments par une lettre ou un numéro qui n'est pas forcément celui de
			l'application. La correspondance se saisit ici — elle ne se déduit jamais de l'ordre.
		</p>
		<div class="lettres">
			{#each etat.batiments as b (b.id)}
				<label class="field">
					{b.libelle}
					<input
						type="text"
						maxlength="8"
						autocomplete="off"
						bind:value={lettres[b.id]}
						placeholder="Lettre de l'acte"
					/>
				</label>
			{/each}
		</div>
		{#if etat.lettres_citees.length}
			<p class="aide">
				Le fichier cite : {etat.lettres_citees.join(', ')}.
				{#if lettresManquantes.length}
					<strong class="manquantes">Sans correspondance : {lettresManquantes.join(', ')}.</strong>
				{/if}
			</p>
		{/if}
		<div class="form-actions largeur-saisie">
			<button
				class="btn btn-primary"
				on:click={enregistrerLettres}
				disabled={enregistrement}
				aria-busy={enregistrement}
			>
				{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</section>

	{#if !etat.importe_le}
		<div class="empty-state card">
			<h3>Aucun état descriptif</h3>
			<p>
				Téléchargez le gabarit, recopiez-y l'état descriptif du règlement, puis importez-le : rien
				ne touche au patrimoine avant le geste « Appliquer ».
			</p>
		</div>
	{:else}
		<section class="card config-section">
			<h2 class="config-section-title"><Icon name="shield-check" size={17} />Contrôles</h2>
			{#if etat.constats.length === 0}
				<p class="muted">Aucun constat : le fichier tombe juste.</p>
			{:else}
				<ul class="constats">
					{#each [...bloquants, ...avertissements] as c (c.code + c.message)}
						<li>
							<Badge teinte={TEINTE[c.gravite]}>{GRAVITE[c.gravite]}</Badge>
							<div>
								<p class="constat-message">{c.message}</p>
								{#if c.lots.length}
									<p class="aide">
										Lot{c.lots.length > 1 ? 's' : ''}
										{c.lots.slice(0, LOTS_MONTRES).join(', ')}{c.lots.length > LOTS_MONTRES
											? ` et ${c.lots.length - LOTS_MONTRES} autre(s)`
											: ''}
									</p>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section class="card config-section carte-lignes">
			<h2 class="config-section-title"><Icon name="clipboard-list" size={17} />Lignes lues</h2>
			{#if affichees.length === 0}
				<p class="muted">Aucune ligne pour cette recherche.</p>
			{:else}
				<table class="table imp-table-dense">
					<thead>
						<tr>
							<th>Lot</th><th>Bât.</th><th>Nature</th><th>Porte ou place</th><th>Niveau</th>
							<th>Desservi par</th>
							{#each etat.cles as cle (cle.code)}
								<th class="nombre" title="{cle.libelle} — sur {cle.denominateur}">{cle.libelle}</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each affichees as l (l.rang)}
							<tr>
								<td class="numero-lot">
									{l.lot}
									{#if l.lot_origine}<span class="aide-ligne">divisé de {l.lot_origine}</span>{/if}
								</td>
								<td>{l.batiment ?? '—'}</td>
								<td class:illisible={!l.nature_lue}>
									{l.nature_lue ? NATURE[l.nature_lue] : (l.nature ?? '—')}
								</td>
								<td>{l.numero_usage ?? '—'}</td>
								<td>{l.niveau ?? '—'}</td>
								<td>{l.circulation ?? 'Accès direct'}</td>
								{#each etat.cles as cle (cle.code)}
									<td class="nombre">{l.quotes[cle.code] ?? ''}</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</section>

		<div class="card config-section application">
			<p class="muted">
				{#if etat.applique_le}
					Appliqué le {fmtDatetime(etat.applique_le)}. Importez un nouveau fichier pour le
					remplacer.
				{:else if etat.applicable}
					Tous les contrôles sont passés.
				{:else}
					Un contrôle bloque : corrigez le fichier ou la correspondance, puis réimportez.
				{/if}
			</p>
			<button
				class="btn btn-primary"
				on:click={appliquer}
				disabled={!etat.applicable || application}
				aria-busy={application}
			>
				{application ? 'Application…' : 'Appliquer au patrimoine'}
			</button>
		</div>
	{/if}
{/if}

<style>
	/*  Une lettre tient en un caractère : le champ prend la largeur de son contenu
	    (`ux-patterns` §9 bis), plusieurs bâtiments par ligne, et passe à la ligne. */
	.lettres {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(8rem, 11rem));
		gap: 0.75rem 1rem;
	}
	.gabarit {
		margin: 0 0 0.75rem;
	}
	.constats {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.75rem;
	}
	.constats li {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.6rem;
		align-items: start;
	}
	.constat-message {
		margin: 0;
	}
	.manquantes {
		color: var(--color-danger);
	}
	.carte-lignes {
		overflow-x: auto;
	}
	.nombre {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.numero-lot {
		font-weight: 600;
	}
	.aide-ligne {
		display: block;
		font-weight: 400;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.illisible {
		color: var(--color-danger);
	}
	.application {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}
	.application p {
		margin: 0;
	}
</style>
