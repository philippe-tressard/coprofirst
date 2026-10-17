"""Les alias et le registre des copropriétés d'une installation commune (#1894).

Spec `specs/architecture/multi-coproprietes.md` §4.1 bis et §4.2. Ce que ce fichier
tient :

- l'alias est `code postal` + nom NORMALISÉS (accents, casse, ponctuation, espaces →
  tiret), jamais de `_`, et forme toujours un nom d'hôte valide sous l'hôte commun ;
- il est UNIQUE dans l'installation, anciens alias compris : un doublon est refusé
  dès la déclaration ;
- l'adresse dérivée `<alias>.<hôte commun>` désigne la copropriété au même titre que
  son propre domaine ; l'hôte commun et les anciens alias n'en désignent aucune ;
- une déclaration qui ne peut pas servir ne sert RIEN — jamais un repli.
"""

from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient

from app import contexte
from app.installation_commune.alias import alias_de, est_alias, est_nom_d_hote
from app.installation_commune.declaration import DeclarationInvalide, lire
from app.main import app as application
from tests.aides_installation_commune import (
    COPROPRIETES,
    ENVIRONNEMENT,
    HOTE_COMMUN,
    installation_commune,
)

ORIGINE = f"https://{HOTE_COMMUN}"


# ── L'alias ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("code_postal", "nom", "attendu"),
    [
        ("75015", "Les Tilleuls", "75015-les-tilleuls"),
        ("75015", "  les   tilleuLS  ", "75015-les-tilleuls"),
        ("69003", "Résidence des Chênes", "69003-residence-des-chenes"),
        ("13001", "L'Étang_du Moulin (bât. A)", "13001-l-etang-du-moulin-bat-a"),
        ("20000", "Œuvre — Cœur", "20000-uvre-cur"),
    ],
)
def test_l_alias_normalise_code_postal_et_nom(code_postal, nom, attendu):
    assert alias_de(code_postal, nom) == attendu


@pytest.mark.parametrize(
    ("code_postal", "nom"),
    [
        ("7501", "Les Tilleuls"),
        ("750150", "X"),
        ("ABCDE", "X"),
        ("75015", "  "),
        ("75015", "…"),
        ("75015", "x" * 80),
    ],
)
def test_ce_qui_ne_forme_pas_un_alias_ne_forme_rien(code_postal, nom):
    assert alias_de(code_postal, nom) is None


@pytest.mark.parametrize(
    "nom",
    ["Les Tilleuls", "Résidence_des_Chênes", "A.B/C\\D", "Ça & là !", "x" * 57, "ÿ-ŷ-ž 2"],
)
def test_un_alias_forme_toujours_un_nom_d_hote_valide(nom):
    alias = alias_de("75015", nom)
    assert alias is not None and "_" not in alias
    assert est_nom_d_hote(f"{alias}.{HOTE_COMMUN}")


@pytest.mark.parametrize(
    "hote",
    [
        "a_b.example",
        "10.0.0.1",
        "localhost",
        "-a.example",
        "a-.example",
        "a..example",
        "A.example",
        f"{'a' * 64}.example",
        "",
    ],
)
def test_un_nom_d_hote_invalide_est_refuse(hote):
    assert not est_nom_d_hote(hote)


def test_un_alias_commence_par_le_code_postal():
    assert est_alias("75015-les-tilleuls")
    assert not est_alias("registre") and not est_alias("www") and not est_alias("75015")


# ── La déclaration ───────────────────────────────────────────────────────────


def _lire(coproprietes, origine=ORIGINE, env=None):
    return lire(json.dumps({"coproprietes": coproprietes}), origine, env or ENVIRONNEMENT)


def _avec(index, **champs):
    coproprietes = copy.deepcopy(COPROPRIETES)
    coproprietes[index].update(champs)
    return coproprietes


