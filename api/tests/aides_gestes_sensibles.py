"""Les gestes sensibles : chaque fonction de `app/` qui écrit au journal de sécurité.

## Pourquoi une table ici (#2941, audit du 23/11/2026)

`GESTES_SENSIBLES` vivait dans `test_journal_securite.py`, tenue à la main : 24
entrées quand 41 fonctions de `app/` appelaient `journaliser_securite`. Retirer
l'appel de `routers/montres.py` ou de `routers/ecrans.py` laissait le test vert.
La table est désormais confrontée, dans les deux sens, à ce que le code ÉMET
(`test_journal_securite.test_les_emettrices_sont_exactement_les_gestes_declares`) :
toute émettrice y figure avec sa raison, toute entrée émet.

Sortie du fichier de tests pour qu'il reste sous 500 lignes (`standards/02` §6).
Un module d'aide, pas un `test_*.py` : `test_aides_de_tests_source_unique.py`
refuse l'import depuis un autre fichier de tests.

Chaque raison dit ce que la ligne permet de savoir APRÈS COUP.
"""

#: (fichier relatif à `app/`, fonction) → ce que la ligne permet de savoir après coup.
GESTES_SENSIBLES = {
    ("utils/courriel_delegation.py", "apres_ecriture"): "un signataire admis pour le domaine "
    "d'un autre (#2554) — un tiers de plus à qui l'on confie l'authenticité des réponses",
    ("utils/acces_gestes.py", "journaliser_acces"): "ce qu'un badge ouvre, posé ou "
    "changé par le conseil — une porte physique (#2217) ; la dérivation ne fait que proposer",
    ("routers/auth.py", "login"): "une connexion refusée — sans elle, une attaque "
    "par force brute est freinée par le rate limit mais jamais signalée",
    ("routers/auth_mot_de_passe.py", "change_password"): "un mot de passe changé par son porteur",
    ("routers/auth_mot_de_passe.py", "reset_password"): "un mot de passe réinitialisé "
    "par jeton — le chemin qu'emprunterait quelqu'un qui a pris la boîte mail",
    ("routers/admin/utilisateurs.py", "ajouter_role"): "une élévation de rôle : c'est "
    "le geste qui donne des droits, et rien ne nommait l'admin qui l'a fait",
    ("routers/admin/utilisateurs.py", "retirer_role"): "un retrait de rôle",
    ("utils/roles_du_statut.py", "changer_statut"): "les rôles qu'un changement de statut "
    "ajoute ou retire — la fiche de l'administrateur et la demande approuvée (claude-config#603)",
    ("routers/admin/utilisateurs.py", "ban_communaute"): "un bannissement",
    ("routers/auth.py", "refresh"): "un jeton de rafraîchissement rejoué — le seul "
    "signal d'un vol de session, et toutes les sessions du compte viennent de fermer",
    ("auth/appartenance.py", "exiger_lot_du_bailleur"): "un bail demandé sur le lot "
    "d'un autre — l'écran ne le propose pas, la requête a été forgée (#1535)",
    #  Le cycle de vie d'un compte (#1548, audit du 02/10/2026) : #1040 avait posé
    #  la porte, la liste s'arrêtait aux mots de passe et aux rôles.
    ("auth/appartenance.py", "exiger_lots_proposes_au_locataire"): "un locataire qui "
    "se dit locataire d'un lot qu'on ne lui proposait pas — requête forgée",
    ("utils/rattachement_locataire.py", "rattacher_lots_declares"): "un locataire "
    "rattaché sur sa seule déclaration : il reçoit les badges du lot",
    ("routers/admin/comptes.py", "traiter_compte"): "un compte validé ou refusé — "
    "le geste qui OUVRE l'accès, fait par le conseil syndical",
    ("routers/admin/utilisateurs.py", "modifier_utilisateur"): "un compte désactivé ou "
    "réactivé par l'administration",
    ("routers/admin/utilisateurs.py", "supprimer_utilisateur"): "un compte effacé "
    "définitivement — après lui, il ne reste QUE cette ligne pour dire qui l'a fait",
    ("routers/delegations.py", "create_delegation"): "une délégation créée : un "
    "tiers va lire au nom d'un résident",
    ("routers/delegations.py", "accepter_delegation"): "une délégation acceptée — "
    "c'est à cet instant que la lecture au nom d'autrui commence",
    ("routers/delegations.py", "revoquer_delegation"): "une délégation révoquée",
    ("utils/verification_adresse.py", "demander_changement_adresse"): "un changement "
    "d'adresse demandé, par le titulaire ou l'administrateur — le premier geste d'un "
    "détournement de compte, que rien ne traçait (#1549)",
    ("utils/verification_adresse.py", "_confirmer_changement"): "une nouvelle adresse "
    "confirmée : c'est désormais elle qui reçoit le mot de passe oublié (#1549)",
    #  La purge des comptes inactifs (#1580) : personne n'agit, le planificateur
    #  efface. Après lui, il ne reste QUE cette ligne pour dire qu'un compte a
    #  existé et pourquoi il n'est plus là.
    ("utils/purge_comptes/tache.py", "_supprimer"): "un compte effacé par la purge "
    "des comptes inactifs, sans acteur humain",
    ("utils/purge_comptes/tache.py", "_avertir"): "l'avertissement qui ouvre le délai "
    "de trente jours avant l'effacement",
    ("utils/purge_comptes/tache.py", "_signaler"): "un compte d'administration inactif "
    "épargné par la purge, et signalé — dormant, il reste une porte ouverte (#1580)",
    ("utils/purge_comptes/tache.py", "_supprimer_ferme"): "un compte fermé effacé à "
    "l'échéance de sa fermeture (#1822), sans acteur humain — il n'en reste que cette ligne",
    ("utils/fusion_conciliation.py", "appliquer"): "une fusion conciliée : la principale "
    "change de lecteurs et des personnes liront ce qu'elles ne lisaient pas",
    #  Les émettrices que la liste tenue à la main avait laissées dehors — relevées
    #  par l'audit du 23/11/2026 (#2941), quand la liste s'est dérivée du code.
    ("auth/cle_maintenance.py", "exiger_cle_maintenance"): "la fausse clé de maintenance "
    "présentée (#2365) — qui la présente l'a prise dans le faux `.env.bak` ; S6 en fait un FAIL",
    ("routers/ecrans.py", "confirmer_appairage"): "un écran de hall appairé (#2770) : un "
    "appareil sans personne derrière lui lira les affiches, et la ligne nomme qui l'a admis",
    ("routers/ecrans.py", "interroger_appairage"): "l'écran qui retire son jeton — "
    "l'instant où l'appareil commence à lire, sans acteur humain (#2770)",
    ("routers/ecrans.py", "retirer_ecran"): "un écran retiré : son jeton cesse de servir, "
    "et la ligne dit qui l'a coupé et quand",
    ("routers/montres.py", "emettre_montre"): "une montre reliée au compte (#2771) : un "
    "jeton de plus qui lit la cloche hors du téléphone, sans biométrie",
    ("routers/montres.py", "retirer_montre"): "une montre retirée par son porteur — la "
    "fin de la fenêtre qu'ouvrait la ligne `montre_reliee`",
    ("utils/demande_suppression.py", "deposer_demande"): "la suppression de son compte "
    "demandée (#2699), ou refusée sur un mot de passe faux — sur un compte volé, le premier "
    "geste pour effacer ses traces",
    ("utils/demande_suppression.py", "retirer"): "une demande de suppression retirée par la "
    "personne : le délai de traitement ne court plus",
    ("utils/demande_suppression.py", "traiter"): "la demande traitée et le compte effacé "
    "par l'administration — après lui, il ne reste QUE cette ligne pour dire qui l'a fait",
    ("utils/points_conseil_validation.py", "valider_par_present"): "un compte rendu de "
    "point CS / Syndic validé par le lien d'un présent, sans compte — le jeton seul l'identifie",
    ("utils/points_conseil_validation.py", "valider_point"): "un compte rendu qui fait foi "
    "par la main du conseil : il change l'état des affaires abordées (#2082)",
    ("utils/points_conseil_validation.py", "valider_pour"): "l'administrateur qui valide AU "
    "NOM d'un présent (#2082) — un geste pour autrui, qui doit se relire",
    ("utils/points_conseil_validation.py", "auto_valider"): "un compte rendu validé d'office "
    "au bout de sept jours (#2042), sans acteur — ses textes deviennent lisibles à l'affaire",
    ("utils/rattachement_bailleur.py", "rattacher_au_bailleur"): "un locataire rattaché "
    "d'office au bail ou au logement de son bailleur, par le seul nom (#1136) : il en "
    "reçoit les badges",
    ("utils/rattachement_locataire.py", "remettre_badges_manquants"): "les badges d'un lot "
    "remis à un locataire par le rattrapage de l'appariement (#2267) — une porte physique "
    "qui change de main",
    ("routers/admin/export_copropriete.py", "lancer_export"): "l'export complet de la "
    "copropriété (#1749) — comptes, adresses et fichiers dans une archive ; la ligne dit "
    "quel administrateur l'a fait écrire (#2941)",
}
