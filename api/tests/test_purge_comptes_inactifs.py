"""La purge des comptes inactifs (#1580) : avertir, attendre, puis supprimer.

## La règle arbitrée (04/10/2026)

La politique de confidentialité annonçait « durée de la relation + 2 ans » sans
qu'aucun code ne l'applique — une durée fictive (`standards/14` §1). Arbitrage de
Philippe : un compte **sans connexion depuis 2 ans** reçoit un **avertissement
par courriel**, puis il est **supprimé 30 jours plus tard** s'il ne s'est pas
reconnecté entre-temps.

## Ce que ces tests tiennent, et pourquoi chacun

La suppression est **irréversible** : chaque test garde une des conditions sans
lesquelles elle ne doit pas avoir lieu — un avertissement réellement parti, daté
d'au moins 30 jours, un compte toujours inactif, qui n'est ni un administrateur
ni le gestionnaire du site, et un passage dont le volume n'a rien d'anormal.

Les noms sont fictifs (`test_identites_fictives.py`) : `compte()` pose
« Prénom Nom ».
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from fastapi import Response
from sqlmodel import select

from app.auth.empreinte_jeton import empreinte
from app.auth.jwt import create_refresh_token, hash_password
from app.models.core import ConfigSite, RefreshToken, Utilisateur
from app.routers.auth import login, refresh
from app.routers.auth_schemas import LoginRequest
from app.utils import horloge
from app.utils.purge_comptes import regles
from app.utils.purge_comptes import tache as tache_purge
from app.utils.purge_comptes.tache import purger_comptes_inactifs
from tests.aides_base import compte
from tests.conftest import requete_de_test

#: L'instant simulé du passage. Les comptes sont vieillis par rapport à lui :
#: c'est l'horloge qu'on simule, jamais la règle.
T = horloge.maintenant()
INACTIF = T - regles.INACTIVITE - timedelta(days=1)


class _Envois:
    """Le facteur simulé : il note ce qu'on lui confie, et réussit ou échoue."""

    def __init__(self, reussit: bool = True):
        self.reussit = reussit
        self.recus: list[tuple[int, dict]] = []

    def __call__(self, session, user, contexte) -> bool:
        self.recus.append((user.id, contexte))
        return self.reussit


@pytest.fixture()
def journal(caplog):
    """Les lignes du journal de sécurité — et rien qu'elles."""
    caplog.set_level(logging.INFO, logger="securite")
    return lambda: [r.getMessage() for r in caplog.records if r.name == "securite"]


def _inactif(session, **champs) -> Utilisateur:
    return compte(session, prefixe="inactif", derniere_connexion=INACTIF, **champs)


def _averti(session, il_y_a: timedelta, **champs) -> Utilisateur:
    return _inactif(session, purge_avertie_le=T - il_y_a, **champs)


def _existe(session, user_id: int) -> bool:
    session.expire_all()
    return session.get(Utilisateur, user_id) is not None


def _passer(session, envois=None, maintenant=T):
    return purger_comptes_inactifs(session, maintenant=maintenant, envoyer=envois or _Envois())


# ── Les cas ordinaires ───────────────────────────────────────────────────────


def test_un_compte_actif_n_est_pas_touche(session):
    recent = compte(session, prefixe="recent", derniere_connexion=T - timedelta(days=10))
    envois = _Envois()
    rendu = _passer(session, envois)
    assert envois.recus == []
    assert rendu["avertis"] == 0 and rendu["supprimes"] == 0
    session.refresh(recent)
    assert recent.purge_avertie_le is None


def test_inactif_depuis_deux_ans_il_est_averti_et_rien_n_est_supprime(session, journal):
    vieux = _inactif(session)
    envois = _Envois()
    rendu = _passer(session, envois)
    assert rendu["avertis"] == 1 and rendu["supprimes"] == 0
    assert _existe(session, vieux.id), "un avertissement ne supprime rien"
    session.refresh(vieux)
    assert vieux.purge_avertie_le == T, "la date de l'avertissement doit être mémorisée"
    ((destinataire, contexte),) = envois.recus
    assert destinataire == vieux.id
    #  Le courriel dit QUAND, et ce qu'il suffit de faire : le contexte porte la date.
    assert set(contexte) == {"destinataire", "date_suppression", "derniere_activite"}
    assert str((T + regles.DELAI_AVANT_SUPPRESSION).year) in contexte["date_suppression"]
    assert journal() == [f"securite compte_purge_averti acteur=- cible={vieux.id}"]


