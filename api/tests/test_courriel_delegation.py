"""Les signataires DÉLÉGUÉS — un domaine admis pour en signer un autre (#2554).

Le cas d'origine : un cabinet sous Microsoft 365, sans signature propre, dont
les messages portent `d=<abonnement>.onmicrosoft.com` pour un `From:` de son
domaine. Trois réponses du syndic refusées en dix jours, et aucune n'est entrée.

Les signatures sont VRAIES (`dkimpy`, clé tirée pour le module, faux DNS) : la
leçon de `test_courriel_authenticite` — tester ce qui nourrit la décision.
"""

from __future__ import annotations

import base64

import dkim
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from sqlmodel import select

from app.models.core import ConfigSite
from app.routers.config import save_config
from app.utils import courriel_delegation as cd
from app.utils.courriel_authenticite import repond_de, verifier_expediteur

_SELECTEUR = b"selector1"
_CABINET = "cabinet-gestion.fr"
_ABONNEMENT = "cabinetgestion.onmicrosoft.com"


@pytest.fixture(scope="module")
def cle():
    privee = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = privee.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    publique = privee.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem, b"v=DKIM1; k=rsa; p=" + base64.b64encode(publique)


def _signe_par_l_abonnement(cle, de: str = f"gestion@{_CABINET}") -> tuple[bytes, object]:
    """Un message « de » `de`, signé du domaine de l'abonnement — et le DNS qui sert sa clé."""
    message = (
        f"From: Gestionnaire <{de}>\r\n"
        "To: affaire@5hostachy.fr\r\n"
        "Subject: RE: Affaire #TK-121048 - Porte\r\n"
        "Date: Thu, 05 Nov 2026 09:53:00 +0100\r\n"
        "Message-ID: <essai@exemple.test>\r\n"
        "\r\n"
        "Nous intervenons jeudi.\r\n"
    ).encode()
    signe = dkim.sign(message, _SELECTEUR, _ABONNEMENT.encode(), cle[0]) + message
    nom = _SELECTEUR + b"._domainkey." + _ABONNEMENT.encode() + b"."
    return signe, lambda n, timeout=5: cle[1] if n == nom else None


# ── La vérification ───────────────────────────────────────────────────────────


def test_sans_delegation_la_signature_de_l_abonnement_est_refusee_et_dit_quoi_faire(cle):
    brut, dns = _signe_par_l_abonnement(cle)
    ok, motif = verifier_expediteur(brut, f"gestion@{_CABINET}", dnsfunc=dns)
    assert not ok
    assert _ABONNEMENT in motif and "signataires délégués" in motif


def test_avec_la_delegation_declaree_la_reponse_est_authentifiee(cle):
    brut, dns = _signe_par_l_abonnement(cle)
    delegues = cd.delegations(f"{_CABINET} = {_ABONNEMENT}")
    ok, motif = verifier_expediteur(brut, f"gestion@{_CABINET}", dnsfunc=dns, delegues=delegues)
    assert ok, motif
    assert motif == f"signé par {_ABONNEMENT}, signataire admis pour {_CABINET}"


def test_la_delegation_ne_couvre_ni_un_sous_domaine_ni_un_autre_domaine(cle):
    """Exacte, au libellé près : elle répond d'UN domaine, pas de sa famille."""
    delegues = cd.delegations(f"{_CABINET} = {_ABONNEMENT}")
    for de in (f"x@mail.{_CABINET}", "x@autre-cabinet.fr"):
        brut, dns = _signe_par_l_abonnement(cle, de)
        ok, _ = verifier_expediteur(brut, de, dnsfunc=dns, delegues=delegues)
        assert not ok, de


def test_un_autre_abonnement_n_est_pas_admis_pour_le_cabinet():
    delegues = cd.delegations(f"{_CABINET} = {_ABONNEMENT}")
    assert repond_de(_ABONNEMENT, _CABINET, delegues)
    assert not repond_de("pirate.onmicrosoft.com", _CABINET, delegues)
    assert not repond_de("onmicrosoft.com", _CABINET, delegues)


# ── La saisie ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ligne",
    [
        f"{_CABINET} = onmicrosoft.com",  # la racine de TOUS les abonnements
        f"{_CABINET} = gmail.com",  # n'importe quel compte Gmail
        f"{_CABINET} = {_CABINET}",  # inutile
        f"{_CABINET} {_ABONNEMENT}",  # sans séparateur
        f"{_CABINET} = pas un domaine",
        f"* = {_ABONNEMENT}",
    ],
)
def test_une_ligne_dangereuse_ou_illisible_est_refusee(ligne):
    assert cd.refus_des_delegations(ligne)
    assert cd.delegations(ligne) == frozenset()


def test_la_saisie_se_normalise():
    texte = f"\n  {_CABINET.upper()}  →  {_ABONNEMENT}.\n{_CABINET} -> {_ABONNEMENT}\n"
    assert cd.refus_des_delegations(texte) is None
    assert cd.normaliser_delegations(texte) == f"{_CABINET} = {_ABONNEMENT}"


def test_les_signataires_partages_sont_tous_des_domaines():
    """Cas zéro de la liste : une faute de frappe ne protégerait de rien."""
    assert cd.SIGNATAIRES_PARTAGES
    assert all(cd._DOMAINE.match(d) for d in cd.SIGNATAIRES_PARTAGES)


# ── L'écriture par PUT /config ────────────────────────────────────────────────


class _Admin:
    id = 7


def test_put_config_refuse_un_suffixe_partage_et_n_ecrit_rien(session):
    with pytest.raises(HTTPException) as refus:
        save_config({cd.CLE_DELEGATIONS: f"{_CABINET} = onmicrosoft.com"}, _Admin(), session)
    assert refus.value.status_code == 422
    assert session.get(ConfigSite, cd.CLE_DELEGATIONS) is None


def test_put_config_ecrit_la_forme_normale_et_journalise_le_geste(session, monkeypatch):
    from app.utils import journal_securite

    vus: list[tuple] = []
    monkeypatch.setattr(
        journal_securite, "journaliser_securite", lambda ev, **k: vus.append((ev, k))
    )
    save_config({cd.CLE_DELEGATIONS: f"{_CABINET} → {_ABONNEMENT}"}, _Admin(), session)
    ligne = session.exec(select(ConfigSite).where(ConfigSite.cle == cd.CLE_DELEGATIONS)).one()
    assert ligne.valeur == f"{_CABINET} = {_ABONNEMENT}"
    assert cd.delegations_du_site(session) == {(_CABINET, _ABONNEMENT)}
    ((evenement, champs),) = vus
    assert evenement == "signataires_delegues_modifies"
    assert champs["acteur_id"] == _Admin.id
