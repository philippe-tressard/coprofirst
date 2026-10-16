"""Le taux d'adoption rapporte les comptes VENUS aux comptes qui POUVAIENT venir (#1628).

Jeu fictif : quatre comptes ouverts au bâtiment A (dont un membre du conseil et
un qui a refusé la mesure), un locataire sans bâtiment, un compte fermé qui est
venu quand même. Trois sont venus dans les 30 jours, un seul avant — et celui-là
a laissé une PRÉSENCE MENSUELLE il y a six mois, que seule la fenêtre Année lit
(03/10/2026).
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.models.copropriete import Batiment
from app.models.core import PresenceMensuelle, RoleUtilisateur, StatutUtilisateur, TelemetryEvent
from app.utils import horloge
from app.utils.adoption import SANS_BATIMENT, Fenetre, adoption
from tests.aides_base import compte, moteur_de_test

JOURS = 30


def _fenetre_mois() -> Fenetre:
    return Fenetre("30 derniers jours", horloge.maintenant() - timedelta(days=JOURS))


def _mois_il_y_a(n: int) -> str:
    j = horloge.aujourd_hui()
    y, m = j.year, j.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}"


def _jeu(s: Session) -> None:
    bat = Batiment(copropriete_id=1, numero="A")
    s.add(bat)
    s.commit()
    copro = StatutUtilisateur.copropriétaire_résident
    venu = compte(s, statut=copro, batiment_id=bat.id)
    conseil = compte(
        s, statut=copro, batiment_id=bat.id, roles_json=RoleUtilisateur.conseil_syndical.value
    )
    absent = compte(s, statut=copro, batiment_id=bat.id)
    refus = compte(s, statut=copro, batiment_id=bat.id, opt_out_telemetrie=True)
    locataire = compte(s, statut=StatutUtilisateur.locataire)
    ferme = compte(s, statut=copro, batiment_id=bat.id, actif=False)

    maintenant = horloge.maintenant()
    for u, age in [(venu, 1), (conseil, 29), (locataire, 0), (ferme, 0), (absent, JOURS + 1)]:
        s.add(TelemetryEvent(user_id=u.id, page="/", cree_le=maintenant - timedelta(days=age)))
    #  Le refus n'a pas d'événement (la collecte l'ignore) ; on en pose un quand
    #  même : il ne doit compter nulle part, ni en haut ni en bas.
    s.add(TelemetryEvent(user_id=refus.id, page="/", cree_le=maintenant))
    #  L'absent est venu il y a six mois : la présence mensuelle le sait, les
    #  événements (30 jours) ne le savent plus.
    s.add(PresenceMensuelle(mois=_mois_il_y_a(6), user_id=absent.id))
    s.commit()
    return {"venu": venu.id, "absent": absent.id}


def _resultat(fenetre: Fenetre | None = None, exclure: str | None = None) -> dict:
    moteur = moteur_de_test()
    with Session(moteur) as s:
        ids = _jeu(s)
        exclus = {ids[exclure]} if exclure else set()
        return adoption(s, fenetre or _fenetre_mois(), exclus)


def test_le_denominateur_exclut_les_refus_et_les_comptes_fermes():
    r = _resultat()
    assert r["global"] == {"libelle": "Tous les comptes", "actifs": 3, "comptes": 4, "taux": 75}
    assert r["refus"] == 1
    assert r["periode"] == "30 derniers jours"


def test_la_fenetre_annee_lit_la_presence_mensuelle():
    """L'absent des 30 jours est venu il y a six mois : la vue Année le compte."""
    annee = Fenetre("12 derniers mois", horloge.maintenant() - timedelta(days=30), _mois_il_y_a(11))
    r = _resultat(annee)
    assert (r["global"]["actifs"], r["global"]["comptes"]) == (4, 4)
    assert r["periode"] == "12 derniers mois"
    #  Une présence plus vieille que la fenêtre ne compte pas.
    courte = Fenetre("x", horloge.maintenant() - timedelta(days=30), _mois_il_y_a(5))
    assert _resultat(courte)["global"]["actifs"] == 3


def test_un_compte_exclu_sort_des_deux_termes():
    """Le gestionnaire du site, en lecture « sans » : ni venu, ni à venir."""
    r = _resultat(exclure="venu")
    assert (r["global"]["actifs"], r["global"]["comptes"]) == (2, 3)
    r = _resultat(exclure="absent")
    assert (r["global"]["actifs"], r["global"]["comptes"]) == (3, 3)


def test_ventilation_par_type_de_resident():
    lignes = {ligne["libelle"]: ligne for ligne in _resultat()["par_type"]}
    assert set(lignes) == {"Copropriétaire résident", "Locataire"}
    copro = lignes["Copropriétaire résident"]
    assert (copro["actifs"], copro["comptes"], copro["taux"]) == (2, 3, 67)
    assert (lignes["Locataire"]["actifs"], lignes["Locataire"]["comptes"]) == (1, 1)


def test_ventilation_par_profil_roles_cumules_libelles_partages():
    """Un compte compte sous CHACUN de ses rôles ; le libellé vient de `roles_libelles`."""
    lignes = {ligne["libelle"]: ligne for ligne in _resultat()["par_profil"]}
    assert set(lignes) == {"Résident", "Conseil syndical"}
    assert (lignes["Résident"]["actifs"], lignes["Résident"]["comptes"]) == (2, 3)
    assert (lignes["Conseil syndical"]["actifs"], lignes["Conseil syndical"]["comptes"]) == (1, 1)


def test_ventilation_par_batiment_et_sans_batiment():
    lignes = {ligne["libelle"]: ligne for ligne in _resultat()["par_batiment"]}
    assert set(lignes) == {"Bât. A", SANS_BATIMENT}
    assert (lignes["Bât. A"]["actifs"], lignes["Bât. A"]["comptes"], lignes["Bât. A"]["taux"]) == (
        2,
        3,
        67,
    )


def test_aucun_compte_ne_divise_pas_par_zero():
    moteur = moteur_de_test()
    with Session(moteur) as s:
        r = adoption(s, _fenetre_mois())
    assert (
        r["global"]["taux"] is None
        and r["par_profil"] == []
        and r["par_type"] == []
        and r["par_batiment"] == []
    )
