"""Garde-fou — **un fait, un courriel par personne** (#850).

Consigne de Philippe, le 08/09/2026, en recevant deux fois « 🎫 Nouveau ticket » :

> *« Pour les notifications par mail : éviter le doublon quand la notification
> comprend les destinataires qui sont inclus dans la diffusion du ticket ou de
> l'actualité. Ce point est important pour éviter de recevoir deux fois le même
> mail. »*

## Le défaut

À la création d'un ticket, jusqu'à trois courriels partent, décidés à trois
endroits qui ne se connaissent pas :

=========================  ===========================  =====================
Envoi                      Destinataires                Décidé par
=========================  ===========================  =====================
``ticket_syndic``          syndic + CS                  les cases de diffusion
``ticket_bug_admin``       gestionnaire du site         la catégorie « bug »
``ticket_nouveau_cs``      CS du **périmètre**          automatique, toujours
=========================  ===========================  =====================

Un conseiller rattaché au bâtiment visé, sur un ticket dont l'auteur a coché
« CS », est dans **deux** listes.

## 🔴 Pourquoi aucun contrôle ne pouvait le voir

Les trois envois sont **chacun corrects**. Chaque fonction a la bonne liste, la
bonne portée, la bonne préférence — et une docstring qui explique pourquoi. Ce
qui manque n'est dans **aucune des trois** : c'est leur intersection, et personne
ne lit trois fonctions à la fois.

La déduplication par adresse existait déjà — `membres_cs_notifiables` dédoublonne
sa liste, `copie_auteur` retire l'auteur du groupe. Elle s'appliquait **à
l'intérieur** d'un envoi ; jamais **entre** deux.

## Ce qui n'est PAS un doublon, et le rester

⚠️ Les notifications **in-app** ont volontairement une portée plus large — *« ce
qui est tolérable dans une liste qu'on parcourt ne l'est pas dans une boîte aux
lettres »*. Deux lignes dans une liste ne dérangent personne ; deux courriels,
si. Un test ci-dessous verrouille ce sens-là.

⚠️ L'**actualité** n'a pas ce défaut, contrairement à ce que j'ai d'abord cru :
son annonce de hall appelle `creer_annonce_hall` avec `envoyer_cs=False`, donc
aucun courriel ne part de ce côté. Vérifié plutôt que supposé — un test le tient,
parce que la valeur par défaut peut changer.
"""

from __future__ import annotations

import inspect

#  La forme d'une adresse vit dans `auth.adresse_compte` depuis #1550.
from app.auth.adresse_compte import normaliser_adresse
from app.utils.envois_uniques import adresses, sans_les_deja_servies


# ── Le module de déduplication, éprouvé seul ─────────────────────────────────


def test_les_adresses_se_comparent_sans_casse_ni_espaces():
    """Deux écritures de la même boîte doivent se reconnaître."""
    assert normaliser_adresse("  Jean.Dupont@Exemple.TEST  ") == "jean.dupont@exemple.test"


def test_la_normalisation_ne_va_PAS_plus_loin():
    """🔴 Une déduplication trop zélée fait disparaître du courrier.

    `jean.dupont@` et `jeandupont@` sont deux adresses distinctes pour la plupart
    des serveurs. Les « normaliser » ensemble retirerait un destinataire légitime
    — et c'est le mauvais côté de l'erreur : un doublon dérange, une absence prive.
    """
    assert normaliser_adresse("jean.dupont@x.test") != normaliser_adresse("jeandupont@x.test")
    assert normaliser_adresse("a+ticket@x.test") != normaliser_adresse("a@x.test")


def test_le_retrait_conserve_l_ORDRE():
    """L'ordre porte une décision ailleurs : `syndic_puis` met le syndic devant.

    Le réordonner ferait gagner le doublon interne à quelqu'un d'autre (#480).
    """
    liste = [(1, "syndic@x.test"), (2, "a@x.test"), (3, "b@x.test")]
    assert sans_les_deja_servies(liste, {"a@x.test"}) == [(1, "syndic@x.test"), (3, "b@x.test")]


def test_une_liste_VIDE_est_un_resultat_normal():
    """Tout le monde a déjà été servi par l'envoi le plus disant.

    L'appelant doit alors ne rien envoyer — pas envoyer à personne, ce qui
    laisserait une trace sans destinataire dans `historique_email`.
    """
    assert sans_les_deja_servies([(1, "a@x.test")], {"A@X.TEST"}) == []


def test_adresses_ignore_les_entrees_vides():
    """Un membre sans adresse ne doit pas produire une chaîne vide qui matcherait tout."""
    assert adresses([(1, ""), (2, None), (3, "a@x.test")]) == {"a@x.test"}


# ── Le branchement, sans lequel le module ne servirait à rien ────────────────


