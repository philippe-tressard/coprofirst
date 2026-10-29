<!--
  **L'onglet « Gestion locative »** de « Mes lots & accès » : les baux d'un
  bailleur, ses locataires, et ce qu'il leur a confié.

  ## Pourquoi extrait (12/09/2026, #928)

  La page a reçu deux sous-onglets d'accès, et le plafond de modularité a refusé
  les quarante-trois lignes que cela lui ajoutait. C'est le refus attendu : #928
  l'avait annoncé avant d'écrire une ligne — *« il faut factoriser dans `mon-lot`
  d'abord »*.

  🔴 Trois migrations vers `tenter` n'ont pas suffi (neuf lignes), et c'est une
  information : ce fichier n'était pas long par duplication, il était long parce
  qu'il porte DEUX écrans — les lots et la gestion locative. La coupe suit donc
  cette frontière-là, celle que la barre d'onglets dessine déjà.

  ## Ses gestes vivent ici (01/10/2026, #779)

  Créer, terminer et supprimer un bail, recoudre son inventaire, affecter ses
  accès : ces gestes n'ont jamais servi qu'à cet onglet, et la page les tenait
  pour les lui redescendre en dix-sept props. La raison donnée — « les modales
  de confirmation vivent dans l'écran » — est tombée avec elles : terminer se
  confirme EN PLACE dans la carte (`GesteEnPlace`), et supprimer passe par
  `confirmerPuis(SUPPRESSION(…))`.

  ⚠️ Ce qui reste à la page, et pourquoi : la liste des baux (`bind:baux`), que
  la vue bailleur lit aussi ; l'ouverture de la création et les lots cochés,
  que l'en-tête et la vue bailleur posent ; la correction d'un locataire et ses
  accès, qui s'ouvrent aussi depuis la vue bailleur.
