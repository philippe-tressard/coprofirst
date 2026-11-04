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

	//  ── Ma résidence et Annuaire (#2505) ─────────────────────────────────────
	libelleExercice: {
		quoi: "l'exercice comptable de la fiche (« 1er juillet → 30 juin »)",
		migration: {
			ticket: '#2505',
			raison: "la Fiche de l'app n'en montre rien : `exercice_libelle` à servir",
		},
	},
	nomAffiche: {
		quoi: '« Prénom NOM » d’une personne (annuaire, annonces, auteurs)',
		api: 'api/app/utils/noms.py#nom_affiche',
		migration: {
			ticket: '#2505',
			raison:
				"le serveur la calcule pour ses courriels et ses PDF sans la servir ; l'app montre les champs bruts (`nom_affiche`, `auteur_affiche` à servir — #2506 aussi)",
		},
	},
	etageLabel: {
		quoi: "l'étage en clair (« RDC », « 2e étage »)",
		api: 'api/app/utils/etages.py#etage_label',
		migration: {
			ticket: '#2505',
			raison:
				"calculée au serveur pour l'annonce d'arrivée, non servie : annuaire (#2505) et lots (#2507) l'attendent en `etage_libelle`",
		},
	},
	telephonesDe: {
		quoi: 'les numéros d’un champ téléphone découpés sur les virgules',
		migration: {
			ticket: '#2505',
			raison: "l'app recoupe la donnée elle-même : `telephones: [string]` à servir",
		},
	},
	perimetreLabel: {
		quoi: 'le lieu lisible d’un périmètre (🔹, muet pour celui par défaut)',
		api: 'api/app/utils/perimetres/libelles.py#perimetre_label',
		migration: {
			ticket: '#2505',
			raison:
				"le serveur la calcule (recherche, parc, affiches) sans la servir aux listes ; CR d'AG, fil et cartes d'affaire de l'app ne montrent pas le lieu (#2506, #2508 aussi)",
		},
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
		migration: {
			ticket: '#2511',
			raison:
				"tenue contre le serveur par `test_lecture_pastille.py`, sans être servie ; l'aperçu du formulaire d'affaire (`SectionDestinataires`) la calcule sur une saisie non enregistrée : `lecture_libelle` à servir aux listes",
		},
	},
	peutEditer: {
		quoi: 'le crayon d’un contenu (auteur, « saisi pour », admin)',
		api: 'api/app/auth/deps.py#peut_editer',
		migration: {
			ticket: '#2511',
			raison:
				"servie en `peut_modifier` sur les idées, les annonces (#2506) et les affaires (#2508)  ; la carte d'affaire et l'Historique la recopient encore : leur crayon ouvre une correction plus large que le contenu (liées, diffusion, suivi), un geste à servir",
		},
	},
	peutCommenter: {
		quoi: 'le geste « Répondre » d’un contenu',
		api: 'api/app/auth/deps.py#peut_commenter',
		//  Servie en `peut_supprimer` (réponses de la Communauté, #2506) et en
		//  `peut_repondre` / `peut_changer_etat` (affaires, `auth/gestes_affaire`, #2508).
	},

	//  ── Mes lots et accès, prestataires (#2507) ─────────────────────────────
	lotTypeLabel: {
		quoi: 'le type d’un lot en clair (« Appartement », « Cave »)',
		migration: {
			ticket: '#2507',
			raison:
				'`type_de_lot` du serveur rend le code, pas le libellé : `libelle_type` à servir dans `LotRead`',
		},
	},
	lotTypeComplet: {
		quoi: 'le type complet d’un lot (« Appartement T3 »)',
		migration: { ticket: '#2507', raison: 'même champ `libelle_type`' },
	},
	nomDuLot: {
		quoi: 'le nom d’un lot dans le tableau des charges',
		migration: { ticket: '#2507', raison: 'servi avec le tableau des charges' },
	},
	tableauDesCharges: {
		quoi: 'le tableau des charges (pivot par clé, totaux, pourcentages)',
		migration: {
			ticket: '#2507',
			raison: "l'app renvoie au site : `GET /lots/mes-charges` prêt à afficher",
		},
	},
	frequenceLabel: {
		quoi: 'la fréquence d’un contrat en clair',
		migration: { ticket: '#2507', raison: '`frequence_libelle` à servir dans `ContratRead`' },
	},
	contratUrgence: {
		quoi: 'l’échéance d’un contrat (préavis passé, cette année, plus tard)',
		migration: { ticket: '#2507', raison: '`en_retard` à servir dans `ContratRead`' },
	},
	typeEquipementDuContrat: {
		quoi: 'l’équipement effectif d’un contrat (le sien, sinon la spécialité du prestataire)',
		migration: {
			ticket: '#2507',
			raison: "l'app en garde une copie provisoire (`Fonctions/Prestataires/Provisoire/`)",
		},
	},
	moyenneNotes: {
		quoi: 'la note moyenne d’un prestataire',
		migration: { ticket: '#2507', raison: '`note_moyenne` à servir dans `PrestataireRead`' },
	},

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
			ticket: '#2511',
			raison:
				"servis pour les affaires (`peut_archiver`, `peut_deplacer_au_kanban`, `referentiels.categories[].permise`, #2508) ; le site garde `$isCS` pour une cinquantaine d'écrans hors affaires",
		},
	},
	categorieTicketLabel: {
		quoi: 'le libellé d’une catégorie d’affaire (carnet, cartes)',
		api: 'api/app/utils/categories_ticket.py#libelle_categorie',
		migration: {
			ticket: '#2511',
			raison:
				"servi avec l'affaire (`categorie_libelle`) et le référentiel (#2508) ; le front l'applique encore au carnet, au reporting et au pied de carte, que l'API ne sert pas avec ce champ",
		},
	},
	statutTicketLabel: {
		quoi: 'le libellé d’un statut d’affaire',
		migration: {
			ticket: '#2511',
			raison:
				"servi avec l'affaire (`statut_libelle`) et le référentiel (#2508) ; le front l'applique encore aux états du fil et des CR, servis en codes",
		},
	},
	estTicketClos: {
		quoi: 'une affaire close (résolue ou annulée)',
		migration: {
			ticket: '#2511',
			raison:
				"servie avec l'affaire (`close`) et le référentiel (`statuts[].clos`, #2508) ; le front l'applique encore au fil, aux affaires liées et à l'état choisi d'une fusion",
		},
	},
};
