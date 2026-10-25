"""Les portes d'un badge, dérivées des lots — et confrontées à la règle de #953 (#2217).

🔴 « Proposer, jamais poser » (arbitrage du 25/10/2026) : la dérivation n'écrit rien ;
la règle de #953 (`acces_perimetre.acces_deduit`) reste celle des chemins silencieux,
et `test_acces_perimetre.py` la tient inchangée. Ce fichier tient l'ÉQUIVALENCE :
là où #953 rend une valeur, la proposition la contient toujours ; et les cas où elle
propose PLUS sont énumérés et nommés ici — un cas neuf qui ouvrirait plus échoue.

Lots et bâtiments fictifs.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from sqlmodel import select

import app.models.core  # noqa: F401  (relations entre modèles)
from app.models.acces import Vigik
from app.models.copropriete import Lot, NatureLot, TypeLot
from app.models.perimetre import Perimetre
from app.utils import acces_perimetre, acces_portes
from app.utils.acces_portes import Porte, fusionner, portes_du_lot
from app.utils.constats import AVERTISSEMENT, INCONNU, applicable
from tests.aides_badges import _compte, _lier

L, C, P = NatureLot.logement, NatureLot.cave, NatureLot.parking


def _code(batiment: int | None) -> str | None:
    return f"bat:{batiment}" if batiment else None


@pytest.fixture(autouse=True)
def codes_par_convention(monkeypatch):
    """Les deux règles parlent des mêmes codes, sans dépendre de l'arbre du processus."""
    monkeypatch.setattr(acces_perimetre, "code_batiment", lambda b: f"bat:{b}")
    monkeypatch.setattr(acces_portes, "code_batiment", lambda b: f"bat:{b}")


#: (nature, bâtiment où l'acte situe le lot, bâtiment de la circulation qui le dessert)
#: par cas — et ce que la proposition rend.
CAS = {
    "a_logement_seul": ([(L, 1, None)], {"bat:1"}),
    "a_logement_et_cave_de_sa_circulation": ([(L, 1, None), (C, 1, 1)], {"bat:1"}),
    "b_place_desservie_par_un_autre_batiment": ([(L, 1, None), (P, None, 4)], {"bat:1", "bat:4"}),
    "c_exterieur_une_seule_place": ([(P, None, 4)], {"bat:4"}),
    "d_place_en_acces_direct": ([(P, None, None)], set()),
    "e_logements_dans_deux_batiments": ([(L, 1, None), (L, 2, None)], {"bat:1", "bat:2"}),
}

#: 🔴 Les cas où la proposition ouvre PLUS que #953 — et seulement ceux-là. Ce sont
#: des PROPOSITIONS, que le conseil reprend ou non : rien n'y est posé.
PROPOSENT_PLUS = {
    "b_place_desservie_par_un_autre_batiment",
    "c_exterieur_une_seule_place",
    "e_logements_dans_deux_batiments",
}


def _proposition(lots) -> set[str]:
    return {
        p.code
        for p in fusionner(
            porte
            for nature, bat, circ in lots
            for porte in portes_du_lot(nature, _code(bat), _code(circ))
        )
    }


@pytest.mark.parametrize("nom", sorted(CAS))
def test_la_proposition_de_chaque_cas(nom):
    lots, attendu = CAS[nom]
    assert _proposition(lots) == attendu


@pytest.mark.parametrize("nom", sorted(CAS))
def test_equivalence_avec_953_jamais_moins_et_plus_seulement_ou_c_est_nomme(nom):
    lots, _ = CAS[nom]
    proposition = _proposition(lots)
    regle_953 = set(acces_perimetre.acces_deduit([bat for _, bat, _ in lots]) or [])
    assert regle_953 <= proposition, f"{nom} : la proposition retire {regle_953 - proposition}"
    assert (proposition > regle_953) == (nom in PROPOSENT_PLUS), (
        f"{nom} : la proposition ouvre plus que #953 sans être déclarée dans PROPOSENT_PLUS"
        if proposition > regle_953
        else f"{nom} : déclaré dans PROPOSENT_PLUS, or il n'ouvre pas plus"
    )


def test_chaque_porte_dit_sa_raison_et_une_porte_ne_paraît_qu_une_fois():
    portes = fusionner(
        [*portes_du_lot(L, "bat:1", None), *portes_du_lot(C, "bat:1", "bat:1")]
        + portes_du_lot(P, None, "bat:4")
    )
    assert portes == [
        Porte("bat:1", "votre logement · dessert votre cave"),
        Porte("bat:4", "dessert votre place"),
    ]


# ── Sur la base : les lots d'un compte, liens actifs seulement ─────────────────


def _lot(session, numero, nature, batiment_id=None, circulation=None):
    noeud = None
    if circulation:
        noeud = session.exec(select(Perimetre).where(Perimetre.code == circulation)).first()
        if noeud is None:
            noeud = Perimetre(code=circulation, libelle=circulation)
            session.add(noeud)
            session.flush()
    lot = Lot(
        numero=numero,
        type=TypeLot.parking if nature is P else TypeLot.appartement,
        nature=nature,
        batiment_id=batiment_id,
        circulation_perimetre_id=noeud.id if noeud else None,
    )
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return lot


