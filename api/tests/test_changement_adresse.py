"""Changer l'adresse d'un compte : le mot de passe, puis la nouvelle adresse confirmée (#1549).

## Le défaut (audit du 02/10/2026)

`PATCH /auth/me {"email": …}` remplaçait l'adresse sur-le-champ : ni mot de
passe, ni re-vérification, ni avis, ni journal. L'administrateur faisait de même
pour un autre compte. Une session en cours suffisait donc — poste partagé,
cookie volé :

1. `PATCH /auth/me {"email": "attaquant@…"}` ;
2. `POST /auth/mot-de-passe-oublie` sur cette adresse ;
3. mot de passe posé par l'attaquant, toutes les autres sessions fermées —

et la victime ne recevait rien : son adresse n'était plus celle du compte.
L'inscription, elle, exige qu'une adresse soit prouvée avant d'ouvrir la porte.

## La règle tenue ici

- changer l'adresse — la sienne ou, pour l'administrateur, celle d'un autre —
  exige le mot de passe de **celui qui agit** ;
- la nouvelle adresse ne remplace l'ancienne qu'une fois **confirmée** par le
  lien envoyé à la nouvelle (jeton stocké par empreinte, expirant) ; d'ici là,
  l'ancienne reste celle du compte, connexion comprise ;
- l'**ancienne** adresse reçoit un avis ;
- la demande et la confirmation sont journalisées, sans aucune adresse.

Le lien se rejoue (`standards/03` §5 bis) : les messageries l'ouvrent avant le
destinataire ; un jeton dont l'effet est acquis répond « déjà confirmée ».
"""

from __future__ import annotations

import ast
import asyncio
import logging
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from sqlmodel import select

from app.auth.empreinte_jeton import empreinte
from app.auth.jwt import hash_password
from app.models.core import EmailVerificationToken, RoleUtilisateur
from app.routers import auth, auth_profil
from app.routers.admin import utilisateurs as admin_utilisateurs
from app.routers.auth_schemas import LoginRequest
from app.utils import horloge
from tests.aides_base import compte
from tests.aides_sources import modules_app
from tests.conftest import requete_de_test

MDP = "Mdp-Actuel-1"
NOUVELLE = "nouvelle.adresse@exemple.test"


@pytest.fixture()
def courriels(monkeypatch) -> list[tuple[str, str, dict]]:
    """Les courriels « envoyés » : (code, destinataire, contexte) — rien ne part."""
    envois: list[tuple[str, str, dict]] = []

    async def _intercepter(code, to, context, *args, **kwargs):  # noqa: ARG001
        envois.append((code, to, context))

    monkeypatch.setattr("app.utils.email.send_email", _intercepter)
    return envois


def _titulaire(session, **champs):
    valeurs = {"hashed_password": hash_password(MDP), "email_verifie": True}
    valeurs.update(champs)
    return compte(session, prefixe="titulaire", **valeurs)


def _profil(session, user, **champs):
    """`PATCH /auth/me`, tâches de fond exécutées (les courriels sont interceptés)."""
    taches = BackgroundTasks()
    lu = auth_profil.update_me(
        requete_de_test("/auth/me", "PATCH"),
        body=auth_profil.MeUpdate(**champs),
        background_tasks=taches,
        session=session,
        user=user,
    )
    asyncio.run(taches())
    return lu


def _confirmer(session, brut):
    return auth.verify_email(
        requete_de_test("/auth/verifier-email", "GET"), token=brut, session=session
    )


def _lien(courriels, a: str) -> str:
    """Le jeton brut du dernier lien de vérification envoyé à `a`."""
    liens = [ctx["lien"] for code, to, ctx in courriels if code == "verification_email" and to == a]
    assert liens, f"aucun lien de vérification envoyé à {a}"
    return parse_qs(urlparse(liens[-1]).query)["token"][0]


def _connexion(session, adresse):
    return auth.login(
        requete_de_test("/auth/login"),
        body=LoginRequest(email=adresse, password=MDP),
        response=Response(),
        session=session,
    )


