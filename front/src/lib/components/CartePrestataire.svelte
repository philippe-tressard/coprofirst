<!--
  La CARTE D'UN PRESTATAIRE — sa ligne de titre, ses actions, son détail déplié,
  et le formulaire qui prend sa place quand on le corrige.

  Extraite de `prestataires/+page.svelte` le 11/09/2026, pour la même raison que
  `CarteContrat` la veille et **sur exactement le même signalement** : *« le mode
  édition (crayon) ne respecte pas le standard UX déployé sur le reste du site,
  par exemple sur tickets »*. Le crayon était dans la carte, la boîte s'ouvrait en
  tête de liste — l'objet corrigé quittait sa place sous les yeux.

  🔴 **La correction s'ouvre DANS LA CARTE, à la place de son corps.** L'en-tête
  reste, avec son titre et ses actions ; le mode se lit sur le crayon
  (`aria-pressed`, `ux-patterns` §13 bis) ; aucune `cle` n'est nécessaire, rien
  n'a bougé donc il n'y a rien à ramener à l'écran.

  ⚠️ **Pourquoi un FICHIER et pas un bloc de plus dans la page** : le geste exige
  deux rendus de `FormulaireCreation` — la création en tête de page, la correction
  dans la carte —, et `lint:geste-edition` (règle B) refuse deux rendus éloignés
  dans un même fichier, à raison : c'est la signature du formulaire qui s'ouvre
  loin de son geste. Séparer la carte n'est donc pas un contournement du contrôle,
  c'est ce qui rend la règle vraie des deux côtés.
-->
<script lang="ts">
	import { fmtDateShort } from '#lib/date.ts';
	import { PRESTATAIRE } from '#lib/entites/prestataire.ts';
	import { classeTypePrestataire } from '#lib/prestataires-gouttiere.ts';
	import {
		equipLabel,
		typePrestataireLabel,
		type ContactSaisi,
		type FormulairePrestataire,
	} from '#lib/prestataires.ts';
	import type { ContratEntretien, Notation, Prestataire } from '#lib/api/index.ts';
	import { safeDescription } from '#lib/sanitize.ts';
	import { nomAffiche } from '#lib/noms.ts';
	import CarteModifiable from './CarteModifiable.svelte';
	import NotationsPrestataire from './NotationsPrestataire.svelte';
	import MetriquesPrestataire from './MetriquesPrestataire.svelte';
	import { isCS } from '#lib/stores/auth.ts';
	import ChampsPrestataire from './ChampsPrestataire.svelte';
	import PiedFormulaire from './PiedFormulaire.svelte';

	export let p: Prestataire;
	export let cs: ContratEntretien[] = [];
	export let nextVisit: string | null = null;
	export let notations: Notation[] = [];
	export let expanded = false;
	export let compactPrests = false;
	export let peutModifier = false;
	/**  Rendue aux Archives : ↩️ y remplace 📦, et le crayon se tait — on
	 *   ressort une fiche avant de la corriger (#1538). */
	export let archive = false;
	export let telephonesDe: (t: string) => string[] = () => [];

	/**  Le prestataire en cours de correction — la carte cède sa place au
	 *   formulaire quand c'est le sien. */
	export let editPrestId: number | null = null;
	export let prestForm: FormulairePrestataire;
	export let prestContacts: ContactSaisi[] = [];
	export let typesPrestataire: readonly { val: string; label: string; desc?: string }[] = [];
	export let equipements: readonly { val: string; label: string }[] = [];
	export let submitting = false;

	export let onBasculer: (id: number) => void = () => {};
	export let onModifier: (p: Prestataire) => void = () => {};
	/** 📦 `true` range la fiche, `false` la ressort des Archives. */
	export let onArchiver: (id: number, archivee: boolean) => void = () => {};
	export let onAnnuler: () => void = () => {};
	export let onEnregistrer: () => void = () => {};
</script>

