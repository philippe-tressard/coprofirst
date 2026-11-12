/**
 * Le CONTRAT d'entretien, déclaré une fois — les sections du cadre, ce qu'elles
 * portent, et **chaque divergence entre états avec son motif** (R4).
 *
 * Septième entité du cadre #430, déclarée le 12/09/2026 sur signalement à
 * l'écran : *« l'édition de Contrats ne respecte pas l'UX — l'ordre des sections,
 * la séparation par un trait, l'intitulé des sections »* (#909).
 *
 * ## Pourquoi la déclaration vient AVANT le balisage
 *
 * `ChampsContrat` n'employait **aucune** `SectionFormulaire` : ni titre de
 * section, ni filet, ni ordre — quinze champs dans une seule grille. Réordonner
 * le balisage sans déclarer l'entité aurait produit un écran conforme *ce jour-là*
 * et rien pour le maintenir : c'est `lint:etats` qui refuse une section rendue
 * hors déclaration, et une absence non motivée.
 *
 * ## Ce que la déclaration a fait apparaître
 *
 * 🔴 **Quatre sections sur neuf sont sans objet ici, et aucune ne l'était par
 * hasard.** Les écrire oblige à dire pourquoi — et l'une d'elles, la Diffusion,
 * mérite d'être relue : un contrat signé n'est annoncé à personne aujourd'hui,
 * alors que son échéance concerne le conseil syndical. Ce n'est pas une omission
 * de ce lot, c'est une décision qui n'a jamais été prise.
 *
 * ⚠️ Le contrat n'a pas d'état `evolution` : il ne porte pas de fil. Ses
 * changements se lisent dans le **carnet d'entretien**, qui est une VUE sur trois
 * tables (`project_carnet_entretien`) — pas un historique de l'objet.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `ChampsContrat.svelte` — la saisie (`sectionPresente`)
 */

import type { EntiteDeclaree } from './types';

