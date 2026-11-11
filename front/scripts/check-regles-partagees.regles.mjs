/**
 * Les règles d'affichage que le site ET l'app iOS affichent (#2501).
 *
 * Lues par `check-regles-partagees.mjs`. Clé : le nom de la règle dans le front
 * (fonction ou constante dérivée). Champs :
 *
 * - `quoi` — ce que la règle affiche, en une ligne ;
 * - `api` — `api/app/<module>.py#<fonction>` : la fonction du serveur qui la
 *   calcule. Seule, elle dit la règle **servie** : le front ne la définit plus ;
 * - `migration` — `{ ticket, raison }` : le front la calcule encore. Le ticket
 *   porte la migration (le serveur la sert, le front lit le champ, puis la
 *   dérogation se retire — elle fait échouer le contrôle dès qu'elle ne sert plus).
 *   🔴 Le ticket est OUVERT : une dérogation dont le porteur est fermé n'a plus
 *   personne pour la résorber (#2511 et #2507 l'ont été avec neuf dérogations,
 *   #2633). `lint` est hors ligne et ne le voit pas : le pré-check le demande à
 *   GitHub (point 25, `--tickets`), API muette → INCONNU.
 *
 * Trois règles, celles des autres listes déclarées du dépôt :
 *   1. **Une raison, toujours.**
 *   2. **Une dérogation qui ne sert plus fait ÉCHOUER le contrôle.**
 *   3. **Jamais de seuil** : on nomme les règles, elles se comptent.
 *
 * Ce qui n'est PAS ici l'est par décision, écrite dans #2501 : les tables de
 * libellés que l'app GÉNÈRE depuis le front (statuts d'idée, d'annonce, d'accès…,
 * surveillées par sa concordance quotidienne — `standards/09` §8, règle 2), et les
 * formats d'une valeur typée (date ISO, montant en centimes), que chaque client
 * rend avec le formateur de sa plateforme.
 */
