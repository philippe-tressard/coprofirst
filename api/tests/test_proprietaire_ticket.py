"""Le « Saisi pour » **se substitue à l'auteur** — pour le nom lu et pour la copie.

## La demande (12/09/2026, à l'écran)

> Pour un ticket dont le « Saisi pour » possède un résident inscrit ou une
> personne extérieure, ce dernier se substitue à l'auteur :
>   • pour le nom qui apparaît dans les publications du fil d'actualité,
>   • pour « Envoyer une copie à XXX » dans la catégorie DIFFUSION.

## Pourquoi c'est la suite d'un arbitrage déjà pris

`copie_auteur.py` est né le 31/08/2026 sur ces mots : *« c'est bien le
propriétaire du ticket, pas celui qui fait un commentaire »*. La question était
déjà la bonne ; la réponse s'arrêtait à l'auteur parce que rien d'autre
n'existait alors. Le « Saisi pour » la complète : quand le conseil syndical
enregistre le signalement d'un résident qui a téléphoné, l'auteur est celui qui
a **tapé**, et le propriétaire celui qui **a le problème**.

## Ce que ce test verrouille

🔴 **Le nom lu et le destinataire servi sont la MÊME personne.** C'est tout
l'enjeu : un écran qui annonce « Envoyer une copie à Martin » et qui envoie à
Dupont ment, et personne ne s'en aperçoit — le courriel part ailleurs, en
silence. Les deux viennent donc de `proprietaire()`, et d'elle seule.

⚠️ Le nom peut exister SANS adresse : une personne extérieure dont on ne connaît
que le nom. L'écran doit alors annoncer ce nom et n'envoyer aucune copie. Les
confondre ferait soit taire le nom, soit promettre un envoi qui n'a pas lieu.
"""

from __future__ import annotations

import pathlib

import pytest

from app.utils.copie_auteur import copie_demandee, destinataires_et_copie, proprietaire
from tests.aides_saisi_pour import ObjetSaisiPour as _Ticket
from tests.aides_saisi_pour import alice_et_bruno


@pytest.fixture()
def session(session):
    """La base du conftest, portant Alice et Bruno."""
    alice_et_bruno(session)
    return session


def test_sans_saisi_pour_le_proprietaire_est_l_AUTEUR(session):
    """Le cas courant, et celui des publications, événements et annonces : ces
    objets n'ont aucun champ « Saisi pour », et traversent la fonction sans que
    rien ne change pour eux."""
    nom, email = proprietaire(session, _Ticket(auteur_id=1))
    assert nom == "Alice MARTIN"
    assert email == "alice@x.test"


def test_un_resident_INSCRIT_se_substitue_a_l_auteur(session):
    """🔴 Le cœur de la demande. Alice (CS) saisit pour Bruno : c'est Bruno que
    le fil nomme, et Bruno qui reçoit la copie."""
    nom, email = proprietaire(session, _Ticket(auteur_id=1, sp_user=2))
    assert nom == "Bruno DUPONT"
    assert email == "bruno@x.test"


def test_une_personne_EXTERIEURE_se_substitue_aussi(session):
    """Le second cas : personne d'inscrit, seulement un nom et une adresse
    saisis. Ils priment sur l'auteur de la même façon."""
    nom, email = proprietaire(
        session, _Ticket(auteur_id=1, sp_nom="Paul EXTERNE", sp_email="paul@dehors.test")
    )
    assert nom == "Paul EXTERNE"
    assert email == "paul@dehors.test"


def test_un_nom_SANS_adresse_reste_un_nom(session):
    """⚠️ Le cas qui distingue les deux questions : on sait QUI, on ne sait pas
    OÙ. L'écran doit nommer cette personne — la taire au motif qu'on ne peut pas
    lui écrire reviendrait à afficher l'auteur, donc quelqu'un d'autre."""
    nom, email = proprietaire(session, _Ticket(auteur_id=1, sp_nom="Paul EXTERNE"))
    assert nom == "Paul EXTERNE"
    assert email is None


def test_un_saisi_pour_INTROUVABLE_retombe_sur_l_auteur(session):
    """Le compte a été supprimé depuis la saisie. On ne laisse pas le ticket sans
    propriétaire : l'auteur reprend la place, et la copie part quand même."""
    nom, email = proprietaire(session, _Ticket(auteur_id=1, sp_user=999))
    assert nom == "Alice MARTIN"
    assert email == "alice@x.test"