-->
<script lang="ts">
	import FormulaireBail from '#lib/components/FormulaireBail.svelte';
	import InventaireBail from '#lib/components/InventaireBail.svelte';
	import { fmtDateShort as fmt } from '#lib/date.ts';
	import { lotTypeComplet } from '#lib/utils.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import GesteEnPlace from '#lib/components/GesteEnPlace.svelte';
	import Onglet from '#lib/components/Onglet.svelte';
	import { isCS } from '#lib/stores/auth.ts';
	import { TITRE_ARCHIVES } from '#lib/archives.ts';
	import { bailleur as bailApi, type Bail, type MonLot, type ObjetRemis } from '#lib/api/index.ts';
	import { bailVierge, nomLocataire } from '#lib/bail.ts';
	import { confirmerPuis, SUPPRESSION } from '#lib/confirmation.ts';
	import { messageErreur, tenter } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { etageLabel, lotTypeLabel } from '#lib/utils.ts';

	//  Les routes viennent de la TABLE, jamais écrites ici (`lint:pages`).
	const ROUTE_BAUX_ACTIFS = routeSousOnglet('mon-lot', 'location', 'actif');
	const ROUTE_BAUX_ARCHIVES = routeSousOnglet('mon-lot', 'location', 'archives');
	import { routeSousOnglet } from '#lib/routes-onglets.ts';
	import BadgeStatutBail from '#lib/components/BadgeStatutBail.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';

	/**  Les baux — LIÉS : la vue bailleur de la page les lit aussi, et chaque
	 *   geste d'ici les met à jour. */
	export let baux: Bail[] = [];
	export let bauxActifs: Bail[] = [];
	export let bauxTermines: Bail[] = [];
	export let bauxLoading = false;
	export let lots: MonLot[] = [];

	/** Le sous-onglet courant — « actif » ou « archives ». */
	export let bailTab = 'actif';

	/** La boîte de création, ouverte depuis l'en-tête ou la vue bailleur. */
	export let showNewBail = false;
	export let newBailLotIds: Set<number> = new Set();

	/**  Les gestes qui s'ouvrent aussi depuis la vue bailleur : la page les tient. */
	export let ouvrirEditionLocataire: (bail: Bail) => void;
	export let ouvrirAccesBail: (bail: Bail) => void;
	/**  Relire les baux que ce compte gère — la règle vit dans la page, qui
	 *   les charge selon le rôle. */
	export let lireBaux: () => Promise<Bail[]> | null;

	let newBail = bailVierge();
	let savingBail = false;
	let newBailLocataireId: number | null = null;
	let bailATerminer: Bail | null = null;
	let dateSortie = '';

	async function creerBail() {
		if (newBailLotIds.size === 0 || !newBail.date_entree) {
			toast('error', "Sélectionnez au moins un lot et renseignez la date d'entrée");
			return;
		}
		savingBail = true;
		try {
			const nouvellesBaux = await bailApi.creerBailMulti({
				lot_ids: [...newBailLotIds],
				...newBail,
				locataire_id: newBailLocataireId ?? null,
				date_sortie_prevue: newBail.date_sortie_prevue || null,
			});
			baux = [...nouvellesBaux, ...baux];
			showNewBail = false;
			newBailLotIds = new Set();
			newBail = bailVierge();
			//  L'état de la RECHERCHE de locataire vit dans `FormulaireBail` : il
			//  n'a d'existence que pendant la saisie. Le formulaire est démonté par
			//  `showNewBail = false`, donc il repart vierge — rien à réinitialiser
			//  ici, et surtout rien à réinitialiser DEUX fois.
			newBailLocataireId = null;
			toast(
				'success',
				nouvellesBaux.length > 1 ? `${nouvellesBaux.length} baux créés` : 'Bail créé',
			);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			savingBail = false;
		}
	}

	async function confirmerTerminer() {
		if (!bailATerminer) return;
		const cible = bailATerminer;
		await tenter(async () => {
			const updated = await bailApi.terminerBail(cible.id, {
				date_sortie_reelle: dateSortie || null,
			});
			baux = baux.map((b) => (b.id === updated.id ? updated : b));
			bailATerminer = null;
		}, 'Bail terminé');
	}

	/**  Supprimer un bail (conseil syndical) — confirmé par `SUPPRESSION`, comme
	 *   toute suppression définitive (`lint:suppression-confirmee`). La modale
	 *   écrite ici à la main en était la dernière copie avec celle des comptes. */
	function supprimerBail(bail: Bail) {
		return confirmerPuis(
			SUPPRESSION(`Le bail de ${nomLocataire(bail)} et tous ses objets associés.`),
			'Bail supprimé',
			async () => {
				await bailApi.supprimerBail(bail.id);
				baux = baux.filter((b) => b.id !== bail.id);
			},
		);
	}

	//  `confirmerRetour` et `supprimerObjet` sont partis dans `InventaireBail`
	//  (#806) : quatre gestes sur une sous-entité entièrement contenue dans le
	//  bail. La page n'en apprend que le résultat, par `on:change`.
	/**  Recoud la liste d'objets d'un bail après un geste du composant. */
	function majObjets(bailId: number, objets: ObjetRemis[]) {
		baux = baux.map((b) => (b.id === bailId ? { ...b, objets } : b));
	}

	async function affecterAuto(bail: Bail) {
		try {
			const accesAll = await bailApi.accesBail(bail.id);
			const vigikIds: number[] = [];
			const tcIds: number[] = [];
			for (const a of accesAll) {
				if (!a.eligible_transfert || a.chez_locataire || !a.recommande) continue;
				if (a.type === 'vigik') vigikIds.push(a.id);
				else tcIds.push(a.id);
			}
			if (vigikIds.length === 0 && tcIds.length === 0) {
				toast('info', 'Aucun accès à affecter automatiquement');
				return;
			}
			await bailApi.transfererAcces(bail.id, { vigik_ids: vigikIds, tc_ids: tcIds });
			const n = vigikIds.length + tcIds.length;
			toast('success', `${n} accès affecté${n > 1 ? 's' : ''} automatiquement`);
			const lecture = lireBaux();
			if (lecture) baux = await lecture;
		} catch (e) {
			toast('error', messageErreur(e, "Erreur lors de l'affectation automatique"));
		}
	}

	//  🔴 `typeLabel`, `statutObjetBadge` et `statutObjetLabel` sont partis AVEC le
	//  balisage qui les emploie (`InventaireBail`, #806). Les laisser ici aurait
	//  produit un tableau nu chez le voisin — le défaut de `standards/02` §4 ter,
	//  celui qui ne casse rien et qui se voit en production.

	//  🔴 La table des libellés vivait ICI, puis descendait en prop chez
	//  `OngletGestionLocative`, qui recomposait la TEINTE du même état en
	//  ternaire. Le libellé et la couleur d'un état sont deux attributs d'une
	//  même chose : ils se déclarent ensemble, dans `#lib/bail`.

	//  Les lots tels que `FormulaireBail` les attend : un libellé et un état.
	//  🔴 La préparation vit ICI, pas dans le composant : `lotLabel` s'appuie sur
	//  `lotTypeLabel`, qui sert encore à l'affichage des accès plus bas. L'emporter
	//  dans le composant en aurait fait une deuxième écriture.
	$: lotsACocher = lots.map((l) => ({
		id: l.id,
		libelle: lotLabel(l),
		occupe: !!bauxActifs.find((b) => b.lot_id === l.id),
	}));

	function lotLabel(lot: MonLot): string {
		const bat = lot.batiment_nom ?? '—';
		const type = lotTypeLabel(lot.type);
		const sub = lot.type_appartement ? ` ${lot.type_appartement}` : '';
		//  ⚠️ SEPTIÈME écriture du libellé d'étage, et quatrième rendu (« Ét. 2 »).
		//  Trouvée par `lint:etage-libelle`, pas par ma relecture : elle est dans
		//  une fonction, pas dans le gabarit, et le relevé à la main l'avait sautée.
		const etiquette = etageLabel(lot.etage);
		const etage = etiquette ? ` · ${etiquette}` : '';
		const surface = lot.superficie ? ` · ${lot.superficie} m²` : '';
		return `${bat} — ${type}${sub} n°${lot.numero}${etage}${surface}`;
	}
