"""Le canal, les vagues et la version cible portée par le bail (#2210, §4.11 règle 6).

`registre/canaux.version_cible` est PURE : ses règles se jouent cas par cas, sans base.
Le reste — les versions relues, le geste de l'opérateur, le bail qui porte la version,
la mise à jour nocturne qui la lit — se joue de bout en bout dans
`test_registre_canaux_bail.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from app.registre import canaux, versions as registre_versions
from app.registre.canaux import VAGUE_FIXE, VAGUE_PILOTE, VAGUE_STANDARD, VAGUE_URGENCE
from app.registre.contrat import Bail
from app.registre.modeles import EtatInscription, Installation, VersionDisponible
from app.utils import taches

MAINTENANT = datetime(2026, 10, 20, 4, 20)

#: Les versions publiées, et leur âge : 2.172 vient de sortir, 2.171.3 a 8 jours.
AGES = {
    "2.168.0": 40,
    "2.169.0": 30,
    "2.169.4": 25,
    "2.170.0": 20,
    "2.170.2": 12,
    "2.171.0": 10,
    "2.171.3": 8,
    "2.171.4": 3,
    "2.172.0": 1,
}


def _versions(ages: dict[str, int] = AGES) -> list[VersionDisponible]:
    return [
        VersionDisponible(version=v, publiee_le=MAINTENANT - timedelta(days=j))
        for v, j in ages.items()
    ]


def _inst(**champs) -> Installation:
    defaut = dict(
        identifiant="CF-000002",
        etat=EtatInscription.active,
        canal=canaux.CANAL_URGENCE,
        vague=VAGUE_STANDARD,
        version_logicielle="2.169.0",
    )
    return Installation(**{**defaut, **champs})


def _cible(inst: Installation, versions=None) -> str | None:
    return canaux.version_cible(inst, _versions() if versions is None else versions, MAINTENANT)


# ── Le format du bail ne s'étend pas ─────────────────────────────────────────


def test_le_bail_garde_ses_champs():
    """`Bail` refuse les champs inconnus : un champ neuf ferait REJETER le bail par toute
    installation pas encore à jour — plus de mise à jour automatique, donc jamais à jour.
    Ce que la référence décide voyage dans `version_cible`. Ajouter un champ ici, c'est
    ouvrir une nouvelle version du contrat ET prévoir comment les installations la
    rejoignent."""
    assert set(Bail.model_fields) == {
        "identifiant",
        "empreinte_cle",
        "etat",
        "canal",
        "version_cible",
        "services_autorises",
        "epoque",
        "delivre_le",
        "echeance",
    }


# ── Les vagues ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "vague, attendu",
    [
        (VAGUE_URGENCE, "2.172.0"),  # la dernière, aussitôt
        (VAGUE_PILOTE, "2.171.3"),  # la dernière de plus de 7 jours
        (VAGUE_STANDARD, "2.171.3"),  # 2.172 est la dernière mineure : y-1 = 2.171
    ],
)
def test_les_vagues_du_canal_urgence(vague, attendu):
    assert _cible(_inst(vague=vague)) == attendu


def test_standard_vise_la_mineure_precedente_a_son_dernier_correctif_rode():
    """La dernière mineure est 2.172 : Standard vise 2.171, et en 2.171 le dernier
    correctif de plus de 7 jours — 2.171.3, pas 2.171.4 (3 jours). Sans 2.172, la
    dernière mineure est 2.171 : Standard vise 2.170."""
    assert registre_versions.derniere_standard(_versions(), MAINTENANT).version == "2.171.3"
    sans_172 = {v: j for v, j in AGES.items() if v != "2.172.0"}
    assert _cible(_inst(), _versions(sans_172)) == "2.170.2"


def test_standard_passe_la_majeure():
    """y vaut 0 : la mineure précédente est la dernière de la majeure d'avant."""
    versions = _versions({"2.9.1": 20, "2.9.2": 9, "3.0.0": 2})
    assert registre_versions.derniere_standard(versions, MAINTENANT).version == "2.9.2"


def test_standard_se_replie_sur_une_mineure_anterieure_rodee():
    """y-1 (2.171) n'a que 3 jours : Standard prend la dernière version rodée d'une
    mineure antérieure, sinon l'installation ne bougerait plus tant que les mineures
    se suivent."""
    versions = _versions({"2.170.0": 20, "2.170.1": 9, "2.171.0": 3, "2.172.0": 1})
    assert registre_versions.derniere_standard(versions, MAINTENANT).version == "2.170.1"