def _aucune_adresse_journalisee(caplog, *adresses):
    for rec in caplog.records:
        for adresse in adresses:
            assert adresse not in rec.getMessage(), f"adresse journalisée : {rec.getMessage()}"


# ── La demande ────────────────────────────────────────────────────────────────


def test_sans_mot_de_passe_l_adresse_ne_change_pas(session, courriels):
    user = _titulaire(session)
    ancienne = user.email
    with pytest.raises(HTTPException) as exc:
        _profil(session, user, email=NOUVELLE)
    assert exc.value.status_code == 400
    session.refresh(user)
    assert user.email == ancienne
    assert not courriels
    assert not session.exec(select(EmailVerificationToken)).all()


def test_un_mauvais_mot_de_passe_est_refuse_et_journalise(session, courriels, caplog):
    user = _titulaire(session)
    with caplog.at_level(logging.INFO, logger="securite"):
        with pytest.raises(HTTPException) as exc:
            _profil(session, user, email=NOUVELLE, mot_de_passe_actuel="pas-le-bon")
    assert exc.value.status_code == 400
    assert any("connexion_refusee" in r.getMessage() for r in caplog.records)
    _aucune_adresse_journalisee(caplog, NOUVELLE, user.email)
    assert not courriels


def test_la_demande_garde_l_ancienne_adresse_et_previent_les_deux(session, courriels, caplog):
    user = _titulaire(session)
    ancienne = user.email
    with caplog.at_level(logging.INFO, logger="securite"):
        lu = _profil(
            session, user, email="  Nouvelle.Adresse@Exemple.TEST ", mot_de_passe_actuel=MDP
        )

    session.refresh(user)
    assert lu.email == ancienne and user.email == ancienne, "l'adresse a changé sans confirmation"
    assert user.email_verifie, "l'ancienne adresse, toujours celle du compte, reste vérifiée"

    #  La nouvelle reçoit le lien, l'ancienne l'avis — et rien d'autre ne part.
    assert sorted((code, to) for code, to, _ in courriels) == sorted(
        [("verification_email", NOUVELLE), ("adresse_changement_avis", ancienne)]
    )
    avis = next(ctx for code, _, ctx in courriels if code == "adresse_changement_avis")
    assert avis["nouvelle_adresse"] == NOUVELLE

    #  Le jeton est stocké par son empreinte, avec l'adresse qu'il confirmera.
    brut = _lien(courriels, NOUVELLE)
    evt = session.exec(select(EmailVerificationToken)).one()
    assert evt.token == empreinte(brut) and brut not in evt.token
    assert evt.nouvelle_adresse == NOUVELLE
    assert evt.expires_at > horloge.maintenant()

    assert any("adresse_changement_demande" in r.getMessage() for r in caplog.records)
    _aucune_adresse_journalisee(caplog, NOUVELLE, ancienne)


def test_la_meme_adresse_a_la_casse_pres_n_est_pas_un_changement(session, courriels):
    user = _titulaire(session)
    _profil(session, user, email=user.email.upper(), prenom="Autre")
    assert not courriels
    assert not session.exec(select(EmailVerificationToken)).all()


def test_une_adresse_prise_n_est_revelee_qu_apres_le_mot_de_passe(session, courriels):
    user = _titulaire(session)
    autre = compte(session, prefixe="autre")
    with pytest.raises(HTTPException) as sans:
        _profil(session, user, email=autre.email)
    assert "mot de passe" in sans.value.detail.lower(), "l'existence d'un compte fuite"
    with pytest.raises(HTTPException) as avec:
        _profil(session, user, email=autre.email, mot_de_passe_actuel=MDP)
    assert "déjà utilisée" in avec.value.detail
    assert not courriels


# ── La confirmation ───────────────────────────────────────────────────────────


