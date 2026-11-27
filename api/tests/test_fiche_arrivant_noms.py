"""Un nom de la fiche d'accueil s'écrit en entier, sur une ligne, ou le dit (#3144, #3151).

## Pourquoi

En quatre colonnes, un nom de vingt-trois caractères passait à la ligne en 14,5 px :
le document remis à l'arrivant montrait le prénom sur une ligne et le nom sur la
suivante. La taille se décide donc avant d'écrire le document, en mesurant chaque
nom dans la police embarquée (`fiche_arrivant_noms`). Ces tests tiennent la règle
arbitrée — une taille pour tous les noms du document, conseil et syndic, photo
comprise ; un nom toujours entier ; le passage à la ligne plutôt qu'un nom coupé — et
le fait que la mesure lit bien la police. De #3144 à #3151, un nom que la photo
serrait abrégeait son prénom à l'initiale, et le syndic avait sa propre taille.
"""

from __future__ import annotations

import re

import pytest

from app.utils import fiche_arrivant_noms as noms
from app.utils.fiche_arrivant import generer_fiche_arrivant
from app.utils.fiche_arrivant_css import ECART_CARTES_PX, PHOTO_ECART_PX, PHOTO_PX, place_nom

PLACE_4 = place_nom(4, ecart=ECART_CARTES_PX)


def _membre(prenom: str, nom: str, batiment_id: int, **k) -> dict:
    return {
        "genre": "M.",
        "prenom": prenom,
        "nom": nom,
        "batiment_id": batiment_id,
        "etage": 2,
        **k,
    }


def _fiche(membres: list[dict], syndic: list[dict] | None = None) -> str:
    return generer_fiche_arrivant(
        cs_data={"membres": membres},
        syndic_data={
            "nom_syndic": "Syndic Témoin",
            "adresse": "1 rue Témoin",
            "membres": syndic or [],
        },
        site_nom="Résidence Témoin",
        site_url="https://residence.example",
        logo_png=None,
        consignes=[],
    )


def _noms_rendus(html: str) -> list[tuple[str, str]]:
    return re.findall(r'<div class="(membre-nom(?: long)?)">(?:<img[^>]*>)?([^<]*)</div>', html)


# ── La mesure lit la police ───────────────────────────────────────────────────


def test_la_mesure_lit_la_police_embarquee():
    """Sans la police, la mesure retombe sur une estimation : ce test le verrait."""
    assert noms._metriques() is not None, "police de mesure illisible : les noms sont estimés"
    #  Atkinson n'est pas à chasse fixe : un « i » est plus étroit qu'un « M ».
    assert noms.largeur("iiii", 10) < noms.largeur("MMMM", 10)


def test_la_largeur_est_proportionnelle_a_la_taille():
    assert noms.largeur("M. Jean EXEMPLE", 20) == pytest.approx(
        2 * noms.largeur("M. Jean EXEMPLE", 10)
    )


def test_la_place_d_une_carte_suit_la_feuille():
    """Quatre colonnes sur A4 moins les marges : un peu moins de 160 px par nom."""
    assert 150 < PLACE_4 < 165
    assert place_nom(1, ecart=ECART_CARTES_PX) > 3 * PLACE_4


# ── La règle : taille commune, nom entier, ligne autorisée ────────────────────


def test_des_noms_courts_gardent_le_plafond():
    assert noms.taille_commune([("M. Paul FICTIF", PLACE_4)]) == noms.PLAFOND


def test_la_taille_commune_est_celle_du_plus_long_et_il_tient():
    longs = [("M. Paul FICTIF", PLACE_4), ("Mme Christine EXEMPLE", PLACE_4)]
    taille = noms.taille_commune(longs)
    assert noms.PLANCHER <= taille < noms.PLAFOND
    assert noms.largeur("Mme Christine EXEMPLE", taille) <= PLACE_4
    assert noms.largeur("Mme Christine EXEMPLE", taille + 0.2) > PLACE_4 - 1, "taille sous-estimée"


def test_la_taille_ne_descend_jamais_sous_le_plancher():
    assert (
        noms.taille_commune([("M. Jean-Christophe DE LA FONTAINE-TÉMOIN", PLACE_4)])
        == noms.PLANCHER
    )


def test_un_nom_qui_tient_reste_entier():
    assert noms.poser("M.", "Paul", "Fictif", 14.5, PLACE_4) == ("M. Paul FICTIF", True)


def test_un_nom_qui_deborde_reste_entier_et_le_dit():
    pose = noms.poser("M.", "Jean-Christophe", "Martineau", 14.5, PLACE_4)
    assert pose == ("M. Jean-Christophe MARTINEAU", False)


def test_un_nom_trop_long_passe_a_la_ligne_plutot_que_d_etre_coupe():
    pose = noms.poser("Mme", "Anne", "Martin-Leroy Durandal Martineau", 12.5, PLACE_4)
    assert pose.tient is False
    assert pose.texte == "Mme Anne MARTIN-LEROY DURANDAL MARTINEAU", "le nom est tronqué"


# ── Ce que la fiche en fait ───────────────────────────────────────────────────


def test_la_fiche_porte_la_taille_commune_et_l_annonce_au_document():
    fiche = _fiche(
        [_membre("Paul", "Fictif", b) for b in (1, 2, 3)] + [_membre("Christine", "Exemplaire", 4)]
    )
    tailles = [float(t) for t in re.findall(r"--taille-nom: ([\d.]+)px", fiche)]
    assert tailles and all(noms.PLANCHER <= t <= noms.PLAFOND for t in tailles)