def test_sans_connexion_la_date_de_reference_est_celle_du_compte(session):
    """Jamais connecté : la création, ou la validation si elle est postérieure."""
    jamais = compte(session, prefixe="jamais", cree_le=INACTIF, derniere_connexion=None)
    valide_tard = compte(
        session,
        prefixe="tard",
        cree_le=INACTIF,
        decision_compte_le=T - timedelta(days=30),
        derniere_connexion=None,
    )
    assert regles.date_de_reference(jamais) == INACTIF
    assert regles.date_de_reference(valide_tard) == T - timedelta(days=30)
    envois = _Envois()
    _passer(session, envois)
    assert [uid for uid, _ in envois.recus] == [jamais.id]


def test_averti_il_y_a_31_jours_et_toujours_inactif_il_est_supprime(session, journal, monkeypatch):
    """Par la suppression de l'administration — la même fonction, jamais une seconde."""
    vise = _averti(session, timedelta(days=31))
    jeton = RefreshToken(user_id=vise.id, token="x", expires_at=T + timedelta(days=1))
    session.add(jeton)
    session.commit()
    appels = []
    from app.utils import suppression_compte

    vraie = suppression_compte.supprimer_compte

    def espion(s, user_id):
        appels.append(user_id)
        return vraie(s, user_id)

    monkeypatch.setattr(tache_purge, "supprimer_compte", espion)
    cible = vise.id
    rendu = _passer(session)
    assert rendu["supprimes"] == 1
    assert appels == [cible], "la purge doit passer par `supprimer_compte`"
    assert not _existe(session, cible)
    assert session.exec(select(RefreshToken).where(RefreshToken.user_id == cible)).all() == []
    lignes = journal()
    assert len(lignes) == 1 and lignes[0].startswith(
        f"securite compte_purge_inactivite acteur=- cible={cible}"
    )
    assert "@" not in lignes[0], "le journal nomme un identifiant, jamais une adresse"


def test_averti_il_y_a_29_jours_il_attend_encore(session):
    vise = _averti(session, timedelta(days=29))
    rendu = _passer(session)
    assert rendu["supprimes"] == 0 and rendu["avertis"] == 0
    assert _existe(session, vise.id)


def test_une_reconnexion_par_jeton_remet_l_etat_a_zero(session):
    """Un résident qui reste connecté ne passe JAMAIS par l'écran de connexion :
    c'est l'échange du jeton de rafraîchissement qui doit dire qu'il est là."""
    vise = _averti(session, timedelta(days=31))
    brut = create_refresh_token({"sub": str(vise.id)})
    session.add(
        RefreshToken(
            user_id=vise.id,
            token=empreinte(brut),
            expires_at=horloge.maintenant() + timedelta(days=7),
        )
    )
    session.commit()
    refresh(requete_de_test("/auth/refresh"), Response(), refresh_token=brut, session=session)
    session.refresh(vise)
    assert vise.purge_avertie_le is None, "la reconnexion n'a pas annulé l'avertissement"
    assert vise.derniere_connexion is not None and vise.derniere_connexion > INACTIF
    rendu = _passer(session, maintenant=horloge.maintenant())
    assert rendu["supprimes"] == 0
    assert _existe(session, vise.id)


def test_une_connexion_remet_l_etat_a_zero(session):
    vise = _averti(session, timedelta(days=31), hashed_password=hash_password("Secret-123"))
    vise.email_verifie = True
    session.add(vise)
    session.commit()
    corps = LoginRequest(email=vise.email, password="Secret-123")
    login(requete_de_test("/auth/login"), corps, Response(), session)
    session.refresh(vise)
    assert vise.purge_avertie_le is None
    assert _existe(session, vise.id)


def test_une_activite_posterieure_a_l_avertissement_empeche_la_suppression(session):
    """Ceinture et bretelles : un état mal remis à zéro ne suffit pas à supprimer."""
    vise = _averti(session, timedelta(days=31))
    vise.derniere_connexion = T - timedelta(days=5)
    session.add(vise)
    session.commit()
    rendu = _passer(session)
    assert rendu["supprimes"] == 0
    session.refresh(vise)
    assert vise.purge_avertie_le is None


