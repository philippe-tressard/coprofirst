<script lang="ts">
	import { confirmer, SUPPRESSION } from '#lib/confirmation.ts';
	import { FAQ } from '#lib/entites/faq.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import FormulaireFaq from '#lib/components/FormulaireFaq.svelte';
	import CarteFaq from '#lib/components/CarteFaq.svelte';
	import ReorganisationFaq from '#lib/components/ReorganisationFaq.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import EntetePage from '#lib/components/EntetePage.svelte';
	import { onMount } from 'svelte';
	import { marquerDonneesAffichees } from '#lib/telemetry.ts';
	import { cibleDuHash, revelerCible } from '#lib/deepLink.ts';
	import { faq as faqApi, manuel, type EntreeFaq } from '#lib/api/index.ts';
	import { isCS, currentUser } from '#lib/stores/auth.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		getPageConfig,
		configStore,
		siteNomStore,
		defautsDePage,
	} from '#lib/stores/pageConfig.ts';
	import {
		categoriesPourStatut,
		categorieSaisie,
		estQuestionPrixBadge,
		grouperParCategorie,
		normalizeCategorieLabel,
		saisieFaqDepuis,
		saisieFaqVide,
		type SaisieFaq,
	} from '#lib/faq.ts';
	import { richEmpty } from '#lib/publications.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { essayer } from '#lib/chargement.ts';
	import BoutonNouveau from '#lib/components/BoutonNouveau.svelte';

	$: _pc = getPageConfig($configStore, 'faq', defautsDePage('faq'));
	$: _siteNom = $siteNomStore;

	let open: Record<number, boolean> = {};
	let items: EntreeFaq[] = [];
	let loading = true;
	//  Un échec de chargement se DIT (#1329) : il s'affichait « Aucune question ».
	let erreur = '';

	// ---- edition ----
	let showForm = false;
	let editingItem: EntreeFaq | null = null;
	let form: SaisieFaq = saisieFaqVide();
	let saving = false;
	let existingCategories: string[] = [];
	let erreurCategories = '';

	//  Le mode « Réorganiser » vit dans `ReorganisationFaq` (#779).
	let reorderMode = false;

	$: canEdit = $isCS;

	$: grouped = grouperParCategorie(items);
	// Masquer les catégories FAQ non pertinentes selon le statut
	$: filteredGrouped = canEdit ? grouped : categoriesPourStatut(grouped, $currentUser?.statut);

	onMount(async () => {
		await loadFaq();
		// `#faq-<id>` : question visée par le fil d'activité ou une notification.
		const idFaq = cibleDuHash('faq');
		if (idFaq !== null) {
			open = { [idFaq]: true };
			revelerCible(`faq-${idFaq}`);
		}

		// `#badge-prix` : raccourci historique, documenté dans le manuel et utilisé
		// depuis /acces-securite — il vise la question par son libellé, pas par son
		// id, qui varie d'une instance à l'autre.
		if (typeof window !== 'undefined' && window.location.hash === '#badge-prix') {
			const badgeItem = items.find((i) => estQuestionPrixBadge(i.question));
			if (badgeItem) {
				open = { [badgeItem.id]: true };
				revelerCible(`faq-${badgeItem.id}`);
			}
		}
	});

	async function loadFaq() {
		loading = true;
		erreur = '';
		try {
			items = canEdit ? await faqApi.listAll() : await faqApi.list();
		} catch (e) {
			items = [];
			erreur = messageErreur(e);
		} finally {
			loading = false;
			//  Une fois par écran : un rechargement de la liste ne remesure rien.
			marquerDonneesAffichees();
		}
	}

	function toggle(id: number) {
		const wasOpen = open[id];
		open = { [id]: !wasOpen };
	}

	//  Les catégories en service, relues à chaque ouverture — écrit deux fois avant #1329.
	async function chargerCategories() {
		//  En échec, le cache précédent reste — et l'échec se dit (#1459).
		[existingCategories, erreurCategories] = await essayer(faqApi.categories(), existingCategories);
	}

	async function openNew() {
		editingItem = null;
		form = saisieFaqVide();
		await chargerCategories();
		showForm = true;
	}

	async function openEdit(it: EntreeFaq) {
		editingItem = it;
		await chargerCategories();
		form = saisieFaqDepuis(it, existingCategories);
		showForm = true;
	}

	async function saveItem() {
		if (!form.question.trim() || richEmpty(form.reponse)) {
			toast('error', 'Question et réponse sont obligatoires.');
			return;
		}
		const categorie = categorieSaisie(form);
		if (!categorie) {
			toast('error', 'La catégorie est obligatoire.');
			return;
		}
		saving = true;
		try {
			// Calcul auto de l'ordre : dernier de la catégorie + 1
			const catItems = items.filter(
				(i) => normalizeCategorieLabel(i.categorie) === normalizeCategorieLabel(categorie),
			);
			const maxOrdre = catItems.length ? Math.max(...catItems.map((i) => i.ordre ?? 0)) : -1;
			const ordre = editingItem ? editingItem.ordre : maxOrdre + 1;

			const payload = {
				categorie,
				question: form.question.trim(),
				reponse: form.reponse.trim(),
				ordre,
				actif: true,
			};
			if (editingItem) {
				const id = editingItem.id;
				const updated = await faqApi.update(id, payload);
				items = items.map((i) => (i.id === id ? updated : i));
				toast('success', 'Élément mis à jour.');
			} else {
				const created = await faqApi.create(payload);
				items = [...items, created];
				toast('success', 'Élément ajouté.');
			}
			showForm = false;
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			saving = false;
		}
	}

	async function deleteItem(it: EntreeFaq) {
		if (!(await confirmer(SUPPRESSION(`« ${it.question} »`)))) return;
		try {
			await faqApi.delete(it.id);
			items = items.filter((i) => i.id !== it.id);
			toast('info', 'Élément supprimé.');
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function toggleActif(it: EntreeFaq) {
		try {
			const updated = await faqApi.update(it.id, { actif: !it.actif });
			items = items.map((i) => (i.id === it.id ? updated : i));
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	// ---- rename category ----
	let editingCategory: string | null = null;
	let editCategoryName = '';
	let savingCategory = false;

	function startEditCategory(cat: string) {
		editingCategory = cat;
		editCategoryName = cat;
	}

	function cancelEditCategory() {
		editingCategory = null;
		editCategoryName = '';
	}

	async function saveCategory() {
		if (!editCategoryName.trim() || !editingCategory) return;
		if (editCategoryName.trim() === editingCategory) {
			cancelEditCategory();
			return;
		}
		savingCategory = true;
		try {
			await faqApi.renameCategory(editingCategory, editCategoryName.trim());
			// Mettre à jour localement
			const oldName = editingCategory;
			const newName = editCategoryName.trim();
			items = items.map((i) => (i.categorie === oldName ? { ...i, categorie: newName } : i));
			toast('success', 'Catégorie renommée.');
			cancelEditCategory();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			savingCategory = false;
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'help-circle'}>
	{#if canEdit}
		{#if !reorderMode}
			<button class="btn btn-outline page-header-btn" on:click={() => (reorderMode = true)}
				><Icon name="move" size={15} /> Réorganiser</button
			>
			<BoutonNouveau
				ouvert={showForm && !editingItem}
				libelle={FAQ.libelleNouveau}
				on:basculer={openNew}
			/>
		{/if}
	{/if}
</EntetePage>

<!--  La CRÉATION s'ouvre en tête de la liste ; la correction, dans la carte de
      la question (#1329) — les deux s'ouvraient en bas de page, après l'aide. -->
{#if showForm && !editingItem}
	<FormulaireFaq
		cle="creation"
		bind:form
		categories={existingCategories}
		{erreurCategories}
		enregistrement={saving}
		onEnregistrer={saveItem}
		on:annule={() => (showForm = false)}
	/>
{/if}

{#if loading || erreur || items.length === 0}
	<EtatListe
		chargement={loading}
		{erreur}
		vide={items.length === 0}
		titreErreur="Impossible d’afficher la FAQ"
		titreVide="Aucune question pour l'instant"
	/>
{:else if reorderMode}
	<ReorganisationFaq
		{items}
		on:fermer={(e) => {
			if (e.detail) items = e.detail;
			reorderMode = false;
		}}
	>
		<h2 slot="titre" class="categorie-title" let:categorie>{categorie}</h2>
	</ReorganisationFaq>
{:else}
	{#each Object.entries(filteredGrouped) as [categorie, catItems] (categorie)}
		<div class="entete-categorie">
			{#if canEdit && editingCategory === categorie}
				<div class="categorie-edit">
					<input
						class="input-field categorie-input"
						type="text"
						bind:value={editCategoryName}
						on:keydown={(e) => {
							if (e.key === 'Enter') saveCategory();
							if (e.key === 'Escape') cancelEditCategory();
						}}
					/>
					<button
						class="btn-icon-edit"
						on:click={saveCategory}
						disabled={savingCategory}
						title="Valider"
						aria-label="Valider"><IconeAction icone="check" /></button
					>
					<button
						class="btn-icon-edit"
						on:click={cancelEditCategory}
						disabled={savingCategory}
						title="Annuler"
						aria-label="Annuler"><IconeAction icone="x" /></button
					>
				</div>
			{:else}
				<h2 class="categorie-title">{categorie}</h2>
				{#if canEdit}
					<button
						class="btn-icon-edit btn-edit-cat"
						on:click={() => startEditCategory(categorie)}
						title="Renommer la catégorie"
						aria-label="Renommer la catégorie"><IconeAction icone="pencil" /></button
					>
				{/if}
			{/if}
		</div>
		{#each catItems as item (item.id)}
			<CarteFaq
				{item}
				ouvert={!!open[item.id]}
				{canEdit}
				avecCta={estQuestionPrixBadge(item.question)}
				enEdition={showForm && editingItem?.id === item.id}
				on:basculer={() => toggle(item.id)}
				on:modifier={() => (editingItem?.id === item.id ? (showForm = false) : openEdit(item))}
				on:basculerActif={() => toggleActif(item)}
				on:supprimer={() => deleteItem(item)}
			>
				<FormulaireFaq
					slot="formulaire"
					modeEdition
					cle={item.id}
					bind:form
					categories={existingCategories}
					{erreurCategories}
					enregistrement={saving}
					onEnregistrer={saveItem}
					on:annule={() => (showForm = false)}
				/>
			</CarteFaq>
		{/each}
	{/each}
{/if}

<div class="still-need-help card">
	<strong>Vous ne trouvez pas la réponse ?</strong>
	<p>
		Créez une affaire via la rubrique <a href="/tickets">Affaires</a> et le conseil syndical vous répondra
		dans les meilleurs délais.
	</p>
	<p class="renvoi-manuel">
		<span class="icone-manuel"><Icon name="book-open" size={15} /></span>Le
		<a href="/manuel-utilisateur.html" target="_blank" rel="noopener">Manuel utilisateur</a>
		vous guide pas à pas, et existe
		<a href={manuel.pdfUrl()} target="_blank" rel="noopener">en PDF</a>.
	</p>
</div>

<style>
	.categorie-title {
		font-size: var(--fs-md);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin: 1.5rem 0 0.5rem;
	}
	.btn-edit-cat {
		opacity: 0.4;
		font-size: var(--fs-xs);
		transition: opacity var(--duree-geste);
		margin-top: 0.75rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.btn-edit-cat:hover {
			opacity: 1;
		}
	}
	.categorie-edit {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 1.25rem 0 0.35rem;
	}
	.categorie-input {
		font-size: var(--fs-md);
		font-weight: 700;
		padding: 0.3rem 0.5rem;
		max-width: 300px;
	}
	.still-need-help {
		margin-top: 2rem;
		padding: 1.25rem;
	}
	.still-need-help p {
		margin: 0.5rem 0 0;
		font-size: var(--fs-base);
		color: var(--color-text-muted);
	}
	/*  Ne sert plus qu'au renommage de catégorie EN LIGNE. Fond explicite : son absence rendait les champs blancs (#413). */
	.input-field {
		padding: 0.45rem 0.65rem;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		font-size: var(--fs-base);
		font-family: inherit;
		width: 100%;
		box-sizing: border-box;
		resize: vertical;
		background: var(--color-bg);
		color: var(--color-text);
	}
	.btn-outline {
		padding: 0.4rem 0.9rem;
	} /* le reste vient de la charte (#607) */
	.entete-categorie {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.renvoi-manuel {
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}
	.icone-manuel {
		vertical-align: middle;
		margin-right: 0.3rem;
		display: inline-flex;
	}
</style>