def test_le_lien_confirme_et_se_rejoue(session, courriels, caplog):
    """§5 bis : le scanner de la messagerie passe, puis le destinataire."""
    user = _titulaire(session)
    _profil(session, user, email=NOUVELLE, mot_de_passe_actuel=MDP)
    brut = _lien(courriels, NOUVELLE)

    with caplog.at_level(logging.INFO, logger="securite"):
        premier = _confirmer(session, brut)
    second = _confirmer(session, brut)
    session.refresh(user)

    assert user.email == NOUVELLE and user.email_verifie
    assert premier["changement_adresse"] and second["changement_adresse"]
    assert "déjà" in second["message"]
    assert any("adresse_changee" in r.getMessage() for r in caplog.records)
    _aucune_adresse_journalisee(caplog, NOUVELLE)
    with pytest.raises(HTTPException):
        _confirmer(session, "jeton-que-personne-n-a-recu")


def test_la_connexion_suit_la_confirmation(session, courriels):
    user = _titulaire(session)
    ancienne = user.email
    _profil(session, user, email=NOUVELLE, mot_de_passe_actuel=MDP)
    assert _connexion(session, ancienne).id == user.id, "l'ancienne doit rester active"

    _confirmer(session, _lien(courriels, NOUVELLE))
    assert _connexion(session, NOUVELLE).id == user.id
    with pytest.raises(HTTPException) as exc:
        _connexion(session, ancienne)
    assert exc.value.status_code == 401


def test_un_lien_expire_ne_change_rien(session, courriels):
    user = _titulaire(session)
    ancienne = user.email
    _profil(session, user, email=NOUVELLE, mot_de_passe_actuel=MDP)
    evt = session.exec(select(EmailVerificationToken)).one()
    evt.expires_at = horloge.maintenant() - timedelta(minutes=1)
    session.add(evt)
    session.commit()

    with pytest.raises(HTTPException) as exc:
        _confirmer(session, _lien(courriels, NOUVELLE))
    session.refresh(user)
    assert exc.value.status_code == 400 and user.email == ancienne


def test_une_seconde_demande_annule_la_premiere(session, courriels):
    user = _titulaire(session)
    _profil(session, user, email=NOUVELLE, mot_de_passe_actuel=MDP)
    premier = _lien(courriels, NOUVELLE)
    _profil(session, user, email="encore.une@exemple.test", mot_de_passe_actuel=MDP)

    with pytest.raises(HTTPException):
        _confirmer(session, premier)
    _confirmer(session, _lien(courriels, "encore.une@exemple.test"))
    session.refresh(user)
    assert user.email == "encore.une@exemple.test"


def test_une_adresse_prise_entre_temps_n_est_pas_volee(session, courriels):
    user = _titulaire(session)
    ancienne = user.email
    _profil(session, user, email=NOUVELLE, mot_de_passe_actuel=MDP)
    compte(session, email=NOUVELLE)  # quelqu'un s'est inscrit avec, depuis

    with pytest.raises(HTTPException) as exc:
        _confirmer(session, _lien(courriels, NOUVELLE))
    session.refresh(user)
    assert exc.value.status_code == 400 and user.email == ancienne


# ── L'administrateur : la même règle, avec SON mot de passe ──────────────────


def _admin_modifie(session, admin, cible, **champs):
    taches = BackgroundTasks()
    lu = admin_utilisateurs.modifier_utilisateur(
        cible.id,
        body=admin_utilisateurs.AdminUserUpdate(**champs),
        background_tasks=taches,
        session=session,
        admin=admin,
    )
    asyncio.run(taches())
    return lu


def test_l_administrateur_suit_la_meme_regle(session, courriels, caplog):
    admin = _titulaire(session, role=RoleUtilisateur.admin, roles_json="admin")
    cible = compte(session, prefixe="cible", email_verifie=True)
    ancienne = cible.email

    with pytest.raises(HTTPException):
        _admin_modifie(session, admin, cible, email=NOUVELLE)
    with caplog.at_level(logging.INFO, logger="securite"):
        lu = _admin_modifie(session, admin, cible, email=NOUVELLE, mot_de_passe_actuel=MDP)

    session.refresh(cible)
    assert lu.email == ancienne and cible.email == ancienne
    assert ("adresse_changement_avis", ancienne) in [(c, t) for c, t, _ in courriels]
    demande = [
        r.getMessage() for r in caplog.records if "adresse_changement_demande" in r.getMessage()
    ]
    assert demande and f"acteur={admin.id}" in demande[0] and f"cible={cible.id}" in demande[0]

    _confirmer(session, _lien(courriels, NOUVELLE))
    session.refresh(cible)
    assert cible.email == NOUVELLE