export const REGLES_PARTAGEES = {
	//  ── Servies par l'API ────────────────────────────────────────────────────
	libelleLogement: {
		quoi: 'le logement sous le nom (« Bât. A, T3, 2ème »)',
		api: 'api/app/utils/logement.py#libelle_logement',
		//  Servie par `UserRead.libelle_logement` depuis v3.61.0 (#2500).
	},

	//  ── Admin › Utilisateurs (#2618) ─────────────────────────────────────────
	gestesAdminOperateur: {
		quoi: 'les gestes de rôle offerts sur un compte (+ CS, – Admin, + Opérateur…)',
		api: 'api/app/utils/gestes_roles.py#gestes_roles',
		//  Servie par `UtilisateurAdminRead.gestes_roles` depuis #2618.
	},
	compterTitulaires: {
		quoi: 'les titulaires actifs des rôles jamais vacants (Admin, Opérateur)',
		api: 'api/app/utils/gestes_roles.py#titulaires',
		//  Lue par `gestes_roles` : l'écran ne compte plus les titulaires (#2618).
	},

	//  ── Ma résidence et Annuaire (#2505) ─────────────────────────────────────
	libelleExercice: {
		quoi: "l'exercice comptable de la fiche (« de juillet à juin »)",
		api: 'api/app/utils/dates_fr.py#libelle_exercice',
		//  Servie par `CoproprieteRead.exercice_libelle` depuis #2505.
	},
	nomAffiche: {
		quoi: '« Prénom NOM » d’une personne (annuaire, annonces, auteurs)',
		api: 'api/app/utils/noms.py#nom_affiche',
		migration: {
			ticket: '#2633',
			raison:
				"l'annuaire la sert depuis #2505 (`nom_affiche`, lu par `CarteContact`), une affaire son `nom_proprietaire` (#2508) ; restent les annonces, les baux, les points du conseil et les écrans d'administration qui nomment un compte",
		},
	},
	etageLabel: {
		quoi: "l'étage en clair (« RDC », « 2ème étage »)",
		api: 'api/app/utils/etages.py#etage_label',
		//  Servie par l'annuaire (#2505), `LotRead` (`etage_libelle`, `etage_libelle_complet`),
		//  le bail du locataire et le rapprochement d'un nom (#2633).
	},
	telephonesDe: {
		quoi: 'les numéros d’un champ téléphone découpés sur les virgules',
		api: 'api/app/utils/telephones.py#telephones_de',
		//  Servie par l'annuaire (#2505) et `PrestataireRead.telephones` (#2633).
	},
	perimetreLabel: {
		quoi: 'le lieu lisible d’un périmètre (🔹, muet pour celui par défaut)',
		api: 'api/app/utils/perimetres/libelles.py#perimetre_label',
		//  Servie en `perimetre_libelle` (contenus à badge, ligne du fil), `perimetre_precise_libelle`
		//  (une Suite), `perimetres_libelle` (un équipement) et par `POST /perimetres/libelle` (#2633).
	},

	//  ── Communauté, FAQ, Profil, Notifications (#2506) ──────────────────────
	categoriesPourStatut: {
		quoi: 'les catégories de la FAQ montrées selon le statut du lecteur',
		api: 'api/app/utils/faq_categories.py#categorie_lue_par',
		//  Servie par `GET /faq`, qui ne rend que ce que le lecteur lit (#2506).
	},
	normalizeCategorieLabel: {
		quoi: 'le libellé d’une catégorie de FAQ (« 📋 Copropriétaire bailleur »)',
		api: 'api/app/utils/faq_categories.py#libelle_categorie_faq',
		//  Servie par `FaqItemRead.categorie_libelle` (#2506).
	},
	isNouveau: {
		quoi: 'le badge « NEW » d’un élément de moins de 48 h',
		api: 'api/app/utils/nouveaute.py#est_nouveau',
		//  Servie en `nouveau` : idées, annonces, sondages (#2506), affaires (#2508).
	},
	lectureDe: {
		quoi: 'la pastille « qui le lit » d’un contenu',
		api: 'api/app/utils/lecture_pastille/regle.py#lecture_de',
		//  Servie en `lecture` (affaire, ligne du fil, Suivi des affaires, annonces,
		//  idées, sondages) et par `POST /lectures/apercu` pour une saisie (#2633).
	},
	peutEditer: {
		quoi: 'le crayon d’un contenu (auteur, « saisi pour », admin)',
		api: 'api/app/auth/deps.py#peut_editer',
		//  Servie en `peut_modifier` (idées, annonces, #2506 ; affaires, #2508), dans
		//  l'Historique (#2646), et le CRAYON d'une affaire en `peut_corriger` (#2633).
	},
	peutCommenter: {
		quoi: 'le geste « Répondre » d’un contenu',
		api: 'api/app/auth/deps.py#peut_commenter',
		//  Servie en `peut_supprimer` (réponses de la Communauté, #2506) et en
		//  `peut_repondre` / `peut_changer_etat` (affaires, `auth/gestes_affaire`, #2508).
	},

	//  ── Mes lots et accès, prestataires (#2507) ─────────────────────────────
	//  Servies depuis #2507 : `LotRead`, `GET /lots/mes-charges`, `ContratRead`,
	//  `PrestataireRead` les portent, le site les lit.
	lotTypeLabel: {
		quoi: 'le type d’un lot en clair (« Appartement », « Cave »)',
		api: 'api/app/utils/libelles_lot.py#libelle_type_lot',
	},
	lotTypeComplet: {
		quoi: 'le type complet d’un lot (« Appartement – T3 »)',
		api: 'api/app/utils/libelles_lot.py#libelle_type_complet',
	},
	nomDuLot: {
		quoi: 'le nom d’un lot dans le tableau des charges',
		api: 'api/app/utils/libelles_lot.py#nom_du_lot',
	},
	tableauDesCharges: {
		quoi: 'le tableau des charges (pivot par clé, totaux)',
		api: 'api/app/utils/tableau_charges.py#tableau_des_charges',
	},
	frequenceLabel: {
		quoi: 'la fréquence d’un contrat en clair',
		api: 'api/app/utils/frequence_contrat.py#frequence_libelle',
		//  Servie par `ContratRead` (#2507), l'affaire et son contrat (#2633).
	},
	contratUrgence: {
		quoi: 'l’échéance d’un contrat (préavis passé, cette année, plus tard)',
		api: 'api/app/utils/echeance_contrat.py#urgence_echeance',
	},
	contratEnRetard: {
		quoi: 'la visite d’un contrat en retard (le jour même n’en est pas une)',
		api: 'api/app/utils/echeance_contrat.py#visite_en_retard',
	},
	typeEquipementDuContrat: {
		quoi: 'l’équipement effectif d’un contrat (le sien, sinon la spécialité du prestataire)',
		api: 'api/app/utils/carnet_entretien.py#type_equipement_resolu',
	},
	moyenneNotes: {
		quoi: 'la note moyenne d’un prestataire',
		api: 'api/app/utils/notes_prestataires.py#note_moyenne',
	},
	nextVisitForPrest: {
		quoi: 'la prochaine visite d’un prestataire (la plus proche de ses contrats en cours)',
		api: 'api/app/routers/prestataires_lecture.py#lire_prestataires',
	},

	//  ── Reporting › Renouvellements (#2525) ──────────────────────────────────
	//  Servies par `GET /reporting/renouvellements` : le site et l'app iOS lisent le
	//  même relevé (échéances, ordre, compteurs, année de référence).
	diagNextDate: {
		quoi: 'la prochaine échéance d’un diagnostic (dernier rapport + périodicité)',
		api: 'api/app/utils/echeance_diagnostic.py#prochaine_echeance',
	},
	diagUrgence: {
		quoi: 'l’urgence d’un diagnostic (dépassé, cette année, plus tard)',
		api: 'api/app/utils/echeance_diagnostic.py#urgence_diagnostic',
	},
	contratsAvecEcheance: {
		quoi: 'les contrats à renouveler, la pire note d’abord, et ce qui tombe dans l’année',
		api: 'api/app/routers/reporting_renouvellements.py#releve_renouvellements',
	},
	diagnosticsAvecEcheance: {
		quoi: 'les diagnostics applicables rangés par échéance, et les audits à planifier',
		api: 'api/app/routers/reporting_renouvellements.py#releve_renouvellements',
	},
	//  L'année de référence (le jour de Paris) est servie aussi (`releve.annee`) ;
	//  elle ne se déclare pas sous `anneeCourante`, que le pied de page emploie pour
	//  son copyright — un homonyme, pas la règle.

	//  ── Affaires (#2508) ─────────────────────────────────────────────────────
	//  Servies par `TicketRead` (`schemas_affaire_servie`) depuis #2508 : urgence,
	//  colonne du Kanban, nom affiché. Les gestes (`auth/gestes_affaire`) et les tables
	//  (`GET /tickets/referentiels`) le sont aussi ; ce qui reste au front l'est HORS
	//  des affaires, et sa migration est portée par #2511.
	ticketUrgent: {
		quoi: "l'urgence d'une affaire (⚡)",
		api: 'api/app/utils/categories_ticket.py#ticket_urgent',
		//  Servie par `TicketRead.urgente` (#2508).
	},
	colonneDuTicket: {
		quoi: 'la colonne du Kanban d’une affaire selon son statut',
		api: 'api/app/utils/kanban_tickets.py#colonne_du_ticket',
		//  Servie par `TicketRead.colonne_kanban` (#2508).
	},
	nomProprietaire: {
		quoi: 'le nom d’un objet « saisi pour » (le propriétaire, sinon le rédacteur)',
		api: 'api/app/schemas_affaire_servie.py#nom_proprietaire',
		//  Servie par `TicketRead.nom_proprietaire` (#2508).
	},
	isCS: {
		quoi: 'les gestes du modérateur (archiver, déplacer au Kanban, catégories réservées)',
		api: 'api/app/auth/deps.py#est_moderateur',
		migration: {
			ticket: '#2633',
			raison:
				"servis pour les affaires (`peut_archiver`, `peut_deplacer_au_kanban`, `referentiels.categories[].permise`, #2508), la FAQ (`GET /faq/gestes`) et les sondages (`GET /sondages/gestes`, #2654) ; le site garde `$isCS` pour une cinquantaine d'écrans hors affaires",
		},
	},
	categorieTicketLabel: {
		quoi: 'le libellé d’une catégorie d’affaire (carnet, cartes)',
		api: 'api/app/utils/categories_ticket.py#libelle_categorie',
		//  Servie en `categorie_libelle` : l'affaire et le référentiel (#2508), la
		//  ligne du fil, le carnet, son bilan et le relevé du suivi (#2511).
	},
	statutTicketLabel: {
		quoi: 'le libellé d’un statut d’affaire',
		api: 'api/app/utils/etat_affaire.py#libelle_etat',
		//  Servie en `statut_libelle` (l'affaire, la ligne du fil, les affaires liées),
		//  `nouveau_statut_libelle` (une Suite), `etat_cible_libelle` (un CR) — #2633.
	},
	estTicketClos: {
		quoi: 'une affaire close (résolue ou annulée)',
		api: 'api/app/utils/etat_affaire.py#affaire_close',
		//  Servie en `close` : l'affaire (#2508), la ligne du fil et les affaires
		//  liées (#2511) ; l'état CHOISI d'une fusion se lit au référentiel
		//  (`statuts[].clos`, `fusion-affaires.etatQuiClot`).
	},

	//  ── Espace CS (#2522) ────────────────────────────────────────────────────
	//  Comptes, parc des accès, annuaire : ce que l'app iOS porte dans ses trois
	//  premiers onglets. Le front ne définit plus aucune de ces règles.
	annonceValidation: {
		quoi: 'la phrase d’une validation de compte (« 3 lot(s) résolu(s) automatiquement »)',
		api: 'api/app/utils/annonce_compte.py#annonce_validation',
		//  Servie par `CompteTraiteResult.annonce` (#2522).
	},
	annonceLocataire: {
		quoi: 'ce que l’appariement a fait d’un locataire (validation et relance)',
		api: 'api/app/utils/annonce_compte.py#annonce_relance',
		//  Servie par `annonce` à la validation et par `AutoMatchRelance.annonce`.
	},
	inscritParNom: {
		quoi: 'l’inscrit que désigne le nom saisi dans une fiche de l’annuaire',
		api: 'api/app/utils/annuaire.py#rapprochement',
		//  Servie par `GET /admin/annuaire/rapprochement`, appliquée par le `PUT`.
	},
	localisationParNom: {
		quoi: 'le logement d’un membre du conseil d’après le registre importé',
		api: 'api/app/utils/annuaire.py#rapprochement',
	},
};
