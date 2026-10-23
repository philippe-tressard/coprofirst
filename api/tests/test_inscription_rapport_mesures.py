"""Les trois mesures du rapport nocturne qui partaient toujours « inconnues » (#1981).

`registre/alertes` sait lever *sauvegarde sans copie hors de la machine*,
*certificat proche de l'échéance* et *mise à jour revenue en arrière* (#1960) ;
le rapport d'une installation ne remplissait aucun des trois champs. Chacun se
mesure désormais sur ce que l'installation SAIT déjà, et une mesure impossible
reste `None` — jamais une valeur supposée (`standards/04` §1).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from sqlmodel import Session

from app import contexte
from app.config import get_settings
from app.inscription import rapport
from app.models.core import HistoriqueMaintenance, TachePlanifiee
from app.registre.contrat import ISSUES_MISE_A_JOUR
from app.utils import horloge
from app.utils.backup import nom_archive
from tests.aides_base import moteur_de_test

SCRIPT_MAJ = Path(__file__).resolve().parents[2] / "deploiement" / "standard" / "mise-a-jour.sh"


@pytest.fixture
def base(monkeypatch):
    moteur = moteur_de_test()
    monkeypatch.setattr(contexte, "moteur", lambda: moteur)
    monkeypatch.setattr(contexte, "nouvelle_session", lambda: Session(moteur))
    return moteur


def _tache(moteur, tache: TachePlanifiee, statut="succes", details=None, il_y_a=timedelta(0)):
    with Session(moteur) as s:
        s.add(
            HistoriqueMaintenance(
                tache=tache.value,
                statut=statut,
                details=json.dumps(details) if details is not None else None,
                cree_le=horloge.maintenant() - il_y_a,
            )
        )
        s.commit()


# ── La mise à jour nocturne : l'issue que le script nomme ────────────────────


def test_l_issue_de_la_derniere_mise_a_jour_part_telle_quelle(base):
    _tache(base, TachePlanifiee.mise_a_jour, details={"issue": "reussie"}, il_y_a=timedelta(1))
    _tache(base, TachePlanifiee.mise_a_jour, "erreur", {"de": "2.1.0", "issue": "revenue"})
    assert rapport.construire().identite.derniere_mise_a_jour == "revenue"


@pytest.mark.parametrize(
    "details",
    [None, {"de": "2.1.0", "vers": "2.2.0"}, {"issue": "inventee"}],
    ids=["sans détails", "script d'avant #1981", "issue inconnue"],
)
def test_une_issue_illisible_reste_inconnue(base, details):
    _tache(base, TachePlanifiee.mise_a_jour, "erreur", details)
    assert rapport.construire().identite.derniere_mise_a_jour is None


def test_sans_mise_a_jour_nocturne_rien_n_est_dit(base):
    """La référence n'en fait pas : l'absence n'est pas un échec."""
    assert rapport.construire().identite.derniere_mise_a_jour is None


def test_l_etat_des_correctifs_du_systeme_part_au_registre(base):
    """Le contrôle de `correctifs-systeme.sh` en défaut → la référence le sait ;
    sans contrôle posé (la référence elle-même), rien ne part."""
    assert rapport.construire().identite.correctifs_systeme is None
    _tache(base, TachePlanifiee.correctifs_systeme, "erreur", il_y_a=timedelta(hours=2))
    assert rapport.construire().identite.correctifs_systeme == "en_defaut"


def test_le_script_nomme_une_issue_du_contrat_a_chaque_compte_rendu():
    """`mise-a-jour.sh` et le contrat parlent les mêmes mots — sinon l'issue se perd."""
    source = SCRIPT_MAJ.read_text(encoding="utf-8")
    appels = re.findall(r"^\s*rendre_compte (succes|erreur) .*$", source, re.M)
    assert appels, "aucun compte rendu trouvé dans mise-a-jour.sh — le contrôle ne voit rien"
    lignes = re.findall(r"^\s*rendre_compte (?:succes|erreur) .*$", source, re.M)
    for ligne in lignes:
        issue = re.findall(r'"([a-z_]+)"\s*(?:;;)?\s*$', ligne)
        assert issue and issue[0] in ISSUES_MISE_A_JOUR, f"issue absente ou inconnue : {ligne}"


