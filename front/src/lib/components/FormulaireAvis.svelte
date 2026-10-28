<!--
  Le formulaire d'un AVIS sur l'application — le dépôt et la correction (#2075).

  Ordre du cadre (`#lib/entites/avis`) : le titre, puis la NOTE — sous 3
  étoiles, ce qui a manqué —, puis la description, puis, à partir de 4 étoiles,
  la question de publication sur le site vitrine. La note précède la
  description, comme demandé : la remarque se pose avant qu'on raconte le reste.

  🔴 La question de publication n'a PAS de réponse par défaut (arbitrage du
  18/10/2026) : une case pré-cochée n'est pas un consentement (RGPD, CJUE
  *Planet49*). Les deux pastilles sont libres jusqu'au choix, et le serveur
  refuse un avis de 4 étoiles ou plus sans réponse (`utils/avis`).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CadreFormulaire from '#lib/components/CadreFormulaire.svelte';
	import SectionTitre from '#lib/components/SectionTitre.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '#lib/components/ChampsCommuns.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import NoteEtoiles from '#lib/components/NoteEtoiles.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { sectionPresente, type Etat } from '#lib/entites/types.ts';
	import { AVIS } from '#lib/entites/avis.ts';
	import { avis as avisApi, type Avis } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		NOTE_PUBLIABLE,
		NOTE_REMARQUE,
		OPTIONS_ACCORD,
		VITRINE,
		accordDe,
		choixAccord,
		merciPour,
	} from '#lib/avis.ts';

	const dispatch = createEventDispatcher<{ cree: Avis; modifie: Avis; annule: void }>();

	/** L'avis à corriger, ou `null` pour un dépôt — la seule prop qui distingue les deux. */
	export let avis: Avis | null = null;
	/**  Faux quand la CARTE porte déjà le cadre de la correction
	 *   (`CarteModifiable`, slot `edition`) : une boîte dans la boîte, c'est #425. */
	export let cadre = true;

	const modeEdition = avis !== null;
	const etat: Etat = modeEdition ? 'edition' : 'creation';
	const id = `avis-${avis?.id ?? 'new'}`;

	//  Initialisés À LA CONSTRUCTION : `{#key}` chez l'appelant remonte le
	//  composant d'un avis à l'autre (même contrat que `FormulaireIdee`).
	let titre = avis?.titre ?? '';
	let description = avis?.description ?? '';
	let note = avis?.note ?? 0;
	let remarque = avis?.remarque ?? '';
	let accord = choixAccord(avis?.consentement_publication ?? null);
	let envoi = false;

	$: avecRemarque = note > 0 && note < NOTE_REMARQUE;
	$: avecAccord = note >= NOTE_PUBLIABLE;

	async function enregistrer() {
		envoi = true;
		const saisie = {
			note,
			titre,
			description,
			remarque: avecRemarque ? remarque : null,
			consentement_publication: avecAccord ? accordDe(accord) : null,
		};
		try {
			if (avis) {
				const maj = await avisApi.modifier(avis.id, saisie);
				toast('success', merciPour(maj));
				dispatch('modifie', maj);
			} else {
				const cree = await avisApi.create(saisie);
				toast('success', merciPour(cree));
				dispatch('cree', cree);
			}
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			envoi = false;
		}
	}
</script>

{#snippet corps()}
	<form on:submit|preventDefault={enregistrer}>
		<SectionTitre
			id="{id}-titre"
			bind:valeur={titre}
			placeholder="Ex. Enfin une résidence où l'on sait ce qui se passe"
		/>

		{#if sectionPresente(AVIS, etat, 'nature')}
			<SectionFormulaire titre="Note" requis rempli={note > 0}>
				<NoteEtoiles saisie bind:note />
				<p class="aide">
					Votre avis se lit de vous et du conseil syndical. À partir de 4 étoiles, vous pourrez
					accepter qu'il se lise de tous.
				</p>
				{#if avecRemarque}
					<div class="field remarque">
						<label for="{id}-remarque">
							<span>Ce qui vous a manqué<EtoileRequis vide={!remarque.trim()} /></span>
						</label>
						<textarea
							id="{id}-remarque"
							rows="3"
							bind:value={remarque}
							placeholder="Dites-nous ce qui ne va pas : c'est ce qui fait progresser le site."
						></textarea>
					</div>
				{/if}
			</SectionFormulaire>
		{/if}

		<ChampsCommuns
			entite={AVIS}
			idPrefixe={id}
			avecDescription={sectionPresente(AVIS, etat, 'description')}
			descriptionRequise
			bind:description
			descriptionPlaceholder="Ce que l'application vous apporte, ce que vous aimeriez y trouver…"
		/>

		{#if avecAccord && sectionPresente(AVIS, etat, 'diffusion')}
			<SectionFormulaire
				titre="Diffusion sur coprofirst.fr"
				requis
				rempli={accord !== ''}
				idTitre="{id}-publication"
			>
				<p class="aide">
					Avec votre accord, votre avis se lira aussi de tous les comptes de la résidence, et votre
					témoignage aidera d'autres copropriétés à découvrir l'application. Seuls votre prénom,
					l'initiale de votre nom et votre rôle seraient affichés sur coprofirst.fr, et vous pourrez
					revenir sur votre choix à tout moment depuis cet écran. Que vous répondiez oui ou non,
					votre avis compte tout autant pour nous.
				</p>
				<ChoixPastilles
					options={OPTIONS_ACCORD}
					bind:valeur={accord}
					tous={false}
					libelle="Acceptez-vous que cet avis soit lu de tous et publié sur {VITRINE} ?"
					libelleVisible
					radio="{id}-accord"
					defilante={false}
					requis
				/>
			</SectionFormulaire>
		{/if}

		<PiedFormulaire enCours={envoi} on:annule />
	</form>
{/snippet}

{#if cadre}
	<CadreFormulaire
		edition={modeEdition}
		encadre={!modeEdition}
		titre={modeEdition ? AVIS.libelleModifier : AVIS.libelleNouveau}
	>
		{@render corps()}
	</CadreFormulaire>
{:else}
	{@render corps()}
{/if}

<style>
	.remarque {
		margin-top: 0.75rem;
	}
</style>
