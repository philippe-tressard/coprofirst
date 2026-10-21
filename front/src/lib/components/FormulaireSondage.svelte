<!--
  Le formulaire de création d'un sondage — extrait de `sondages/+page.svelte` le
  16/08/2026.

  POURQUOI. La page portait encore DEUX formulaires (sondage et annonce) et 812
  lignes : le garde-fou de modularité refuse qu'un fichier déjà au-dessus de 500
  grossisse (`standards/02` §6). La règle est de découper quand on y touche.

  ⚠️ CE QUI CHANGE VRAIMENT ICI, et qui n'est pas un déplacement de code : le
  ciblage du sondage rejoint le STANDARD du site.

  Jusqu'ici, cet écran était le seul à cibler avec ses propres notions —
  `batiments_ids` (des identifiants de bâtiments) et `profils_autorises` (des
  statuts bruts) — servies par un composant qui n'existait que pour lui. Deux
  conséquences visibles, l'une esthétique et l'autre fonctionnelle :

    • son sélecteur avait sa propre typographie et un bouton « Réinitialiser »
      que ni `PerimetrePicker` ni `DestinatairePicker` n'ont ;
    • on ne pouvait cibler NI le parking, NI l'AFUL, NI un espace de bâtiment —
      l'arborescence complète des périmètres lui était inaccessible.

  Le modèle a suivi (migration 0147) : `perimetre_cible` + `public_cible`, comme
  les publications, et `sondage_accessible` applique désormais exactement la même
  règle que `publication_visible`. Décision de l'utilisateur le 16/08/2026, après
  qu'on lui a présenté le choix « apparence seulement » ou « modèle compris ».
