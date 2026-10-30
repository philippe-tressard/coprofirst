<!--
  **L'inventaire d'un bail** — ce qui a été remis au locataire, et les gestes
  qui le tiennent à jour.

  ## 🔴 Pourquoi ce composant (#806, 06/09/2026)

  Le tableau existait dans `mon-lot`, avec deux gestes : marquer un objet rendu,
  et le supprimer. Il manquait celui **par lequel tout commence** — enregistrer
  un objet.

  Et le constat était plus large que le ticket ne le disait : `BailCreateMulti`
  ne porte **aucun objet**. `POST /bailleur/baux/{id}/objets` était donc la seule
  façon d'en enregistrer un, et aucun écran ne l'appelait. Autrement dit,
  l'inventaire d'un bail créé depuis l'interface affichait **toujours** « Aucun
  objet enregistré », et les deux boutons présents portaient sur des lignes qui
  ne pouvaient pas exister.

  C'est le cas exact de `sondages.modifier` (#783) : chemin serveur complet,
  testé, déployé, et inatteignable — sauf qu'ici il manquait le geste de
  création, pas seulement celui de correction.

  ## Créer et corriger emploient LE MÊME formulaire

  `ux-patterns` §14 bis : la boîte dans la page, pour les deux gestes, par
  `CadreFormulaire`. Ce qui le rend possible sans divergence, c'est
  l'enrichissement de `ObjetUpdate` côté serveur — `type` et `remis_le` y ont été
  ajoutés le même jour. Un schéma plus pauvre que son jumeau force l'écran à
  diverger, et la divergence devient une dette à déclarer (motif `api`, R4) :
  autant ne pas la créer.

  ⚠️ Ce qui reste hors du formulaire : **le statut et la date de retour**. Un
  retour se prononce par son propre geste (`↩`), qui pose les deux ensemble. Les
  ouvrir ici donnerait deux chemins vers le même fait, dont un capable d'écrire
  « rendu » sans date.

  ## Ce que ce composant emporte, et pourquoi il parle à l'API

  Les objets sont une sous-entité **entièrement contenue** dans le bail : le
  parent n'a rien à en savoir sinon que la liste a changé (`on:change`). Y
  laisser les appels aurait dispersé quatre gestes sur deux fichiers, dont un de
  1 600 lignes — c'est le contraire de ce que l'extraction cherche.

  ⚠️ Les trois tables de libellés (`typeLabel`, `statutObjetBadge`,
  `statutObjetLabel`) partent AVEC le balisage qui les emploie : les laisser
  derrière aurait produit un tableau nu, le défaut de `standards/02` §4 ter.

  ## 🔴 Ce fichier n'est PAS mesuré par `lint:css-orphelin` (#810)

  Il porte `class="badge {statutObjetBadge[objet.statut] ?? …}"`. Devant une
  classe interpolée, Svelte ne peut pas résoudre ce qui sera rendu : il cesse de
  déclarer des sélecteurs inutilisés **pour tout le fichier**.

  C'est en sortant ce tableau de `mon-lot` que dix sélecteurs morts depuis
  longtemps y sont apparus d'un coup — l'écran entier était aveuglé par cette
  seule ligne. Le contrôle annonce désormais sa portée réelle (142/172 fichiers),
  et la dette est suivie en #810.

  ⚠️ L'interpolation n'est pas fautive pour autant : c'est la table qui est la
  source unique du couple statut → badge. L'éclater en cinq `class:` recréerait
  la duplication que la table supprime. Le sujet est le CONTRÔLE, pas ce code.