# ── La copie hors de la machine : le jugement de l'écran de santé ────────────


def test_une_copie_hors_site_fraiche_vaut_oui(base):
    archive = nom_archive(horloge.maintenant() - timedelta(hours=3))
    _tache(base, TachePlanifiee.export_hors_site, details={"archive": archive})
    assert rapport.construire().sauvegarde.copie_hors_machine is True


@pytest.mark.parametrize(
    "statut, age_archive",
    [("succes", timedelta(days=30)), ("erreur", timedelta(hours=3))],
    ids=["archive périmée", "export en échec"],
)
def test_une_copie_hors_site_perimee_ou_ratee_vaut_non(base, statut, age_archive):
    archive = nom_archive(horloge.maintenant() - age_archive)
    _tache(base, TachePlanifiee.export_hors_site, statut, {"archive": archive})
    assert rapport.construire().sauvegarde.copie_hors_machine is False


def test_aucune_copie_hors_site_enregistree_vaut_non(base):
    assert rapport.construire().sauvegarde.copie_hors_machine is False


# ── Le certificat que le public reçoit ───────────────────────────────────────


def _certificat(fin: datetime) -> bytes:
    cle = ec.generate_private_key(ec.SECP256R1())
    nom = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "residence.example")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(nom)
        .issuer_name(nom)
        .public_key(cle.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(fin - timedelta(days=90))
        .not_valid_after(fin)
        .sign(cle, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


@pytest.mark.parametrize("dans", [timedelta(days=40), timedelta(days=-2)], ids=["valide", "expiré"])
def test_l_echeance_se_lit_meme_sur_un_certificat_expire(dans):
    fin = (datetime.now(timezone.utc) + dans).replace(microsecond=0)
    lue = rapport.echeance_certificat(_certificat(fin))
    assert lue == fin.replace(tzinfo=None)


def test_l_echeance_se_mesure_sur_l_origine_https(monkeypatch, base):
    fin = (datetime.now(timezone.utc) + timedelta(days=15)).replace(microsecond=0)
    monkeypatch.setattr(get_settings(), "origin", "https://residence.example")
    demandes = []
    monkeypatch.setattr(
        rapport,
        "_certificat_servi",
        lambda hote, port: demandes.append((hote, port)) or _certificat(fin),
    )
    assert rapport.construire().hebergement.certificat_expire_le == fin.replace(tzinfo=None)
    assert demandes == [("residence.example", 443)]


def test_sans_https_le_certificat_reste_inconnu(monkeypatch, base):
    monkeypatch.setattr(get_settings(), "origin", "http://192.168.1.10")
    monkeypatch.setattr(rapport, "_certificat_servi", lambda *a: pytest.fail("aucune connexion"))
    assert rapport.construire().hebergement.certificat_expire_le is None


def test_un_certificat_injoignable_reste_inconnu(monkeypatch, base):
    monkeypatch.setattr(get_settings(), "origin", "https://residence.example")

    def injoignable(hote, port):
        raise OSError("réseau")

    monkeypatch.setattr(rapport, "_certificat_servi", injoignable)
    assert rapport.construire().hebergement.certificat_expire_le is None


# ── La sauvegarde est-elle attendue ici ? (#1982) ────────────────────────────


@pytest.mark.parametrize(
    "demo, attendue", [("oui", False), ("", True)], ids=["démo", "installation"]
)
def test_le_rapport_dit_si_la_sauvegarde_est_attendue(monkeypatch, base, demo, attendue):
    """La règle se lit dans `TACHES_HORS_DEMO` (la tâche `backup` coupée), pas à côté."""
    monkeypatch.setattr(get_settings(), "mode_demo", demo)
    assert rapport.construire().sauvegarde.attendue is attendue
