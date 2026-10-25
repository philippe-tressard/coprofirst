"""L'état descriptif du règlement : lecture, contrôles, application (#2213).

Tout est FICTIF : numéros de lots 9xx, lettres X et Y, tantièmes inventés. Aucun
relevé d'une copropriété réelle n'entre dans le dépôt (public).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.charges import CleDeCharges, QuotePartLot
from app.models.copropriete import Batiment, Lot, NatureLot, TypeLot
from app.models.perimetre import LotPerimetre, Perimetre
from app.utils import constats as C
from app.utils import etat_descriptif as E
from tests.aides_purge import purger_referentiellement
from app.utils.etat_descriptif_application import (
    EtatDescriptifRefuse,
    appliquer,
    constats,
    poser,
)

EN_TETES = (
    "Lot",
    "Bâtiment",
    "Nature",
    "Numéro usage",
    "Niveau",
    "Circulation desservante",
    "Lot origine",
    "Source",
    "Générales /100",
    "Ascenseur X /10",
)


def _lecture(*lignes, en_tetes=EN_TETES):
    return E.lire([en_tetes, *lignes])


def _connus(*lots):
    return [E.LotConnu(n, b, nat) for n, b, nat in lots]


# ── Lecture ──────────────────────────────────────────────────────────────────


def test_les_colonnes_se_reconnaissent_a_l_en_tete_et_les_cles_au_denominateur():
    lu = _lecture((901, "X", "Appartement", "12", "2", "X", None, None, 60, 6))
    assert [(c.code, c.denominateur) for c in lu.cles] == [("generales", 100), ("ascenseur-x", 10)]
    (ligne,) = lu.lignes
    assert (ligne.lot, ligne.batiment, ligne.circulation) == ("901", "X", "X")
    assert ligne.quotes == {"generales": 60, "ascenseur-x": 6}
    assert lu.avec_circulation


def test_une_cle_prime_est_une_autre_cle():
    """« Escalier A' » n'est pas « Escalier A » (25/10/2026) : un même code faisait
    écraser les tantièmes de l'une par l'autre, et la clé répétée figeait l'écran."""
    lu = _lecture(
        (901, "A", "Appartement", "12", "2", "A", None, None, 60, 6, 7),
        en_tetes=(*EN_TETES[:-1], "Escalier A /10", "Escalier A' /10"),
    )
    assert [c.code for c in lu.cles] == ["generales", "escalier-a", "escalier-a-prime"]
    assert lu.lignes[0].quotes == {"generales": 60, "escalier-a": 6, "escalier-a-prime": 7}
    assert not lu.erreurs
    #  Toutes les graphies du prime, et aucune autre ponctuation n'en fait un.
    for graphie in ("Escalier A’", "Escalier A′", "Escalier Aʼ"):
        assert E.code_de_cle(graphie) == "escalier-a-prime"
    assert E.code_de_cle("Escalier (A)") == "escalier-a"


def test_deux_colonnes_d_une_meme_cle_bloquent():
    lu = _lecture(
        (901, "A", "Appartement", "12", "2", "A", None, None, 60, 6, 7),
        en_tetes=(*EN_TETES[:-1], "Escalier A /10", "Escalier (A) /10"),
    )
    assert lu.erreurs == [
        "Deux colonnes désignent la même clé : « Escalier A » et « Escalier (A) »."
    ]
    assert not C.applicable(E.controler(lu, _connus(("901", 1, None)), {"A": 1}, {1}))


def test_un_fichier_sans_colonne_de_circulation_le_dit():
    """Cas zéro : il s'importe comme avant, et un constat le dit."""
    lu = E.lire([("Lot", "Nature"), ("901", "Cave")])
    assert not lu.avec_circulation
    codes = {c.code for c in E.controler(lu, _connus(("901", None, None)), {}, set())}
    assert "sans_circulation" in codes


def test_un_fichier_vide_rend_inconnu_jamais_ok():
    lu = E.lire([EN_TETES])
    trouves = E.controler(lu, [], {}, set())
    assert any(c.gravite == C.INCONNU for c in trouves)
    assert not C.applicable(trouves)