def test_un_avertissement_trop_ancien_est_renvoye_jamais_execute(session):
    """Un avertissement resté sans suite (compte désactivé puis réactivé, purge
    suspendue des semaines) ne vaut plus : la personne est prévenue à nouveau."""
    vise = _averti(session, regles.VALIDITE_AVERTISSEMENT + timedelta(days=1))
    envois = _Envois()
    rendu = _passer(session, envois)
    assert rendu["supprimes"] == 0 and rendu["avertis"] == 1
    assert _existe(session, vise.id)
    session.refresh(vise)
    assert vise.purge_avertie_le == T


# ── Un courriel qui ne part pas n'est pas un avertissement ────────────────────


def test_un_echec_d_envoi_n_enregistre_rien(session, journal):
    vise = _inactif(session)
    rendu = _passer(session, _Envois(reussit=False))
    assert rendu["avertis"] == 0 and rendu["echecs_envoi"] == 1
    session.refresh(vise)
    assert vise.purge_avertie_le is None, (
        "un courriel non parti a été compté comme un avertissement"
    )
    assert journal() == []
    #  …et donc, trente et un jours plus tard, rien n'est supprimé.
    rendu = _passer(session, _Envois(reussit=False), maintenant=T + timedelta(days=31))
    assert rendu["supprimes"] == 0
    assert _existe(session, vise.id)


def test_le_vrai_moteur_smtp_eteint_n_avertit_personne(session):
    """Le facteur par défaut, sans configuration d'envoi : `send_email` ne part pas,
    et doit le DIRE — sinon la purge croirait avoir prévenu."""
    session.add(ConfigSite(cle="smtp_enabled", valeur="0"))
    session.commit()
    vise = _inactif(session)
    rendu = purger_comptes_inactifs(session, maintenant=T)
    assert rendu["avertis"] == 0 and rendu["echecs_envoi"] == 1
    session.refresh(vise)
    assert vise.purge_avertie_le is None


def test_send_email_dit_s_il_est_parti(session, monkeypatch):
    """Le contrat dont la purge dépend : vrai si le message est parti, faux sinon."""
    import asyncio

    from app.models.core import ModeleEmail
    from app.seed import EMAIL_TEMPLATES
    from app.utils.email import send_email

    code, libelle, sujet, corps, _ = next(
        r for r in EMAIL_TEMPLATES if r[0] == "compte_inactif_avertissement"
    )
    session.add(ModeleEmail(code=code, libelle=libelle, sujet=sujet, corps_html=corps))
    session.add(ConfigSite(cle="smtp_enabled", valeur="1"))
    session.commit()

    class _FauxFastMail:
        echoue = False

        def __init__(self, cfg):
            pass

        async def send_message(self, message):
            if _FauxFastMail.echoue:
                raise ConnectionError("serveur injoignable")

    monkeypatch.setattr("fastapi_mail.FastMail", _FauxFastMail)
    #  La connexion n'est pas ce qu'on éprouve : sa validation exigerait un serveur réel.
    monkeypatch.setattr("app.utils.email.connexion_smtp", lambda *a, **k: None)
    contexte = {
        "destinataire": {"prenom": "Prénom", "nom": "Nom"},
        "date_suppression": "1er janvier 2030",
        "derniere_activite": "1er janvier 2028",
    }
    assert asyncio.run(send_email(code, "resident@example.com", contexte, session)) is True
    _FauxFastMail.echoue = True
    assert asyncio.run(send_email(code, "resident@example.com", contexte, session)) is False


# ── Ceux que la purge ne supprime jamais ─────────────────────────────────────


def test_un_administrateur_n_est_jamais_supprime_seulement_signale(session, journal):
    admin = _averti(session, timedelta(days=40), roles_json="résident,admin")
    envois = _Envois()
    rendu = _passer(session, envois)
    assert rendu["supprimes"] == 0 and rendu["avertis"] == 0
    assert rendu["epargnes"] == 1
    assert envois.recus == [], "un administrateur n'est pas averti : il n'est pas concerné"
    assert _existe(session, admin.id)
    assert journal() == [
        f"securite compte_purge_epargne acteur=- cible={admin.id} administrateur inactif"
    ]


