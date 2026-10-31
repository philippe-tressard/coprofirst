<script lang="ts">
	import IconeAction from '#lib/components/IconeAction.svelte';
	import BoiteNouveauPerimetre from '#lib/components/BoiteNouveauPerimetre.svelte';
	import BoiteDuplicationPerimetre from '#lib/components/BoiteDuplicationPerimetre.svelte';
	import ChampsPerimetre from '#lib/components/ChampsPerimetre.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import { onMount } from 'svelte';
	import { perimetres as perimetresApi } from '#lib/api/index.ts';
	import { tenter, messageErreur } from '#lib/erreurs.ts';
	import { confirmerPuis, SUPPRESSION } from '#lib/confirmation.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { perimetresStore, rechargerPerimetres } from '#lib/stores/perimetres.ts';
	import { codeSousParent, type Perimetre } from '#lib/perimetres/index.ts';
	import { siteNomStore } from '#lib/stores/pageConfig.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	$: _siteNom = $siteNomStore;

	let chargement = true;
	let enregistrement = false;
	let ouvert: string | null = null;

	//  Une seule fiche ouverte à la fois — le pattern des listes du produit.
	function basculer(code: string) {
		ouvert = ouvert === code ? null : code;
	}

	/**  Le nœud est-il déplié ? Il l'est aussi quand on le corrige, qu'on crée
	 *   un sous-périmètre sous lui ou qu'on le duplique : la boîte vit DANS son
	 *   corps, et replier emporterait ce qu'on est en train de saisir. */
	function estDeplie(
		code: string,
		ouvertCode: string | null,
		e: Perimetre | null,
		c: { parent: string | null } | null,
		d: Perimetre | null,
	) {
		return ouvertCode === code || e?.code === code || c?.parent === code || d?.code === code;
	}

	/*  🔴 `rechargerPerimetres` avalait son échec : l'arborescence restait vide et
	    l'écran annonçait « Aucun périmètre », en invitant à en créer un. Sur une
	    copropriété qui en a douze, c'est une invitation à recréer ce qui existe
	    déjà — le pire que puisse faire un écran d'administration (#816). */
	let erreur = '';

	onMount(async () => {
		try {
			await rechargerPerimetres();
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			chargement = false;
		}
	});

	// ── Édition ───────────────────────────────────────────────────────────────
	let edite: Perimetre | null = null;
	let form = {
		libelle: '',
		libelle_court: '',
		description: '',
		icone: '',
		portee_globale: false,
		selectionnable: true,
		privatif: false,
		hors_copropriete: false,
		ordre: 0,
		actif: true,
		acces_fixes: [] as string[],
	};

	function editer(n: Perimetre) {
		//  🔴 Un seul geste à la fois : ouvrir la correction referme une création
		//  en cours, sinon les deux boîtes se disputeraient le corps du nœud.
		creation = null;
		duplique = null;
		edite = n;
		form = {
			libelle: n.libelle,
			libelle_court: n.libelle_court === n.libelle ? '' : n.libelle_court,
			description: n.description,
			icone: n.icone ?? '',
			portee_globale: n.portee_globale,
			selectionnable: n.selectionnable,
			privatif: n.privatif,
			hors_copropriete: n.hors_copropriete,
			ordre: n.ordre,
			actif: n.actif,
			acces_fixes: [...(n.acces_fixes ?? [])],
		};
	}

	async function enregistrer() {
		if (!edite) return;
		//  La cible est capturée AVANT le rappel : TypeScript ne conserve pas dans
		//  une closure le fait que `edite` n'est pas nul.
		const cible = edite;
		enregistrement = true;
		await tenter(
			async () => {
				await perimetresApi.update(cible.id, {
					libelle: form.libelle,
					libelle_court: form.libelle_court || null,
					description: form.description,
					icone: form.icone || null,
					portee_globale: form.portee_globale,
					selectionnable: form.selectionnable,
					privatif: form.privatif,
					hors_copropriete: form.hors_copropriete,
					ordre: Number(form.ordre) || 0,
					actif: form.actif,
					acces_fixes: form.acces_fixes,
				});
				await rechargerPerimetres();
				edite = null;
			},
			'Périmètre enregistré',
			'Erreur à l’enregistrement',
		);
		enregistrement = false;
	}

	// ── Création ──────────────────────────────────────────────────────────────
	let creation: { parent: string | null } | null = null;
	let nouveau = { code: '', libelle: '', description: '' };

	function creer(parent: string | null) {
		edite = null;
		duplique = null;
		creation = { parent };
		nouveau = { code: '', libelle: '', description: '' };
	}

	//  Le code est proposé à partir du libellé et du parent, mais reste modifiable :
	//  il est IMMUABLE après création (il est stocké dans les contenus publiés), donc
	//  c'est le seul moment où on peut le choisir.
	$: codePropose = creation ? codeSousParent(creation.parent, nouveau.libelle) : '';

	async function enregistrerNouveau() {
		enregistrement = true;
		await tenter(
			async () => {
				await perimetresApi.create({
					code: (nouveau.code || codePropose).trim(),
					libelle: nouveau.libelle.trim(),
					description: nouveau.description,
					parent: creation?.parent ?? null,
				});
				await rechargerPerimetres();
				creation = null;
			},
			'Périmètre créé',
			'Erreur à la création',
		);
		enregistrement = false;
	}

	// ── Duplication — le nœud et sa branche (13/10/2026) ─────────────────────
	let duplique: Perimetre | null = null;

	function dupliquer(n: Perimetre) {
		edite = null;
		creation = null;
		duplique = n;
	}

	async function supprimer(n: Perimetre) {
		//  ⚠️ Le serveur refuse la suppression d'une branche dont un nœud est cité
		//  par un contenu, et dit quoi faire à la place : `messageErreur` relaie son
		//  message tel quel, le repli ne sert que s'il n'a pas répondu du tout.
		//  Un nœud qui a des enfants les emporte : la confirmation les COMPTE, et
		//  c'est elle seule qui autorise la cascade (`avec_descendants`).
		const enfants = n.nb_descendants;
		await confirmerPuis(
			SUPPRESSION(
				enfants
					? `Le périmètre « ${n.libelle} » et ses ${enfants} sous-périmètre(s), qui seront supprimés avec lui.`
					: `Le périmètre « ${n.libelle} »`,
			),
			'Périmètre supprimé',
			async () => {
				await perimetresApi.remove(n.id, enfants > 0);
				await rechargerPerimetres();
			},
			'Suppression impossible',
		);
	}

	async function deplacer(n: Perimetre, delta: number) {
		await tenter(
			async () => {
				await perimetresApi.update(n.id, { ordre: (n.ordre ?? 0) + delta });
				await rechargerPerimetres();
			},
			undefined,
			'Déplacement impossible',
		);
	}

	$: noeuds = $perimetresStore;
