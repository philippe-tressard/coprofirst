"""L'export neutre d'une copropriété se réimporte à l'identique, et l'import vérifie (#1749).

Ce que ces tests tiennent :
- l'aller-retour : export d'une base peuplée, import dans une base neuve, même
  contenu table par table (empreintes) — date, booléen, énumération, texte
  accentué, NULL ;
- l'import REFUSE une archive altérée, et la base cible reste vide ;
- `verifier_restauration` dit qu'une base se restaure ;
- une valeur sans forme neutre lève, au lieu d'une empreinte fausse.

"""

from __future__ import annotations

import io
import json
import tarfile
from datetime import datetime

import pytest
from sqlmodel import Session, select

from app.models.core import ConfigSite, FaqItem, RoleUtilisateur, Utilisateur
from app.utils import export_copropriete as ex
from app.utils import import_copropriete as im
from tests.aides_base import adresse_de_test, compte, moteur_de_test


def _base_peuplee():
    moteur = moteur_de_test()
    with Session(moteur) as s:
        compte(s, prenom="Élodie", nom="D'Aubigné", role=RoleUtilisateur.conseil_syndical)
        compte(s, prenom="Zoé", nom="Martin", actif=False)
        s.add(ConfigSite(cle="site_nom", valeur="Résidence « Les Tilleuls »"))
        s.add(ConfigSite(cle="vide", valeur=""))
        s.add(
            FaqItem(
                categorie="Vie pratique",
                question="Où sont les poubelles ?",
                reponse="Au sous-sol — porte B.",
            )
        )
        s.commit()
    return moteur


def test_l_aller_retour_rend_le_meme_contenu(tmp_path):
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    manifeste = ex.exporter(source, archive)
    assert manifeste["tables"]["utilisateur"]["lignes"] == 2
    assert manifeste["tables"]["config_site"]["lignes"] == 2

    cible = moteur_de_test()
    bilan = im.importer(archive, cible)
    assert bilan.ecarts == [] and bilan.lignes >= 5

    with Session(cible) as s:
        elodie = s.exec(select(Utilisateur).where(Utilisateur.prenom == "Élodie")).one()
        assert elodie.nom == "D'Aubigné" and elodie.actif is True
        assert isinstance(elodie.cree_le, datetime)
        assert s.exec(select(ConfigSite).where(ConfigSite.cle == "vide")).one().valeur == ""
        assert elodie.etage is None, "un NULL reste un NULL"
    #  Et la cible relue donne EXACTEMENT les empreintes de la source.
    with cible.connect() as c:
        relu, _, _ = ex.lire(c)
    par_nom = {t.name: t for t in ex.tables()}
    for nom, attendu in manifeste["tables"].items():
        assert ex.empreinte_table(par_nom[nom], relu[nom]) == attendu["empreinte"], nom


def _alterer(archive, sortie, table, remplacer):
    with tarfile.open(archive, "r:gz") as a, tarfile.open(sortie, "w:gz") as b:
        for membre in a.getmembers():
            donnees = a.extractfile(membre).read()
            if membre.name == f"tables/{table}.jsonl":
                donnees = remplacer(donnees)
            info = tarfile.TarInfo(membre.name)
            info.size = len(donnees)
            b.addfile(info, io.BytesIO(donnees))


def test_une_archive_alteree_est_refusee_et_la_cible_reste_vide(tmp_path):
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    alteree = tmp_path / "alteree.tar.gz"
    _alterer(archive, alteree, "faq_item", lambda d: d.replace("sous-sol".encode(), b"grenier"))

    cible = moteur_de_test()
    with pytest.raises(im.ImportRefuse, match="faq_item"):
        im.importer(alteree, cible)
    with Session(cible) as s:
        assert s.exec(select(FaqItem)).all() == [], "la transaction annulée laisse la cible vide"


def test_une_ligne_perdue_est_refusee(tmp_path):
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    amputee = tmp_path / "amputee.tar.gz"
    _alterer(archive, amputee, "config_site", lambda d: d.split(b"\n", 1)[1])
    with pytest.raises(im.ImportRefuse, match="config_site : 1 ligne"):
        im.importer(amputee, moteur_de_test())