def test_une_declaration_valide_se_lit_en_entier():
    commune = _lire(COPROPRIETES)
    assert commune.hote_commun == HOTE_COMMUN
    assert [e.alias for e in commune.entrees] == [
        "75015-les-tilleuls",
        "69003-residence-des-chenes",
        "13001-les-erables",
    ]
    tilleuls = commune.entrees[0]
    assert tilleuls.copropriete.secret == ENVIRONNEMENT["TILLEULS_SECRET"]
    assert commune.adresse(tilleuls) == "https://75015-les-tilleuls.acces.example"
    assert commune.adresse(commune.entrees[1]) == "https://residence-chenes.example"


def test_les_alias_de_la_declaration_sont_uniques_et_forment_des_noms_d_hote():
    """Le garde-fou demandé par le ticket, sur la déclaration elle-même."""
    commune = _lire(COPROPRIETES)
    tous = [a for e in commune.entrees for a in (e.alias, *e.anciens_alias)]
    assert len(tous) == len(set(tous)) > 0
    assert all(est_nom_d_hote(f"{a}.{commune.hote_commun}") for a in tous)


@pytest.mark.parametrize(
    ("coproprietes", "motif"),
    [
        (_avec(1, **{"code_postal": "75015", "nom": "les  TilLeuls"}), "alias en double"),
        (_avec(1, anciens_alias=["75015-les-tilleuls"]), "alias en double"),
        (_avec(1, identifiant="tilleuls"), "identifiant en double"),
        (_avec(0, identifiant="principale"), "réservé"),
        (_avec(0, identifiant="Tilleuls_1"), "Identifiant invalide"),
        (_avec(0, code_postal="7501"), "alias valide"),
        (_avec(0, anciens_alias=["tilleuls"]), "ancien alias invalide"),
        (_avec(1, hotes=["residence_chenes.example"]), "nom d'hôte refusé"),
        (_avec(1, hotes=[HOTE_COMMUN]), "nom d'hôte refusé"),
        (_avec(1, hotes=[f"75015-les-tilleuls.{HOTE_COMMUN}"]), "nom d'hôte refusé"),
        (_avec(1, hotes=["residence-chenes.example"], racine_fichiers="relatif"), "chemin absolu"),
        (_avec(2, racine_fichiers="/srv/uploads/tilleuls"), "racine des fichiers en double"),
        (_avec(0, base="ABSENTE"), "absente ou vide"),
        (_avec(0, secret="minuscule"), "absente ou vide"),
        (_avec(0, base="CHENES_BASE"), "base en double"),
        (_avec(0, expediteur="personne"), "expéditeur invalide"),
        ([], "Aucune copropriété"),
    ],
)
def test_une_regle_violee_refuse_toute_la_declaration(coproprietes, motif):
    with pytest.raises(DeclarationInvalide, match=motif):
        _lire(coproprietes)


def test_un_secret_faible_est_refuse_sans_etre_cite():
    env = {**ENVIRONNEMENT, "TILLEULS_SECRET": "court-et-devinable"}
    with pytest.raises(DeclarationInvalide) as refus:
        _lire(COPROPRIETES, env=env)
    assert "32 caractères" in str(refus.value)
    assert "court-et-devinable" not in str(refus.value)


def test_un_champ_inconnu_est_refuse_sans_citer_sa_valeur():
    with pytest.raises(DeclarationInvalide) as refus:
        _lire(_avec(0, mot_de_passe="ne-pas-citer"))
    assert "ne-pas-citer" not in str(refus.value)


@pytest.mark.parametrize("origine", ["http://10.0.0.5", "http://localhost", "https://acces"])
def test_l_hote_commun_doit_etre_un_nom_de_domaine(origine):
    with pytest.raises(DeclarationInvalide, match="ORIGIN"):
        _lire(COPROPRIETES, origine=origine)


# ── La résolution (#1751) ────────────────────────────────────────────────────


