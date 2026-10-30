<!--
  La CARTE D'UN CONTRAT d'entretien — sa ligne de titre, ses actions, son détail
  déplié, et le formulaire qui prend sa place quand on la corrige.

  Extraite de `prestataires/+page.svelte` le 10/09/2026, au fil de l'eau : cet
  écran était à 1 777 lignes et devait accueillir l'édition en place. Le plafond
  de modularité (rang 1) refuse qu'un fichier déjà au-dessus de 500 grossisse, et
  c'est cette carte qui s'en détache le plus proprement — un objet, ses gestes,
  aucun état partagé avec le reste de la page.

  🔴 **La correction s'ouvre DANS LA CARTE, à la place de son corps** — le motif
  des tickets, des annonces et des actualités (`AnnonceCard`, `CarteActualite`),
  désigné à l'écran : *« l'affaire modifiée passe en premier ! prends exemple sur
  tickets »*.

  Quatre positions auront été essayées en une journée, et les trois premières
  déplaçaient quelque chose : la boîte en bas de page, puis en haut, puis à la
  place de la carte ENTIÈRE — cette dernière effaçait la ligne du contrat, et
  `FormulaireCreation` ramenait sa boîte en HAUT de la fenêtre dès qu'elle n'y
  tenait pas. L'objet corrigé quittait donc sa place dans la liste.

  Le motif des tickets ne déplace rien : **l'en-tête reste**, avec son titre et
  ses actions, et seul le CORPS de la carte cède la place au formulaire. Le mode
  se lit sur le crayon (`aria-pressed`, `ux-patterns` §13 bis), et aucune `cle`
  n'est nécessaire — rien n'a bougé, il n'y a rien à ramener à l'écran.

  ⚠️ §14 bis n'est pas remis en cause : c'est toujours LA MÊME BOÎTE — même
  composant, même format. Ce qui changeait était sa position ; elle est désormais
  celle de l'objet, sans que l'objet s'efface.

  🔴 **Le composant existait en DEUX exemplaires** — `AnnonceCard` et
  `CarteActualite` portent tous deux un `formulaireOuvert` qui fait exactement
  cela. Je ne suis pas allé les lire : j'ai inventé une troisième façon, et c'est
  Philippe qui a nommé la première. Chercher la NOTION, pas le nom demandé.
-->
<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import { frequenceLabel, type FormulaireContratData } from '#lib/prestataires.ts';
	import { classeEquipement } from '#lib/prestataires-gouttiere.ts';
	import { typeEquipementDuContrat } from '#lib/reporting.ts';
	import type { ContratEntretien, Document, Prestataire } from '#lib/api/index.ts';
	import { fmtDateShort } from '#lib/date.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import { CONTRAT } from '#lib/entites/contrat.ts';
	import CarteModifiable from './CarteModifiable.svelte';
	import ListeDocuments from './ListeDocuments.svelte';
	import FormulaireContrat from './FormulaireContrat.svelte';
	import GesteEnPlace from './GesteEnPlace.svelte';
	import IconeIA from './IconeIA.svelte';
	import NoteEtoiles from './NoteEtoiles.svelte';

	export let contrat: ContratEntretien;
	export let prest: Prestataire | null | undefined = null;
	export let expanded = false;
	export let enRetard = false;
	export let documents: Document[] = [];
	export let peutModifier = false;
	/**  Rendue aux Archives : ↩️ y remplace 📦, et ✨ ✏️ se taisent — on
	 *   ressort un contrat avant de le corriger (#1538). */
	export let archive = false;

	/**  Le contrat en cours de correction — `null` quand aucun ne l'est. La carte
	 *   cède sa place au formulaire quand c'est le sien. */
	export let editContratId: number | null = null;
	export let contratForm: FormulaireContratData;
	export let prestataires: Prestataire[] = [];
	export let equipements: readonly { val: string; label: string }[] = [];
	export let submitting = false;

	export let onBasculer: (id: number) => void = () => {};
	export let onModifier: (c: ContratEntretien) => void = () => {};
	/** 📦 `true` range le contrat, `false` le ressort des Archives. */
	export let onArchiver: (id: number, archivee: boolean) => void = () => {};
	export let onSupprimerDoc: (contratId: number, docId: number) => void = () => {};
	export let onAjouteDoc: (contratId: number) => void = () => {};
	export let onAnnuler: () => void = () => {};
	export let onEnregistrer: () => void = () => {};
	/**  Noter le prestataire depuis la carte du contrat — le geste ne vivait
	 *   QUE dans l'onglet Visites retiré (#603), et un affichage sans son geste
	 *   de saisie ne se voit pas. */
	/**  Les notes dépliées — état LOCAL depuis l'extraction (10/09/2026) : il ne
	 *   concerne que cette carte, alors que le `Set` du parent retenait l'état de
	 *   toutes. Une carte qui sait se déplier n'a pas besoin qu'on le lui dise. */
	let notesOuvertes = false;

	export let onNoter: (prestataireId: number, contratId: number) => void = () => {};
	/**  La notation ouverte sur CE contrat — l'état vit dans la page, qui porte
	 *   l'appel réseau ; la carte ne fait que le rendre au bon endroit. */
	export let noteEnCours = false;
	export let noteValeur: number | null = null;
	export let noteCommentaire = '';
	export let noteSaving = false;
	export let onAnnulerNote: () => void = () => {};
	export let onEnregistrerNote: () => void = () => {};

	/**  🔴 Le geste ✨ — MANUEL, et il le reste (11/09/2026, demandé à l'écran :
	 *   « comment on lance l'IA ? cela doit être manuel par une icône »).
	 *
	 *   Rien ne le déclenche seul : ni la création d'un contrat, ni le dépôt d'un
	 *   document, ni une tâche planifiée. Chaque synthèse est facturée, et chacune
	 *   doit être voulue.
	 *
	 *   ⚠️ `contrat.synthese_disponible` vient du SERVEUR : l'écran ne sait pas si
	 *   l'assistant est configuré, et n'a pas à le savoir — cette configuration ne
	 *   regarde pas la session d'un membre du conseil syndical. */
	export let onSynthetiser: (c: ContratEntretien) => void = () => {};
	/** Le contrat dont la synthèse est en cours de rédaction, s'il y en a un. */
	export let syntheseEnCoursId: number | null = null;

	/**  Cette carte est-elle celle qu'on corrige ? Son corps cède alors la place au
	 *   formulaire, et le crayon s'inverse. */
	$: enEdition = editContratId === contrat.id;

	/**  🗂️ La gouttière (10/10/2026, la page Affaires devenue le standard) : la
	 *   date que la carte affichait — la prochaine visite, sinon le début du
	 *   contrat —, puis le TYPE D'ÉQUIPEMENT. C'est lui qui classe un contrat :
	 *   l'onglet range déjà ses groupes par cette clé, par la même règle
	 *   (`typeEquipementDuContrat`). La fréquence est un rythme, pas un
	 *   classement : elle reste une capsule de la dernière ligne. */
	$: classe = classeEquipement(typeEquipementDuContrat(contrat, prestataires));