-->
<script lang="ts">
	import { contexteAssistant, perimetreContexte } from '$lib/assistant';
	import { createEventDispatcher } from 'svelte';
	import CadreFormulaire from '$lib/components/CadreFormulaire.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import SectionTitre from '$lib/components/SectionTitre.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import { sectionPresente, type Etat } from '$lib/entites/types';
	import { SONDAGE } from '$lib/entites/sondage';
	import { pliageDe, requisDe } from '$lib/pliage';
	import {
		sondages as sondagesApi,
		type SondageCorrige,
		type SondageCree,
		type SondageDetail,
	} from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { toast } from '$lib/components/Toast.svelte';
	import { perimetreDefautListe } from '$lib/perimetres';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';

	//  Ce que le serveur rend, tel quel (#1572) ; la page recharge sa liste.
	const dispatch = createEventDispatcher<{
		cree: SondageCree;
		modifie: SondageCorrige;
		annule: void;
	}>();

	//  `id` n'existe QU'EN édition : le serveur corrige un libellé par son
	//  identifiant, et vérifie qu'il appartient bien à ce sondage.
	type OptionForm = { id?: number; libelle: string; champ_libre: boolean };

	/**  Le sondage à corriger, ou `null` pour une création (#783).
	 *
	 *   🔴 Ce fichier portait, jusqu'au 06/09/2026, ce constat : «
	 *   `PATCH /sondages/{id}` existe côté serveur et personne ne l'appelle ».
	 *   Tout était écrit et testé sauf le chemin pour y arriver — corriger une
	 *   faute de frappe imposait de supprimer et recréer, donc de perdre les votes.
	 *   Le constat était juste ; il devient l'implantation.
	 *
	 *   🔴 Une FICHE, toujours (#1661) : la liste ne porte pas `options`, et
	 *   `PageCommunaute` charge la fiche avant d'ouvrir la correction. Le typer
	 *   `Sondage` ferait de nouveau échouer la vérification sur cet écart. */
	export let sondage: SondageDetail | null = null;

	$: modeEdition = sondage !== null;
	$: etat = (modeEdition ? 'edition' : 'creation') as Etat;

	//  Initialisés À LA CONSTRUCTION, jamais réactifs : un `$:` écraserait la
	//  saisie en cours dès que le parent rafraîchit sa liste. C'est `{#key}` chez
	//  l'appelant qui remonte le composant — même contrat que `FormulaireAnnonce`.
	let question = sondage?.question ?? '';
	let description = sondage?.description ?? '';
	//  Vrai dès qu'une proposition de l'assistant IA a été appliquée (#985).
	let assisteIA = false;
	//  `<input type="datetime-local">` veut `AAAA-MM-JJTHH:MM`, pas de l'ISO avec
	//  fuseau : couper à seize caractères est ce que fait déjà l'événement.
	let clotureLe = sondage?.cloture_le ? String(sondage.cloture_le).slice(0, 16) : '';
	let resultatsPublics = sondage?.resultats_publics ?? true;
	let options: OptionForm[] = sondage?.options?.length
		? sondage.options.map((o) => ({
				id: o.id,
				libelle: o.libelle,
				champ_libre: o.champ_libre,
			}))
		: [
				{ libelle: '', champ_libre: false },
				{ libelle: '', champ_libre: false },
			];
	let perimetreCible: string[] = [...(sondage?.perimetre_cible ?? perimetreDefautListe())];
	let publicCible: string[] = [...(sondage?.public_cible ?? ['résidents'])];
	let partagerWhatsapp = false;
	let envoyerSyndic = false;
	let envoyerCs = false;
	//  « Envoyer une copie à … » — la case vit dans `CanauxNotification`, qui
	//  porte la règle et son pourquoi. Elle s'affichait ici sans être lue (31/08).
	let envoyerAuteur = false;
	let submitting = false;

	function ajouterOption() {
		options = [...options, { libelle: '', champ_libre: false }];
	}
	function retirerOption(i: number) {
		options = options.filter((_, idx) => idx !== i);
	}
	function monter(i: number) {
		if (i === 0) return;
		const arr = [...options];
		[arr[i - 1], arr[i]] = [arr[i], arr[i - 1]];
		options = arr;
	}
	function descendre(i: number) {
		if (i === options.length - 1) return;
		const arr = [...options];
		[arr[i], arr[i + 1]] = [arr[i + 1], arr[i]];
		options = arr;
	}

	function reinitialiser() {
		question = '';
		description = '';
		clotureLe = '';
		resultatsPublics = true;
		options = [
			{ libelle: '', champ_libre: false },
			{ libelle: '', champ_libre: false },
		];
		perimetreCible = perimetreDefautListe();
		publicCible = ['résidents'];
		partagerWhatsapp = false;
		envoyerSyndic = false;
		envoyerCs = false;
	}

	/**  Corriger un sondage — strictement ce que `SondageUpdate` accepte.
	 *
	 *   🔴 Ni le ciblage ni les canaux de diffusion ne sont renvoyés, et ce n'est
	 *   pas un oubli : le serveur ne les expose pas. Restreindre un périmètre après
	 *   coup masquerait le sondage à des gens qui ont déjà voté ; renvoyer un canal
	 *   rediffuserait. Les envoyer quand même serait ignoré côté serveur, et ferait
	 *   croire ICI que le geste a marché.
	 *
	 *   ⚠️ Les options portent leur `id` : le serveur corrige un LIBELLÉ, il
	 *   n'ajoute ni ne retire de réponse — la liste engagerait ceux qui ont voté.
	 *   Les options nouvelles (sans `id`) sont donc écartées ici plutôt que
	 *   refusées là-bas : l'écran ne les propose pas non plus. */
	async function corriger() {
		if (!sondage) return;
		if (!question.trim()) {
			toast('error', 'La question est obligatoire');
			return;
		}
		submitting = true;
		try {
			const maj = await sondagesApi.modifier(sondage.id, {
				question,
				description: description || null,
				assiste_ia: assisteIA || undefined,
				cloture_le: clotureLe ? new Date(clotureLe).toISOString() : null,
				resultats_publics: resultatsPublics,
				options: options
					.filter((o) => o.id !== undefined && o.libelle.trim())
					.map((o) => ({ id: o.id, libelle: o.libelle })),
			});
			toast('success', 'Sondage mis à jour');
			dispatch('modifie', maj);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			submitting = false;
		}
	}

	async function enregistrer() {
		if (modeEdition) return corriger();
		const opts = options
			.map((o, i) => ({ libelle: o.libelle, ordre: i, champ_libre: o.champ_libre }))
			.filter((o) => o.libelle.trim());
		if (!question || opts.length < 2) {
			toast('error', 'Question et au moins 2 options requises');
			return;
		}
		submitting = true;
		try {
			const cree = await sondagesApi.create({
				question,
				description: description || undefined,
				assiste_ia: assisteIA,
				cloture_le: clotureLe ? new Date(clotureLe).toISOString() : undefined,
				resultats_publics: resultatsPublics,
				options: opts,
				//  Comme les publications : un ciblage vide vaut « aucune
				//  restriction », c'est le serveur qui en décide (`visibility.py`).
				perimetre_cible: perimetreCible.length > 0 ? perimetreCible : null,
				public_cible: publicCible.length > 0 ? publicCible : null,
				partager_whatsapp: partagerWhatsapp,
				envoyer_syndic: envoyerSyndic,
				envoyer_cs: envoyerCs,
				envoyer_auteur: envoyerAuteur,
			});
			reinitialiser();
			toast('success', 'Sondage créé');
			dispatch('cree', cree);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			submitting = false;
		}
	}
