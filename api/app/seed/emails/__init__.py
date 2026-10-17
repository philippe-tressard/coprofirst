"""Modèles d'e-mail : assemblage des quatre familles et intention de chacun.

`EMAIL_TEMPLATES` reste la surface publique historique — quatre migrations
figées l'importent depuis `app.seed`, ainsi que l'administration et les tests.
L'ordre de la liste n'a aucune portée : chaque modèle est inséré indépendamment,
et le seed ne pose que ce qui manque.

## `{{ prefixe_copro }}` — la référence de copropriété dans l'objet

Tout message adressé au syndic porte sa référence de copropriété, **sans
exception** : c'est l'identifiant sous lequel il classe ses dossiers, et un
message qui ne la porte pas sort de son tri par affaire.

L'objet ne la compose donc jamais lui-même. Il écrit `{{ prefixe_copro }}` en
tête, et `email._prefixe_copro` rend « 🏢 00213 — » ou rien. Deux raisons, dont la
seconde n'est visible que d'ici :

1. Le préambule était recopié dans **sept** objets, et deux formes coexistaient
   déjà — « 🏢 00213 — » d'un côté, « [🏢 00213] – » pour `relance_syndic`. Deux
   copies d'une même notion divergent ; celles-ci l'avaient fait.
2. Un modèle vit **en base** et se réécrit depuis Admin → Emails. Le
   `{% if reference_copro %}` qui portait la règle pouvait être retiré d'un
   formulaire, et la règle avec lui. Dans le code, il ne peut pas l'être.

La variable est injectée après le contexte de l'appelant (`email._contexte_rendu`) :
aucun point d'appel ne peut l'omettre ni la contredire. Et comme un préfixe vide
ne se voit pas, `health_monitor._check_reference_copro` alerte le gestionnaire du
site quand la clé n'est pas renseignée — sans quoi la règle serait vérifiée sur
les modèles et fausse à chaque envoi.

Les **corps** HTML, eux, écrivent librement « — réf. {{ reference_copro }} » :
c'est une phrase, pas le préambule d'un objet.
"""

from app.seed.emails.comptes import MODELES as _COMPTES
from app.seed.emails.exploitation import MODELES as _EXPLOITATION
from app.seed.emails.tickets import MODELES as _TICKETS
from app.seed.emails.vie_collective import MODELES as _VIE_COLLECTIVE

# ── Styles inline mutualisés (CTA = Call-to-action button) ──
# Les templates sont encapsulés dans le gabarit email.py (_wrap_email)
# => pas besoin de <html>/<body>, juste le contenu riche.
EMAIL_TEMPLATES = [
    *_COMPTES,
    *_TICKETS,
    *_VIE_COLLECTIVE,
    *_EXPLOITATION,
]

#: 🔴 Les modèles qu'aucune case ne coupe (#2054) — le cinquième élément de chaque
#: tuple, `desactivable`, posé depuis toujours et lu par personne jusqu'au
#: 17/10/2026. La case « Actif » d'Admin › Modèles e-mail coupait donc aussi le
#: mot de passe oublié : plus personne ne récupérait son compte, sans un mot.
#:
#: Lue dans le CODE et non dans la colonne `modele_email.desactivable` : un modèle
#: vit en base, et une ligne insérée par une ancienne migration peut dire autre
#: chose. Les courriels de sécurité (`services.COURRIELS_DE_SECURITE`) en font
#: partie — `test_modeles_non_desactivables` le vérifie.
NON_DESACTIVABLES: frozenset[str] = frozenset(
    code for code, _libelle, _sujet, _corps, desactivable in EMAIL_TEMPLATES if not desactivable
)


def est_desactivable(code: str) -> bool:
    """PURE. La case « Actif » de ce modèle a-t-elle un effet ?"""
    return code not in NON_DESACTIVABLES


