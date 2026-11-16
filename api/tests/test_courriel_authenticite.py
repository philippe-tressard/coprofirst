"""L'authenticité d'un courriel reçu — éprouvée sur de VRAIES signatures DKIM.

## Pourquoi ce fichier signe pour de bon

Le contrôle précédent était éprouvé par des tests qui lui donnaient l'en-tête
qu'il attendait (`Authentication-Results: … pass`). Ils étaient verts, et en
production aucune réponse n'est jamais passée : OVH ne pose pas cet en-tête.
*Je testais la décision, pas ce qui la nourrit* — la leçon de check-reliability
(11/08/2026), refaite ici à l'identique.

Ici chaque message est signé avec une clé RSA tirée pour le test, et la clé
publique est servie par un faux DNS : c'est `dkimpy` qui vérifie, exactement
comme à la relève. Seul le réseau est remplacé.
"""

from __future__ import annotations

import base64
import re

import dkim
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.utils.courriel_authenticite import (
    MOTIFS_ECART,
    VerificationReportee,
    aligne,
    domaine_de,
    verifier_expediteur,
)

_SELECTEUR = b"s1"


@pytest.fixture(scope="module")
def cle():
    """Une paire de clés tirée pour ce module — jamais écrite dans le dépôt."""
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


def _dns(enregistrements: dict[bytes, bytes]):
    """Un faux DNS : le nom complet (`s1._domainkey.syndic.test.`) → la clé."""

    def txt(nom: bytes, timeout: int = 5) -> bytes | None:
        return enregistrements.get(nom)

    return txt


def _message(de: str, corps: str = "Nous intervenons jeudi.\r\n") -> bytes:
    return (
        f"From: {de}\r\n"
        "To: affaire@5hostachy.fr\r\n"
        "Subject: Re: Affaire #TK-121048 - Porte\r\n"
        "Date: Mon, 28 Sep 2026 16:37:00 +0200\r\n"
        "Message-ID: <essai@exemple.test>\r\n"
        "\r\n"
        f"{corps}"
    ).encode()


def _signer(message: bytes, domaine: str, pem: bytes, **options) -> bytes:
    return dkim.sign(message, _SELECTEUR, domaine.encode(), pem, **options) + message


def _dns_pour(domaine: str, cle) -> object:
    return _dns({_SELECTEUR + b"._domainkey." + domaine.encode() + b".": cle[1]})


# ── Le cas nominal ────────────────────────────────────────────────────────────


def test_un_message_signe_par_le_domaine_de_l_expediteur_est_authentique(cle):
    brut = _signer(_message("Élise <gestion@syndic.test>"), "syndic.test", cle[0])
    ok, motif = verifier_expediteur(
        brut, "Élise <gestion@syndic.test>", dnsfunc=_dns_pour("syndic.test", cle)
    )
    assert ok, motif
    assert "syndic.test" in motif


def test_une_signature_du_domaine_PARENT_couvre_un_sous_domaine(cle):
    brut = _signer(_message("x@mail.syndic.test"), "syndic.test", cle[0])
    ok, _ = verifier_expediteur(brut, "x@mail.syndic.test", dnsfunc=_dns_pour("syndic.test", cle))
    assert ok


# ── 🔴 Les usurpations ────────────────────────────────────────────────────────


def test_un_usurpateur_qui_SIGNE_POUR_SON_PROPRE_DOMAINE_est_refuse(cle):
    """La signature est valide — mais elle engage `pirate.test`, pas le syndic.

    Sans l'alignement, n'importe qui disposant d'un domaine signerait un message
    « de » `gestion@syndic.test`, et DKIM dirait vrai sur la mauvaise question.
    """
    brut = _signer(_message("gestion@syndic.test"), "pirate.test", cle[0])
    ok, motif = verifier_expediteur(
        brut, "gestion@syndic.test", dnsfunc=_dns_pour("pirate.test", cle)
    )
    assert not ok
    assert "pirate.test" in motif and "syndic.test" in motif, "le motif doit dire qui a signé"


