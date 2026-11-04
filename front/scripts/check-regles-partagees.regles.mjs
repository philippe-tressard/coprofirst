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
		quoi: "l'exercice comptable de la fiche (« de juillet à juin »)",
		api: 'api/app/utils/dates_fr.py#libelle_exercice',
		//  Servie par `CoproprieteRead.exercice_libelle` depuis #2505.
	},
	nomAffiche: {
		quoi: '« Prénom NOM » d’une personne (annuaire, annonces, auteurs)',
		api: 'api/app/utils/noms.py#nom_affiche',
		migration: {
			ticket: '#2506',
			raison:
				"l'annuaire la sert depuis #2505 (`nom_affiche`, lu par `CarteContact`) ; restent les annonces et les auteurs (`auteur_affiche`), et les écrans d'administration qui nomment un compte",
		},
	},
	etageLabel: {
		quoi: "l'étage en clair (« RDC », « 2ème étage »)",
		api: 'api/app/utils/etages.py#etage_label',
		migration: {
			ticket: '#2507',
			raison:
				"l'annuaire la sert depuis #2505 (`etage_libelle`, avec `suffixe`) ; restent les lots, le profil et l'import (`etage_libelle` dans `LotRead`)",
		},
	},
	telephonesDe: {
		quoi: 'les numéros d’un champ téléphone découpés sur les virgules',
		api: 'api/app/utils/telephones.py#telephones_de',
		migration: {
			ticket: '#2507',
			raison:
				"l'annuaire la sert depuis #2505 (`telephones`) ; reste la carte d'un prestataire (`OngletPrestataires`) : `telephones` à servir dans `PrestataireRead`",
		},
	},
	perimetreLabel: {
		quoi: 'le lieu lisible d’un périmètre (🔹, muet pour celui par défaut)',
		api: 'api/app/utils/perimetres/libelles.py#perimetre_label',
		migration: {
			ticket: '#2506',
			raison:
				"CR d'AG et carnet le servent depuis #2505 (`perimetre_libelle`, lu par `BadgePerimetre libelle=`, `perimetres.perimetre_badge`) ; restent le fil, les cartes d'affaire (#2508) et les sélecteurs de périmètre",
		},
	},

	//  ── Communauté, FAQ, Profil, Notifications (#2506) ──────────────────────
	isNouveau: {
		quoi: 'le badge « NEW » d’un élément de moins de 48 h',
		migration: {
			ticket: '#2506',
			raison: "aucun pendant au serveur ; l'app ne le montre pas : `nouveau: bool` à servir",
		},
	},
	categoriesPourStatut: {
		quoi: 'les catégories de la FAQ montrées selon le statut du lecteur',
		migration: {
			ticket: '#2506',
			raison: "l'app montre toutes les catégories : filtrer dans `GET /faq`",
		},
	},
	normalizeCategorieLabel: {
		quoi: 'le libellé d’une catégorie de FAQ (« 📋 Copropriétaire bailleur »)',
		migration: { ticket: '#2506', raison: 'servir le libellé avec la catégorie' },
	},
	lectureDe: {
		quoi: 'la pastille « qui le lit » d’un contenu',
		migration: {
			ticket: '#2506',
			raison:
				"le serveur n'en a que le mot court des PDF (`lecture_affaire.lecture_courte`) ; l'app ne montre rien : `lecture_libelle` à servir",
		},
	},
	peutEditer: {
		quoi: 'le crayon d’un contenu (auteur, « saisi pour », admin)',
		api: 'api/app/auth/deps.py#peut_editer',
		migration: {
			ticket: '#2506',
			raison:
				"le prédicat du serveur décide, le front le recopie pour offrir le geste ; l'app le recompose depuis les rôles : `peut_modifier` à servir avec chaque élément",
		},
	},
	peutCommenter: {
		quoi: 'le geste « Répondre » d’un contenu',
		api: 'api/app/auth/deps.py#peut_commenter',
		migration: {
			ticket: '#2506',
			raison: 'même cas que `peutEditer` ; `peut_commenter` à servir (affaires : #2508)',
		},
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
	isCS: {
		quoi: 'les gestes du modérateur (archiver, déplacer au Kanban, catégories réservées)',
		api: 'api/app/auth/deps.py#est_moderateur',
		migration: {
			ticket: '#2508',
			raison:
				"l'app recompose « conseil ou admin » depuis `/auth/me` : `peut_archiver`, `peut_changer_etat` à servir avec l'affaire",
		},
	},
	ticketUrgent: {
		quoi: "l'urgence d'une affaire (⚡)",
		api: 'api/app/utils/categories_ticket.py#ticket_urgent',
		migration: {
			ticket: '#2508',
			raison:
				'le serveur la calcule pour la suite groupée, le front la recopie pour la carte : `urgente` à servir dans `TicketRead`',
		},
	},
	colonneDuTicket: {
		quoi: 'la colonne du Kanban d’une affaire selon son statut',
		api: 'api/app/utils/kanban_tickets.py#colonne_du_ticket',
		migration: {
			ticket: '#2508',
			raison: "l'app la génère depuis `kanban.ts` : servir la colonne, ou la table avec le contrat",
		},
	},
	categorieTicketLabel: {
		quoi: 'le libellé d’une catégorie d’affaire (carnet, cartes)',
		api: 'api/app/utils/categories_ticket.py#libelle_categorie',
		migration: {
			ticket: '#2508',
			raison:
				"l'app la génère depuis `tickets-categories.ts` : `categorie_libelle` à servir (carnet : #2505)",
		},
	},
	nomProprietaire: {
		quoi: 'le nom d’un objet « saisi pour » (le propriétaire, sinon le rédacteur)',
		migration: {
			ticket: '#2508',
			raison:
				"l'app choisit elle-même entre `proprietaire_nom` et `auteur_nom` : un seul champ affiché à servir",
		},
	},
	statutTicketLabel: {
		quoi: 'le libellé d’un statut d’affaire',
		migration: {
			ticket: '#2508',
			raison: "aucun pendant au serveur ; l'app le génère depuis `tickets.ts`",
		},
	},
	estTicketClos: {
		quoi: 'une affaire close (résolue ou annulée)',
		migration: {
			ticket: '#2508',
			raison:
				"la liste des statuts clos vit au serveur (`STATUTS_TICKET_CLOS`), le prédicat dans le front : l'app le génère",
		},
	},
};