def test_mentions_de_nature_et_de_niveau():
    assert E.nature_de("T3") == NatureLot.logement
    assert E.nature_de("ps") == NatureLot.parking
    assert E.nature_de("Local commercial") == NatureLot.commerce
    assert E.nature_de("???") is None
    assert (E.niveau_de("2SS"), E.niveau_de("RDC"), E.niveau_de("-3")) == (-2, 0, -3)
    assert E.lettre_de("/") is None and E.lettre_de(" x ") == "X"


# ── Contrôles ────────────────────────────────────────────────────────────────

LETTRES = {"X": 1, "Y": 2}
AVEC_NOEUD = {1, 2}


def _fichier_juste():
    return _lecture(
        ("901", "X", "Appartement", None, "1", None, None, None, 60, 10),
        ("902", "Y", "Parking", "5 & 6", "-2", "X", None, None, 40, 0),
    )


def _app_juste():
    return _connus(("901", 1, NatureLot.logement), ("902", None, NatureLot.parking))


def test_un_fichier_juste_est_applicable():
    trouves = E.controler(_fichier_juste(), _app_juste(), LETTRES, AVEC_NOEUD)
    assert C.applicable(trouves), trouves


@pytest.mark.parametrize(
    "modifier, code",
    [
        (lambda lu, app: lu.lignes.append(lu.lignes[0]), "double_fichier"),
        (lambda lu, app: setattr(lu.lignes[1], "circulation", "Z"), "lettre"),
        (lambda lu, app: setattr(lu.lignes[0], "nature", "?"), "nature"),
        (lambda lu, app: setattr(lu.lignes[0], "batiment", "Y"), "batiment_different"),
    ],
)
def test_chaque_controle_bloquant_bloque(modifier, code):
    lu, app = _fichier_juste(), _app_juste()
    modifier(lu, app)
    trouves = E.controler(lu, app, LETTRES, AVEC_NOEUD)
    assert code in {c.code for c in trouves if c.gravite == C.BLOQUANT}
    assert not C.applicable(trouves)


@pytest.mark.parametrize(
    "modifier, code",
    [
        (lambda lu, app: lu.lignes[1].quotes.update(generales=41), "somme"),
        (lambda lu, app: app.append(E.LotConnu("903", 1, NatureLot.logement)), "absent_fichier"),
        (lambda lu, app: app.pop(), "absent_application"),
    ],
)
def test_un_fichier_incomplet_avertit_sans_bloquer(modifier, code):
    """Incomplet n'est pas faux (25/10/2026) : un règlement dont les totaux ne tombent
    pas juste, ou un lot qu'il ne cite pas, ne tenait pas l'import fermé — il le disait."""
    lu, app = _fichier_juste(), _app_juste()
    modifier(lu, app)
    trouves = E.controler(lu, app, LETTRES, AVEC_NOEUD)
    assert code in {c.code for c in trouves if c.gravite == C.AVERTISSEMENT}
    assert C.applicable(trouves), trouves


def test_l_ecart_d_une_somme_se_dit_dans_les_deux_sens():
    court, trop = _fichier_juste(), _fichier_juste()
    court.lignes[1].quotes.update(generales=38)
    trop.lignes[1].quotes.update(generales=43)
    messages = [
        next(
            c.message
            for c in E.controler(lu, _app_juste(), LETTRES, AVEC_NOEUD)
            if c.code == "somme"
        )
        for lu in (court, trop)
    ]
    assert "il en manque 2" in messages[0] and "il y en a 3 de trop" in messages[1]


def test_une_circulation_sans_noeud_bloque():
    trouves = E.controler(_fichier_juste(), _app_juste(), LETTRES, {2})
    assert "circulation_sans_noeud" in {c.code for c in trouves}