def test_un_compte_recoit_les_portes_de_ses_liens_actifs_et_d_aucun_autre(session):
    resident = _compte(session, "Arnaud")
    logement = _lot(session, "901", L, batiment_id=1)
    place = _lot(session, "902", P, circulation="bat:4")
    voisin = _lot(session, "903", L, batiment_id=2)
    _lier(session, resident, logement)
    _lier(session, resident, place)
    locataire = _compte(session, "Bernard")
    _lier(session, locataire, voisin, type_lien="locataire")

    assert {p.code for p in acces_portes.portes_proposees(session, resident.id, None)} == {
        "bat:1",
        "bat:4",
    }
    #  Le locataire du 903 reçoit les portes de SON lot — rien des lots du résident.
    assert {p.code for p in acces_portes.portes_proposees(session, locataire.id, None)} == {"bat:2"}


def test_un_lien_inactif_ne_propose_rien(session):
    ancien = _compte(session, "Charles")
    lot = _lot(session, "904", L, batiment_id=3)
    _lier(session, ancien, lot)
    for lien in session.exec(select(app.models.core.UserLot)).all():
        lien.actif = False
        session.add(lien)
    session.commit()
    assert acces_portes.portes_proposees(session, ancien.id, None) == []


# ── Le constat : jamais bloquant ──────────────────────────────────────────────


def test_le_constat_signale_le_manque_et_l_exces_sans_jamais_bloquer(session, monkeypatch):
    from app.utils import acces_constats

    monkeypatch.setattr(acces_constats, "codes_batiments", lambda: ["bat:1", "bat:2", "bat:4"])
    monkeypatch.setattr(acces_constats, "code_par_defaut", lambda: "residence")
    resident = _compte(session, "Arnaud")
    logement = _lot(session, "911", L, batiment_id=1)
    place = _lot(session, "912", P, circulation="bat:4")
    _lier(session, resident, logement)
    _lier(session, resident, place)
    orphelin = _lot(session, "913", L, batiment_id=2)
    session.add_all(
        [
            Vigik(code="V1", lot_id=logement.id, perimetre_cible='["bat:1"]'),  # manque bat:4
            Vigik(code="V2", lot_id=logement.id, perimetre_cible='["bat:1","bat:2","bat:4"]'),
            Vigik(code="V3", lot_id=logement.id, perimetre_cible='["residence"]'),  # tout : rien
            Vigik(code="V4", perimetre_cible='["bat:2"]'),  # ni lot ni porteur : INCONNU
            Vigik(code="V5", lot_id=orphelin.id),  # sans accès : compté
        ]
    )
    session.commit()

    trouves = {c.code: c for c in acces_constats.constater_badges(session)}
    assert trouves["badge_manque"].lots == ["911"]
    assert trouves["badge_exces"].lots == ["911"]
    assert trouves["badge_manque"].gravite == trouves["badge_exces"].gravite == AVERTISSEMENT
    assert trouves["badge_non_juge"].gravite == INCONNU and trouves["badge_non_juge"].lots == [
        "badge V4"
    ]
    assert "1 badge(s)" in trouves["badge_sans_acces"].message
    #  Un constat de badge ne bloque rien : aucun BLOQUANT parmi eux.
    assert applicable([c for c in trouves.values() if c.gravite != INCONNU])


# ── Le journal : une porte posée par le conseil laisse sa trace ───────────────


def test_les_deux_gestes_du_parc_journalisent_ce_que_le_badge_ouvre():
    parc = pathlib.Path(__file__).resolve().parents[1] / "app/routers/acces/parc.py"
    arbre = ast.parse(parc.read_text(encoding="utf-8"))
    for nom in ("creer_acces_admin", "modifier_acces_admin"):
        fn = next(n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == nom)
        appels = {
            n.func.id
            for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "journaliser_acces" in appels, nom


def test_la_ligne_de_journal_dit_qui_et_quoi_sans_donnee_personnelle(caplog):
    import logging
    from types import SimpleNamespace

    from app.utils.acces_gestes import journaliser_acces
    from app.utils.types_acces import VIGIK

    objet = SimpleNamespace(id=7, user_id=12, perimetre_cible='["bat:1","bat:4"]', code="V9")
    with caplog.at_level(logging.INFO, logger="securite"):
        journaliser_acces(SimpleNamespace(id=3), VIGIK, objet, '["bat:1"]')
        journaliser_acces(SimpleNamespace(id=3), VIGIK, objet, objet.perimetre_cible)  # inchangé
    (ligne,) = [r for r in caplog.records if "acces_perimetre_pose" in r.getMessage()]
    assert ligne.levelno == logging.WARNING
    assert ligne.getMessage().endswith(
        "acteur=3 cible=12 type=vigik objet=7 avant=bat:1 apres=bat:1,bat:4"
    )


def test_un_badge_chez_le_locataire_ne_se_justifie_pas_par_les_autres_lots_du_bailleur(session):
    """Spec §7 : le locataire reçoit les portes des lots de son bail, jamais celles du bailleur."""
    from types import SimpleNamespace

    bailleur = _compte(session, "Arnaud")
    locataire = _compte(session, "Bernard")
    logement = _lot(session, "921", L, batiment_id=1)
    place_du_bailleur = _lot(session, "922", P, circulation="bat:4")
    _lier(session, bailleur, logement)
    _lier(session, bailleur, place_du_bailleur)
    _lier(session, locataire, logement, type_lien="locataire")

    def portes(chez_locataire, detenteur):
        badge = SimpleNamespace(
            id=1, lot_id=logement.id, user_id=detenteur.id, chez_locataire=chez_locataire
        )
        return {p.code for p in acces_portes.portes_de_badge(session, badge)}

    assert portes(False, bailleur) == {"bat:1", "bat:4"}
    assert portes(True, locataire) == {"bat:1"}