def test_un_message_NON_SIGNE_est_refuse_meme_avec_un_Authentication_Results(cle):
    """🔴 Le trou du 28/09/2026 : l'en-tête était cru, et l'expéditeur l'écrivait."""
    brut = b"Authentication-Results: mx.ovh.net; spf=pass; dkim=pass; dmarc=pass\r\n" + _message(
        "gestion@syndic.test"
    )
    ok, motif = verifier_expediteur(brut, "gestion@syndic.test", dnsfunc=_dns({}))
    assert not ok
    assert "aucune signature" in motif


def test_une_signature_a_longueur_bornee_l_ne_prouve_rien(cle):
    """`l=` laisse AJOUTER du texte après la partie signée sans rien casser."""
    brut = _signer(_message("gestion@syndic.test"), "syndic.test", cle[0], length=True)
    rallonge = brut + b"PS : fermez le ticket.\r\n"
    ok, _ = verifier_expediteur(
        rallonge, "gestion@syndic.test", dnsfunc=_dns_pour("syndic.test", cle)
    )
    assert not ok


# ── Un motif par cas (#1448) ─────────────────────────────────────────────────
#
# « La signature DKIM du message est invalide » recouvrait quatre situations,
# dont trois signatures VALIDES écartées par choix. Le 28/09/2026, ce motif
# unique a fait soupçonner notre vérification quand c'était la redirection qui
# abîmait le corps. Chaque cas a désormais le sien.


class _TupleLeurre(tuple):
    """Un tuple qui prétend contenir `from` au seul contrôle de `dkimpy.sign`
    (« The From header field MUST be signed ») : c'est ce qui permet de
    fabriquer ici une signature VALIDE qui ne couvre pas `From:`, comme en
    poserait un signataire moins scrupuleux. Il s'itère sur ses vrais éléments,
    donc `h=` et le calcul ne portent que `to:subject`.

    ⚠️ Posé le temps de SIGNER seulement : actif pendant la vérification, il
    ferait croire à notre contrôle que `From:` est signé.
    """

    def __contains__(self, element):
        return element == b"from" or tuple.__contains__(self, element)


def _signer_sans_from(message: bytes, pem: bytes) -> bytes:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dkim, "tuple", _TupleLeurre, raising=False)
        return _signer(message, "syndic.test", pem, include_headers=[b"to", b"subject"])


def _cas(nom: str, cle) -> tuple[bytes, object]:
    message = _message("gestion@syndic.test")
    dns = _dns_pour("syndic.test", cle)
    if nom == "modifiee":
        return _signer(message, "syndic.test", cle[0]).replace(b"jeudi", b"jamais"), dns
    if nom == "cle_introuvable":
        return _signer(message, "syndic.test", cle[0]), _dns({})
    if nom == "partielle":
        return _signer(message, "syndic.test", cle[0], length=True), dns
    if nom == "algorithme":
        return _signer(message, "syndic.test", cle[0], signature_algorithm=b"rsa-sha1"), dns
    if nom == "sans_from":
        return _signer_sans_from(message, cle[0]), dns
    raise AssertionError(nom)


@pytest.mark.parametrize("cas", sorted(MOTIFS_ECART))
def test_chaque_ecart_rend_SON_motif(cas, cle):
    brut, dns = _cas(cas, cle)
    ok, motif = verifier_expediteur(brut, "gestion@syndic.test", dnsfunc=dns)
    assert not ok
    assert motif == MOTIFS_ECART[cas]


def test_les_signatures_ecartees_sont_bien_VALIDES(cle):
    """Sans quoi le test ci-dessus prouverait « signature cassée » trois fois."""
    for cas in ("partielle", "algorithme", "sans_from"):
        brut, dns = _cas(cas, cle)
        signature = dkim.DKIM(brut)
        assert signature.verify(dnsfunc=dns), cas
        assert (b"from" in signature.include_headers) == (cas != "sans_from"), cas