def test_une_division_sans_acte_avertit_sans_bloquer():
    """Le lot d'origine reste en historique ; ses divisions sont des lots de l'application."""
    lu = _lecture(
        ("901", "X", "Appartement", None, None, None, None, None, 60, 10),
        ("950", "Y", "Appartement", None, None, None, None, None, 40, 0),
        ("951", "Y", "Appartement", None, None, None, "950", None, None, None),
        ("952", "Y", "Appartement", None, None, None, "950", "acte du 01/01/2020", None, None),
    )
    app = _connus(
        ("901", 1, NatureLot.logement),
        ("951", 2, NatureLot.logement),
        ("952", 2, NatureLot.logement),
    )
    trouves = E.controler(lu, app, LETTRES, AVEC_NOEUD)
    assert C.applicable(trouves), trouves
    par_code = {c.code: c for c in trouves}
    assert par_code["division_sans_acte"].lots == ["951"]
    assert par_code["divise"].lots == ["950"]


# ── Application ──────────────────────────────────────────────────────────────


def _monter(session, batiments):
    #  Le contrôle confronte le fichier à TOUS les lots en base : ceux qu'un test
    #  précédent aurait laissés feraient un « lot absent du fichier ». Ce test pose
    #  donc lui-même le patrimoine qu'il contrôle.
    purger_referentiellement(session, Lot)
    b1, b2 = (session.get(Batiment, i) for i in batiments[:2])
    b1.lettre_rcp, b2.lettre_rcp = "X", "Y"
    lots = [
        Lot(numero="901", batiment_id=b1.id, type=TypeLot.appartement),
        #  La liste du syndic rattachait la cave au bâtiment de son propriétaire (X).
        Lot(numero="902", batiment_id=b1.id, type=TypeLot.cave),
        Lot(numero="903", batiment_id=None, type=TypeLot.parking),
    ]
    session.add_all([b1, b2, *lots])
    session.flush()
    return b1, b2, lots


def _rows():
    return [
        EN_TETES,
        ("901", "X", "T2", None, "1", None, None, None, 50, 4),
        ("902", "Y", "Cave", "C7", "-1", "Y", None, None, 20, 0),
        ("903", None, "Parking", "5 & 6", "-2", "X", None, None, 30, 6),
    ]


def test_appliquer_pose_la_desserte_les_tantiemes_et_les_perimetres(batiments):
    with Session(engine) as session:
        b1, b2, (logement, cave, place) = _monter(session, batiments)
        poser(session, _rows())
        bilan = appliquer(session)
        session.flush()

        assert bilan["lots"] == 3 and bilan["cles_creees"] == 2
        #  La cave est située dans SON bâtiment et desservie par sa circulation —
        #  plus par le bâtiment de son propriétaire.
        assert cave.batiment_id == b2.id and cave.nature == NatureLot.cave
        assert place.numero_usage == "5 & 6" and place.etage == -2
        noeud_x = session.exec(select(Perimetre).where(Perimetre.code == f"bat:{b1.id}")).one()
        assert place.circulation_perimetre_id == noeud_x.id
        parts = {
            (p.lot_id, c.code): p.numerateur
            for p, c in session.exec(
                select(QuotePartLot, CleDeCharges).join(
                    CleDeCharges, CleDeCharges.id == QuotePartLot.cle_id
                )
            ).all()
        }
        assert parts[(place.id, "ascenseur-x")] == 6
        assert (cave.id, "ascenseur-x") not in parts, "une cellule vide ne pose pas de part"
        desservi = {
            p.code
            for lp, p in session.exec(
                select(LotPerimetre, Perimetre)
                .join(Perimetre, Perimetre.id == LotPerimetre.perimetre_id)
                .where(LotPerimetre.lot_id == place.id)
            ).all()
        }
        assert f"bat:{b1.id}/ascenseur" in desservi and f"bat:{b1.id}" not in desservi

        #  Rejouer le même fichier : rien en double, rien à changer.
        poser(session, _rows())
        rejoue = appliquer(session)
        assert rejoue["cles_creees"] == 0 and rejoue["quotes_modifiees"] == 0
        assert len(session.exec(select(CleDeCharges)).all()) == 2
        session.rollback()


