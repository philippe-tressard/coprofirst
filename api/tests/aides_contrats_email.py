"""Les deux CONTRATS que les modeles d'e-mail doivent tenir.

Des tables de reference, pas des tests : `test_email_templates.py` les eprouve,
`test_email_objets.py` pourrait en faire autant demain. Les sortir du fichier de
tests est ce qu'impose la regle de modularite (rang 1) — « on decoupe le fichier
QUAND on y touche » — et la separation est celle qui allait de soi : d'un cote ce
qui est attendu, de l'autre ce qui le verifie.

⚠️ Une table modifiee sans que le `send_email(code=...)` correspondant fournisse
les memes variables produit un echec **silencieux a l'envoi** : le gabarit rend
une chaine vide, personne ne voit rien. C'est pour cela que ces contrats
existent, et pourquoi ils se mettent a jour consciemment.
"""

# Contrat figé : variables de premier niveau requises par chaque template.
# Extrait de seed.EMAIL_TEMPLATES — à mettre à jour consciemment lors de toute
# modification d'un template (en alignant le point d'appel send_email).
EXPECTED_VARS: dict[str, set[str]] = {
    "reinitialisation_mdp": {"destinataire", "lien"},
    "compte_en_attente": {"utilisateur"},
    "compte_active": {"destinataire"},
    "compte_refuse": {"destinataire"},
    "ticket_bug_admin": {"auteur", "ticket"},
    #  #1643 : `envoyer_avis` fournit les trois.
    "synthese_a_valider": {"ticket", "issue", "synthese"},
    #  #2042 : `envoyer_pour_validation` fournit les cinq.
    "point_conseil_validation": {"point", "affaires", "non_traitees", "echeance", "jeton"},
    "point_conseil_valide": {"point"},
    #  `commentaire_perimetre` ajouté le 31/08/2026 : le courriel du syndic ne
    #  disait PAS le périmètre — *« cette information est capitale pour le syndic
    #  ou le CS pour identifier le périmètre du problème »*. Le ticket porte le
    #  sien dans `ticket.perimetre`, chaque entrée de l'historique dans
    #  `m.perimetre`, et celle en cours ici.
    "ticket_syndic": {
        "messages",
        "date_creation",
        "commentaire",
        "is_commentaire",
        "ticket",
        "fichiers",
        "date_commentaire",
        "historique",
        "auteur",
        "commentaire_perimetre",
        #  Les affaires liées, sous l'historique (05/10/2026, migration 0266).
        "affaires_liees",
    },
    #  `urgent` conditionne un liseré rouge et la mention URGENT : c'est le
    #  ticket qui le porte, pas le destinataire.
    "ticket_nouveau_cs": {"ticket", "auteur", "urgent"},
    "ticket_statut_change": {"destinataire", "ticket"},
    "ticket_nouveau_message": {"ticket", "auteur_action", "message"},
    "ticket_partage": {"ticket", "auteur_action"},
    "lien_partage": {"objet", "auteur_action"},
    "reponse_communaute": {"reponse"},
    "idee_statut": {"idee"},
    "relance_syndic": {
        "tickets",
        "interlocuteurs",
        "anciennete",
    },
    "vigik_commande_recue": {"lot", "demandeur", "type"},
    "vigik_accepte": {"destinataire", "type"},
    "vigik_refuse": {"type", "destinataire", "motif"},
    "calendrier_evenement_cree": {"evenement"},
    #  Le suivi porte EN PLUS `suivi` : l'état atteint et le commentaire. Sans
    #  cette ligne, un template pourrait citer une variable que l'appel ne
    #  fournit pas — c'est la panne `'evenement' is undefined` du 28/07/2026.
    #  `fichiers` s'y ajoute le 18/08/2026 : le modele annonce desormais les pieces
    #  jointes de l'entree, comme le font ceux des tickets. Le garde-fou a REFUSE
    #  le template avant cette ligne — c'est son travail, et c'est ce qui garantit
    #  qu'aucune variable citee n'est absente du contexte de l'appel.
    "calendrier_evenement_suivi": {"evenement", "suivi", "fichiers"},
    "document_publie": {"document"},
    "publication_syndic": {
        "date_publication",
        "evolutions",
        "commentaire",
        "is_commentaire",
        "fichiers",
        "publication",
        "date_commentaire",
        "auteur",
    },
    # Remplace `sauvegarde_echec` et `alerte_espace_disque` : le contrôle
    # quotidien découvre les problèmes ensemble et n'envoie qu'un message.
    "alerte_systeme": {"problemes", "nb_problemes", "date_controle"},
    "verification_email": {"expire_heures", "lien", "prenom"},
    #  L'avis à l'ancienne adresse d'un compte dont l'adresse va changer (#1549).
    "adresse_changement_avis": {"destinataire", "nouvelle_adresse", "par_un_administrateur"},
    #  L'avertissement avant la purge d'un compte inactif (#1580) : la date de la
    #  suppression et celle de la dernière activité, rendues en toutes lettres.
    "compte_inactif_avertissement": {"destinataire", "date_suppression", "derniere_activite"},
    "annonce_hall": {"annonce", "auteur"},
    # Prévient le gestionnaire du site quand l'appariement a créé des accès
    # sans validation préalable. `resultat` porte aussi les accords en français,
    # calculés au point d'appel : un modèle n'a pas à porter la grammaire.
    "acces_apparies_auto": {"utilisateur", "resultat"},
    "etage_divergent": {"utilisateur", "etage"},
    # Les trois modèles destinés à des destinataires EXTERNES (syndic, tiers),
    # longtemps déclarés en migration seulement et donc sans contrat ici.
    #  Enrichi le 08/09/2026 : le MÊME modèle sert le syndic, l'arrivant et le
    #  conseil de son bâtiment. `role_destinataire` choisit l'objet, la formule
    #  d'appel et la demande ; `lien_consignes` arrive RELATIF, préfixé de
    #  `{{ app.url }}` par le corps — sa source est `arrivants.FICHE_CONSIGNES`.
    #  Un second modèle aurait été la copie de celui-ci : « standardiser et non
    #  dupliquer » (consigne du 08/09/2026).
    "nouvel_arrivant_bal": {
        "nom_complet",
        "batiment",
        "ancien_resident",
        "role_destinataire",
        "lien_consignes",
        "destinataire",
    },
    "publication_externe": {
        "date_publication",
        "evolutions",
        "commentaire",
        "is_commentaire",
        "fichiers",
        "publication",
        "date_commentaire",
        "auteur",
    },
    "ticket_externe": {
        "messages",
        "date_creation",
        "commentaire",
        "is_commentaire",
        "ticket",
        "fichiers",
        "date_commentaire",
        "auteur",
    },
}