def test_un_nom_trop_long_porte_la_classe_qui_autorise_la_ligne():
    fiche = _fiche([_membre("Marie", "De La Fontaine-Témoin-Exemplaire", b) for b in (1, 2, 3, 4)])
    assert all(classe == "membre-nom long" for classe, _ in _noms_rendus(fiche))


def test_le_nom_est_echappe():
    fiche = _fiche([_membre("<b>", "<script>x</script>", 1)])
    assert "<script>x" not in fiche and "&lt;SCRIPT&gt;" in fiche


# ── Le conseil : nom, étage, vignette ─────────────────────────────────────────


def test_un_membre_s_ecrit_en_trois_lignes_nom_etage_vignette():
    fiche = _fiche([_membre("Paul", "Fictif", 1, etage=3, est_president=True)])
    corps = fiche.split('<div class="membre">', 1)[1]
    nom, etage, vignette = (
        corps.index(x) for x in ("FICTIF", "3ème étage", 'class="vignette">Président')
    )
    assert nom < etage < vignette


def test_le_rez_de_chaussee_reste_lisible():
    fiche = _fiche([_membre("Paul", "Fictif", 1, etage=0)])
    assert '<div class="membre-detail">RDC</div>' in fiche


# ── Le syndic : la fonction en bandeau, l'interlocuteur principal en vignette ──


def _contact(prenom: str, nom: str, fonction: str | None, principal: bool = False) -> dict:
    return {
        "genre": "Mme",
        "prenom": prenom,
        "nom": nom,
        "fonction": fonction,
        "est_principal": principal,
    }


def test_la_fonction_est_dans_le_bandeau_et_le_principal_en_vignette():
    fiche = _fiche(
        [],
        [
            _contact("Anne", "Essai", "Gestionnaire de copropriétés", True),
            _contact("Paul", "Fictif", "Comptable"),
        ],
    )
    assert re.findall(r'<div class="bat-label">([^<]*)</div>', fiche) == [
        "Gestionnaire de copropriétés",
        "Comptable",
    ]
    assert fiche.count("Interlocuteur principal") == 1
    assert "★" not in fiche


def test_un_contact_sans_fonction_a_quand_meme_un_bandeau():
    fiche = _fiche([], [_contact("Anne", "Essai", None, True), _contact("Paul", "Fictif", None)])
    assert re.findall(r'<div class="bat-label">([^<]*)</div>', fiche) == ["Gestionnaire", "Contact"]


def test_le_cabinet_monte_dans_le_titre_echappe():
    fiche = generer_fiche_arrivant(
        cs_data={"membres": []},
        syndic_data={
            "nom_syndic": "<i>Cabinet</i>",
            "adresse": "1 rue <b>Témoin</b>",
            "membres": [],
        },
        site_nom="Résidence Témoin",
        site_url="https://residence.example",
        logo_png=None,
        consignes=[],
    )
    titre = fiche.split("🏛 Syndic</h3>", 1)[1].split("</div>", 1)[0]
    assert "&lt;i&gt;Cabinet&lt;/i&gt;" in titre and "1 rue &lt;b&gt;Témoin&lt;/b&gt;" in titre


# ── Un nom entier, une taille pour tout le document (#3151) ───────────────────


def _fiche_avec_photo(monkeypatch) -> tuple[str, list[dict], list[dict]]:
    """Le conseil sur quatre bâtiments, le gestionnaire du site avec sa photo, et un
    syndic aux noms courts : le cas où v3.127.0 abrégeait le prénom du gestionnaire
    et imprimait le syndic plus gros que le conseil."""
    monkeypatch.setattr(
        "app.utils.fiche_arrivant._photo_data_uri", lambda _url: "data:image/png;base64,AA=="
    )
    membres = [
        _membre("Christine", "Exemple", 1),
        _membre("Christine", "Exemple", 2, est_gestionnaire_site=True, photo_url="/p.png"),
        #  Le plus long du conseil : sans photo, il le faisait déjà passer sous le
        #  plafond, quand le syndic restait à 14,5 px.
        _membre("Christine", "Exemplaire", 3),
        _membre("Paul", "Fictif", 4),
    ]
    syndic = [_contact("Anne", "Essai", "Gestionnaire", True), _contact("Paul", "Fictif", None)]
    return _fiche(membres, syndic), membres, syndic


def test_aucun_prenom_n_est_reduit_a_son_initiale(monkeypatch):
    """Chaque nom s'imprime en entier, prénom compris, photo ou non — et sur une ligne."""
    fiche, membres, syndic = _fiche_avec_photo(monkeypatch)
    attendus = [noms.nom_complet(m["genre"], m["prenom"], m["nom"]) for m in membres + syndic]
    rendus = _noms_rendus(fiche)
    assert [texte for _, texte in rendus] == attendus, "un prénom a été abrégé"
    assert all(classe == "membre-nom" for classe, _ in rendus), "un nom passe sur deux lignes"


def test_le_conseil_et_le_syndic_ont_une_seule_taille_de_nom(monkeypatch):
    """Une taille pour tous les noms du document, et c'est celle où le plus contraint
    — le nom que la photo serre — tient encore."""
    fiche, _, _ = _fiche_avec_photo(monkeypatch)
    tailles = {float(t) for t in re.findall(r"--taille-nom: ([\d.]+)px", fiche)}
    assert len(tailles) == 1, f"plusieurs tailles de nom sur la fiche : {sorted(tailles)}"
    (taille,) = tailles
    place_photo = PLACE_4 - PHOTO_PX - PHOTO_ECART_PX
    assert noms.largeur("M. Christine EXEMPLE", taille) <= place_photo - 1, "la photo est oubliée"
