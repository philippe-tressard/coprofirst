<!--
  Les CHAMPS d'un prestataire — nom, type, spécialité, contacts, description.

  Extraits de `prestataires/+page.svelte` le 11/09/2026, pour la même raison que
  `ChampsContrat` avant eux : le formulaire doit pouvoir s'ouvrir à DEUX endroits
  — en tête de page pour une création, dans la carte pour une correction — et un
  bloc de champs recopié aux deux endroits aurait divergé au premier ajout.

  🔴 Il ne porte ni `<form>`, ni pied de formulaire, ni titre : ce sont des
  décisions de l'appelant, qui seul sait s'il crée ou s'il corrige. Les y mettre
  ferait de ce composant un écran, et il n'en est pas un.
-->
<script context="module" lang="ts">
	//  Partagé par toutes les instances : c'est ce qui rend les identifiants
	//  uniques d'un rendu à l'autre.
	let compteur = 0;
</script>

<script lang="ts">
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { pliageDe, requisDe } from '#lib/pliage.ts';
	import SectionTitre from '#lib/components/SectionTitre.svelte';
	import { PRESTATAIRE } from '#lib/entites/prestataire.ts';
	import SectionDescription from '#lib/components/SectionDescription.svelte';
	import SectionEquipement from '#lib/components/SectionEquipement.svelte';
	import { contexteAssistant } from '#lib/assistant.ts';
	import {
		contactRenseigne,
		contactVide,
		type ContactSaisi,
		type FormulairePrestataire,
	} from '#lib/prestataires.ts';
	import { sectionPresente, type Etat } from '#lib/entites/types.ts';

	export let prestForm: FormulairePrestataire;
	export let prestContacts: ContactSaisi[] = [];
	export let typesPrestataire: readonly { val: string; label: string; desc?: string }[] = [];

	//  Un identifiant par instance : les deux rendus — création en tête de page et
	//  correction dans la carte — coexistent, et deux `id` identiques feraient
	//  pointer les deux libellés sur le premier champ.
	const idNom = `prest-nom-${++compteur}`;

	/**  Création ou correction. Les deux rendent les mêmes sections ici — et c'est
	 *   la DÉCLARATION qui le dit, pas une absence de condition : un prestataire
	 *   n'a ni workflow ni diffusion, donc rien qui varie d'un état à l'autre. */
	export let etat: Etat = 'creation';
</script>

<!--  ══ 1. TITRE ══ Le nom SEUL : ce qui qualifie l'objet est en section 2
      (§0, arbitré le 18/08/2026). Il partageait la grille avec le type et la
      spécialité — quatre champs d'un bloc, sans rien pour dire lequel nomme
      l'entreprise et lesquels la décrivent. -->
<!--  ══ 1. NOM ══ La section n'a pas de titre : le champ porte le sien, comme
      sur les dix autres écrans (12/09/2026). Voir `ChampsContrat`. -->
<SectionTitre id={idNom} libelle="Nom" bind:valeur={prestForm.nom} />

<!--  🔴 LES SECTIONS STANDARD (24/09/2026, signalé à l'écran : « Prendre exemple
      sur l'UX d'Affaires »). « L'entreprise » et « Contact » n'étaient pas au
      cadre : le type devient la CATÉGORIE, la spécialité l'ÉQUIPEMENT — c'était
      la même liste —, et le courriel rejoint les CONTACTS, facultatifs donc
      pliés. -->