def test_la_COPIE_part_au_saisi_pour_et_non_a_l_auteur(session):
    """🔴 Le test qui relie les deux moitiés : ce que l'écran annonce et ce que
    le serveur envoie doivent désigner la même personne.

    Vérifié sur la version fautive : avant le 12/09, cette copie partait à
    `alice@x.test` — l'adresse de celle qui avait tapé."""
    bcc = copie_demandee(session, _Ticket(auteur_id=1, sp_user=2), [], demandee=True)
    assert bcc == ["bruno@x.test"]


def test_la_copie_n_est_pas_DOUBLEE_quand_le_proprietaire_est_deja_servi(session):
    """La déduplication vaut pour le propriétaire comme elle valait pour
    l'auteur : un résident déjà destinataire principal ne reçoit pas deux fois le
    même courriel."""
    bcc = copie_demandee(session, _Ticket(auteur_id=1, sp_user=2), ["BRUNO@X.TEST"], demandee=True)
    assert bcc is None


def test_le_FIL_et_la_COPIE_lisent_la_MEME_fonction():
    """⚠️ Garde-fou statique, et c'est lui qui empêche la dérive silencieuse : si
    le fil recalculait le nom de son côté, l'écran pourrait annoncer une personne
    et le courriel partir à une autre — sans qu'aucun test de valeur ne le voie,
    puisque les deux seraient « corrects » séparément."""
    flux = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "flux" / "tickets.py"
    ).read_text(encoding="utf-8")
    assert "proprietaire(" in flux, (
        "le fil des tickets doit nommer le propriétaire par `copie_auteur.proprietaire`"
    )
    assert "auteur_nom(ctx.session, tk.auteur_id)" not in flux, (
        "le fil ne doit plus nommer l'auteur directement : le « Saisi pour » prime"
    )


def test_la_copie_COCHEE_SEULE_devient_le_destinataire_avec_SON_gabarit(session):
    """🔴 03/10/2026 : « quand on met l'auteur seul, celui-ci ne reçoit pas de
    mail ». La copie n'était qu'un `bcc` accroché à l'envoi au syndic / au
    conseil : sans eux, rien ne partait. Le propriétaire devient alors le
    destinataire de l'envoi, sans copie cachée, et `seule` commande son gabarit."""
    destinataires, bcc, seule = destinataires_et_copie(
        session, _Ticket(auteur_id=1, sp_user=2), [], demandee=True
    )
    assert destinataires == [(None, "bruno@x.test")]
    assert bcc is None
    assert seule is True


def test_sans_la_case_et_sans_destinataire_rien_ne_part(session):
    assert destinataires_et_copie(session, _Ticket(auteur_id=1), [], demandee=False) == (
        [],
        None,
        False,
    )


def test_avec_des_destinataires_la_copie_reste_un_bcc_et_le_gabarit_ne_change_pas(session):
    principaux = [(9, "cs@x.test")]
    destinataires, bcc, seule = destinataires_et_copie(
        session, _Ticket(auteur_id=1, sp_user=2), principaux, demandee=True
    )
    assert destinataires == principaux
    assert bcc == ["bruno@x.test"]
    assert seule is False


def test_les_gabarits_de_copie_existent_et_ne_portent_pas_la_reference_du_syndic():
    """Le message d'un résident n'a pas à porter la référence de copropriété du syndic."""
    from app.seed import EMAIL_TEMPLATES

    seed = {m[0]: m for m in EMAIL_TEMPLATES}
    for copie in ("ticket_copie_auteur", "publication_copie_auteur"):
        assert copie in seed, copie
        assert "prefixe_copro" not in seed[copie][2], copie
        assert "reference_copro" not in seed[copie][3], copie


def test_les_envois_se_declenchent_aussi_sur_la_seule_copie():
    """Garde statique : la condition d'appel portait seulement syndic / conseil, ce
    qui rendait la correction de `destinataires_et_copie` inatteignable."""
    racine = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "tickets"
    for nom, motif in (
        ("crud.py", 'or getattr(body, "envoyer_auteur"'),
        ("evolutions.py", 'or getattr(body, "envoyer_auteur"'),
        ("mise_a_jour.py", "or copie_auteur"),
        ("actualite.py", "if syndic or cs or auteur"),
    ):
        assert motif in (racine / nom).read_text(encoding="utf-8"), nom
