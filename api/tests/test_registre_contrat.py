"""Le contrat de données du registre et ses conditions (R0 #1876, R1 #1877, spec §4.11).

- chaque champ du contrat dit sa FINALITÉ ;
- aucune donnée de résident : les seules données personnelles sont celles de
  l'administrateur de l'installation, DÉCLARÉES (`personnel=True`) ;
- un champ inconnu est refusé ;
- chaque version des conditions porte l'empreinte qui la fige ;
- les tables du registre ne sont pas celles de la résidence.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError
from sqlmodel import SQLModel

from app.registre import conditions, contrat
from app.registre.modeles import registre_plateforme

#: Des noms de champ qui désignent une PERSONNE. Hors de l'administrateur, ils
#: diraient qu'une donnée de résident part chez la référence (D5).
NOMS_PERSONNELS = {"prenom", "courriel", "email", "telephone", "adresse", "ip", "naissance"}

#: Les champs `nom` admis hors de l'administrateur, avec ce qu'ils nomment.
NOMS_QUI_NE_SONT_PAS_DES_PERSONNES = {
    ("CoproprieteRapport", "nom"): "le nom d'une copropriété",
}


def _champs():
    for schema in contrat.SCHEMAS:
        for nom, champ in schema.model_fields.items():
            yield schema, nom, champ


def test_le_contrat_n_est_pas_vide():
    """Cas zéro : un contrat sans champ rendrait les contrôles suivants verts pour rien."""
    assert len(list(_champs())) > 30


@pytest.mark.parametrize(
    "schema,nom,champ", list(_champs()), ids=lambda x: getattr(x, "__name__", x)
)
def test_chaque_champ_dit_sa_finalite(schema, nom, champ):
    assert (champ.description or "").strip(), f"{schema.__name__}.{nom} : finalité absente"


def test_les_donnees_personnelles_sont_celles_de_l_administrateur_seul():
    personnels = {
        (schema.__name__, nom)
        for schema, nom, champ in _champs()
        if (champ.json_schema_extra or {}).get("personnel")
    }
    #  Témoin : l'administrateur en déclare bien.
    assert ("AdministrateurInstallation", "courriel") in personnels
    assert {s for s, _ in personnels} == {"AdministrateurInstallation"}


def test_aucun_champ_hors_administrateur_ne_designe_une_personne():
    fautifs = [
        f"{schema.__name__}.{nom}"
        for schema, nom, _ in _champs()
        if schema is not contrat.AdministrateurInstallation
        and (nom in NOMS_PERSONNELS or nom == "nom")
        and (schema.__name__, nom) not in NOMS_QUI_NE_SONT_PAS_DES_PERSONNES
    ]
    assert not fautifs, f"donnée de personne hors de l'administrateur : {fautifs}"


def test_les_exceptions_servent():
    for schema_nom, champ in NOMS_QUI_NE_SONT_PAS_DES_PERSONNES:
        schema = getattr(contrat, schema_nom)
        assert champ in schema.model_fields, f"exception morte : {schema_nom}.{champ}"


def test_un_champ_inconnu_est_refuse():
    with pytest.raises(ValidationError):
        contrat.Posture(documentation_api_coupee=True, mot_de_passe="x")


def test_chaque_schema_refuse_l_inconnu():
    for schema in contrat.SCHEMAS:
        assert issubclass(schema, BaseModel)
        assert schema.model_config.get("extra") == "forbid", schema.__name__


def test_chaque_version_des_conditions_porte_son_empreinte():
    """Une version publiée ne change plus : son acceptation serait la preuve d'un autre texte."""
    versions = conditions.versions()
    assert versions, "aucune version des conditions"
    assert set(versions) == set(conditions.EMPREINTES), "une version sans empreinte, ou l'inverse"
    for v in versions:
        assert conditions.empreinte(v) == conditions.EMPREINTES[v], (
            f"v{v}.md a changé : une version publiée ne se modifie pas, on en écrit une nouvelle"
        )
    assert conditions.version_en_vigueur() == max(versions)


def test_les_conditions_engagent_les_deux_parties():
    """Le contrat d'engagements réciproques (arbitrage du 12/10/2026) : les deux listes."""
    texte = conditions.texte(conditions.version_en_vigueur())
    assert "Ce à quoi l'exploitant de l'installation s'engage" in texte
    assert "Ce à quoi l'exploitant de la référence s'engage" in texte
    assert "archive" in texte


def test_les_tables_du_registre_ne_sont_pas_celles_de_la_residence():
    plateforme = set(registre_plateforme.metadata.tables)
    assert plateforme == {
        "installation",
        "contact_installation",
        "decision_registre",
        "acceptation_conditions",
        "rapport_installation",
        "canal_distribution",
        "version_disponible",
    }
    assert not plateforme & set(SQLModel.metadata.tables)