def test_standard_sans_correctif_rode_ni_mineure_precedente_aucune():
    assert (
        registre_versions.derniere_standard(_versions({"2.171.4": 3, "2.172.0": 1}), MAINTENANT)
        is None
    )
    assert registre_versions.derniere_standard(_versions({"2.172.0": 30}), MAINTENANT) is None
    assert _cible(_inst(), _versions({"2.172.0": 30})) is None


def test_une_inscription_neuve_suit_standard():
    assert canaux.VAGUE_DEFAUT == VAGUE_STANDARD
    assert Installation(identifiant="CF-000009").vague == VAGUE_STANDARD
    assert Installation(identifiant="CF-000009").canal == canaux.CANAL_URGENCE


@pytest.mark.parametrize("age, attendu", [(8, "2.170.0"), (3, "2.169.0")])
def test_fixe_attend_les_sept_jours(age, attendu):
    """Avant ses 7 jours, la version choisie n'est pas installée : rien ne bouge."""
    versions = _versions({**AGES, "2.170.0": age})
    assert _cible(_inst(canal="2.170.0", vague=VAGUE_FIXE), versions) == attendu


def test_fixe_plus_ancienne_est_l_ordre_de_revenir():
    """Le seul chemin d'un retour : l'ordre est signé avec le bail."""
    inst = _inst(canal="2.168.0", vague=VAGUE_FIXE, version_logicielle="2.171.3")
    assert _cible(inst) == "2.168.0"


def test_fixe_sur_une_version_plus_publiee_ne_bouge_rien():
    inst = _inst(canal="2.150.0", vague=VAGUE_FIXE)
    assert _cible(inst) == "2.169.0"
    assert _cible(_inst(canal="2.150.0", vague=VAGUE_FIXE, version_logicielle=None)) is None


def test_les_vagues_du_canal_urgence_ne_font_jamais_reculer():
    inst = _inst(vague=VAGUE_PILOTE, version_logicielle="2.172.0")
    assert _cible(inst) == "2.172.0"
    #  Une version qui ne se compare pas (un commit) ne retient rien.
    assert _cible(_inst(vague=VAGUE_PILOTE, version_logicielle="5aa41dad0242")) == "2.171.3"


def test_sans_version_publiee_aucune():
    assert _cible(_inst(), []) is None


# ── L'inscription (règle 3) et la référence (règle 6) ────────────────────────


@pytest.mark.parametrize("etat", [EtatInscription.en_attente, EtatInscription.resiliee])
def test_sans_inscription_valide_aucune_version(etat):
    assert _cible(_inst(etat=etat)) is None


def test_une_installation_suspendue_recoit_ses_correctifs():
    assert _cible(_inst(etat=EtatInscription.suspendue)) == "2.171.3"


def test_la_reference_n_a_pas_de_version_cible():
    assert _cible(_inst(canal="main")) is None


# ── Les valeurs d'avant #2210, qu'une image précédente écrirait ──────────────


@pytest.mark.parametrize(
    "champs, attendu",
    [
        ({"canal": "replica", "vague": 0}, ("urgence", VAGUE_URGENCE)),
        ({"canal": "special-a", "vague": 7}, ("urgence", VAGUE_STANDARD)),
        ({"canal": "replica", "version_epinglee": "2.169.4"}, ("2.169.4", VAGUE_FIXE)),
        ({"canal": "2.170.0", "vague": VAGUE_URGENCE}, ("2.170.0", VAGUE_FIXE)),
        ({"canal": "urgence", "vague": VAGUE_FIXE}, ("urgence", VAGUE_STANDARD)),
    ],
)
def test_le_suivi_ramene_toute_valeur_a_une_combinaison_permise(champs, attendu):
    assert canaux.suivi_de(_inst(**champs)) == attendu


# ── La liste proposée ────────────────────────────────────────────────────────


def test_les_cinq_dernieres_mineures_a_leur_dernier_correctif():
    proposees = [v.version for v in registre_versions.versions_proposees(_versions())]
    assert proposees == ["2.172.0", "2.171.4", "2.170.2", "2.169.4", "2.168.0"]
    versions = _versions({f"3.{m}.{z}": 1 for m in range(8) for z in range(3)})
    assert [v.version for v in registre_versions.versions_proposees(versions)] == [
        "3.7.2",
        "3.6.2",
        "3.5.2",
        "3.4.2",
        "3.3.2",
    ]


# ── Les releases, relues chaque nuit ─────────────────────────────────────────


