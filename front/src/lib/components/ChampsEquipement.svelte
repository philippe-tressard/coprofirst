<!--
  La FICHE d'un équipement — maquette C, arbitrée le 01/11/2026 (#2442) : les
  champs à gauche, et à droite ce qu'ils PRODUISENT (l'aperçu) et, en
  correction, ce qu'ils TOUCHENT (ce qui le cite).

  Comme `ChampsPrestataire`, il ne porte ni `<form>`, ni pied, ni titre : la
  création s'ouvre en tête de l'onglet, la correction dans la carte, et seul
  l'appelant sait ce qu'enregistrer veut dire. Les sections sont celles de la
  déclaration (`#lib/entites/equipement`), dans l'ordre du cadre.
-->
<script context="module" lang="ts">
	let compteur = 0;
</script>

<script lang="ts">
	import SectionFormulaire from './SectionFormulaire.svelte';
	import SectionTitre from './SectionTitre.svelte';
	import GrilleIcones from './GrilleIcones.svelte';
	import PerimetrePicker from './PerimetrePicker.svelte';
	import ApercuEquipement from './ApercuEquipement.svelte';
	import { EQUIPEMENT } from '#lib/entites/equipement.ts';
	import { SECTIONS_LIBELLE, sectionPresente, type Etat } from '#lib/entites/types.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { pliageDe, requisDe } from '#lib/pliage.ts';
	import { perimetreLabel } from '#lib/perimetres/index.ts';
	import { slug } from '#lib/texte.ts';
	import {
		ABREVIATION_MAX,
		ICONES_EQUIPEMENT,
		abreviationDe,
		type FormulaireEquipement,
	} from '#lib/equipements.ts';

	export let form: FormulaireEquipement;
	/** Création ou correction : la déclaration en tire les sections présentes. */
	export let etat: Etat = 'creation';
	/** Le code, figé — en correction seulement. En création, il se déduit du libellé. */
	export let code: string | null = null;

	const id = `equipement-${++compteur}`;

	//  Le code que le serveur posera — même règle que lui (`en_slug`, tirets bas).
	$: codePropose = code ?? slug(form.libelle, '_');
	$: perimetresChoisis = form.perimetres.length ? perimetreLabel(form.perimetres) : '';
</script>

<div class="fiche">
	<div>
		<SectionTitre {id} libelle="Libellé" bind:valeur={form.libelle} maxlength={80} />
		<p class="aide code">
			{#if code}
				Code <code>{code}</code>{SEPARATEUR.tiret}non modifiable : il est enregistré dans les
				contrats, les affaires et les prestataires.
			{:else if codePropose}
				Code <code>{codePropose}</code>{SEPARATEUR.tiret}déduit du libellé, figé à l’enregistrement.
			{/if}
		</p>

		{#if sectionPresente(EQUIPEMENT, etat, 'nature')}
			<SectionFormulaire
				titre="Icône et abréviation"
				pliable={pliageDe(EQUIPEMENT, 'nature')}
				requis={requisDe(EQUIPEMENT, 'nature')}
				rempli={!!form.icone}
				resume={abreviationDe(form)}
			>
				<GrilleIcones icones={ICONES_EQUIPEMENT} bind:valeur={form.icone} libelle="Icône" />
				<label class="field abreviation"
					>Abréviation<input
						bind:value={form.abreviation}
						maxlength={ABREVIATION_MAX}
						placeholder={abreviationDe({ abreviation: null, libelle: form.libelle || 'Autre' })}
					/>
					<span class="aide">
						Le mot de la gouttière des cartes, en capitales{SEPARATEUR.tiret}{ABREVIATION_MAX}
						caractères au plus. Vide, c’est le début du libellé.
					</span>
				</label>
			</SectionFormulaire>
		{/if}

		{#if sectionPresente(EQUIPEMENT, etat, 'perimetre')}
			<SectionFormulaire
				titre="Périmètres concernés"
				pliable={pliageDe(EQUIPEMENT, 'perimetre')}
				requis={requisDe(EQUIPEMENT, 'perimetre')}
				rempli={form.perimetres.length > 0}
				valeurModifiee={form.perimetres.length > 0}
				resume={perimetresChoisis || 'aucun'}
			>
				<PerimetrePicker bind:value={form.perimetres} titre="" requis={false} />
				<p class="aide">
					Où se trouve l’équipement. Dans une affaire, choisir l’un propose l’autre, jamais à la
					place d’un choix déjà fait.
				</p>
			</SectionFormulaire>
		{/if}

		{#if sectionPresente(EQUIPEMENT, etat, 'description')}
			<SectionFormulaire
				titre={SECTIONS_LIBELLE.description}
				pliable={pliageDe(EQUIPEMENT, 'description')}
				requis={requisDe(EQUIPEMENT, 'description')}
				rempli={!!form.description.trim()}
				valeurModifiee={!!form.description.trim()}
				resume={form.description.trim() ? 'renseignée' : 'aucune'}
				pour="{id}-description"
			>
				<div class="field">
					<textarea id="{id}-description" rows="3" bind:value={form.description}></textarea>
				</div>
			</SectionFormulaire>
		{/if}

		{#if sectionPresente(EQUIPEMENT, etat, 'mise_en_avant')}
			<SectionFormulaire
				titre="Ordre"
				pliable={pliageDe(EQUIPEMENT, 'mise_en_avant')}
				requis={requisDe(EQUIPEMENT, 'mise_en_avant')}
				rempli
				resume="rang {form.ordre}"
				pour="{id}-ordre"
			>
				<div class="field largeur-saisie">
					<input id="{id}-ordre" type="number" bind:value={form.ordre} />
				</div>
				<p class="aide">Les plus petits d’abord, dans les listes où l’on choisit.</p>
			</SectionFormulaire>
		{/if}
	</div>

	<aside class="apercu" aria-label="Aperçu">
		<ApercuEquipement {form} />
		<slot name="usages" />
	</aside>
</div>

<style>
	/*  Deux colonnes au bureau, la fiche puis l'aperçu ; empilées au téléphone —
	    l'aperçu SOUS les champs, qu'on remplit d'abord. */
	.fiche {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 1rem;
	}
	@media (min-width: 768px) {
		.fiche {
			grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
			align-items: start;
		}
		.apercu {
			position: sticky;
			top: 1rem;
		}
	}
	.apercu {
		display: grid;
		gap: 0.75rem;
	}
	.code {
		margin: -0.4rem 0 0.8rem;
	}
	.abreviation {
		margin-top: 0.75rem;
	}
	.abreviation input {
		max-width: 16rem;
	}
</style>