</script>

<div class="colonne">
	<!--  🔴 LA BOÎTE DANS LA PAGE, et non une modale (#367 / #672).

	      « Nouveau bail » était la dernière modale de création du site. Elle y
	      avait échappé parce que `lint:formulaires` ne cherchait qu'un `<form>`,
	      et ce formulaire n'en porte aucun — seulement des `.field`.

	      ⚠️ Le corps vit dans `FormulaireBail.svelte` : cette page pesait 2 229
	      lignes, et le contrôle de modularité refusait d'y ajouter la moindre
	      ligne. Comme les huit refus précédents, il désignait un PLACEMENT — la
	      saisie d'un bail n'a rien à faire dans l'écran qui liste les lots, les
	      baux, les accès et les diagnostics. -->
	{#if showNewBail}
		<FormulaireBail
			lots={lotsACocher}
			bind:lotIds={newBailLotIds}
			bind:bail={newBail}
			bind:locataireId={newBailLocataireId}
			enregistrement={savingBail}
			on:annuler={() => (showNewBail = false)}
			on:enregistrer={creerBail}
		/>
	{/if}

	<!--  Deux LIENS, pas deux boutons : le sous-onglet a une adresse, donc il
	      s'envoie, le bouton Précédent le retrouve et le clic milieu l'ouvre à
	      côté. Et c'est `Onglet` qui les rend : `.bail-tabs` était une rangée
	      d'onglets de plus, avec ses 25 lignes de style et sans les trois marques
	      de l'onglet actif (`ux-patterns` §4 bis). -->
	<div class="tabs sous-onglets">
		<Onglet href={ROUTE_BAUX_ACTIFS} actif={bailTab === 'actif'}>
			Baux actifs ({bauxActifs.length})
		</Onglet>
		<Onglet href={ROUTE_BAUX_ARCHIVES} actif={bailTab === 'archives'}>
			{TITRE_ARCHIVES} ({bauxTermines.length})
		</Onglet>
	</div>

	{#if bauxLoading}
		<EtatListe chargement />
	{:else}
		{@const displayed = bailTab === 'actif' ? bauxActifs : bauxTermines}
		{@const grouped = (() => {
			const map = new Map();
			for (const b of displayed) {
				const key = b.locataire_id ?? `ext_${b.id}`;
				if (!map.has(key)) map.set(key, { bail: b, baux: [] });
				map.get(key).baux.push(b);
			}
			return [...map.values()];
		})()}

		{#if grouped.length === 0}
			<div class="empty-state">
				<p>{bailTab === 'actif' ? 'Aucun bail actif.' : 'Aucun bail terminé.'}</p>
			</div>
		{:else}
			{#each grouped as group (group)}
				{@const premierBail = group.bail}
				<div class="card carte-locataire">
					<!-- En-tête locataire -->
					<div class="entete-locataire">
						<div>
							<div class="nom-locataire">{nomLocataire(premierBail)}</div>
							{#if premierBail.locataire_email}
								<div class="text-muted-md">
									{premierBail.locataire_email}
								</div>
							{/if}
							{#if premierBail.locataire_telephone}
								<div class="text-muted-md">
									{premierBail.locataire_telephone}
								</div>
							{/if}
						</div>
						<div class="form-actions">
							<BadgeStatutBail statut={premierBail.statut} />
						</div>
					</div>

					<!-- Actions globales locataire -->
					{#if premierBail.statut !== 'termine'}
						<div class="gestes">
							<button
								class="btn-icon-edit"
								aria-label="Modifier"
								title="Modifier"
								on:click={() => ouvrirEditionLocataire(premierBail)}>&#x270F;&#xFE0F;</button
							>
							<button class="btn btn-sm" on:click={() => ouvrirAccesBail(premierBail)}
								>&#x1F511; Accès</button
							>
						</div>
					{/if}

					<!-- Détails par bail (lot) -->
					{#each group.baux as bail (bail.id)}
						{@const lot = lots.find((l) => l.id === bail.lot_id)}
						<div class="bloc-bail">
							<div class="entete-bail">
								<div class="lot-bail">
									{#if lot}
										<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
										<span class="badge badge-gray type-lot"
											>{lotTypeComplet(lot.type, lot.type_appartement)}</span
										>
									{/if}
									{#if group.baux.length > 1}
										<BadgeStatutBail statut={bail.statut} compact />
									{/if}
								</div>
								{#if bail.statut !== 'termine'}
									<button
										class="btn btn-xs btn-outline"
										on:click={() => affecterAuto(bail)}
										title="Affecter automatiquement les accès recommandés"
									>
										🪄 Auto
									</button>
									<!--  Le MODE se lit sur le bouton qui l'a ouvert
									      (`aria-pressed`, `ux-patterns` §13 bis). -->
									<button
										class="btn btn-xs btn-danger"
										aria-pressed={bailATerminer?.id === bail.id}
										on:click={() => {
											bailATerminer = bailATerminer?.id === bail.id ? null : bail;
											dateSortie = '';
										}}
									>
										{bailATerminer?.id === bail.id ? 'Annuler' : 'Terminer'}
									</button>
								{/if}
								{#if $isCS}
									<button
										class="btn btn-xs btn-danger"
										on:click={() => {
											void supprimerBail(bail);
										}}
									>
										🗑️ Supprimer
									</button>
								{/if}
							</div>

							<!--  Le geste s'ouvre DANS la carte du bail (#889) : il était en
							      fenêtre, pour UN champ de date sur un objet de liste. -->
							{#if bailATerminer?.id === bail.id}
								<GesteEnPlace
									danger
									question={`Confirmer la fin du bail de <strong>${nomLocataire(bail)}</strong> ?`}
									onAnnuler={() => (bailATerminer = null)}
									onValider={confirmerTerminer}
								>
									<label class="field champ-moyen">
										Date de sortie réelle
										<input type="date" bind:value={dateSortie} />
									</label>
								</GesteEnPlace>
							{/if}

							<div class="dates-bail">
								<span><strong>Entrée :</strong> {fmt(bail.date_entree)}</span>
								<span><strong>Sortie prévue :</strong> {fmt(bail.date_sortie_prevue)}</span>
								{#if bail.date_sortie_reelle}
									<span><strong>Sortie réelle :</strong> {fmt(bail.date_sortie_reelle)}</span>
								{/if}
							</div>

							{#if bail.notes}
								<div class="rich-content notes-bail">
									{@html safeHtml(bail.notes)}
								</div>
							{/if}

							<InventaireBail
								bailId={bail.id}
								objets={bail.objets}
								modifiable={bail.statut !== 'termine'}
								on:change={(e) => majObjets(bail.id, e.detail)}
							/>
						</div>
					{/each}
				</div>
			{/each}
		{/if}
	{/if}
</div>

<style>
	/*  Le style suit le BALISAGE : ces règles étaient restées dans l'écran quand
	    l'onglet est parti ici (12/09/2026, #928). */
	.sous-onglets {
		margin-bottom: 1.5rem;
	}
	/*  `.lbc-lot-badge` est dans la charte depuis le 30/09/2026 (#779). */
	.colonne {
		max-width: 900px;
	}
	.carte-locataire {
		margin-bottom: 1.5rem;
		padding: 1.25rem;
	}
	.entete-locataire {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		margin-bottom: 1rem;
	}
	.nom-locataire {
		font-weight: 700;
		font-size: var(--fs-xl);
	}
	.gestes {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
		flex-wrap: wrap;
	}
	.bloc-bail {
		border-top: 1px solid var(--color-border);
		padding-top: 1rem;
		margin-top: 1rem;
	}
	.entete-bail {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.6rem;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.lot-bail {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.type-lot {
		font-size: var(--fs-2xs);
		text-transform: capitalize;
	}
	.dates-bail {
		display: flex;
		gap: 2rem;
		font-size: var(--fs-md);
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}
	.notes-bail {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-bottom: 0.75rem;
		font-style: italic;
	}
</style>