#  Les copies de l'auteur (cochées SEULES, 03/10/2026) partagent le corps — donc les
#  variables — du gabarit au syndic : seuls l'objet et les phrases changent.
EXPECTED_VARS["ticket_copie_auteur"] = EXPECTED_VARS["ticket_syndic"]
EXPECTED_VARS["publication_copie_auteur"] = EXPECTED_VARS["publication_syndic"]

# Modèles dont l'objet doit NOMMER ce dont il parle, et l'expression qui le fait.
#
# « Ticket #TK-427648 — 5Hostachy » n'apprenait rien : deux tickets de la même
# copropriété avaient des objets interchangeables, et il fallait ouvrir pour
# savoir de quoi il s'agissait (11/08/2026). Le titre a été ajouté aux cinq
# modèles qui en manquaient ; les cinq autres l'avaient déjà.
#
# Ce contrat est ici parce que rien d'autre ne le porte : les modèles vivent en
# base, `EXPECTED_VARS` ne regarde que le premier niveau (`ticket` suffit à le
# satisfaire, que le titre soit dans l'objet ou seulement dans le corps), et une
# migration qui réécrit un objet le ferait disparaître sans un test rouge.
SUJETS_QUI_NOMMENT_L_OBJET: dict[str, str] = {
    "ticket_syndic": "{{ ticket.titre }}",
    "ticket_copie_auteur": "{{ ticket.titre }}",
    "ticket_statut_change": "{{ ticket.titre }}",
    "ticket_nouveau_message": "{{ ticket.titre }}",
    "ticket_partage": "{{ ticket.titre }}",
    "ticket_bug_admin": "{{ ticket.titre }}",
    "ticket_externe": "{{ ticket.titre }}",
    "publication_syndic": "{{ publication.titre }}",
    "publication_copie_auteur": "{{ publication.titre }}",
    "publication_externe": "{{ publication.titre }}",
    "calendrier_evenement_cree": "{{ evenement.titre }}",
    "idee_statut": "{{ idee.titre }}",
    "annonce_hall": "{{ annonce.titre }}",
}