<!--  🔴 L'en-tête passe par `EnteteCarte` (12/09/2026) — comme les ONZE autres
      cartes du site. Il était écrit à la main ici, et il en portait les deux
      défauts que ce composant existe pour supprimer :

        • le NOM partageait sa ligne avec les badges de type, de spécialité et la
          note. Sur un téléphone, les badges ayant une largeur fixe et la ligne
          étant en `flex`, c'est le nom qui se réduisait à trois points — on
          lisait une liste de prestataires sans savoir lesquels.
        • le geste était SYMÉTRIQUE : le conteneur portait `role="button"`, donc
          la carte dépliée se refermait au moindre clic dans son corps, et la
          sélection de texte était interceptée. La norme du 18/08 est
          asymétrique — repliée, toute la carte ouvre ; dépliée, seul le titre
          referme.

      Le squelette — conteneur, en-tête, 🔗 ✏️ 📦, corps qui cède la place au
      formulaire — vit dans `CarteModifiable` depuis le 02/10/2026 (#1539) :
      `CarteContrat` le recopiait.

      🗂️ La GOUTTIÈRE (10/10/2026, la page Affaires devenue le standard) : la
      prochaine visite — la date que la ligne portait —, puis la catégorie, qui
      range l'annuaire. La date y figure même en mode compact : elle ne coûte
      plus de hauteur. La catégorie reste AUSSI en capsule sur la dernière
      ligne : l'abrégé de la gouttière ne dit pas le mot entier, et la recherche
      comme les tests la lisent là. -->
<CarteModifiable
	entite={PRESTATAIRE}
	ancreId="presta-{p.id}"
	quoi="la fiche prestataire"
	titre={p.nom}
	quand={nextVisit}
	classe={classeTypePrestataire(p.type_prestataire)}
	{expanded}
	enEdition={editPrestId === p.id}
	{peutModifier}
	{archive}
	titreRestaurer="Restaurer — la fiche revient dans l'annuaire"
	onBasculer={() => onBasculer(p.id)}
	onModifier={() => onModifier(p)}
	{onAnnuler}
	onArchiver={(archivee) => onArchiver(p.id, archivee)}
>
	<svelte:fragment slot="tags">
		<!--  Capsules NEUTRES : la catégorie et la spécialité décrivent, elles ne
		      disent aucun état (la dernière ligne d'une affaire, `ux-patterns` §3). -->
		<span class="badge badge-gray">{typePrestataireLabel(p.type_prestataire)}</span>
		<span class="badge badge-gray">{equipLabel(p.specialite)}</span>
		<NotationsPrestataire resume {notations} />
		<!--  « Sous contrat » se LIT sur les contrats actifs, il ne se saisit pas
		      (#1444) : c'était une catégorie, et une entreprise qui entretient
		      sous contrat et dépanne hors contrat n'y tenait pas. Rien quand il
		      n'y en a aucun — « 0 contrat » n'apprenait rien. -->
		{#if cs.length}
			<span class="badge badge-gray">&#x1F4C4; Sous contrat ({cs.length})</span>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="apercu">
		<!--  Les contacts sont l'APERÇU de la carte : ils viennent sous l'en-tête, à
		      la place que le modèle leur donne, et non serrés dans sa ligne de titre. -->
		{#if !compactPrests || expanded}
			<div class="prest-contacts">
				{#if p.contacts && p.contacts.length > 0}
					{#each p.contacts as c (c)}
						<span class="prest-contact">
							📞 {c.telephone}{#if c.prenom || c.nom}&nbsp;— {nomAffiche(
									c,
								)}{/if}{#if c.fonction}&nbsp;({c.fonction}){/if}
						</span>
					{/each}
				{:else if p.telephone}
					{#each telephonesDe(p.telephone) as tel, ti (`${ti}|${tel}`)}
						<span class="prest-contact">📞 {tel.trim()}</span>
					{/each}
				{/if}
				{#if p.email}<span class="prest-contact">✉️ {p.email}</span>{/if}
			</div>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="edition">
		<form on:submit|preventDefault={onEnregistrer}>
			<ChampsPrestataire
				bind:prestForm
				bind:prestContacts
				{typesPrestataire}
				{equipements}
				etat="edition"
			/>
			<PiedFormulaire enCours={submitting} on:annule={onAnnuler} />
		</form>
	</svelte:fragment>

	<svelte:fragment slot="detail">
		<div class="detail-grid">
			{#if p.telephone}
				<div>
					<span class="detail-label">Téléphone</span>
					{#each telephonesDe(p.telephone) as tel, ti (`${ti}|${tel}`)}
						<span class="ligne-telephone">📞 {tel.trim()}</span>
					{/each}
				</div>
			{/if}
			{#if p.email}<div><span class="detail-label">Email</span>✉️ {p.email}</div>{/if}
			{#if p.adresse}<div>
					<span class="detail-label">Adresse</span><span class="adresse">📮 {p.adresse}</span>
				</div>{/if}
			<div><span class="detail-label">Contrats</span>{cs.length}</div>
			{#if nextVisit}<div>
					<span class="detail-label">Prochaine visite</span><span class="prochaine-visite"
						>🗓 {fmtDateShort(nextVisit)}</span
					>
				</div>{/if}
		</div>
		<!--  La description (#1327), assainie comme partout. -->
		{#if p.description}<div class="prest-description">
				{@html safeDescription(p.description)}
			</div>{/if}
		<!--  Les avis, enfin visibles un par un (#807). L'écran n'en montrait
		      que la MOYENNE, dans un badge : impossible de savoir qui avait
		      noté quoi, et donc impossible de retirer une note posée par
		      erreur — alors que l'endpoint de suppression existait. -->
		<NotationsPrestataire {notations} peutSupprimer={peutModifier} on:supprimee />
		<!--  📊 Les affaires qu'il a traitées, en chiffres (#1646) — le conseil seul,
		      comme les avis. Chargées à l'ouverture de la fiche, pas avant. -->
		{#if $isCS}
			<MetriquesPrestataire prestataireId={p.id} />
		{/if}
	</svelte:fragment>
</CarteModifiable>

<style>
	/*  L'adresse s'écrit sur plusieurs lignes, comme sur une enveloppe. */
	.adresse {
		white-space: pre-line;
	}
	.prest-description {
		margin-top: 0.6rem;
	}
	/*  🔴 Cinq règles ont disparu avec l'en-tête écrit à la main (12/09/2026) :
	    `.prest-header`, `.prest-main`, `.prest-nom`, `.prest-meta` et leur point
	    de rupture à 600 px. Elles décrivaient une disposition que `EnteteCarte`
	    porte désormais — et le point de rupture avec, ce qui est précisément R1 :
	    la responsivité appartient au squelette, pas à chaque carte.

	    ⚠️ Le style part AVEC le balisage. Laissé derrière, il ne lève rien à
	    l'exécution : `lint:css-orphelin` et `svelte-check` sont les seuls à le
	    voir, et c'est le défaut qui a été repris quatre fois cette semaine.

	    `.badge-type` est partie le 10/10/2026 : la catégorie est une capsule
	    neutre (`badge-gray`), comme toute pastille qui décrit. */
	/*  L'aperçu de la carte : les contacts, sous l'en-tête. */
	/*  Plus de retrait propre : les contacts sont rendus DANS l'en-tête
	    (`slot="apercu"`, 18/09/2026), qui porte déjà le sien. L'y laisser
	    décalait le bloc de deux fois la marge. */
	.prest-contacts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 0.75rem;
	}
	.prest-contact {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	/*  `.prest-body` est partie avec le corps, dans `CarteModifiable` (#1539). */
	.ligne-telephone {
		display: block;
	}
	.prochaine-visite {
		color: var(--color-primary);
		font-weight: 600;
	}
</style>