def test_la_lecture_d_un_lot_dit_ses_parts_leurs_totaux_et_ce_qu_il_faut_savoir(batiments):
    """Après l'application : chaque part porte le nombre de lots de la clé et sa somme ; une
    clé qui ne tombe plus juste devient une alerte sur les lots qui y contribuent."""
    from app.utils.lecture_lots import designations

    with Session(engine) as session:
        _, _, (logement, cave, place) = _monter(session, batiments)
        poser(session, _rows())
        appliquer(session)
        session.flush()

        lues = designations(session, [logement, cave, place], lambda _lot: True)
        ascenseur = next(q for q in lues[place.id].quotes_parts if q.cle == "ascenseur-x")
        assert (ascenseur.numerateur, ascenseur.nb_lots, ascenseur.somme) == (6, 2, 10)
        assert all(not lues[lot.id].alertes for lot in (logement, cave, place)), (
            "le fichier tombe juste"
        )

        #  Une part corrigée à la main : la clé ne totalise plus son dénominateur.
        part = session.exec(
            select(QuotePartLot).where(QuotePartLot.lot_id == place.id).order_by(QuotePartLot.id)
        ).all()[-1]
        part.numerateur = 5
        session.add(part)
        session.flush()
        apres = designations(session, [logement, place], lambda _lot: True)
        #  L'écart se dit sous la clé (#2251), plus en alerte du lot.
        assert not apres[place.id].alertes
        notes = [q.note for q in apres[place.id].quotes_parts if q.note]
        assert len(notes) == 1 and "il en manque 1" in notes[0]
        #  Un lecteur qui ne voit pas les tantièmes n'en lit pas non plus les écarts.
        sans = designations(session, [place], lambda _lot: False)
        assert sans[place.id].quotes_parts is None and not sans[place.id].alertes
        session.rollback()


# ── Ce que finance une clé (#2251) ────────────────────────────────────────────


def test_la_feuille_cles_dit_ce_que_finance_chaque_cle():
    feuille = [
        ("clé", "ce qu'elle finance"),
        ("Ascenseur X", "L'ascenseur du bâtiment X"),
        ("Escalier X'", "L'escalier qui dessert les deux niveaux de sous-sol"),
        ("Générales", None),  # une ligne sans texte ne pose rien
    ]
    lues = E.lire_descriptions(feuille)
    assert lues == {
        "ascenseur-x": "L'ascenseur du bâtiment X",
        "escalier-x-prime": "L'escalier qui dessert les deux niveaux de sous-sol",
    }
    lu = E.lire([EN_TETES], lues)
    assert [c.description for c in lu.cles] == [None, "L'ascenseur du bâtiment X"]
    #  Une feuille absente, ou sans les deux colonnes, ne rend rien : c'est facultatif.
    assert E.lire_descriptions(None) == {} and E.lire_descriptions([("a", "b")]) == {}


def test_la_feuille_cles_se_lit_dans_le_classeur_a_cote_de_la_premiere():
    import io

    import openpyxl

    from app.utils.import_xlsx import feuille_du_classeur, lignes_du_classeur

    classeur = openpyxl.Workbook()
    classeur.active.append(list(EN_TETES))
    classeur.create_sheet("Clés").append(["clé", "ce qu'elle finance"])
    tampon = io.BytesIO()
    classeur.save(tampon)
    contenu = tampon.getvalue()
    assert lignes_du_classeur(contenu)[0][0] == "Lot"
    assert feuille_du_classeur(contenu, E.FEUILLE_CLES) == [("clé", "ce qu'elle finance")]
    assert feuille_du_classeur(contenu, "Absente") is None


def test_appliquer_pose_la_description_et_un_fichier_sans_feuille_ne_l_efface_pas(batiments):
    with Session(engine) as session:
        _monter(session, batiments)
        poser(session, _rows(), {"ascenseur-x": "L'ascenseur du bâtiment X"})
        appliquer(session)
        session.flush()
        cle = session.exec(select(CleDeCharges).where(CleDeCharges.code == "ascenseur-x")).one()
        assert cle.description == "L'ascenseur du bâtiment X"
        poser(session, _rows())
        appliquer(session)
        session.flush()
        session.refresh(cle)
        assert cle.description == "L'ascenseur du bâtiment X"
        session.rollback()


