"""Créer une copropriété dans une installation commune — la part de l'API (#2053).

- **`noms`** : la copropriété projetée est validée contre la déclaration en service ;
  un alias déjà pris est refusé, et rien n'est écrit ;
- **`ajouter`** : la base est préparée et semée AVANT que la déclaration soit écrite —
  l'API ne sert jamais une copropriété dont la base n'est pas prête ; une base qui ne
  se prépare pas laisse la déclaration intacte ;
- **de bout en bout** sur une vraie base du serveur des tests : après `ajouter`, la
  nouvelle copropriété est déclarée, sa base est servable et a son administrateur.
"""

from __future__ import annotations

import json
from argparse import Namespace

import pytest
from sqlmodel import Session, create_engine, select

from app.installation_commune import creer
from app.installation_commune.declaration import DeclarationInvalide
from app.models.core import Utilisateur
from app.utils.preparer_bases import preparer_base
from app.utils.revision_base import servable
from tests.aides_base import adresse_de_test
from tests.aides_installation_commune import ENVIRONNEMENT, installation_commune
from tests.aides_processus import SERVEUR_INJOIGNABLE


@pytest.fixture(autouse=True)
def _volume_du_conteneur(monkeypatch):
    """La racine du volume `uploads` telle que le conteneur (Linux) la voit : la
    déclaration exige un chemin absolu à sa façon, quel que soit le poste."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", "/app/uploads")


def _args(identifiant="peupliers", code_postal="33000", appellation="Les Peupliers", **autres):
    return Namespace(
        identifiant=identifiant,
        code_postal=code_postal,
        nom=appellation,
        expediteur=autres.get("expediteur", "contact@peupliers.example"),
        hote=autres.get("hote"),
    )


def test_les_noms_derivent_de_l_identifiant_seul():
    assert creer.noms_derives("bloc-2") == {
        "ROLE": "copro_bloc_2",
        "BASE": "copro_bloc_2",
        "VAR_BASE": "BLOC_2_DATABASE_URL",
        "VAR_SECRET": "BLOC_2_SECRET_KEY",
        "RACINE": "/app/uploads/bloc-2",
    }


def test_noms_refuse_un_alias_deja_pris_sans_rien_ecrire(tmp_path, monkeypatch, capsys):
    with installation_commune(tmp_path, monkeypatch) as fichier:
        avant = fichier.read_text(encoding="utf-8")
        code = creer.main(
            [
                "noms",
                "tilleuls-bis",
                "--code-postal",
                "75015",
                "--nom",
                "Les Tilleuls",
                "--expediteur",
                "x@exemple.fr",
            ]
        )
        assert code == 1
        assert "alias en double" in capsys.readouterr().out
        assert fichier.read_text(encoding="utf-8") == avant


def test_noms_rend_les_noms_et_l_adresse(tmp_path, monkeypatch, capsys):
    with installation_commune(tmp_path, monkeypatch):
        code = creer.main(
            [
                "noms",
                "peupliers",
                "--code-postal",
                "33000",
                "--nom",
                "Les Peupliers",
                "--expediteur",
                "contact@peupliers.example",
            ]
        )
    sortie = capsys.readouterr().out
    assert code == 0
    assert "VAR_BASE=PEUPLIERS_DATABASE_URL" in sortie
    assert "ADRESSE=https://33000-les-peupliers.acces.example" in sortie


def test_une_base_qui_ne_se_prepare_pas_laisse_la_declaration_intacte(tmp_path, monkeypatch):
    environnement = ENVIRONNEMENT | {
        "PEUPLIERS_DATABASE_URL": f"postgresql+psycopg://p@{SERVEUR_INJOIGNABLE}/p",
        "PEUPLIERS_SECRET_KEY": "p" * 40,
    }
    semees = []
    with installation_commune(tmp_path, monkeypatch) as fichier:
        avant = fichier.read_text(encoding="utf-8")
        with pytest.raises(DeclarationInvalide, match="non préparée"):
            creer.ajouter(
                fichier,
                creer.entree(_args()),
                environnement,
                preparer=lambda _url: "illisible",
                semer=semees.append,
            )
        assert fichier.read_text(encoding="utf-8") == avant
    assert semees == []


def test_ajouter_prepare_seme_puis_declare(tmp_path, monkeypatch):
    adresse, retirer = adresse_de_test()
    #  Un chemin ABSOLU au sens du conteneur (Linux), que la déclaration exige — sur le
    #  poste Windows, il se pose sur le disque courant.
    racine = "/" + tmp_path.as_posix().split(":", 1)[-1].lstrip("/") + "/uploads/peupliers"
    environnement = ENVIRONNEMENT | {
        "PEUPLIERS_DATABASE_URL": adresse,
        "PEUPLIERS_SECRET_KEY": "p" * 40,
    }
    try:
        with installation_commune(tmp_path, monkeypatch) as fichier:
            ordre = []

            def preparer(url):
                ordre.append(("preparer", "peupliers" in fichier.read_text(encoding="utf-8")))
                return preparer_base(url, delai=5)

            def semer(copro):
                ordre.append(("semer", "peupliers" in fichier.read_text(encoding="utf-8")))
                creer._semer(copro)

            nouvelle = creer.entree(_args())
            nouvelle["racine_fichiers"] = racine
            assert creer.ajouter(fichier, nouvelle, environnement, preparer, semer) == (
                "https://33000-les-peupliers.acces.example"
            )
            #  Préparée et semée AVANT d'être déclarée : jamais servie à moitié.
            assert ordre == [("preparer", False), ("semer", False)]
            declarees = json.loads(fichier.read_text(encoding="utf-8"))["coproprietes"]
            assert [c["identifiant"] for c in declarees][-1] == "peupliers"
            assert (tmp_path / "uploads" / "peupliers").is_dir()
        assert servable(adresse)
        moteur = create_engine(adresse)
        with Session(moteur) as s:
            assert s.exec(select(Utilisateur)).first() is not None  # son administrateur initial
        moteur.dispose()
    finally:
        retirer()