def test_l_adresse_derivee_designe_la_copropriete(tmp_path, monkeypatch):
    with installation_commune(tmp_path, monkeypatch):
        de = contexte.copropriete_de_l_hote
        assert de(f"75015-les-tilleuls.{HOTE_COMMUN}").identifiant == "tilleuls"
        assert de(f"75015-Les-Tilleuls.{HOTE_COMMUN}:443").identifiant == "tilleuls"
        assert de(f"69003-residence-des-chenes.{HOTE_COMMUN}").identifiant == "chenes"
        assert de("residence-chenes.example").identifiant == "chenes"
        assert len(contexte.coproprietes()) == 3


@pytest.mark.parametrize(
    "hote",
    [
        HOTE_COMMUN,
        f"75015-tilleuls.{HOTE_COMMUN}",
        f"99999-inconnue.{HOTE_COMMUN}",
        "localhost",
        "10.0.0.23",
        "api",
        f"75015-les-tilleuls.{HOTE_COMMUN}.evil.example",
    ],
)
def test_ni_l_hote_commun_ni_un_ancien_alias_ne_designent_une_copropriete(
    tmp_path, monkeypatch, hote
):
    with installation_commune(tmp_path, monkeypatch):
        assert contexte.copropriete_de_l_hote(hote) is None


def test_chaque_copropriete_sert_sa_base_et_son_secret(tmp_path, monkeypatch):
    with installation_commune(tmp_path, monkeypatch):
        copro = contexte.copropriete_de_l_hote(f"75015-les-tilleuls.{HOTE_COMMUN}")
        assert copro.url_base == ENVIRONNEMENT["TILLEULS_BASE"]
        assert copro.secret == ENVIRONNEMENT["TILLEULS_SECRET"]
        assert str(copro.racine_fichiers).replace("\\", "/") == "/srv/uploads/tilleuls"


def test_une_installation_propre_ne_lit_aucune_declaration():
    """Cas zéro du mode : sans fichier, la seule copropriété de la configuration."""
    assert [c.identifiant for c in contexte.coproprietes()] == [contexte.IDENTIFIANT_UNIQUE]


def test_une_declaration_invalide_ne_sert_rien(tmp_path, monkeypatch):
    """Tout ou rien : 503 partout, jamais la copropriété de la configuration en repli."""
    with installation_commune(tmp_path, monkeypatch, coproprietes=_avec(0, base="ABSENTE")):
        client = TestClient(application)
        for hote in (HOTE_COMMUN, f"75015-les-tilleuls.{HOTE_COMMUN}", "testserver"):
            assert client.get("/config", headers={"host": hote}).status_code == 503
        assert client.get("/health", headers={"host": HOTE_COMMUN}).status_code == 200


def test_un_fichier_declare_mais_absent_ne_sert_rien(tmp_path, monkeypatch):
    with installation_commune(tmp_path, monkeypatch) as fichier:
        fichier.unlink()
        with pytest.raises(DeclarationInvalide):
            contexte.coproprietes()


# ── La vérification avant mise en service ────────────────────────────────────


def test_la_verification_liste_les_adresses_sans_aucun_secret(tmp_path, monkeypatch, capsys):
    from app.installation_commune import verifier

    with installation_commune(tmp_path, monkeypatch):
        assert verifier.main() == 0
    sortie = capsys.readouterr().out
    assert f"adresse https://75015-les-tilleuls.{HOTE_COMMUN}" in sortie
    assert "erables (SUSPENDUE)" in sortie
    assert not any(valeur in sortie for valeur in ENVIRONNEMENT.values())


def test_la_verification_dit_la_regle_violee(tmp_path, monkeypatch, capsys):
    from app.installation_commune import verifier

    with installation_commune(tmp_path, monkeypatch, coproprietes=_avec(0, base="ABSENTE")):
        assert verifier.main() == 1
    assert "absente ou vide" in capsys.readouterr().out


def test_la_verification_n_a_rien_a_dire_d_une_installation_propre():
    from app.installation_commune import verifier

    assert verifier.main() == 2
