<!--
  Le formulaire de dépôt d'une idée — extrait de `sondages/+page.svelte` le
  16/08/2026.

  POURQUOI. La page portait TROIS formulaires de création (sondage, idée, annonce)
  et 868 lignes : le garde-fou de modularité a refusé qu'elle grossisse encore
  (`standards/02` §6). La règle est de découper quand on y touche, et c'est ce
  bloc-ci qui part — le plus autonome des trois, avec son propre état et sa propre
  responsabilité.

  Il suit le contrat de `FormulaireActualite` et `FormulaireTicket` : il porte son
  cadre (`CadreFormulaire`) et signale par un événement.

  ⚠️ Il porte DÉSORMAIS LES DEUX GESTES (#783, 06/09/2026) : déposer une idée
  et la corriger. Le cadre suit — créer dans une boîte, éditer dans une fenêtre
  (`ux-patterns` §14 bis) — et c'est `CadreFormulaire` qui le décide, pas ce
  fichier. Une seconde composante d'édition aurait dupliqué le formulaire entier.

  ⚠️ Deux défauts d'UX corrigés au passage, tous deux du même genre que ceux
  signalés par l'utilisateur sur les autres écrans :
    • le bouton « Soumettre » était posé NU dans le formulaire, donc cadré à
      GAUCHE, alors que `.form-actions` aligne à droite partout ailleurs ;
    • le champ Titre portait une mise en forme en `style=` au lieu d'hériter de
      `.field`, et n'occupait pas la ligne entière alors que c'est un texte libre
      (skill `ux-patterns` §9 bis).
-->
<script lang="ts">
	import { contexteAssistant, perimetreContexte } from '#lib/assistant.ts';
	import { createEventDispatcher } from 'svelte';
	import CadreFormulaire from '#lib/components/CadreFormulaire.svelte';
	import SectionTitre from '#lib/components/SectionTitre.svelte';
	import ChampsCommuns from '#lib/components/ChampsCommuns.svelte';
	import { sectionPresente, type Etat } from '#lib/entites/types.ts';
	import { IDEE } from '#lib/entites/idee.ts';
	import { perimetreDefautListe } from '#lib/perimetres/index.ts';
	import { idees as ideesApi, type Idee, type IdeeCreee } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';

	//  Ce que le serveur rend, tel quel (#1572) : la LIGNE brute à la création —
	//  la page recharge alors sa liste —, l'idée enrichie à la correction, que la
	//  liste remplace en place.
	const dispatch = createEventDispatcher<{ cree: IdeeCreee; modifie: Idee; annule: void }>();

	/**  L'idée à corriger, ou `null` pour un dépôt. C'est la SEULE prop qui
	 *   distingue les deux gestes — tout le reste en découle. */
	export let idee: Idee | null = null;

	$: modeEdition = idee !== null;
	/**  L'état du cadre #430. Il était écrit en CONSTANTE `'creation'`, avec ce
	 *   commentaire : « corriger une idée déposée n'existe pas côté produit, et
	 *   l'écrire ainsi rend le manque visible en relecture ». Le manque a été
	 *   comblé (#783) : la constante devient une déduction. */
	$: etat = (modeEdition ? 'edition' : 'creation') as Etat;

	//  Initialisés À LA CONSTRUCTION, jamais réactifs : un `$:` écraserait la
	//  saisie en cours dès que le parent rafraîchit sa liste. C'est `{#key}` chez
	//  l'appelant qui remonte le composant d'une idée à l'autre — même contrat que
	//  `FormulaireAnnonce`.
	let form = { titre: idee?.titre ?? '', description: idee?.description ?? '' };
	let perimetreCible: string[] = [...(idee?.perimetre_cible ?? perimetreDefautListe())];
	//  Section 5 (#782). Vide = tous les résidents, ici comme côté serveur.
	let publicCible: string[] = [...(idee?.public_cible ?? [])];
	let submitting = false;
	//  Vrai dès qu'une proposition de l'assistant IA a été appliquée (#985).
	let assisteIA = false;

	async function enregistrer() {
		if (!form.titre || !form.description) {
			toast('error', 'Titre et description obligatoires');
			return;
		}
		submitting = true;
		try {
			if (idee) {
				//  ⚠️ Le ciblage n'est PAS renvoyé : `IdeeUpdate` ne l'accepte pas.
				//  Restreindre après coup masquerait l'idée à des gens qui l'ont déjà
				//  votée — même décision que pour le sondage. L'envoyer quand même
				//  serait ignoré par le serveur, et ferait croire ici que ça marche.
				const maj = await ideesApi.modifier(idee.id, {
					...form,
					assiste_ia: assisteIA || undefined,
				});
				toast('success', 'Idée mise à jour');
				dispatch('modifie', maj);
				return;
			}
			const creee = await ideesApi.create({
				...form,
				assiste_ia: assisteIA,
				perimetre_cible: perimetreCible,
				public_cible: publicCible,
			});
			form = { titre: '', description: '' };
			perimetreCible = perimetreDefautListe();
			publicCible = [];
			toast('success', 'Idée soumise !');
			dispatch('cree', creee);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			submitting = false;
		}
	}
</script>

<!--  Sans cadre en correction : elle s'ouvre DANS la carte (#1329, §14 ter). -->
<CadreFormulaire
	edition={modeEdition}
	encadre={!modeEdition}
	titre={modeEdition ? IDEE.libelleModifier : IDEE.libelleNouveau}
>
	<form on:submit|preventDefault={enregistrer}>
		<!--  1. Le titre, par `SectionTitre` comme les six autres formulaires : il
		      était écrit ici en libellé de champ, « Titre * » en noir, au lieu de la
		      section TITRE* dont l'astérisque rougit tant qu'elle est vide (#1186). -->
		<SectionTitre
			id="idee-titre-{idee?.id ?? 'new'}"
			bind:valeur={form.titre}
			placeholder="Ex. Vélos électriques en libre-service"
		/>
		<!--  4 et 6 : le PÉRIMÈTRE et la description, hérités du composant partagé.
		      Le périmètre est arrivé le 18/08/2026 (migration 0153) — l'idée était la
		      dernière entité de la Communauté sans aucune notion de lieu, alors que
		      « un local à vélos dans le bâtiment 3 » et « l'éclairage du parking » ne
		      concernent pas les mêmes voisins.

		      La section 5 (destinataires) s'est ouverte le 06/09 (#782) ; les sections
		      2, 7, 8 et 9 restent `sansObjet`. C'est la DÉCLARATION qui le dit et qui
		      les fait disparaître — jamais une condition écrite ici. -->
		<ChampsCommuns
			entite={IDEE}
			idPrefixe="idee"
			avecPerimetre={sectionPresente(IDEE, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecDestinataires={sectionPresente(IDEE, etat, 'destinataires')}
			bind:destinataires={publicCible}
			avecDescription={sectionPresente(IDEE, etat, 'description')}
			descriptionRequise
			bind:description={form.description}
			assistant={contexteAssistant('idée', { Périmètre: perimetreContexte(perimetreCible) })}
			bind:titreObjet={form.titre}
			bind:assisteIA
			descriptionPlaceholder="Décrivez votre idée…"
		/>
		<!--  « Annuler » est À CÔTÉ d'« Enregistrer » — norme du 18/08/2026, posée
		      sur Tickets, constatée, puis étendue. L'en-tête de page ne porte plus
		      de seconde commande d'annulation (#367). -->
		<PiedFormulaire enCours={submitting} on:annule />
	</form>
</CadreFormulaire>