export const CONTRAT: EntiteDeclaree = {
	id: 'contrat',
	libelle: "Contrat d'entretien",
	libelleNouveau: 'Nouveau contrat',
	libelleModifier: 'Modifier le contrat',
	sections: [
		{
			id: 'titre',
			objet: 'Titre',
			requis: true,
		},
		{
			//  🔴 Les sections STANDARD (24/09/2026, signalé à l'écran : « Prendre
			//  exemple sur l'UX d'Affaires »). Tout vivait dans une section « Le
			//  contrat » que le cadre ne connaît pas — prestataire, équipement, dates
			//  et numéro, sans distinguer l'obligatoire du facultatif. Chaque groupe
			//  rejoint la section qui le nomme sur les affaires ; ne reste ici que le
			//  numéro, facultatif, donc plié.
			id: 'nature',
			objet: 'N° de contrat',
			titreEcran: ['Référence'],
			pliee: true,
		},
		{
			//  Il ne qualifie pas le contrat, il le DÉFINIT — un contrat d'entretien
			//  sans ce qu'il entretient n'existe pas : obligatoire.
			id: 'equipement',
			objet: 'Équipement entretenu',
			requis: true,
		},
		{
			id: 'suivi',
			sansObjet:
				"Un contrat n'a pas d'états à parcourir : il court, ou son échéance est passée. " +
				"C'est une DATE qui le dit, pas un statut qu'on déplace à la main — et une date " +
				"ne se trompe pas d'un clic. Le carnet d'entretien s'en sert pour ranger les " +
				'contrats en cours et les contrats échus.',
		},
		{
			//  Ses DATES — début, durée, rythme, prochaine visite. Le contrat ne
			//  paraît pas pour autant sous le filtre Calendrier : ce sont les
			//  entretiens qu'il déclenche qui s'y inscrivent.
			id: 'quand',
			objet: 'Début · Durée initiale · Fréquence · Prochaine visite · Résilié le · Remplacé par',
			requis: true,
		},
		{
			//  Le prestataire qui signe : la section qui le nomme sur une affaire.
			id: 'intervenant',
			objet: 'Prestataire',
			requis: true,
		},
		{
			id: 'perimetre',
			objet: 'PerimetrePicker — ce que le contrat entretient',
			//  🔴 OBLIGATOIRE, donc DÉPLIÉ (24/09/2026, arbitré à l'écran : « le
			//  périmètre est toujours obligatoire »). Il ne l'était pas, au motif
			//  qu'un contrat d'assurance couvre la copropriété entière — c'est
			//  justement la valeur que le sélecteur propose d'office : rien à
			//  cocher, et le serveur la pose si la liste arrive vide.
			//  ⚠️ L'aide (« il apparaît dans le carnet d'entretien de ce périmètre »)
			//  vit AVEC le champ : la déclaration dit ce qui est rendu, pas comment
			//  on l'explique.
			requis: true,
		},
		{
			id: 'description',
			//  C'est ici qu'atterrit la synthèse proposée par l'assistant IA (#899),
			//  relue et corrigée avant enregistrement.
			objet: 'RichEditor — la synthèse du contrat',
			pliee: true,
		},
		{
			//  🔴 La dette `motif: 'api'` (#921) a été LEVÉE le 12/09/2026, et elle
			//  n'était pas ce qu'elle disait. Le motif écrit était : « un document se
			//  rattache à un `contrat_id` qui n'existe pas encore à la création ».
			//  C'était vrai, et la conclusion — « l'écran ne peut pas la rendre » — ne
			//  l'était pas : les ACTUALITÉS déposent leurs documents à la création
			//  depuis #531, en gardant les fichiers de côté et en les attachant une
			//  fois l'objet enregistré.
			//
			//  ⚠️ Aucun endpoint ne manquait. Le geste existait, sur un autre écran, et
			//  personne n'est allé voir : une dette déclarée avec son motif a
			//  l'apparence d'une décision, et c'est ce qui l'a fait survivre.
			//
			//  ⚠️ La section ne porte que des DOCUMENTS, et c'est un fait sur l'objet,
			//  pas une divergence : un contrat est un document, pas une constatation.
			//  Ce qu'on photographie — un désordre, une intervention — appartient au
			//  ticket ou à l'événement qui s'y rapporte, et le carnet les rassemble.
			id: 'pieces_jointes',
			objet: 'FichiersUpload — le contrat signé, ses avenants, ses conditions générales',
			//  🔴 PLIÉE, comme toute section facultative (21/09/2026, demandé à
			//  l'écran). Elle était l'exception inverse — « dépliée parce que joindre
			//  une photo est le premier geste sur téléphone ». C'est l'ARBITRAGE qui a
			//  changé, pas la règle : un formulaire aux sections toutes ouvertes
			//  n'est pas lisible au pouce.
			//  ⚠️ `valeurModifiee` la rouvre dès qu'un fichier y est joint : en
			//  édition, un objet qui porte des pièces jointes ne les cache pas.
			pliee: true,
		},
		{
			id: 'affaires_liees',
			sansObjet:
				'Un contrat se rattache à son prestataire et à ses interventions ; les ' +
				'affaires qu’il engage le citent, pas l’inverse (#1342).',
		},
		{
			id: 'au_nom_de',
			sansObjet:
				'Un contrat est signé par la copropriété : il ne se saisit pas au nom de ' + "quelqu'un.",
		},
		{
			id: 'destinataires',
			//  🔴 OBLIGATOIRE, donc DÉPLIÉE (22/09/2026, signé à l'écran deux fois).
			//
			//  L'astérisque était écrite en dur par `SectionDestinataires` : la
			//  déclaration ne savait donc pas que la section était obligatoire, et
			//  `lint:etats` — qui CALCULE le pliage à partir d'elle — ne voyait
			//  aucune contradiction à la déclarer pliée. L'écran affichait donc
			//  « DESTINATAIRES* » sur une ligne fermée, ce que la règle interdit.
			requis: true,
			sansObjet:
				"Un contrat ne s'adresse à personne : il lie la copropriété à une entreprise. " +
				'Qui le consulte est décidé par les droits (conseil syndical et administration), ' +
				'pas par un choix de saisie — la sécurité est centralisée, elle ne se règle pas ' +
				'dans un formulaire.',
		},
		{
			id: 'mise_en_avant',
			sansObjet:
				"Deux contrats sont DÉSIGNÉS depuis la fiche de copropriété — l'assurance et " +
				"le mandat de syndic —, et c'est une désignation, pas une mise en avant : " +
				"elle dit le rôle du contrat, pas son rang d'affichage.",
		},
		{
			id: 'diffusion',
			sansObjet:
				"Un contrat ne s'annonce pas : il se signe. Ni WhatsApp, ni courriel au syndic " +
				"à l'enregistrement.\n\n" +
				'⚠️ À RELIRE (12/09/2026) : son ÉCHÉANCE, elle, concerne le conseil syndical, et ' +
				"rien ne la lui signale depuis cet écran. Ce n'est pas une omission de ce lot — " +
				"c'est une décision qui n'a jamais été prise, et elle relève d'une relance " +
				"automatique plutôt que d'une case à cocher.",
		},
	],
};