</script>

<svelte:head><title>Périmètres · {_siteNom}</title></svelte:head>

<p class="page-desc">
	L’arborescence qui sert à localiser une demande{SEPARATEUR.tiret}une affaire, une actualité, un
	événement. Elle est propre à cette copropriété : renommez, réorganisez, ajoutez ou retirez ce qui
	n’existe pas ici.
</p>

<div class="barre">
	<button class="btn btn-primary" on:click={() => creer(null)}>+ Périmètre de premier niveau</button
	>
</div>

<!--
	La création d'un périmètre de PREMIER NIVEAU s'ouvre ici, au ras de la liste :
	le geste part de la barre juste au-dessus (`ux-patterns` §14 ter — créer
	s'ouvre en tête, corriger s'ouvre à la place de l'objet).

	🔴 C'était une modale avant #672, et le contrôle ne pouvait pas le voir : il
	cherchait un `<form>`, et ce formulaire n'en a jamais porté — seulement des
	`.field`.
-->
{#if creation && creation.parent === null}
	<BoiteNouveauPerimetre
		titre="Nouveau périmètre de premier niveau"
		bind:nouveau
		{codePropose}
		{enregistrement}
		on:annule={() => (creation = null)}
		on:enregistre={enregistrerNouveau}
	/>
{/if}

{#if chargement || erreur || noeuds.length === 0}
	<EtatListe
		{chargement}
		{erreur}
		vide={noeuds.length === 0}
		titreErreur="Impossible d’afficher l’arborescence"
		titreVide="Aucun périmètre"
		messageVide="Créez-en un : tant que l’arborescence est vide, un contenu sans périmètre reste visible de tous."
	/>
{:else}
	<div class="ref-list">
		{#each noeuds as n (n.code)}
			{@const deplie = estDeplie(n.code, ouvert, edite, creation, duplique)}
			<div class="ref-item" class:expanded={deplie} class:inactif={!n.actif}>
				<div
					class="ref-tete"
					style="padding-left:{0.6 + n.profondeur * 1.1}rem"
					role="button"
					tabindex="0"
					on:click={() => basculer(n.code)}
					on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && basculer(n.code)}
				>
					{#if n.icone}<Icon name={n.icone} size={16} />{/if}
					<span class="ref-titre">{n.libelle}</span>
					{#if n.portee_globale}
						<span
							class="badge badge-blue"
							title="Ce périmètre porte lui-même la portée globale : visible de tous les résidents"
							>tous</span
						>
					{:else if n.concerne_tous}
						<!--  Hérité d'un ancêtre. Sans cette distinction, la pastille « tous »
						      s'affichait à côté d'une case décochée — deux informations exactes
						      qui se lisent comme une contradiction (signalé le 13/08/2026). -->
						<span
							class="badge badge-gray"
							title="Hérité d’un périmètre parent — la case de ce nœud est décochée, et c’est normal"
							>tous (hérité)</span
						>
					{/if}
					{#if !n.selectionnable}
						<span class="badge badge-gray" title="Non proposé à la saisie">regroupement</span>
					{/if}
					{#if !n.actif}<span class="badge badge-orange">désactivé</span>{/if}
					{#if n.utilise}
						<span class="badge badge-green" title="Cité par des contenus publiés">utilisé</span>
					{/if}
					<code class="ref-code">{n.code}</code>
					<span class="chevron" class:open={deplie}>›</span>
				</div>

				{#if deplie}
					<!--  Le corps ne referme pas le nœud : sans `stopPropagation`, un clic
					      dans la boîte remonterait à la ligne de titre et replierait ce qu'on
					      est en train de saisir (`ux-patterns` §3). -->
					<div
						class="ref-corps"
						role="presentation"
						on:click|stopPropagation
						on:keydown|stopPropagation
					>
						{#if edite?.code === n.code}
							<!--  🔴 LA CORRECTION S'OUVRE ICI, dans le nœud (10/09/2026).
							      Signalé à l'écran : « le crayon provoque l'affichage d'une fenêtre
							      indépendante (hors UX) ».

							      C'était une `Modale`, et ce fichier le DÉCLARAIT : « l'édition,
							      elle, RESTE une modale et le déclare. Un geste, un format. » La
							      phrase était juste — un geste, un format — mais elle appliquait
							      le mauvais format : #367 a retiré la modale du produit après
							      trois signalements, et la création juste au-dessus l'avait
							      abandonnée dès #672. Une exception ÉCRITE reste une exception :
							      la déclarer ne l'a jamais justifiée.

							      `encadre={false}` : le nœud EST le cadre, et sa ligne de titre en
							      est l'en-tête (#425). Pas de `cle` : la boîte s'ouvre sous le
							      crayon qu'on vient de cliquer, il n'y a rien à ramener à l'écran. -->
							<FormulaireCreation titre="Modifier {n.libelle}" encadre={false}>
								<ChampsPerimetre
									bind:form
									code={n.code}
									libelleParDefaut={n.libelle}
									concerneTousHerite={n.concerne_tous}
								/>
								<PiedFormulaire
									enCours={enregistrement}
									desactive={!form.libelle.trim()}
									soumission={false}
									on:annule={() => (edite = null)}
									on:enregistre={enregistrer}
								/>
							</FormulaireCreation>
						{:else if creation?.parent === n.code}
							<!--  Le « ＋ » crée SOUS ce nœud : sa boîte s'ouvre donc dans ce nœud
							      (signalé à l'écran le même jour : « le + s'affiche en haut de
							      liste, au lieu de rester sur la position courante »).

							      ⚠️ Ce n'est pas une entorse à « créer s'ouvre en tête de liste » :
							      la règle place la boîte LÀ OÙ EST LE GESTE. Le bouton de la barre
							      ouvre en tête parce qu'il y est ; le « ＋ » d'un nœud ouvre dans
							      ce nœud pour la même raison. -->
							<BoiteNouveauPerimetre
								titre="Sous-périmètre de {n.libelle}"
								encadre={false}
								bind:nouveau
								{codePropose}
								{enregistrement}
								on:annule={() => (creation = null)}
								on:enregistre={enregistrerNouveau}
							/>
						{:else if duplique?.code === n.code}
							<BoiteDuplicationPerimetre
								source={n}
								on:annule={() => (duplique = null)}
								on:fini={() => (duplique = null)}
							/>
						{:else}
							{#if n.description}<p class="ref-desc">{n.description}</p>{/if}
							<div class="ref-actions">
								<!--  Le mode se lit sur l'icône qui a ouvert la boîte
								      (`ux-patterns` §13 bis) : elle est déjà là, déjà regardée. -->
								<button
									class="btn-icon-edit"
									aria-label="Modifier"
									title="Modifier"
									aria-pressed={edite?.code === n.code}
									on:click={() => editer(n)}><IconeAction icone="pencil" /></button
								>
								<button
									class="btn-icon"
									aria-label="Ajouter un sous-périmètre"
									title="Ajouter un sous-périmètre"
									aria-pressed={creation?.parent === n.code}
									on:click={() => creer(n.code)}><IconeAction icone="plus" /></button
								>
								{#if n.dupliquable}
									<button
										class="btn-icon"
										aria-label="Dupliquer avec ses sous-périmètres"
										title="Dupliquer avec ses sous-périmètres"
										aria-pressed={duplique?.code === n.code}
										on:click={() => dupliquer(n)}><IconeAction icone="copy" /></button
									>
								{/if}
								<button
									class="btn-icon"
									aria-label="Monter"
									title="Monter"
									on:click={() => deplacer(n, -1)}><IconeAction icone="arrow-up" /></button
								>
								<button
									class="btn-icon"
									aria-label="Descendre"
									title="Descendre"
									on:click={() => deplacer(n, 1)}><IconeAction icone="arrow-down" /></button
								>
								<button
									class="btn-icon-danger"
									aria-label="Supprimer"
									title="Supprimer"
									on:click={() => supprimer(n)}><IconeAction icone="trash-2" /></button
								>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.page-desc {
		color: var(--color-text-muted);
		margin-bottom: 1rem;
	}
	.barre {
		margin-bottom: 1rem;
	}
	.ref-list {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.ref-item {
		border-bottom: 1px solid var(--color-border);
		background: var(--color-surface);
	}
	.ref-item:last-child {
		border-bottom: none;
	}
	.ref-item.inactif {
		opacity: 0.55;
	}
	.ref-tete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.55rem 0.8rem;
		cursor: pointer;
	}
	@media (hover: hover) and (pointer: fine) {
		.ref-tete:hover {
			background: var(--color-bg);
		}
	}
	.ref-titre {
		font-size: var(--fs-base);
	}
	.ref-code {
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
		margin-left: auto;
	}
	.ref-corps {
		padding: 0.2rem 1rem 0.8rem 1.6rem;
		border-top: 1px dashed var(--color-border);
	}
	.ref-desc {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		line-height: 1.55;
		margin: 0.5rem 0;
	}
	.ref-actions {
		display: flex;
		gap: 0.3rem;
	}
</style>