def test_l_administrateur_modifie_le_reste_sans_mot_de_passe(session, courriels):
    """Le mot de passe n'est demandé que pour l'adresse : corriger un nom reste simple."""
    admin = _titulaire(session, role=RoleUtilisateur.admin, roles_json="admin")
    cible = compte(session, prefixe="cible")
    lu = _admin_modifie(session, admin, cible, email=cible.email, prenom="Odile")
    assert lu.prenom == "Odile" and not courriels


# ── La classe : l'adresse d'un compte ne s'écrit qu'à la confirmation ────────

#: Le seul endroit où l'adresse d'un compte existant change : le lien servi.
#: Créer un compte (`Utilisateur(email=…)`) n'est pas changer une adresse.
ECRITURE_PERMISE = "utils/verification_adresse.py"


def _ecritures_d_adresse(source: str) -> list[int]:
    """Les lignes qui écrivent un attribut `email` : `x.email = …`, `setattr(x, "email", …)`."""
    lignes = []
    for n in ast.walk(ast.parse(source)):
        cibles = n.targets if isinstance(n, ast.Assign) else []
        if isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            cibles = [n.target]
        if any(isinstance(c, ast.Attribute) and c.attr == "email" for c in cibles):
            lignes.append(n.lineno)
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "setattr"
            and len(n.args) >= 2
            and isinstance(n.args[1], ast.Constant)
            and n.args[1].value == "email"
        ):
            lignes.append(n.lineno)
    return lignes


def test_l_adresse_ne_s_ecrit_qu_a_la_confirmation():
    """Une route qui écrirait l'adresse elle-même rouvrirait #1549, sans un mot."""
    fautes = [
        f"app/{m.rel}:{ligne}"
        for m in modules_app()
        if m.rel != ECRITURE_PERMISE
        for ligne in _ecritures_d_adresse(m.source)
    ]
    assert not fautes, (
        "L'adresse d'un compte s'écrit ailleurs qu'à la confirmation du lien — "
        "passer par `demander_changement_adresse` :\n" + "\n".join(fautes)
    )


def test_le_releve_voit_une_ecriture_d_adresse():
    """Cas zéro, et témoin : la confirmation écrit bien l'adresse, et elle seule."""
    assert _ecritures_d_adresse("user.email = nouvelle\n") == [1]
    assert _ecritures_d_adresse('setattr(user, "email", v)\n') == [1]
    assert _ecritures_d_adresse("Utilisateur(email=a)\nx = user.email\n") == []
    source = next(m.source for m in modules_app() if m.rel == ECRITURE_PERMISE)
    assert _ecritures_d_adresse(source), f"app/{ECRITURE_PERMISE} n'écrit plus l'adresse"


@pytest.mark.parametrize(
    "adresse, admise",
    [
        ("prenom.nom@exemple.test", True),
        ("a+b@sous.exemple.test", True),
        ("sans-point@exemple", False),
        ("a@.exemple.test", False),
        ("a@exemple..test", False),
        ("a@exemple.test.", False),
        ("a b@exemple.test", False),
    ],
)
def test_la_forme_d_une_adresse(adresse, admise):
    from app.utils.verification_adresse import _FORME_ADRESSE

    assert bool(_FORME_ADRESSE.fullmatch(adresse)) is admise


def test_la_forme_d_une_adresse_se_lit_en_temps_lineaire():
    """Le point flottant du domaine coûtait n² sur une saisie sans point (#2882)."""
    import time

    from app.utils.verification_adresse import _FORME_ADRESSE

    debut = time.perf_counter()
    assert not _FORME_ADRESSE.fullmatch("a@" + "!" * 50_000 + "@")
    assert not _FORME_ADRESSE.fullmatch("a@" + "!." * 50_000 + " ")
    assert time.perf_counter() - debut < 1