# Intention de chaque modèle : ce qui est attendu du destinataire, affiché en
# tête du message par le gabarit commun (cf. `email.INTENTIONS`).
#
# Table séparée, et non sixième élément des tuples ci-dessous : les migrations
# 0104 et 0108 déballent `EMAIL_TEMPLATES` en cinq valeurs. Leur ajouter un
# élément les ferait lever `ValueError` sur une base neuve — et `start.sh` a
# `set -e`, donc le conteneur resterait bloqué au démarrage. Une migration est
# figée : c'est le code d'aujourd'hui qui doit rester compatible avec elle.
INTENTIONS_PAR_MODELE: dict[str, str] = {
    # On attend un geste du destinataire.
    "reinitialisation_mdp": "action_requise",
    "verification_email": "action_requise",
    "compte_en_attente": "action_requise",
    "ticket_bug_admin": "action_requise",
    "synthese_a_valider": "action_requise",
    #  Valider le CR d'un point CS / Syndic, ou le commenter (#2042).
    "point_conseil_validation": "action_requise",
    #  Le conseil doit TRAITER le ticket, pas répondre au courriel : il a un
    #  compte, et le fil vit sur le site. C'est ce qui le distingue de
    #  `ticket_syndic` (« réponse attendue »), adressé à quelqu'un qui n'en a
    #  pas forcément — et l'intention commande l'adresse d'expédition.
    "ticket_nouveau_cs": "action_requise",
    "vigik_commande_recue": "action_requise",
    "annonce_hall": "action_requise",
    "nouvel_arrivant_bal": "action_requise",
    "alerte_systeme": "action_requise",
    #  Se connecter pour garder son compte (#1580) : un geste demandé — et qui ne
    #  peut plus se connecter doit pouvoir répondre, d'où `contact@`.
    "compte_inactif_avertissement": "action_requise",
    # On attend une réponse écrite — ce sont les envois vers l'extérieur, ceux
    # dont le silence est justement le problème qu'on cherche à traiter.
    "ticket_syndic": "reponse_attendue",
    "ticket_externe": "reponse_attendue",
    "relance_syndic": "reponse_attendue",
    # On informe, sans rien attendre en retour.
    "compte_active": "information",
    "compte_refuse": "information",
    #  Rien n'est demandé à qui a fait la demande ; qui ne l'a pas faite trouve
    #  dans le corps ce qu'il doit faire.
    "adresse_changement_avis": "information",
    "ticket_statut_change": "information",
    "ticket_nouveau_message": "information",
    "ticket_partage": "information",
    "lien_partage": "information",
    "reponse_communaute": "information",
    "idee_statut": "information",
    "vigik_accepte": "information",
    "vigik_refuse": "information",
    "calendrier_evenement_cree": "information",
    "calendrier_evenement_suivi": "information",
    "document_publie": "information",
    "publication_syndic": "information",
    "ticket_copie_auteur": "information",
    "publication_copie_auteur": "information",
    "publication_externe": "information",
    "acces_apparies_auto": "information",
    "etage_divergent": "information",
}


# ── Qui EXPÉDIE, et pourquoi ce n'est pas toujours « noreply » ────────────────
#
# Consigne de l'utilisateur (05/09/2026) : *« utiliser contact@5hostachy.fr ;
# réserver noreply@5hostachy.fr dans les cas où il n'y a pas de réponse à
# obtenir »*.
#
# Tout partait de `noreply@`, y compris ce qui espérait une réponse du syndic.
# Une adresse qui s'annonce « ne répondez pas » décourage la réponse qu'on
# sollicite — et quand elle arrive quand même, elle arrive dans une boîte dont le
# nom dit qu'on ne la lit pas. C'est le pendant humain du défaut technique de
# #754 : le tuyau existait, le panneau au-dessus disait de ne pas s'en servir.
#
# La décision suit l'INTENTION, qui est déjà déclarée pour chaque modèle : pas de
# seconde table à tenir d'accord, et un modèle neuf hérite d'un choix explicite au
# lieu d'un défaut silencieux.
EXPEDITEUR_REPONSE = "reponse"  # contact@ — on peut nous répondre
EXPEDITEUR_MUET = "muet"  # noreply@ — il n'y a rien à répondre
#  Un courriel d'AFFAIRE (#1314, 25/09/2026) : il part de l'adresse des affaires
#  (`affaire@`, réglée dans Paramétrage → SMTP) et la réponse y revient. Elle
#  remplace l'adresse à jeton `tickets+<jeton>@`, qu'OVH n'achemine pas ; la
#  réponse se rattache par « Affaire #TK-… » dans le sujet.
EXPEDITEUR_AFFAIRE = "affaire"