def _release(tag="v2.172.0", archive=True, draft=False, cree="2026-10-19T04:00:00Z"):
    version = tag.removeprefix("v")
    noms = [f"coprofirst-deploiement-{version}.tar.gz"] if archive else []
    return {
        "tag_name": tag,
        "draft": draft,
        "created_at": cree,
        "assets": [{"name": n} for n in noms],
    }


def test_une_release_publie_sa_version_si_elle_porte_l_archive():
    p = canaux.publication_de(_release())
    assert (p.version, p.publiee_le) == ("2.172.0", datetime(2026, 10, 19, 4, 0))
    assert canaux.publication_de(_release(archive=False)) is None
    assert canaux.publication_de(_release(draft=True)) is None
    assert canaux.publication_de(_release(tag="nightly")) is None
    assert canaux.publication_de(_release(cree="hier")) is None


def test_lire_les_releases_page_par_page():
    pages = {1: [_release(f"v2.{i}.0") for i in range(100)], 2: [_release("v3.0.0")]}

    def get(url, params, timeout):
        return httpx.Response(200, json=pages[params["page"]])

    lues = canaux.lire_publications(get)
    assert len(lues) == 101 and lues[-1].version == "3.0.0"


def test_une_lecture_en_echec_ne_rend_aucune_liste():
    assert canaux.lire_publications(lambda url, params, timeout: httpx.Response(403)) is None

    def panne(url, params, timeout):
        raise httpx.ConnectError("injoignable")

    assert canaux.lire_publications(panne) is None
    assert canaux.URL_RELEASES.endswith("/releases")


class _Session:
    """Ce que `relire_versions` demande à une session : lire, ajouter, retirer."""

    def __init__(self, versions):
        self.versions, self.ajoutees, self.retirees = versions, [], []

    def exec(self, _requete):
        versions = self.versions

        class _R:
            def all(self):
                return versions

        return _R()

    def add(self, objet):
        self.ajoutees.append(objet)

    def delete(self, objet):
        self.retirees.append(objet)


def test_relire_ajoute_et_retire():
    s = _Session(_versions({"2.170.0": 20, "2.171.0": 10}))
    lues = [canaux.Publication("2.171.0", MAINTENANT), canaux.Publication("2.172.0", MAINTENANT)]
    constat = canaux.relire_versions(s, lues, MAINTENANT)
    assert [v.version for v in s.retirees] == ["2.170.0"]
    assert {v.version for v in s.ajoutees} == {"2.171.0", "2.172.0"}
    assert "dernière 2.172.0" in constat


@pytest.mark.parametrize("lues", [None, []])
def test_une_lecture_vide_ou_illisible_ne_retire_rien(lues):
    s = _Session(_versions())
    canaux.relire_versions(s, lues, MAINTENANT)
    assert s.retirees == [] and s.ajoutees == []


def test_la_lecture_des_versions_est_une_tache_de_la_plateforme():
    assert "canaux_registre" in taches.TACHES_PERMANENTES
    assert "canaux_registre" in taches.TACHES_DE_LA_PLATEFORME


# ── Ce que la purge des paquets garde (même règle, `registre/versions`) ──────


def test_la_purge_garde_ce_qu_une_vague_peut_servir():
    vieilles = {f"2.{m}.{z}": 220 - m for m in range(150, 160) for z in range(2)}
    gardees = registre_versions.versions_a_garder(_versions({**vieilles, **AGES}), MAINTENANT)
    #  la liste proposée, les cibles d'Urgence, Pilote et Standard, les moins de 8 jours
    assert gardees == {"2.172.0", "2.171.4", "2.170.2", "2.169.4", "2.168.0", "2.171.3"}
    assert "2.159.1" not in gardees and "2.150.0" not in gardees


def test_le_script_de_la_purge_lit_et_ecrit_des_versions(monkeypatch, capsys):
    import io
    import json

    entree = [{"version": "3.0.0", "publiee_le": "2026-10-19T04:00:00Z"}]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(entree)))
    assert registre_versions.main(["garder"]) == 0
    assert capsys.readouterr().out.split() == ["3.0.0"]
    monkeypatch.setattr("sys.stdin", io.StringIO("[]"))
    assert registre_versions.main(["garder"]) == 1  # ne rien garder purgerait tout
    assert registre_versions.main([]) == 2


def test_le_script_de_la_purge_donne_sa_fenetre(capsys):
    assert registre_versions.main(["fenetre"]) == 0
    assert capsys.readouterr().out.strip() == "8"