</script>

<!--  L'ancre `contrat-{id}` : le carnet d'entretien y renvoie (#870 → carnet,
     10/09/2026), et `test_liens_front` refuse un lien vers une ancre qu'aucun
     onglet ne rend — il a attrapé celui-ci avant la production.

     🔴 L'en-tête passe par `EnteteCarte` (12/09/2026) — comme les ONZE autres
     cartes du site. Écrit à la main ici, il en portait les deux défauts que ce
     composant existe pour supprimer : le TITRE partageait sa ligne avec le
     prestataire, le n° de contrat, l'échéance, la fréquence et quatre icônes
     (réduit à trois points sur un téléphone), et le geste était SYMÉTRIQUE.

     Le squelette — conteneur, en-tête, 🔗 ✏️ 📦, corps qui cède la place au
     formulaire — vit dans `CarteModifiable` depuis le 02/10/2026 (#1539) :
     `CartePrestataire` le recopiait. La règle « pendant la correction, la
     ligne de titre ne replie pas », écrite ici, y est montée pour les deux. -->
<CarteModifiable
	entite={CONTRAT}
	ancreId="contrat-{contrat.id}"
	quoi="le contrat"
	titre={contrat.libelle}
	quand={contrat.prochaine_visite ?? contrat.date_debut}
	{classe}
	{expanded}
	{enEdition}
	urgent={enRetard}
	{peutModifier}
	{archive}
	titreRestaurer="Restaurer — le contrat revient dans la liste"
	teinte
	onBasculer={() => onBasculer(contrat.id)}
	onModifier={() => onModifier(contrat)}
	{onAnnuler}
	onArchiver={(archivee) => onArchiver(contrat.id, archivee)}
>
	<svelte:fragment slot="tags">
		{#if prest}
			<span class="contrat-meta">{prest.nom}</span>
		{:else}
			<!--  Un contrat sans intervenant avait sa propre section, qui le rendait
			      une SECONDE fois : le groupement par équipement retombe déjà sur
			      `type_equipement` quand le prestataire manque. Le fait se dit ici,
			      sur la ligne (#603). -->
			<span class="badge badge-gray">sans intervenant</span>
		{/if}
		{#if contrat.numero_contrat}<span class="contrat-meta">🔖 {contrat.numero_contrat}</span>{/if}
		<!--  L'échéance est montée dans la GOUTTIÈRE (10/10/2026) : une seule date
		      par carte. Son ÉTAT reste ici, en capsule teintée — le retard, qui
		      était la couleur de la date —, et la carte sans échéance le dit :
		      sa gouttière montre alors le DÉBUT du contrat, pas une visite. -->
		{#if contrat.prochaine_visite && enRetard}
			<span class="badge badge-red">⚠️ Visite en retard</span>
		{:else if !contrat.prochaine_visite}
			<span class="badge badge-gray">Sans échéance</span>
		{/if}
		{#if contrat.frequence_type}
			<span class="badge badge-gray">{frequenceLabel(contrat)}</span>
		{/if}
		<span class="badge badge-gray">📄 {documents?.length ?? 0}</span>
	</svelte:fragment>

	<svelte:fragment slot="gestes">
		{#if contrat.synthese_disponible}
			<!--  ✨ avant ✏️ : du moins destructeur au plus. Proposer un texte
			      l'est moins qu'ouvrir la correction, qui l'est moins qu'archiver. -->
			<button
				class="btn-icon"
				aria-label="Proposer une synthèse de ce contrat"
				title={syntheseEnCoursId === contrat.id ? 'Rédaction en cours…' : 'Proposer une synthèse'}
				disabled={syntheseEnCoursId !== null}
				aria-busy={syntheseEnCoursId === contrat.id}
				on:click|stopPropagation={() => onSynthetiser(contrat)}
				><IconeIA enCours={syntheseEnCoursId === contrat.id} /></button
			>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="edition">
		<FormulaireContrat
			bind:contratForm
			{prestataires}
			{equipements}
			contratId={contrat.id}
			{documents}
			onSupprimer={onSupprimerDoc}
			onAjoute={onAjouteDoc}
			{submitting}
			{onAnnuler}
			{onEnregistrer}
		/>
	</svelte:fragment>

	<svelte:fragment slot="detail">
		<div class="contrat-section">
			<!--  🔴 « Le contrat », comme en édition — et non « Infos contrat ».
				      Signalé le 12/09/2026 : *« la zone en lecture n'a pas les mêmes
				      noms que l'édition »*. C'est R3 du cadre, appliqué entre DEUX
				      RENDUS du même objet : un champ garde son libellé qu'on le lise
				      ou qu'on le corrige. L'intitulé vient de la déclaration
				      (`entites/contrat`, `titreEcran`), pas d'un choix local. -->
			<div class="contrat-section-title">Le contrat</div>
			<div class="detail-grid">
				<div>
					<span class="detail-label">Début</span>📅 {fmtDateShort(contrat.date_debut)}
				</div>
				{#if contrat.duree_initiale_valeur}<div>
						<span class="detail-label">Durée initiale</span>{fmtNombre(
							contrat.duree_initiale_valeur,
						)}
						{contrat.duree_initiale_unite}
					</div>{/if}
				{#if contrat.frequence_type}
					<div><span class="detail-label">Fréquence</span>{frequenceLabel(contrat)}</div>
				{/if}
				{#if contrat.prochaine_visite}<div>
						<span class="detail-label">Prochaine visite</span><span class="prochaine-visite"
							>🗓 {fmtDateShort(contrat.prochaine_visite)}</span
						>
					</div>{/if}
			</div>
		</div>
		{#if contrat.notes}
			<div class="contrat-section">
				<!--  « Description », comme en édition — c'est le MÊME champ
			      (`contrat.notes`), et il portait deux noms selon qu'on le lisait ou
			      qu'on le corrigeait (signalé le 12/09/2026). Que la synthèse IA
			      atterrisse ici est vrai, mais c'est ce que le champ CONTIENT
			      souvent, pas ce qu'il EST : le nommer par son contenu le rendait
			      introuvable depuis l'écran de saisie. -->
				<div
					class="contrat-section-title clickable"
					role="button"
					tabindex="0"
					on:click|stopPropagation={() => (notesOuvertes = !notesOuvertes)}
					on:keydown|stopPropagation={(e) =>
						(e.key === 'Enter' || e.key === ' ') && (notesOuvertes = !notesOuvertes)}
				>
					Description {notesOuvertes ? '▲' : '▼'}
				</div>
				{#if notesOuvertes}
					<div class="rich-content notes-contrat">
						{@html safeHtml(contrat.notes)}
					</div>
				{/if}
			</div>
		{/if}
		<!--  🔴 Les documents sont rendus par `ListeDocuments` — le rendu des
		      tickets, pastilles « PDF: nom », et rien d'autre (12/09/2026).

		      Cette liste était écrite ICI **et** dans `DocumentsRattaches`, avec
		      les mêmes styles en ligne au caractère près : une duplication
		      invisible à tout contrôle inter-fichiers, puisque chacune vivait
		      chez elle. Elles auraient divergé à la première retouche — c'est
		      exactement ce qui est arrivé au titre, présent deux fois à
		      l'écran en édition. -->
		<div class="contrat-section">
			<div class="contrat-section-title">Documents ({documents?.length ?? 0})</div>
			<ListeDocuments
				{documents}
				peutSupprimer={peutModifier}
				onSupprimer={(docId) => onSupprimerDoc(contrat.id, docId)}
			/>
		</div>
		{#if peutModifier}
			<div class="gestes-notation">
				<!--  🔴 « Noter » ne vivait QUE dans `CarteVisite`, donc dans le
				      seul onglet Visites : retirer cet onglet sans porter le geste
				      ici aurait rendu la notation d'un prestataire IMPOSSIBLE à
				      saisir, alors que la fiche et le reporting continuaient d'en
				      afficher la moyenne. Un affichage sans son geste de saisie ne
				      se voit pas — rien ne lève, la note reste simplement à jamais
				      celle d'hier (#603).
				      Sans intervenant, il n'y a personne à noter : le bouton
				      n'apparaît pas plutôt que d'ouvrir une modale sans cible. -->
				{#if contrat.prestataire_id}
					<button
						class="btn btn-sm btn-outline contrat-noter"
						aria-pressed={noteEnCours}
						on:click|stopPropagation={() =>
							noteEnCours ? onAnnulerNote() : onNoter(contrat.prestataire_id, contrat.id)}
						>⭐ Noter</button
					>
				{/if}
				<!--  🔴 Le geste s'ouvre DANS la carte (#889) : il était en fenêtre, pour
				      cinq étoiles et un commentaire. Les étoiles viennent de
				      `NoteEtoiles` en mode saisie — saisir et lire une note sont deux
				      rendus du même objet (R3), pas deux composants. -->
				{#if noteEnCours}
					<div role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
						<GesteEnPlace
							enCours={noteSaving}
							onAnnuler={onAnnulerNote}
							onValider={onEnregistrerNote}
						>
							<NoteEtoiles saisie bind:note={noteValeur} />
							<label class="field">
								Commentaire
								<textarea bind:value={noteCommentaire} rows="3"></textarea>
							</label>
						</GesteEnPlace>
					</div>
				{/if}
			</div>
		{/if}
	</svelte:fragment>
</CarteModifiable>

<style>
	/*  Ces règles ont SUIVI le balisage (10/09/2026). Svelte scope les styles au
	    composant : les laisser dans la page les rendait inertes ici et orphelines
	    là-bas. C'est la régression de #356, et ce sont `lint:css-orphelin` et
	    `lint:classes-nues` qui l'ont refusée — la relecture, elle, ne l'avait pas
	    vue. */
	.contrat-noter {
		color: var(--color-warning-texte);
	}
	/*  `.contrat-detail-body` est partie avec le corps, dans `CarteModifiable`
	    (`teinte`, #1539). */
	.contrat-section {
		margin-bottom: 1rem;
	}
	.contrat-section:last-child {
		margin-bottom: 0;
	}
	.contrat-section-title {
		font-size: var(--fs-xs);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-bottom: 0.4rem;
		padding-bottom: 0.25rem;
		border-bottom: 1px solid var(--color-border);
	}
	.contrat-section-title.clickable {
		cursor: pointer;
		user-select: none;
	}
	@media (hover: hover) and (pointer: fine) {
		.contrat-section-title.clickable:hover {
			color: var(--color-primary);
		}
	}
	/*  🔴 Six règles sont parties avec la rangée écrite à la main (12/09/2026) :
	    `.contrat-row` et son survol, `.contrat-body-inner`, `.contrat-titre`,
	    `.contrat-infos` et `.contrat-meta-right`. `EnteteCarte` porte désormais
	    la disposition — et son survol colore le TITRE, non le fond du bloc, ce
	    qui est l'arbitrage n° 2 de `ux-patterns` §0 : cette carte teintait encore
	    tout son fond.

	    ⚠️ `.contrat-infos` était déclarée DEUX fois dans ce même fichier, la
	    seconde ayant perdu le `@media` qui la justifiait — un vestige que rien ne
	    signalait, puisqu'une redéclaration est valide en CSS. */
	.contrat-meta {
		color: var(--color-text-muted);
	}
	/*  Seuls la taille et la couleur restent ici : le rendu du contenu riche
	    (paragraphes, listes, gras, citation) vit dans `styles/composants.css`
	    depuis le 18/09/2026, où les quatre composants qui posent la classe le
	    reçoivent enfin. */
	.rich-content {
		font-size: var(--fs-md);
		color: var(--color-text);
		margin-bottom: 0.5rem;
	}
	.prochaine-visite {
		color: var(--color-primary);
		font-weight: 600;
	}
	.notes-contrat {
		font-size: var(--fs-base);
	}
	.gestes-notation {
		display: flex;
		gap: 0.4rem;
		margin-top: 0.25rem;
		flex-wrap: wrap;
	}
</style>