def test_les_fichiers_voyagent_avec_leur_empreinte(tmp_path):
    televerses = tmp_path / "uploads"
    (televerses / "photos").mkdir(parents=True)
    (televerses / "photos" / "fuite.jpg").write_bytes(b"\xff\xd8\xff photo")
    archive = tmp_path / "export.tar.gz"
    manifeste = ex.exporter(_base_peuplee(), archive, fichiers=televerses)
    assert [f["chemin"] for f in manifeste["fichiers"]] == ["photos/fuite.jpg"]

    restaures = tmp_path / "restaures"
    bilan = im.importer(archive, moteur_de_test(), fichiers=restaures)
    assert bilan.fichiers == 1
    assert (restaures / "photos" / "fuite.jpg").read_bytes() == b"\xff\xd8\xff photo"


def test_verifier_restauration_dit_qu_une_base_se_restaure(tmp_path):
    manifeste, bilan = im.verifier_restauration(_base_peuplee(), tmp_path)
    assert bilan.ecarts == [] and bilan.tables == len(manifeste["tables"])
    assert list(tmp_path.iterdir()) == [], "rien ne reste derrière la vérification"


def test_une_valeur_sans_forme_neutre_leve():
    with pytest.raises(TypeError):
        ex.valeur_neutre(object())
    assert ex.valeur_neutre(b"\x00\x01") == {"$b64": "AAE="}
    assert json.dumps(ex.valeur_neutre(datetime(2026, 10, 9, 1, 2, 3)))


def test_le_manifeste_nomme_ce_qu_il_ne_porte_pas(tmp_path):
    moteur = _base_peuplee()
    from sqlalchemy import text

    with moteur.begin() as c:
        c.execute(text("CREATE TABLE table_historique (x INTEGER)"))
    manifeste = ex.exporter(moteur, tmp_path / "e.tar.gz")
    assert manifeste["ignorees"] == ["table_historique"]


# ── Les routes d'administration ──────────────────────────────────────────────

from app.routers.admin import export_copropriete as routes  # noqa: E402
from tests.aides_http import base_http, client_http  # noqa: E402


@pytest.fixture
def http_admin(monkeypatch, tmp_path):
    """Un client admin, la base de l'APPLICATION remplacée par une base peuplée."""
    import app.database

    #  Partagée : le client de test lit depuis un autre fil, et une base en mémoire
    #  non partagée y serait vide.
    monkeypatch.setattr(app.database, "engine", _base_peuplee())

    #  La sauvegarde et la racine des fichiers : celle-ci se demande au contexte
    #  de copropriété (#1744), qui relit les réglages à chaque appel.
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path / "sauvegardes"))
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path / "uploads"))
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        yield http, tmp_path


@pytest.mark.parametrize("role", [None, RoleUtilisateur.résident, RoleUtilisateur.conseil_syndical])
def test_les_routes_sont_reservees_a_l_administration(role):
    with base_http() as moteur:
        http, _ = client_http(moteur, role)
        assert http.post("/admin/export-copropriete/verifier").status_code in (401, 403)
        assert http.post("/admin/export-copropriete").status_code in (401, 403)
        assert http.get("/admin/export-copropriete/dernier").status_code in (401, 403)


def test_la_route_dit_que_la_base_se_restaure(http_admin):
    http, _ = http_admin
    corps = http.post("/admin/export-copropriete/verifier").json()
    assert corps["restaurable"] is True and corps["ecarts"] == []
    assert corps["tables"] > 10 and corps["lignes"] >= 5


def test_l_export_ecrit_une_archive_entiere_et_se_relit(http_admin):
    http, dossier = http_admin
    (dossier / "uploads").mkdir()
    (dossier / "uploads" / "plan.pdf").write_bytes(b"%PDF-1.7")
    assert http.get("/admin/export-copropriete/dernier").json()["archive"] is None
    nom = http.post("/admin/export-copropriete").json()["archive"]  # tâche de fond jouée
    assert nom.startswith(routes.PREFIXE) and nom.endswith("_paris.tar.gz")
    dernier = http.get("/admin/export-copropriete/dernier").json()
    assert dernier["archive"] == nom and dernier["fichiers"] == 1 and dernier["lignes"] >= 5
    assert not list((dossier / "sauvegardes").glob("*.partiel")), "aucun reste d'écriture"


def test_on_ne_garde_que_les_derniers_exports(http_admin, monkeypatch):
    http, dossier = http_admin
    sauvegardes = dossier / "sauvegardes"
    sauvegardes.mkdir()
    for i in range(5):
        (sauvegardes / f"{routes.PREFIXE}2026010{i}_000000_paris.tar.gz").write_bytes(b"x")
    (sauvegardes / "hostachy_backup_20260101_000000_paris.tar.gz").write_bytes(b"x")
    http.post("/admin/export-copropriete")
    restants = sorted(p.name for p in sauvegardes.iterdir())
    assert len([n for n in restants if n.startswith(routes.PREFIXE)]) == routes.GARDER
    assert "hostachy_backup_20260101_000000_paris.tar.gz" in restants, (
        "les sauvegardes ne sont pas touchées"
    )