<!--  ══ 2. CATÉGORIE ══ Le type d'entreprise. -->
{#if sectionPresente(PRESTATAIRE, etat, 'nature')}
	<SectionFormulaire
		titre="Catégorie"
		pliable={pliageDe(PRESTATAIRE, 'nature')}
		requis={requisDe(PRESTATAIRE, 'nature')}
		rempli={!!prestForm.type_prestataire}
		idTitre="{idNom}-categorie"
	>
		<!--  🔴 Six entrées portant chacune une description : c'est le cas qui a
		      fait donner un sous-texte à `Pastille` (#491, seuil arbitré à 6). -->
		<ChoixPastilles
			options={typesPrestataire}
			bind:valeur={prestForm.type_prestataire}
			tous={false}
			libelle="Catégorie"
			avecDetail
		/>
	</SectionFormulaire>
{/if}

<!--  ══ 3. ÉQUIPEMENT ══ Ce que l'entreprise entretient — ex-« Spécialité ». -->
{#if sectionPresente(PRESTATAIRE, etat, 'equipement')}
	<!--  `SectionEquipement`, la section de l'affaire et du contrat (#1329). -->
	<SectionEquipement
		idPrefixe={idNom}
		pour="contrat"
		pliable={pliageDe(PRESTATAIRE, 'equipement')}
		requis={requisDe(PRESTATAIRE, 'equipement')}
		aide=""
		bind:equipement={prestForm.specialite}
	/>
{/if}

<!--  ══ 6. CONTACTS ══ Une liste répétable : ses personnes SONT le contenu d'une
      fiche d'annuaire. Chaque champ porte son libellé (`.field`) — ils n'avaient
      qu'un placeholder, qui disparaît dès qu'on tape. -->
{#if sectionPresente(PRESTATAIRE, etat, 'intervenant')}
	<SectionFormulaire
		titre="Contacts"
		pliable={pliageDe(PRESTATAIRE, 'intervenant')}
		requis={requisDe(PRESTATAIRE, 'intervenant')}
		rempli={prestContacts.some(contactRenseigne)}
		valeurModifiee={!!prestForm.email ||
			!!prestForm.adresse?.trim() ||
			prestContacts.some(contactRenseigne)}
		resume={prestContacts.filter(contactRenseigne).length
			? `${prestContacts.filter(contactRenseigne).length} contact(s)`
			: 'aucun'}
	>
		<label class="field"
			>E-mail de l’entreprise<input type="email" bind:value={prestForm.email} /></label
		>
		<!--  L'adresse de l'entreprise, facultative (#1327) : plusieurs lignes, comme
		      on l'écrit sur une enveloppe. -->
		<label class="field"
			>Adresse de l’entreprise<textarea rows="2" bind:value={prestForm.adresse}></textarea></label
		>
		{#each prestContacts as _contact, i (_contact)}
			<div class="contact">
				<!--  Deux lignes, demandées à l'écran (#1229) : QUI, puis COMMENT le
				      joindre. La grille auto-fit les répartissait au hasard de la largeur. -->
				<div class="form-grid">
					<label class="field">Prénom<input bind:value={prestContacts[i].prenom} /></label>
					<label class="field">Nom<input bind:value={prestContacts[i].nom} /></label>
					<label class="field">Fonction<input bind:value={prestContacts[i].fonction} /></label>
				</div>
				<div class="form-grid">
					<label class="field">Téléphone<input bind:value={prestContacts[i].telephone} /></label>
					<label class="field"
						>E-mail<input type="email" bind:value={prestContacts[i].email} /></label
					>
				</div>
				{#if prestContacts.length > 1}
					<button
						type="button"
						class="btn btn-sm btn-outline btn-retirer"
						aria-label="Retirer ce contact"
						on:click={() => (prestContacts = prestContacts.filter((_, j) => j !== i))}
						>− Retirer</button
					>
				{/if}
			</div>
		{/each}
		<button
			type="button"
			class="btn btn-sm btn-outline"
			on:click={() => (prestContacts = [...prestContacts, contactVide()])}>+ Nouveau contact</button
		>
	</SectionFormulaire>
{/if}

<!--  ══ 8. DESCRIPTION ══ Rouverte le 25/09/2026 (#1327) : ce qu'il faut savoir de
      l'entreprise, avec l'assistant ✨ comme sur les autres fiches. Facultative,
      donc pliée — et rouverte d'office dès qu'elle porte un texte. -->
{#if sectionPresente(PRESTATAIRE, etat, 'description')}
	<SectionDescription
		idPrefixe={idNom}
		pliable={pliageDe(PRESTATAIRE, 'description')}
		placeholder="Horaires, modalités d’intervention, particularités…"
		bind:valeur={prestForm.description}
		assistant={contexteAssistant('prestataire', {
			Catégorie: prestForm.type_prestataire,
			Équipement: prestForm.specialite,
		})}
		bind:titreObjet={prestForm.nom}
		bind:assisteIA={prestForm.assiste_ia}
	/>
{/if}

<style>
	/*  Une grille plus SERRÉE que la norme — 180 px de colonne minimale au lieu de
	    la valeur globale, et un gap de .65rem. Elle vivait dans
	    `prestataires/+page.svelte`, où elle s'appliquait à TOUS les `.form-grid`
	    de la page ; l'extraction du 11/09/2026 l'a laissée derrière son balisage,
	    et `lint:css-orphelin` l'a vue.

	    ⚠️ Elle est recopiée ici ET dans `OngletConsommations` — non par négligence :
	    Svelte scope au fichier, un `:global()` depuis l'un contaminerait tout le
	    site (#562). La remonter dans `styles/champs.css` changerait la grille de
	    TOUS les formulaires du produit, ce qui est une décision d'interface à
	    prendre devant l'écran, pas un effet de bord d'une extraction.

	    ⚠️ Elle ne part PAS dans `OngletConsommations`, qui l'héritait pourtant de
	    la même page : ses trois champs tiennent dans la grille de la charte, et la
	    recopier là-bas aurait dupliqué une règle pour entériner un héritage
	    accidentel — une variante qui n'apporte rien (`standards/02` §4 bis).
	    Seuls la répartition et l'espacement : la peau des contrôles est partie le
	    28/08/2026 — le pourquoi vit dans `check-styles-nus.mjs`, volet C. */
	.form-grid {
		grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
		gap: 0.65rem;
	}
	/*  Un contact : un cadre, pour qu'on voie où s'arrête une personne et où
	    commence la suivante. Il était posé par un `style=` en ligne. */
	.contact {
		border: 1px solid var(--color-border);
		border-radius: 6px;
		padding: 0.6rem;
		margin: 0.5rem 0;
	}
</style>