</script>

<CadreFormulaire
	edition={modeEdition}
	titre={modeEdition ? SONDAGE.libelleModifier : SONDAGE.libelleNouveau}
>
	<form on:submit|preventDefault={enregistrer}>
		<!--  1. Titre — ici, la question posée, et le titre de la section EST son
		      libellé (`titreEcran: 'Question'`). -->
		<SectionTitre id="sondage-question" libelle="Question" bind:valeur={question} />

		<!--  2. Champs spécifiques du sondage : ses options et sa clôture. DEUX
		      groupes nommés pour une seule section — la déclaration les annonce
		      tous les deux (`titreEcran`), et `lint:etats` refuse tout intitulé
		      inventé sur place. -->
		{#if sectionPresente(SONDAGE, etat, 'nature')}
			<SectionFormulaire
				titre="Réponses possibles"
				pliable={pliageDe(SONDAGE, 'nature')}
				requis={requisDe(SONDAGE, 'nature')}
				rempli={options.filter((o) => o.libelle.trim()).length >= 2}
			>
				<div class="options">
					{#each options as _opt, i (i)}
						<div class="option">
							<div class="option-ligne">
								<span class="option-rang">{i + 1}.</span>
								<input
									class="option-saisie"
									bind:value={options[i].libelle}
									placeholder="Réponse {i + 1}"
									aria-label="Libellé de la réponse {i + 1}"
								/>
								<!--  🔒 EN CORRECTION, la liste des réponses NE BOUGE PAS — seuls
								      les libellés se corrigent. Ajouter, retirer ou réordonner
								      changerait ce que les votes déjà exprimés désignent, et le
								      serveur le refuse (`SondageUpdate` ne prend qu'un `id` et un
								      `libelle`). Masquer ces gestes ici, c'est dire la même chose
								      que l'API — un bouton qui déclencherait un refus serait pire
								      qu'absent. -->
								{#if !modeEdition}
									<button
										type="button"
										class="btn btn-sm btn-outline"
										title="Monter"
										aria-label="Monter la réponse {i + 1}"
										disabled={i === 0}
										on:click={() => monter(i)}>↑</button
									>
									<button
										type="button"
										class="btn btn-sm btn-outline"
										title="Descendre"
										aria-label="Descendre la réponse {i + 1}"
										disabled={i === options.length - 1}
										on:click={() => descendre(i)}>↓</button
									>
								{/if}
								{#if !modeEdition && options.length > 2}
									<button
										type="button"
										class="btn btn-sm btn-outline option-supprimer"
										title="Supprimer"
										aria-label="Supprimer la réponse {i + 1}"
										on:click={() => retirerOption(i)}>✕</button
									>
								{/if}
							</div>
							{#if !modeEdition}
								<label class="case case-secondaire">
									<input type="checkbox" bind:checked={options[i].champ_libre} />
									<span>Champ libre (le répondant pourra préciser sa réponse par écrit)</span>
								</label>
							{/if}
						</div>
					{/each}
					{#if !modeEdition}
						<button type="button" class="btn btn-sm btn-outline" on:click={ajouterOption}>
							+ Ajouter une autre réponse
						</button>
					{/if}
				</div>
			</SectionFormulaire>

			<SectionFormulaire titre="Clôture" pliable={pliageDe(SONDAGE, 'nature')}>
				<div class="form-grid">
					<div class="field">
						<label for="sondage-cloture">Date de clôture</label>
						<input id="sondage-cloture" type="datetime-local" bind:value={clotureLe} />
					</div>
					<div class="field">
						<label class="case">
							<input type="checkbox" bind:checked={resultatsPublics} />
							<span>Afficher les résultats avant la clôture</span>
						</label>
						<!--  L'ancien libellé, « Résultats visibles avant clôture », ne disait
					      pas À QUI — or c'est toute la question : des résultats visibles
					      pendant le vote influencent les votes suivants (#397). L'audience
					      est celle du sondage : son périmètre et ses destinataires. -->
						<p class="aide sous-case">
							Ils seront lus par les destinataires du sondage. Sinon, ils n'apparaissent qu'une fois
							le sondage clôturé.
						</p>
					</div>
				</div>
			</SectionFormulaire>
		{/if}

		<!--  4 à 9 : ordre, intitulés et séparations hérités du composant partagé.
		      Le sondage n'a ni photos ni documents. -->
		<ChampsCommuns
			entite={SONDAGE}
			idPrefixe="sondage"
			avecPerimetre={sectionPresente(SONDAGE, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecDestinataires={sectionPresente(SONDAGE, etat, 'destinataires')}
			bind:destinataires={publicCible}
			avecDescription={sectionPresente(SONDAGE, etat, 'description')}
			bind:description
			assistant={contexteAssistant('sondage', { Périmètre: perimetreContexte(perimetreCible) })}
			bind:titreObjet={question}
			bind:assisteIA
			descriptionPlaceholder="Description du sondage…"
			avecDiffusion={sectionPresente(SONDAGE, etat, 'diffusion')}
			bind:whatsapp={partagerWhatsapp}
			bind:syndic={envoyerSyndic}
			bind:cs={envoyerCs}
			bind:auteur={envoyerAuteur}
		/>

		<!--  Pas de bouton « Annuler » ici : la commande vit dans l'en-tête de page,
		      où le bouton d'ouverture bascule (#367). -->
		<!--  « Annuler » est À CÔTÉ d'« Enregistrer » — norme du 18/08/2026, posée
		      sur Tickets, constatée, puis étendue. L'en-tête de page ne porte plus
		      de seconde commande d'annulation (#367). -->
		<PiedFormulaire enCours={submitting} on:annule />
	</form>
</CadreFormulaire>

<style>
	.form-grid .field {
		margin-bottom: 0;
	}

	.options {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-items: flex-start;
	}
	.option {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.6rem 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-neutre-fond);
	}
	.option-ligne {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}
	.option-rang {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		min-width: 1.1rem;
		text-align: right;
	}
	.option-saisie {
		flex: 1;
		min-width: 0;
		padding: 0.45rem 0.6rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: var(--fs-base);
		background: var(--color-bg);
	}
	.option-supprimer {
		color: var(--color-danger);
	}

	/*  ⚠️ Une case et son libellé, NOMMÉS. La page portait un `input, textarea {
	    width: 100% }` — un sélecteur d'ÉLÉMENT nu, qui atteignait donc aussi les
	    cases à cocher : chacune s'étirait sur toute la largeur et repoussait son
	    texte à l'autre bout de la ligne. C'est le défaut que l'utilisateur a
	    signalé sur le sondage ET sur l'annonce le 16/08/2026 — un seul sélecteur,
	    deux écrans. `npm run lint:styles` le refuse désormais. */
	.case-secondaire {
		padding-left: 1.6rem;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
</style>