-->
<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import Badge from '#lib/components/Badge.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { confirmer, SUPPRESSION } from '#lib/confirmation.ts';
	import { createEventDispatcher } from 'svelte';
	import { bailleur as bailApi, type ObjetRemis } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { fmtDate } from '#lib/date.ts';
	import CadreFormulaire from '#lib/components/CadreFormulaire.svelte';
	import ChampsObjetRemis from '#lib/components/ChampsObjetRemis.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { parAttribut } from '#lib/table-statuts.ts';

	/** Le bail dont on tient l'inventaire. */
	export let bailId: number;
	export let objets: ObjetRemis[] = [];
	/**  Faux sur un bail terminé : l'inventaire se lit encore, il ne se modifie
	 *   plus. C'est la condition qui gouvernait déjà la colonne d'actions. */
	export let modifiable = true;

	const dispatch = createEventDispatcher<{ change: ObjetRemis[] }>();

	//  Les quatre types — une liste de 4, donc des pastilles (`ux-patterns`, seuil
	//  des listes courtes). `ChoixPastilles` la rend, plutôt qu'un `<select>` nu.
	const TYPES = [
		{ val: 'cle', label: '\u{1F511} Clé' },
		{ val: 'telecommande', label: '\u{1F4E1} Télécommande' },
		{ val: 'vigik', label: '\u{1F3F7}\u{FE0F} Vigik' },
		{ val: 'autre', label: '\u{1F4E6} Autre' },
	] as const;

	const typeLabel: Record<string, string> = Object.fromEntries(TYPES.map((t) => [t.val, t.label]));

	const { libelle: statutObjetLabel, badge: statutObjetBadge } = parAttribut({
		en_possession: { libelle: 'En possession', badge: 'badge-green' },
		rendu: { libelle: 'Rendu', badge: 'badge-blue' },
		perdu: { libelle: 'Perdu', badge: 'badge-red' },
		non_remis: { libelle: 'Non remis', badge: 'badge-gray' },
	});

	//  ── La saisie ────────────────────────────────────────────────────────────
	//  `null` = fermée · `{id: null}` = création · `{id: n}` = correction. Un seul
	//  état pour les deux gestes : c'est ce que dit `ux-patterns` §14 bis, et
	//  c'est ce qui empêche d'ouvrir les deux à la fois.
	let saisie: { id: number | null } | null = null;
	let enregistrement = false;

	let fType = 'cle';
	let fLibelle = '';
	let fQuantite = 1;
	let fReference = '';
	let fRemisLe = '';
	let fNotes = '';

	function ouvrirCreation() {
		saisie = { id: null };
		fType = 'cle';
		fLibelle = '';
		fQuantite = 1;
		fReference = '';
		fRemisLe = '';
		fNotes = '';
	}

	function ouvrirCorrection(o: ObjetRemis) {
		//  Un second clic sur la même ligne referme — même geste que les cartes
		//  d'annonce et d'idée.
		if (saisie?.id === o.id) {
			saisie = null;
			return;
		}
		saisie = { id: o.id };
		fType = o.type;
		fLibelle = o.libelle;
		fQuantite = o.quantite;
		fReference = o.reference ?? '';
		fRemisLe = o.remis_le ?? '';
		fNotes = o.notes ?? '';
	}

	async function enregistrer() {
		if (!saisie) return;
		enregistrement = true;
		//  ⚠️ Les champs vides partent en `null`, jamais en chaîne vide : le
		//  serveur distingue « pas de référence » de « référence égale à rien », et
		//  c'est `null` qui s'affiche « — » à la relecture.
		const corps = {
			type: fType,
			libelle: fLibelle.trim(),
			quantite: fQuantite,
			reference: fReference.trim() || null,
			remis_le: fRemisLe || null,
			notes: fNotes.trim() || null,
		};
		try {
			if (saisie.id === null) {
				const cree = await bailApi.ajouterObjet(bailId, corps);
				objets = [...objets, cree];
				toast('success', 'Objet ajouté à l’inventaire.');
			} else {
				const maj = await bailApi.updateObjet(bailId, saisie.id, corps);
				objets = objets.map((o) => (o.id === maj.id ? maj : o));
				toast('success', 'Objet corrigé.');
			}
			saisie = null;
			dispatch('change', objets);
		} catch (e) {
			toast('error', messageErreur(e, 'Enregistrement impossible'));
		} finally {
			enregistrement = false;
		}
	}

	//  ── Le retour ────────────────────────────────────────────────────────────
	//  ⚠️ Il reste en MODALE, contrairement au formulaire ci-dessus. Ce n'est pas
	//  un oubli : `mon-lot` porte quatre modales (terminer un bail, gérer les
	//  accès…), et n'en convertir qu'une donnerait deux paradigmes dans le même
	//  écran — exactement ce que #367 a supprimé pour la création. Leur conversion
	//  est un lot à part, comme celle de `prestataires` déjà déclarée dans
	//  `lint:formulaires`.
	let objetRetour: ObjetRemis | null = null;
	let retourDate = '';
	let retourPerdu = false;

	async function confirmerRetour() {
		if (!objetRetour) return;
		try {
			const maj = await bailApi.retourObjet(objetRetour.bail_id, objetRetour.id, {
				rendu_le: retourDate || null,
				perdu: retourPerdu,
			});
			objets = objets.map((o) => (o.id === maj.id ? maj : o));
			objetRetour = null;
			toast('success', retourPerdu ? 'Objet marqué perdu' : 'Retour enregistré');
			dispatch('change', objets);
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function supprimer(o: ObjetRemis) {
		if (!(await confirmer(SUPPRESSION(`« ${o.libelle} »`)))) return;
		try {
			await bailApi.supprimerObjet(bailId, o.id);
			objets = objets.filter((x) => x.id !== o.id);
			if (saisie?.id === o.id) saisie = null;
			toast('success', 'Objet supprimé');
			dispatch('change', objets);
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}
</script>

<!--  🔴 LE FORMULAIRE D'UN OBJET, écrit UNE fois (#1539, 02/10/2026).

      Il était rendu deux fois dans ce fichier — la création en tête, la
      correction dans la rangée de l'objet —, douze lignes identiques au titre
      près. Les deux places sont voulues (`ux-patterns` §14 ter) ; la double
      écriture ne l'était pas. Un `snippet` et non un composant : le formulaire
      ne vit qu'ici, et ses six champs sont l'état de CE composant — un fichier
      à part les aurait fait voyager en six `bind:` à chaque appel, c'est-à-dire
      recopié la duplication dans le câblage (`standards/02` §4 quinquies).

      `largeur` : la création se pose dans la page et prend la largeur de
      saisie ; la correction remplit sa rangée de tableau. -->
{#snippet formulaireObjet(titre: string, largeur: boolean)}
	<CadreFormulaire encadre={false} {titre} on:fermer={() => (saisie = null)}>
		<form class:largeur-saisie={largeur} on:submit|preventDefault={enregistrer}>
			<ChampsObjetRemis
				types={TYPES}
				bind:fType
				bind:fLibelle
				bind:fQuantite
				bind:fReference
				bind:fRemisLe
				bind:fNotes
			/>
			<PiedFormulaire enCours={enregistrement} on:annule={() => (saisie = null)} />
		</form>
	</CadreFormulaire>
{/snippet}

<div>
	<div class="inv-entete">
		<div class="inv-titre">
			Inventaire ({objets.length} objet{objets.length !== 1 ? 's' : ''})
		</div>
		{#if modifiable}
			<button
				type="button"
				class="btn btn-primary btn-xs"
				on:click={() => (saisie && saisie.id === null ? (saisie = null) : ouvrirCreation())}
			>
				{saisie && saisie.id === null ? '✕ Annuler' : '+ Ajouter un objet'}
			</button>
		{/if}
	</div>

	<!--  🔴 CETTE BOÎTE N'AJOUTE PLUS QUE — elle ne corrige plus (11/09/2026).

	      Le commentaire d'avant expliquait qu'elle était posée AVANT le tableau
	      « pour que le formulaire d'une ligne qu'on corrige reste visible quand le
	      tableau est long » (#787). C'était traiter le symptôme : la boîte restait
	      loin de la ligne, et il fallait une `cle` pour ramener l'écran à elle.

	      La correction s'ouvre désormais DANS la rangée de l'objet (`ux-patterns`
	      §14 ter, #889). Il n'y a plus rien à ramener : la boîte est là où l'on a
	      cliqué. L'ajout, lui, reste ici — son geste « + » est juste au-dessus. -->
	{#if saisie && saisie.id === null}
		{@render formulaireObjet('Nouvel objet remis', true)}
	{/if}

	{#if objets.length === 0}
		<p class="inv-vide">
			Aucun objet enregistré.
			{#if modifiable}
				Ajoutez les clés, badges et télécommandes remis au locataire : c’est cet inventaire qui fera
				foi à la sortie.
			{/if}
		</p>
	{:else}
		<div class="table-wrap">
			<table class="table table-inventaire">
				<thead>
					<tr>
						<th>Type</th>
						<th>Libellé</th>
						<th>Qté</th>
						<th>Référence</th>
						<th>Statut</th>
						<th>Remis le</th>
						<th>Rendu le</th>
						{#if modifiable}<th></th>{/if}
					</tr>
				</thead>
				<tbody>
					{#each objets as objet (objet.id)}
						<tr>
							<td>{typeLabel[objet.type] ?? objet.type}</td>
							<td>{objet.libelle}</td>
							<td class="cellule-quantite">{fmtNombre(objet.quantite)}</td>
							<td>{objet.reference ?? '—'}</td>
							<td>
								<Badge teinte={statutObjetBadge[objet.statut] ?? 'badge-gray'}>
									{statutObjetLabel[objet.statut] ?? objet.statut}
								</Badge>
							</td>
							<td>{fmtDate(objet.remis_le)}</td>
							<td>{fmtDate(objet.rendu_le)}</td>
							{#if modifiable}
								<td>
									<!--  Ordre des actions : ✏️ puis 🗑️, le retour venant en tête
									      parce qu'il est le geste propre à cette ligne
									      (`ux-patterns` §3 pour l'ordre général). -->
									<div class="inv-actions">
										{#if objet.statut === 'en_possession'}
											<button
												type="button"
												class="btn btn-xs"
												title="Enregistrer retour / perte"
												aria-label="Enregistrer le retour de {objet.libelle}"
												on:click={() => {
													objetRetour = objet;
													retourDate = '';
													retourPerdu = false;
												}}><IconeAction icone="undo-2" /></button
											>
										{/if}
										<button
											type="button"
											class="btn btn-xs"
											title="Corriger"
											aria-label="Corriger {objet.libelle}"
											aria-pressed={saisie?.id === objet.id}
											on:click={() => ouvrirCorrection(objet)}>&#x270F;&#xFE0F;</button
										>
										<button
											type="button"
											class="btn btn-xs btn-danger"
											title="Supprimer"
											aria-label="Supprimer {objet.libelle}"
											on:click={() => supprimer(objet)}>✕</button
										>
									</div>
								</td>
							{/if}
						</tr>
						{#if saisie?.id === objet.id}
							<!--  🔴 LA CORRECTION S'OUVRE SOUS LA LIGNE DE L'OBJET (#889).
							      Dans un TABLEAU, « à la place du corps » se rend par une rangée
							      qui couvre toutes les colonnes : la ligne reste lisible au-dessus,
							      comme l'en-tête d'une carte au-dessus de son formulaire. Un
							      `<div>` entre deux `<tr>` serait sorti du tableau par le
							      navigateur. -->
							<tr class="ligne-saisie">
								<td colspan={modifiable ? 8 : 7}>
									{@render formulaireObjet('Corriger l’objet', false)}
								</td>
							</tr>
						{:else if objetRetour?.id === objet.id}
							<!--  Le RETOUR aussi : c'était une `<Modale edition>`, une fenêtre qui
							      sortait l'objet de son tableau. Deux champs sur une ligne du
							      tableau se saisissent là où est la ligne. -->
							<tr class="ligne-saisie">
								<td colspan={modifiable ? 8 : 7}>
									<CadreFormulaire
										encadre={false}
										titre={`Retour — ${objet.libelle}`}
										on:fermer={() => (objetRetour = null)}
									>
										<div class="form-grid">
											<label class="field" for="ro-date-{objet.id}">
												Date de retour
												<input id="ro-date-{objet.id}" type="date" bind:value={retourDate} />
											</label>
											<label class="field inv-case">
												<input type="checkbox" bind:checked={retourPerdu} />
												Marquer comme perdu
											</label>
										</div>
										<!--  Pas de `libelle` : le verbe de soumission est GÉNÉRIQUE
											      partout (#396, `lint:pied-formulaire`). L'ancienne modale
											      disait « Perdu » ou « Retour confirmé » — une nuance que la
											      case cochée porte déjà, et qui faisait de ce bouton le
											      septième libellé différent du site. -->
										<PiedFormulaire
											enCours={enregistrement}
											soumission={false}
											on:annule={() => (objetRetour = null)}
											on:enregistre={confirmerRetour}
										/>
									</CadreFormulaire>
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<style>
	/*  La rangée qui porte une saisie — elle appartient au tableau et se distingue
	    de la ligne de l'objet sans devenir une carte. */
	.ligne-saisie > td {
		background: var(--color-primary-light);
		padding: 0.75rem;
	}

	.inv-entete {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.5rem;
	}
	.inv-titre {
		font-weight: 600;
		font-size: var(--fs-base);
	}
	.inv-vide {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	.inv-actions {
		display: flex;
		gap: 0.35rem;
	}
	/*  ⚠️ Qualifié, jamais `input` nu : un sélecteur d'élément dans un composant
	    atteint toutes les cases de la page hôte (`ux-patterns` §9 octies, et
	    `npm run lint:styles` le refuse). */
	.inv-case {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: var(--fs-base);
	}
	.table-inventaire {
		font-size: var(--fs-md);
	}
	.cellule-quantite {
		text-align: center;
	}
</style>