EXPEDITEUR_PAR_INTENTION: dict[str, str] = {
    #  On attend une réponse écrite : c'est le cas qui a motivé la consigne.
    "reponse_attendue": EXPEDITEUR_REPONSE,
    #  On demande un geste. Le geste se fait sur le site, mais le destinataire
    #  peut légitimement répondre pour demander pourquoi : la porte reste
    #  ouverte. C'est la lecture littérale de la consigne — `noreply@` est
    #  RÉSERVÉ à ce qui n'appelle aucune réponse, pas « employé par défaut ».
    "action_requise": EXPEDITEUR_REPONSE,
    #  On informe. Rien n'est demandé, rien n'est attendu.
    "information": EXPEDITEUR_MUET,
}


def expediteur_du_modele(
    code: str, *, jeton_reponse: str | None = None, intention_servie: str | None = None
) -> str:
    """`EXPEDITEUR_AFFAIRE`, `EXPEDITEUR_REPONSE` ou `EXPEDITEUR_MUET` pour ce modèle.

    ⚠️ **Un envoi d'affaire (il porte un jeton de réponse) est TOUJOURS
    parlant**, quelle que soit son intention : son `Reply-To` dit « répondez à
    ce message », et le site sait rattacher cette réponse au dossier (#703,
    #754). L'expédier depuis `noreply@` se contredirait dans le même message.
    Il part de l'adresse des AFFAIRES depuis #1314.

    Une intention inconnue — un modèle ajouté sans l'inscrire dans
    `INTENTIONS_PAR_MODELE` — rend `EXPEDITEUR_REPONSE` : entre laisser une
    réponse possible et l'interdire par omission, le défaut sûr est le premier.

    ## 🔴 `intention_servie` : l'intention de la LIGNE, et pourquoi elle prime

    Trouvé le 08/09/2026 en vérifiant la cohérence des modèles à la demande de
    Philippe. Une même notion était lue à **deux** endroits :

    ===============================  ==========================================
    Ce qui décide                    Lu depuis
    ===============================  ==========================================
    le bandeau vu par le lecteur     la BASE (`template.intention`)
    l'adresse d'expédition           le CODE (`INTENTIONS_PAR_MODELE`)
    ===============================  ==========================================

    Et **rien ne les resynchronise** : `_poser_les_absents` ne touche pas une
    ligne existante, donc changer une intention dans le code n'atteint jamais une
    installation en service. Pire, l'écran Admin → Emails permet de la modifier —
    c'est une capacité voulue — et cette modification ne changeait que le
    bandeau. Un message pouvait donc partir de `contact@` en affichant
    « Information : rien n'est attendu de vous », ou l'inverse.

    L'intention **servie** gagne : c'est celle que le lecteur voit, et c'est
    celle qu'un administrateur a choisie s'il l'a changée. Le code reste le
    repli — pour un modèle sans ligne, ou dont la ligne ne la porte pas.
    """
    if jeton_reponse:
        return EXPEDITEUR_AFFAIRE
    intention = (intention_servie or "").strip() or INTENTIONS_PAR_MODELE.get(code, "")
    return EXPEDITEUR_PAR_INTENTION.get(intention, EXPEDITEUR_REPONSE)
