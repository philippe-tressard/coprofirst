"""D'où part un message — `contact@` ou `noreply@` (#756).

Consigne de l'utilisateur, 05/09/2026 :

> « utiliser contact@5hostachy.fr ; réserver noreply@5hostachy.fr dans les cas
>   où il n'y a pas de réponse à obtenir »

Tout partait de `noreply@`, y compris ce qui espérait une réponse du syndic. Une
adresse qui s'annonce « ne répondez pas » décourage la réponse qu'on sollicite —
et quand elle arrive quand même, elle arrive dans une boîte dont le nom dit
qu'on ne la lit pas.

⚠️ Ces tests ne posent aucun réseau : la décision est **pure** (une intention et
un jeton en entrée, un genre d'expéditeur en sortie), et c'est ce qui permet de
l'éprouver modèle par modèle. Le tuyau, lui, est éprouvé par le fait qu'il n'y a
qu'un seul appel — `connexion_smtp(..., expediteur=…)`.

## L'intention SERVIE prime sur celle du code (#850, 08/09/2026)

Une même notion se lisait à **deux** endroits : le **bandeau** vu par le lecteur
dans la BASE (`template.intention`), l'**adresse d'expédition** dans le CODE
(`INTENTIONS_PAR_MODELE`). 🔴 Et rien ne les resynchronise : `_poser_les_absents`
ne touche jamais une ligne existante, et l'écran Admin → Emails permet de
changer l'intention — ce qui ne changeait que le bandeau. Un message pouvait donc
partir de `contact@` en affichant « rien n'est attendu de vous », ou de
`noreply@` en affichant « Action requise ».

**L'intention servie**, celle de la ligne, gagne : c'est celle que le lecteur
voit, et celle qu'un administrateur a choisie. Le code reste le repli — jamais
l'inverse, sinon l'écran d'administration mentirait sur ce qu'il permet. Ces
tests vivaient dans `test_intention_source_unique.py`, réuni ici le 30/09/2026 :
les deux fichiers éprouvaient la même table de décision.
"""

from __future__ import annotations

import inspect

from app.seed.emails import (
    EXPEDITEUR_AFFAIRE,
    EXPEDITEUR_MUET,
    EXPEDITEUR_PAR_INTENTION,
    EXPEDITEUR_REPONSE,
    INTENTIONS_PAR_MODELE,
    expediteur_du_modele,
)
from app.utils.smtp import adresse_expedition, adresses_a_tester

_CFG = {"smtp_from": "noreply@5hostachy.fr", "smtp_from_reponse": "contact@5hostachy.fr"}


#  La table de décision de `expediteur_du_modele` :
#  (code du modèle, jeton de réponse, intention servie, expéditeur attendu).
_JETON = "a" * 32
CAS_EXPEDITEUR = [
    #  Un envoi qui attend une réponse part de `contact@` — le cas qui a motivé
    #  la consigne : le ticket envoyé au syndic (#756).
    ("ticket_syndic", None, None, EXPEDITEUR_REPONSE),
    ("relance_syndic", None, None, EXPEDITEUR_REPONSE),
    #  Un envoi qui informe seulement part de `noreply@` : « réserver noreply@ »
    #  — donc il sert, mais seulement là (#756).
    ("compte_active", None, None, EXPEDITEUR_MUET),
    ("document_publie", None, None, EXPEDITEUR_MUET),
    #  🔴 Un message ne dit pas deux choses contraires : un envoi d'affaire porte
    #  un `Reply-To` « répondez à ce message », que `noreply@` contredirait dans
    #  le même en-tête, quelle que soit l'intention. Il part de l'adresse des
    #  AFFAIRES depuis #1314.
    ("ticket_nouveau_message", None, None, EXPEDITEUR_MUET),
    ("ticket_nouveau_message", _JETON, None, EXPEDITEUR_AFFAIRE),
    #  Un modèle sans intention déclarée laisse la porte ouverte : un modèle neuf
    #  ne devient pas muet parce qu'on a oublié de l'inscrire dans la table (#756).
    ("modele_qui_nexiste_pas", None, None, EXPEDITEUR_REPONSE),
    #  🔴 Le défaut de #850 : `compte_active` passé à « Action requise » depuis
    #  l'écran — l'adresse suit, sinon le bandeau dit « agissez » et l'adresse
    #  « ne répondez pas ».
    ("compte_active", None, "action_requise", EXPEDITEUR_REPONSE),
    #  L'inverse aussi (#850) : sans lui, une implémentation qui ne saurait
    #  qu'AJOUTER la possibilité de répondre passerait le cas précédent.
    ("ticket_syndic", None, "information", EXPEDITEUR_MUET),
    #  Sans intention servie, le CODE reprend la main (#850). ⚠️ La chaîne vide
    #  est un repli, PAS une intention « aucun bandeau » : une ligne qui ne
    #  déclare rien hérite du choix du code, elle ne devient pas muette.
    ("compte_active", None, "", EXPEDITEUR_MUET),
    ("compte_active", None, "   ", EXPEDITEUR_MUET),
    ("ticket_syndic", None, "", EXPEDITEUR_REPONSE),
    ("ticket_syndic", None, "   ", EXPEDITEUR_REPONSE),
    #  Le JETON de réponse prime sur TOUT (#703, #754) : la règle passe AVANT
    #  l'intention servie, et ne se perd pas en l'ajoutant (#850).
    ("compte_active", "abc123", "information", EXPEDITEUR_AFFAIRE),
]


