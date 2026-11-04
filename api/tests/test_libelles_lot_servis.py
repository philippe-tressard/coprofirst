"""Les libellés d'un lot et le tableau des charges sont SERVIS par l'API (#2507).

## 🔴 Le défaut

« Mes lots & accès » composait dans le front le type (`lotTypeLabel`,
`lotTypeComplet`), le nom du lot (`nomDuLot`) et le tableau croisé des charges
(`tableauDesCharges`). L'app iOS ne recopie aucune règle du site : elle montrait
« appartement » et « local_commercial » bruts, et renvoyait au site pour ses
charges. Ces cas tiennent ce que l'API sert désormais, et la forme que le site lit.
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session

from app.models.charges import CleDeCharges, QuotePartLot
from app.models.copropriete import Lot, TypeLot
from app.models.core import RoleUtilisateur, TypeLien, UserLot
from app.utils.lecture_lots import QuotePart
from app.utils.libelles_lot import (
    libelle_type_complet,
    libelle_type_lot,
    nom_du_lot,
)
from app.utils.tableau_charges import tableau_des_charges
from tests.aides_http import base_http, client_http


#  ── lotTypeLabel → `libelle_type` ──────────────────────────────────────────


def test_un_type_inconnu_s_affiche_mis_en_forme_jamais_brut():
    """🔴 Le cas que l'app montrait : le code du type, souligné compris."""
    assert libelle_type_lot("local_commercial") == "Local commercial"


def test_les_types_du_reglement_et_l_absence():
    assert libelle_type_lot("appartement") == "Appartement"
    assert libelle_type_lot("parking") == "Parking"
    assert libelle_type_lot("cave") == "Cave"
    assert libelle_type_lot(TypeLot.appartement) == "Appartement"
    #  L'absence se dit par un tiret, jamais par une chaîne vide.
    assert libelle_type_lot(None) == "—"
    assert libelle_type_lot("") == "—"


#  ── lotTypeComplet → `libelle_type_complet` ────────────────────────────────


def test_le_type_complet_porte_la_precision_et_se_tait_sans_elle():
    assert libelle_type_complet("appartement", "T3") == "Appartement – T3"
    assert libelle_type_complet("cave", None) == "Cave"


#  ── nomDuLot → `nom_du_lot` ────────────────────────────────────────────────


def test_un_parking_se_nomme_place_et_la_nature_passe_avant_le_type():
    """🔴 « Parking 450 » n'est pas ce que dit un résident : « Place 450 »."""
    assert (
        nom_du_lot(SimpleNamespace(numero="450", nature="parking", type="parking")) == "Place 450"
    )
    assert nom_du_lot(SimpleNamespace(numero="15", nature="logement", type="appartement")) == (
        "Logement 15"
    )
    assert nom_du_lot(SimpleNamespace(numero="417", nature=None, type="cave")) == "Cave 417"


#  ── tableauDesCharges → `GET /lots/mes-charges` ────────────────────────────


def _part(cle: str, numerateur: int, appelee: bool = True) -> QuotePart:
    return QuotePart(
        cle=cle, libelle=cle.title(), numerateur=numerateur, denominateur=1000, appelee=appelee
    )


def test_le_tableau_additionne_mes_parts_par_cle_et_ecarte_les_lots_sans_part():
    """🔴 Le pivot que l'app ne pouvait pas faire : une ligne par clé, la somme des lots."""
    logement = SimpleNamespace(
        id=1, numero="15", nature="logement", type="appartement", quotes_parts=[_part("gen", 200)]
    )
    cave = SimpleNamespace(
        id=2,
        numero="417",
        nature="cave",
        type="cave",
        quotes_parts=[_part("gen", 5), _part("asc", 7, appelee=False)],
    )
    loue = SimpleNamespace(
        id=3, numero="9", nature="logement", type="appartement", quotes_parts=None
    )
    t = tableau_des_charges([logement, cave, loue])
    assert [(c.lot_id, c.nom) for c in t.colonnes] == [(1, "Logement 15"), (2, "Cave 417")]
    assert [(x.cle, x.total) for x in t.lignes] == [("gen", 205)]
    assert [(p.lot_id, p.numerateur) for p in t.lignes[0].parts] == [(1, 200), (2, 5)]
    #  Prévue au règlement, non appelée : repliée, jamais cachée.
    assert [(x.cle, x.total) for x in t.non_appelees] == [("asc", 7)]