def test_la_notification_d_arrivee_CEDE_aux_envois_plus_disants():
    """🔴 Le défaut lui-même, lu dans le code qui le corrige.

    ⚠️ Contrôle **statique** : rejouer une création complète demanderait SMTP,
    des tâches de fond et six écritures. Ce qui doit être vrai — que la
    notification reçoive les adresses déjà servies et les retire — se lit.
    """
    from app.routers.tickets import arrivee, crud

    source_crud = inspect.getsource(crud)
    assert "deja_servies=adresses_deja_servies(" in source_crud, (
        "la création ne calcule plus les adresses déjà servies : le conseiller du "
        "bâtiment visé recevrait de nouveau deux courriels."
    )

    source_courriels = inspect.getsource(arrivee)
    assert "sans_les_deja_servies(destinataires, deja_servies)" in source_courriels, (
        "`ticket_nouveau_cs` ne retire plus les adresses déjà servies."
    )


def test_les_TROIS_envois_du_ticket_sont_bien_recenses():
    """Cas zéro de la PORTÉE — un quatrième envoi passerait sinon inaperçu.

    `standards/04` §40 : la portée d'un contrôle fait partie du contrôle. Si un
    envoi était ajouté à la création sans rejoindre `adresses_deja_servies`, le
    doublon reviendrait sous une autre forme.
    """
    from app.routers.tickets import crud

    source = inspect.getsource(crud)
    envois = [
        nom
        for nom in (
            "_notifier_cs_creation",
            "envoyer_email_syndic_cs",
            "_alerter_bug",
            "envoyer_email_externe",
        )
        if f"{nom}(" in source
    ]
    assert len(envois) == 4, (
        f"{len(envois)} envoi(s) reconnus à la création au lieu de 4 : {envois}. "
        "Un envoi a été ajouté ou retiré — vérifier qu'il rejoint "
        "`adresses_deja_servies` s'il vise des gens déjà servis."
    )


def test_adresses_deja_servies_ne_reclame_RIEN_sans_diffusion():
    """Un ticket sans case cochée et hors catégorie « bug » n'a rien à retirer.

    Sans ce cas, une implémentation qui retirerait tout le monde en permanence
    passerait les tests précédents — et personne ne recevrait jamais
    `ticket_nouveau_cs`.
    """
    from app.routers.tickets.arrivee import adresses_deja_servies

    class _Ticket:
        destinataire_syndic = False
        destinataire_cs = False
        categorie = "acces_accueil"

    assert adresses_deja_servies(None, _Ticket()) == set()


# ── Ce qui ne doit PAS changer ───────────────────────────────────────────────


def test_les_notifications_IN_APP_gardent_leur_portee_plus_large():
    """Deux lignes dans une liste ne dérangent personne ; deux courriels, si.

    La déduplication ne doit jamais gagner les notifications de l'application :
    ce serait « corriger » une décision explicite du projet.
    """
    from app.routers.tickets import arrivee

    source = inspect.getsource(arrivee._notifier_cs_creation)
    #  Le CORPS entre le calcul des membres et le relais au courriel : c'est là
    #  que les `Notification` sont posées, et c'est là que rien ne doit filtrer.
    debut = source.index("cs_members = membres_cs_ou_admin(session)")
    fin = source.index("_envoyer_email_cs_creation")
    boucle_in_app = source[debut:fin]

    #  La cloche passe par sa porte depuis #1187 (`utils/cloche.sonner`).
    assert "sonner(" in boucle_in_app, "la boucle in-app a disparu du champ du test"
    assert "deja_servies" not in boucle_in_app, (
        "la déduplication a gagné les notifications in-app : leur portée est "
        "volontairement plus large que celle des courriels."
    )
    assert "sans_les_deja_servies" not in boucle_in_app, (
        "les membres notifiés dans l'application sont filtrés sur les adresses "
        "déjà servies par courriel — deux canaux, deux portées."
    )


def test_l_ACTUALITE_n_envoie_AUCUN_courriel_par_son_annonce_de_hall():
    """Vérifié plutôt que supposé — et la valeur par défaut peut changer.

    J'ai d'abord cru à un troisième recouvrement ici. `generer_affiche`
    (`tickets/actualite.py` depuis le 23/09/2026, #1091) appelle
    `creer_annonce_hall` sans passer `envoyer_cs` ni `envoyer_syndic`,
    dont les défauts sont `False` : aucun courriel ne part de ce côté, donc aucun
    doublon possible avec `publication_syndic`.

    Le jour où l'un de ces défauts passerait à `True`, ce test tomberait — et le
    recouvrement devrait être traité comme celui du ticket.
    """
    from app.routers.annonces_hall import creer_annonce_hall
    from app.routers.tickets.actualite import generer_affiche

    parametres = inspect.signature(creer_annonce_hall).parameters
    for nom in ("envoyer_cs", "envoyer_syndic"):
        assert parametres[nom].default is False, (
            f"`{nom}` n'est plus décoché par défaut : l'annonce de hall d'une "
            "actualité enverrait un courriel, en doublon de `publication_syndic`."
        )

    appel = inspect.getsource(generer_affiche)
    for nom in ("envoyer_cs", "envoyer_syndic"):
        assert nom not in appel, (
            f"`generer_affiche` passe désormais `{nom}` : le recouvrement "
            "avec `publication_syndic` doit être traité."
        )