def test_un_reimport_garde_ce_que_le_conseil_a_regle_sur_une_cle(batiments):
    """Appelée ou non, libellé de l'appel de fonds : le conseil les règle, l'acte ne les dit
    pas — un réimport de l'état descriptif ne les remet pas à zéro (#2252)."""
    with Session(engine) as session:
        _monter(session, batiments)
        poser(session, _rows())
        appliquer(session)
        session.flush()
        cle = session.exec(select(CleDeCharges).where(CleDeCharges.code == "ascenseur-x")).one()
        assert cle.appelee is True and cle.libelle_syndic is None, "défaut : appelée, sans libellé"
        cle.appelee, cle.libelle_syndic = False, "ASCENSEUR BAT X"
        session.add(cle)
        session.flush()
        poser(session, _rows())
        appliquer(session)
        session.flush()
        session.refresh(cle)
        assert (cle.appelee, cle.libelle_syndic) == (False, "ASCENSEUR BAT X")
        session.rollback()


def test_appliquer_refuse_un_fichier_bloque_et_n_ecrit_rien(batiments):
    with Session(engine) as session:
        _, _, (logement, cave, place) = _monter(session, batiments)
        rows = _rows()
        rows[1] = ("901", "X", "???", None, "1", None, None, None, 51, 4)  # nature illisible
        imp = poser(session, rows)
        _, trouves = constats(session, imp)
        assert "nature" in {c.code for c in trouves}
        with pytest.raises(EtatDescriptifRefuse):
            appliquer(session)
        assert cave.nature is None and not session.exec(select(CleDeCharges)).all()
        session.rollback()


def test_un_fichier_range_avec_un_code_repete_se_rend_et_demande_un_reimport(batiments):
    """Le fichier rangé en production le 25/10/2026, quand « Escalier A' » prenait le
    code d'« Escalier A » : ses clés reprennent un code unique, et un bloquant dit de
    le réimporter — l'écran se rend au lieu de se figer sur une clé répétée."""
    import json

    with Session(engine) as session:
        _monter(session, batiments)
        imp = poser(session, _rows())
        entete = json.loads(imp.entete_json)
        entete["cles"][1]["libelle"] = "Ascenseur X'"  # code resté « ascenseur-x »
        imp.entete_json = json.dumps(entete)
        lecture, trouves = constats(session, imp)
        assert [c.code for c in lecture.cles] == ["generales", "ascenseur-x-prime"]
        assert any("importez-le de nouveau" in c.message for c in trouves)
        assert not C.applicable(trouves)
        session.rollback()


def test_la_route_d_application_refuse_en_409_et_le_gabarit_se_telecharge(batiments):
    from fastapi.testclient import TestClient

    from app.auth.deps import require_cs_or_admin
    from app.main import app

    app.dependency_overrides[require_cs_or_admin] = lambda: None
    try:
        client = TestClient(app)
        reponse = client.get("/lots/admin/etat-descriptif/gabarit")
        assert reponse.status_code == 200
        assert reponse.content[:2] == b"PK"  # un classeur xlsx est une archive zip
        assert client.get("/lots/admin/etat-descriptif").json()["applicable"] is False
        assert client.post("/lots/admin/etat-descriptif/appliquer").status_code == 409
    finally:
        app.dependency_overrides.pop(require_cs_or_admin, None)


def test_chaque_route_de_l_atelier_exige_le_conseil_ou_l_administration():
    """`routers/lots_etat_descriptif` : aucune route sans `require_cs_or_admin`."""
    from fastapi.routing import APIRoute

    from app.auth.deps import require_cs_or_admin
    from app.routers.lots_etat_descriptif import router

    routes = [r for r in router.routes if isinstance(r, APIRoute)]
    assert len(routes) == 6, "une route ajoutée ou retirée : relire ce test"
    for route in routes:
        appels = {d.call for d in route.dependant.dependencies}
        assert require_cs_or_admin in appels, route.path


def test_un_resident_est_refuse(batiments):
    from fastapi.testclient import TestClient

    from app.auth.deps import get_current_user
    from app.main import app
    from app.models.core import StatutUtilisateur
    from tests.aides_base import compte

    with Session(engine) as session:
        resident = compte(session, statut=StatutUtilisateur.copropriétaire_résident)
    app.dependency_overrides[get_current_user] = lambda: resident
    try:
        reponse = TestClient(app).post("/lots/admin/etat-descriptif/appliquer")
        assert reponse.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