def test_aucun_lot_lisible_rend_un_tableau_vide():
    t = tableau_des_charges([])
    assert (t.colonnes, t.lignes, t.non_appelees) == ([], [], [])


def _poser(moteur, ident: int, type_lien: TypeLien) -> int:
    with Session(moteur) as s:
        cle = CleDeCharges(code="gen", libelle="Charges générales", denominateur=1000)
        lot = Lot(numero="15", type=TypeLot.appartement, type_appartement="T3", etage=2)
        s.add_all([cle, lot])
        s.commit()
        s.add(QuotePartLot(lot_id=lot.id, cle_id=cle.id, numerateur=218))
        s.add(UserLot(user_id=ident, lot_id=lot.id, type_lien=type_lien, actif=True))
        s.commit()
        return lot.id


def test_la_route_sert_le_tableau_de_mes_lots_et_les_libelles():
    with base_http() as moteur:
        http, ident = client_http(moteur, RoleUtilisateur.résident)
        lot_id = _poser(moteur, ident, TypeLien.propriétaire)
        lots = http.get("/lots/mes-lots").json()
        charges = http.get("/lots/mes-charges").json()
    lu = lots[0]
    assert (lu["libelle_type"], lu["libelle_type_complet"], lu["etage_libelle"]) == (
        "Appartement",
        "Appartement – T3",
        "2ème",
    )
    assert lu["nom_du_lot"] == f"{lu['libelle_nature']} 15"
    assert charges["colonnes"] == [{"lot_id": lot_id, "nom": lu["nom_du_lot"]}]
    assert [(x["cle"], x["total"], x["denominateur"]) for x in charges["lignes"]] == [
        ("gen", 218, 1000)
    ]


def test_un_locataire_recoit_un_tableau_vide():
    """Ses tantièmes ne sont pas les siens (`lit_les_tantiemes`) : ni colonne ni ligne."""
    with base_http() as moteur:
        http, ident = client_http(moteur, RoleUtilisateur.résident)
        _poser(moteur, ident, TypeLien.locataire)
        charges = http.get("/lots/mes-charges").json()
    assert charges == {"colonnes": [], "lignes": [], "non_appelees": []}


def test_les_routes_de_mes_lots_sont_typees_dans_le_contrat():
    """Le contrat annonçait `{}` : le client généré de l'app ne lisait rien."""
    from app.main import app

    chemins = app.openapi()["paths"]

    def schema(chemin: str, methode: str = "get") -> dict:
        return chemins[chemin][methode]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema("/lots/mes-lots")["items"]["$ref"].endswith("/LotRead")
    assert schema("/lots/admin/tous")["items"]["$ref"].endswith("/LotRead")
    assert schema("/lots/mes-charges")["$ref"].endswith("/TableauCharges")


def test_l_etat_descriptif_sert_la_nature_en_clair_sinon_la_mention_de_l_acte():
    """L'atelier d'import montrait la nature reconnue par `lotTypeLabel`, côté écran."""
    from app.routers.lots_etat_descriptif import _ligne_lue
    from app.utils.etat_descriptif import Ligne

    ligne = Ligne(rang=1, lot="15", nature="Appart.")
    assert _ligne_lue(ligne, "logement").nature_libelle == "Logement"
    assert _ligne_lue(ligne, None).nature_libelle == "Appart."
    assert _ligne_lue(Ligne(rang=2, lot="16"), None).nature_libelle == "—"