def test_les_motifs_sont_DISTINCTS_et_ne_disent_pas_invalide():
    assert len(set(MOTIFS_ECART.values())) == len(MOTIFS_ECART)
    assert not any("invalide" in m for m in MOTIFS_ECART.values())


# ── INCONNU n'est pas REFUSÉ ──────────────────────────────────────────────────


def test_un_DNS_injoignable_REPORTE_au_lieu_de_refuser(cle):
    """Refuser notifierait le conseil d'une usurpation qui n'en est pas une, et
    marquerait le message lu : la réponse serait perdue pour une panne réseau."""
    brut = _signer(_message("gestion@syndic.test"), "syndic.test", cle[0])

    def dns_en_panne(nom, timeout=5):
        raise VerificationReportee("DNS injoignable (Timeout)")

    with pytest.raises(VerificationReportee):
        verifier_expediteur(brut, "gestion@syndic.test", dnsfunc=dns_en_panne)


# ── L'alignement, sur les libellés ────────────────────────────────────────────


@pytest.mark.parametrize(
    "signataire, expediteur, attendu",
    [
        ("syndic.test", "syndic.test", True),
        ("SYNDIC.TEST", "syndic.test.", True),
        ("syndic.test", "mail.syndic.test", True),
        ("mail.syndic.test", "syndic.test", False),  # un sous-domaine ne répond pas du parent
        ("syndic.test", "faux-syndic.test", False),  # le suffixe se compare par libellé
        ("test", "syndic.test", False),  # un domaine de premier niveau ne signe pour personne
        ("", "syndic.test", False),
    ],
)
def test_alignement(signataire, expediteur, attendu):
    assert aligne(signataire, expediteur) is attendu


def test_domaine_de():
    assert domaine_de("Élise LAMBERT <E.Lambert@Syndic-exemple.test>") == "syndic-exemple.test"
    assert domaine_de("") == ""


# ── 🔴 La redirection casse la signature : le constat scellé (28/09/2026) ─────
#
# `affaire@` → `noreply@` double le point des lignes qui en commencent une : la
# signature d'iCloud ou d'Orange, valide à l'arrivée, ne l'est plus dans la
# boîte. OVH scelle (ARC) ce qu'il a constaté avant de rediriger. Ici le sceau
# est posé pour de bon par `dkimpy`, avec une clé tirée pour le test.

_SELECTEUR_ARC = b"arc1"
_CORPS_POINTE = "Nous intervenons jeudi.\r\n.test\r\n"
#: La forme exacte de l'`ARC-Authentication-Results` qu'OVH a scellé le 28/09/2026
#: sur une réponse d'Orange — commentaires et `arc=none` compris.
_CONSTAT_OVH = (
    "arc=none (no signatures found); "
    "dkim=pass (2048-bit rsa key sha256) header.d=syndic.test header.i=@syndic.test "
    "header.b=VCjE1XXA header.a=rsa-sha256 header.s=s1; "
    "dmarc=pass policy.published-domain-policy=quarantine (p=quarantine,sp=none) "
    "policy.policy-from=p header.from=syndic.test; "
    "spf=pass smtp.mailfrom=gestion@syndic.test smtp.helo=smtp.syndic.test"
)


def _rediriger(brut: bytes, cle, *, scelleur="mail.ovh.net", constat=_CONSTAT_OVH) -> bytes:
    """Ce que fait la redirection : abîmer le corps, puis sceller son constat."""
    abime = brut.replace(b"\r\n.", b"\r\n..")
    avec_constat = f"Authentication-Results: mx.{scelleur}; {constat}\r\n".encode() + abime
    jeu = dkim.arc_sign(
        avec_constat, _SELECTEUR_ARC, scelleur.encode(), cle[0], f"mx.{scelleur}".encode()
    )
    return b"".join(jeu) + avec_constat