def _ligne_de_commande(*arguments: str):
    """`python -m app.utils.export_copropriete …`, comme l'appellent les scripts d'exploitation."""
    import os
    import subprocess
    import sys

    #  L'enfant écrit en UTF-8 quel que soit le poste (la console Windows est en cp1252).
    env = {**os.environ, "SECRET_KEY": "x" * 40, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, "-m", "app.utils.export_copropriete", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=os.getcwd(),
    )


def test_l_import_en_ligne_de_commande_verifie_et_le_dit(tmp_path):
    """Le geste de DI-7 : une archive, une base cible neuve, et un verdict lisible."""
    archive = tmp_path / "e.tar.gz"
    ex.exporter(_base_peuplee(), archive)
    cible, retirer = adresse_de_test()
    autre, retirer_autre = adresse_de_test()
    try:
        r = _ligne_de_commande("importer", str(archive), cible)
        assert r.returncode == 0, r.stderr[-500:]
        assert "Importé et vérifié" in r.stdout
        alteree = tmp_path / "alteree.tar.gz"
        _alterer(archive, alteree, "faq_item", lambda d: d.replace("sous-sol".encode(), b"grenier"))
        r = _ligne_de_commande("importer", str(alteree), autre)
        assert r.returncode != 0 and "IMPORT REFUSÉ" in r.stderr
    finally:
        retirer()
        retirer_autre()


def test_verifier_une_archive_en_ligne_de_commande(tmp_path):
    """La sauvegarde d'une réplique avant sa mise à jour (DI-4) : réimportée à côté, jamais en place."""
    archive = tmp_path / "e.tar.gz"
    ex.exporter(_base_peuplee(), archive)
    r = _ligne_de_commande("verifier", str(archive))
    assert r.returncode == 0, r.stderr[-500:]
    assert "Archive vérifiée" in r.stdout
    alteree = tmp_path / "alteree.tar.gz"
    _alterer(archive, alteree, "faq_item", lambda d: d.replace("sous-sol".encode(), b"grenier"))
    r = _ligne_de_commande("verifier", str(alteree))
    assert r.returncode != 0 and "ARCHIVE REFUSÉE" in r.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["alteree.tar.gz", "e.tar.gz"], (
        "la base jetable de la vérification doit disparaître"
    )


# ── Les clés étrangères ACTIVES (DI-7c, première bascule du 09/10/2026) ─────────
#
#  La bascule des données a été refusée sur `batiment` → `copropriete` : huit
#  tables se citent en cycle, `sorted_tables` les range sans ordre valable, et
#  PostgreSQL vérifie chaque clé ligne à ligne. Ces tests-ci ne l'avaient pas
#  vu : leur cible avait les clés DÉSACTIVÉES (le régime par défaut de
#  `moteur_de_test`). Ici, la cible les vérifie, comme la production.


def _copropriete_et_batiment(moteur, *, copropriete_id=None):
    from app.models.copropriete import Batiment, Copropriete

    with Session(moteur) as s:
        if copropriete_id is None:
            copro = Copropriete(nom="Résidence d'essai", adresse="1 rue de l'Essai")
            s.add(copro)
            s.commit()
            copropriete_id = copro.id
        s.add(Batiment(copropriete_id=copropriete_id, numero="A"))
        s.commit()


def test_des_tables_en_cycle_s_importent_clefs_actives(tmp_path):
    source = _base_peuplee()
    _copropriete_et_batiment(source)
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    ordre = [t.name for t in ex.tables()]
    assert ordre.index("batiment") < ordre.index("copropriete"), (
        "cas zéro : l'enfant n'est plus écrit avant son parent — ce test ne reproduit "
        "plus la panne du 09/10/2026"
    )

    cible = moteur_de_test(cles_etrangeres=True)
    bilan = im.importer(archive, cible)
    assert bilan.ecarts == []
    with cible.connect() as c:
        assert im.lignes_sans_parent(c) == []