def test_la_table_de_decision_de_l_expediteur():
    ecarts = []
    for code, jeton, servie, attendu in CAS_EXPEDITEUR:
        obtenu = expediteur_du_modele(code, jeton_reponse=jeton, intention_servie=servie)
        if obtenu != attendu:
            ecarts.append(
                f"  {code!r} (jeton={jeton!r}, intention servie={servie!r}) : "
                f"{obtenu!r} au lieu de {attendu!r}"
            )
    assert not ecarts, (
        "L'expéditeur contredirait le message (bandeau, Reply-To ou intention) :\n"
        + "\n".join(ecarts)
    )


def test_sans_seconde_adresse_configuree_rien_ne_change():
    """Le repli, et c'est lui qui rend le lot sûr à déployer.

    Une installation qui n'a pas encore renseigné `contact@` continue d'envoyer
    exactement comme avant — jamais depuis une adresse vide, que le serveur
    refuserait pour un motif sans rapport avec le contenu.
    """
    #  Avec les deux adresses, chaque genre prend la sienne.
    assert adresse_expedition(_CFG, EXPEDITEUR_REPONSE) == "contact@5hostachy.fr"
    assert adresse_expedition(_CFG, EXPEDITEUR_MUET) == "noreply@5hostachy.fr"
    #  Sans la seconde, rien ne change.
    cfg = {"smtp_from": "noreply@5hostachy.fr"}
    assert adresse_expedition(cfg, EXPEDITEUR_REPONSE) == "noreply@5hostachy.fr"
    assert adresse_expedition({**cfg, "smtp_from_reponse": "   "}, EXPEDITEUR_REPONSE) == (
        "noreply@5hostachy.fr"
    )


def test_chaque_intention_declaree_a_un_expediteur():
    """Cas zéro : une intention sans expéditeur retomberait sur le défaut sans
    que personne ne l'ait décidé — et la table ne servirait plus à rien.
    """
    intentions = set(INTENTIONS_PAR_MODELE.values())
    manquantes = intentions - set(EXPEDITEUR_PAR_INTENTION)
    assert not manquantes, (
        "ces intentions n'ont pas d'expéditeur déclaré, elles prendront le défaut "
        f"en silence : {sorted(manquantes)}"
    )


def test_le_bouton_de_test_exerce_les_DEUX_adresses():
    """🔴 Un contrôle doit exercer ce qui SERT.

    Le bouton « tester la configuration » n'envoyait que depuis `smtp_from`.
    Depuis que deux adresses servent, un serveur qui refuserait la seconde —
    cas courant quand elle est un **alias** et non un compte — aurait passé le
    test et échoué sur un vrai ticket, dans un journal que personne ne lit à ce
    moment-là.
    """
    assert adresses_a_tester(_CFG) == ["noreply@5hostachy.fr", "contact@5hostachy.fr"]


def test_une_seule_adresse_configuree_ne_fabrique_pas_un_second_envoi():
    """On n'envoie pas deux fois la même chose pour faire nombre : un test qui
    double sans rien prouver de plus finit par être perçu comme du bruit.
    """
    assert adresses_a_tester({"smtp_from": "a@x.test"}) == ["a@x.test"]
    assert adresses_a_tester({"smtp_from": "a@x.test", "smtp_from_reponse": "a@x.test"}) == [
        "a@x.test"
    ]


def test_l_ENVOI_transmet_bien_l_intention_de_la_ligne():
    """Le branchement, sans lequel la table de décision ne prouverait rien (#850).

    ⚠️ Contrôle **statique** : reconstruire un envoi complet demanderait SMTP,
    une session et un modèle en base. Ce qui doit être vrai — que le point
    d'envoi passe `template.intention` — se lit dans le code.
    """
    from app.utils import email

    source = inspect.getsource(email)
    assert "intention_servie=template.intention" in source, (
        "le point d'envoi ne transmet plus l'intention de la ligne : l'adresse "
        "redeviendrait celle du code, et la seconde source reviendrait."
    )


def test_cas_zero_les_deux_expediteurs_sont_bien_DEUX():
    """Sans cet écart, la table de décision passerait sans rien mesurer.

    `standards/04` §40 : la portée d'un contrôle fait partie du contrôle.
    """
    assert EXPEDITEUR_REPONSE != EXPEDITEUR_MUET
    #  Le cas « l'intention SERVIE prime » n'éprouve rien si le code déclarait
    #  déjà `action_requise` pour ce modèle (#850).
    assert INTENTIONS_PAR_MODELE["compte_active"] == "information"