def test_le_gestionnaire_du_site_n_est_jamais_supprime(session):
    gestionnaire = _averti(session, timedelta(days=40), roles_json="résident,admin")
    session.add(ConfigSite(cle="site_manager_user_id", valeur=str(gestionnaire.id)))
    session.commit()
    _passer(session)
    assert _existe(session, gestionnaire.id)
    assert regles.exclusion(gestionnaire, gestionnaire.id) is not None


@pytest.mark.parametrize(
    "champs",
    [
        {"actif": False},  # en attente de validation : le conseil n'a pas tranché
        {"actif": False, "decision_compte_le": INACTIF},  # refusé ou désactivé
    ],
    ids=["en_attente", "desactive"],
)
def test_un_compte_qui_ne_peut_pas_se_connecter_n_est_ni_averti_ni_supprime(session, champs):
    """« Il suffit de vous connecter » serait faux : il ne le peut pas."""
    vise = _averti(session, timedelta(days=40), **champs)
    envois = _Envois()
    rendu = _passer(session, envois)
    assert envois.recus == [] and rendu["supprimes"] == 0
    assert _existe(session, vise.id)


def test_un_compte_banni_de_la_communaute_suit_la_regle_commune(session):
    """Le bannissement restreint la Communauté ; il ne prolonge pas la conservation."""
    banni = _inactif(session, communaute_interdit=True, communaute_ban_count=2)
    envois = _Envois()
    _passer(session, envois)
    assert [uid for uid, _ in envois.recus] == [banni.id]


# ── Le garde-fou de volume ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "nb,total,anormal",
    [
        (0, 100, False),
        (1, 3, False),  # une seule suppression ne fait pas une proportion
        (5, 100, False),
        (6, 1000, True),  # plus de SURETE_NOMBRE_MAX
        (3, 20, True),  # plus de 10 % des comptes
        (2, 20, False),
    ],
)
def test_le_seuil_de_surete(nb, total, anormal):
    assert regles.SURETE_NOMBRE_MAX == 5
    assert regles.SURETE_PROPORTION_MAX == 0.10
    assert regles.suppressions_anormales(nb, total) is anormal


def test_un_passage_anormal_ne_supprime_aucun_compte(session, caplog):
    """Horloge faussée, base restaurée : si la purge s'apprête à supprimer trop,
    elle ne supprime RIEN et le dit."""
    caplog.set_level(logging.WARNING)
    for _ in range(40):
        compte(session, prefixe="voisin", derniere_connexion=T - timedelta(days=3))
    vises = [_averti(session, timedelta(days=31)).id for _ in range(regles.SURETE_NOMBRE_MAX + 1)]
    rendu = _passer(session)
    assert rendu["suspendue"] is True and rendu["supprimes"] == 0
    assert all(_existe(session, uid) for uid in vises)
    avertissements = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("suspendue" in r.getMessage().lower() for r in avertissements)
    assert not any(r.levelno >= logging.ERROR for r in caplog.records), (
        "un passage suspendu est un WARNING : le pré-check compte les ERROR"
    )


def test_un_avertissement_par_passage_au_plus(session):
    """Les avertissements s'échelonnent : c'est ce qui garde les suppressions,
    trente jours plus tard, sous le seuil de sûreté."""
    assert regles.PLAFOND_AVERTISSEMENTS_PAR_PASSAGE == 1
    plus_ancien = compte(session, prefixe="ancien", derniere_connexion=INACTIF - timedelta(days=99))
    for _ in range(3):
        _inactif(session)
    envois = _Envois()
    rendu = _passer(session, envois)
    assert rendu["avertis"] == 1
    assert [uid for uid, _ in envois.recus] == [plus_ancien.id], "le plus ancien d'abord"


def test_la_tache_ne_leve_jamais(session, monkeypatch):
    """Sous le planificateur, une exception tuerait le job pour de bon."""
    _averti(session, timedelta(days=31))

    def casse(s, user_id):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(tache_purge, "supprimer_compte", casse)
    rendu = _passer(session)
    assert rendu["supprimes"] == 0 and rendu["echecs_suppression"] == 1