def test_une_ligne_sans_parent_est_refusee_et_la_cible_reste_vide(tmp_path):
    source = _base_peuplee()  # clés désactivées : l'orphelin peut s'y écrire
    _copropriete_et_batiment(source, copropriete_id=99)
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)

    cible = moteur_de_test(cles_etrangeres=True)
    with pytest.raises(im.ImportRefuse, match=r"batiment\.copropriete_id → copropriete \(1\)"):
        im.importer(archive, cible)
    with Session(cible) as s:
        assert s.exec(select(Utilisateur)).all() == [], "la transaction est annulée"


def test_un_separateur_unicode_dans_un_texte_ne_coupe_pas_la_ligne(tmp_path):
    """U+2028 et U+0085 restent tels quels dans le JSON : `splitlines()` coupait là."""
    texte = "Avant pendant\u0085après\nfin"
    source = _base_peuplee()
    with Session(source) as s:
        s.add(FaqItem(categorie="Vie pratique", question="Séparateurs ?", reponse=texte))
        s.commit()
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)

    cible = moteur_de_test(cles_etrangeres=True)
    assert im.importer(archive, cible).ecarts == []
    with Session(cible) as s:
        relu = s.exec(select(FaqItem).where(FaqItem.question == "Séparateurs ?")).one()
        assert relu.reponse == texte


# ── Une archive d'une AUTRE version du modèle (#1799) ───────────────────────────
#
#  Une sauvegarde est relue par un code plus récent : une colonne a pu être
#  retirée du modèle (contraction, `non_relancable` en v2.130.5) ou ajoutée. Une
#  archive d'une version antérieure est COHÉRENTE avec son propre manifeste :
#  ces tests la fabriquent ainsi, manifeste recalculé.


def _autre_version(archive, sortie, table, transformer):
    """Réécrit `tables/<table>.jsonl` par `transformer(ligne)`, et son manifeste avec."""
    with tarfile.open(archive, "r:gz") as a:
        membres = {m.name: a.extractfile(m).read() for m in a.getmembers()}
    lignes = [transformer(li) for li in im.lignes_jsonl(membres[f"tables/{table}.jsonl"])]
    membres[f"tables/{table}.jsonl"] = "".join(
        json.dumps(li, ensure_ascii=False, separators=(",", ":")) + "\n" for li in lignes
    ).encode()
    manifeste = json.loads(membres["manifeste.json"])
    par_nom = {t.name: t for t in ex.tables()}
    manifeste["tables"][table]["empreinte"] = ex.empreinte_table(par_nom[table], lignes)
    membres["manifeste.json"] = json.dumps(manifeste, ensure_ascii=False).encode()
    with tarfile.open(sortie, "w:gz") as b:
        for nom, donnees in membres.items():
            info = tarfile.TarInfo(nom)
            info.size = len(donnees)
            b.addfile(info, io.BytesIO(donnees))


def test_une_colonne_retiree_du_modele_est_ecartee_et_nommee(tmp_path):
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    ancienne = tmp_path / "ancienne.tar.gz"
    _autre_version(archive, ancienne, "faq_item", lambda li: {**li, "retiree_depuis": "x"})

    cible = moteur_de_test(cles_etrangeres=True)
    bilan = im.importer(ancienne, cible)
    assert bilan.ecarts == []
    assert bilan.colonnes_ecartees == ["faq_item.retiree_depuis"]
    with Session(cible) as s:
        assert len(s.exec(select(FaqItem)).all()) == 1


def test_une_colonne_absente_de_l_archive_recoit_son_defaut(tmp_path):
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    ancienne = tmp_path / "ancienne.tar.gz"
    _autre_version(
        archive, ancienne, "faq_item", lambda li: {k: v for k, v in li.items() if k != "ordre"}
    )

    cible = moteur_de_test(cles_etrangeres=True)
    bilan = im.importer(ancienne, cible)
    assert bilan.ecarts == []
    assert bilan.colonnes_par_defaut == ["faq_item.ordre"]
    with Session(cible) as s:
        assert s.exec(select(FaqItem)).one().ordre == FaqItem().ordre


def test_une_archive_alteree_reste_refusee_avant_toute_ecriture(tmp_path):
    """Recalculer le manifeste est la forme d'une AUTRE version ; l'altérer sans, une fraude."""
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    alteree = tmp_path / "alteree.tar.gz"
    _alterer(archive, alteree, "faq_item", lambda d: d.replace(b'"ordre":0', b'"ordre":7'))
    with pytest.raises(im.ImportRefuse, match="faq_item : contenu différent du manifeste"):
        im.importer(alteree, moteur_de_test())