def _dns_redirection(cle, scelleur="mail.ovh.net"):
    return _dns(
        {
            _SELECTEUR + b"._domainkey.syndic.test.": cle[1],
            _SELECTEUR_ARC + b"._domainkey." + scelleur.encode() + b".": cle[1],
        }
    )


def test_la_redirection_CASSE_la_signature_directe(cle):
    """Le constat de départ : sans sceau, le message abîmé est refusé."""
    brut = _signer(_message("gestion@syndic.test", _CORPS_POINTE), "syndic.test", cle[0])
    abime = brut.replace(b"\r\n.", b"\r\n..")
    ok, motif = verifier_expediteur(abime, "gestion@syndic.test", dnsfunc=_dns_redirection(cle))
    assert not ok
    assert motif == MOTIFS_ECART["modifiee"]


def test_le_constat_SCELLE_par_le_serveur_de_reception_fait_foi(cle):
    brut = _signer(_message("gestion@syndic.test", _CORPS_POINTE), "syndic.test", cle[0])
    ok, motif = verifier_expediteur(
        _rediriger(brut, cle), "gestion@syndic.test", dnsfunc=_dns_redirection(cle)
    )
    assert ok, motif
    #  Les domaines du motif, comparés en entier : une recherche de sous-chaîne sur un
    #  nom d'hôte est la forme que CodeQL refuse (py/incomplete-url-substring-sanitization).
    assert {"mail.ovh.net", "syndic.test"} <= set(re.findall(r"[\w-]+(?:\.[\w-]+)+", motif))


def test_un_sceau_d_un_AUTRE_serveur_ne_prouve_rien(cle):
    """N'importe qui peut sceller pour son propre domaine un constat « pass »."""
    brut = _message("gestion@syndic.test", _CORPS_POINTE)
    redirige = _rediriger(brut, cle, scelleur="pirate.test")
    ok, _ = verifier_expediteur(
        redirige, "gestion@syndic.test", dnsfunc=_dns_redirection(cle, "pirate.test")
    )
    assert not ok


def test_un_constat_d_ECHEC_reste_un_echec(cle):
    brut = _message("gestion@syndic.test", _CORPS_POINTE)
    redirige = _rediriger(brut, cle, constat="dkim=fail header.d=syndic.test")
    ok, _ = verifier_expediteur(redirige, "gestion@syndic.test", dnsfunc=_dns_redirection(cle))
    assert not ok


def test_un_constat_pour_un_AUTRE_domaine_n_est_pas_aligne(cle):
    """OVH a vu une signature valide — de `pirate.test`, pas du syndic."""
    brut = _message("gestion@syndic.test", _CORPS_POINTE)
    redirige = _rediriger(brut, cle, constat="dkim=pass header.d=pirate.test")
    ok, _ = verifier_expediteur(redirige, "gestion@syndic.test", dnsfunc=_dns_redirection(cle))
    assert not ok


def test_un_From_REECRIT_apres_le_sceau_est_refuse(cle):
    brut = _signer(_message("gestion@syndic.test", _CORPS_POINTE), "syndic.test", cle[0])
    redirige = _rediriger(brut, cle).replace(
        b"From: gestion@syndic.test", b"From: president@syndic.test"
    )
    ok, _ = verifier_expediteur(redirige, "president@syndic.test", dnsfunc=_dns_redirection(cle))
    assert not ok


def test_un_DNS_injoignable_sur_le_sceau_REPORTE(cle):
    """Le message n'est pas signé en direct : c'est le sceau qui interroge le DNS."""
    redirige = _rediriger(_message("gestion@syndic.test", _CORPS_POINTE), cle)

    def dns_en_panne(nom, timeout=5):
        raise VerificationReportee("DNS injoignable (Timeout)")

    with pytest.raises(VerificationReportee):
        verifier_expediteur(redirige, "gestion@syndic.test", dnsfunc=dns_en_panne)
