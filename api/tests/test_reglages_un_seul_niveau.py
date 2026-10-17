"""Un réglage a UN niveau — l'installation ou la copropriété — et une seule source (#2058).

Règle du 17/10/2026 : *l'environnement porte les secrets et l'infrastructure de
l'installation, la base porte les choix de chaque copropriété — jamais les deux pour
un même réglage.* SMTP et sauvegarde la violaient : `connexion_smtp` retombait champ
par champ sur `MAIL_*`, `BACKUP_HOUR` et `BACKUP_KEEP_VERSIONS` remplaçaient la ligne
de `config_sauvegarde` absente.

- **le registre** : chaque réglage de `Settings` qui a un JUMEAU en base n'est lu que
  par les lecteurs déclarés ici — l'amorce d'une base neuve, ou l'installation pour
  elle-même (les alertes de la plateforme). Un nouveau lecteur fait échouer ; un
  lecteur déclaré qui ne lit plus aussi ;
- **l'amorce** : elle reproduit, une fois, ce que le repli produisait (rien ne change
  au premier démarrage d'une installation existante), ne touche jamais une clé déjà
  renseignée, ne repasse pas ; sur une installation commune, elle ne recopie jamais
  les identifiants SMTP de l'hébergeur dans la base d'une copropriété ;
- **la base décide seule** : un `MAIL_*` changé après l'amorce n'a plus d'effet.
"""

from __future__ import annotations

import ast

from sqlmodel import select

from app.config import get_settings
from app.models.core import ConfigSite
from app.utils import smtp
from app.utils.email import envoi_actif
from tests.aides_installation_commune import installation_commune
from tests.aides_sources import modules_app

#: Réglage de `Settings` → (son jumeau en base, {lecteur autorisé: raison}).
#: Un lecteur s'écrit `module` ou `module::fonction`.
REGISTRE = {
    "mail_enabled": (
        "smtp_enabled",
        {
            "utils/smtp.py::_amorce": "amorce d'une base",
            "utils/sante_plateforme.py": "le SMTP de l'INSTALLATION (alertes à l'opérateur)",
        },
    ),
    **{
        champ: (
            jumeau,
            {
                "utils/smtp.py::_amorce": "amorce d'une base",
                "utils/smtp.py::connexion_smtp_installation": "le SMTP de l'INSTALLATION",
            },
        )
        for champ, jumeau in (
            ("mail_server", "smtp_server"),
            ("mail_port", "smtp_port"),
            ("mail_username", "smtp_username"),
            ("mail_password", "smtp_password"),
            ("mail_starttls", "smtp_starttls"),
            ("mail_ssl_tls", "smtp_ssl_tls"),
        )
    },
    "mail_from": (
        "smtp_from",
        {"contexte.py": "l'expéditeur de la copropriété de configuration, que l'amorce recopie"},
    ),
    "mail_from_name": (
        "smtp_from_name",
        {"contexte.py": "le nom d'expédition de la copropriété de configuration, idem"},
    ),
    "backup_hour": ("config_sauvegarde.heure_execution", {}),
    "backup_keep_versions": (
        "config_sauvegarde.nb_versions_conservees",
        {"registre/sauvegarde.py": "la base `plateforme`, qui n'a ni ligne ni écran"},
    ),
}


def _lecteurs(champ: str) -> set[str]:
    trouves: set[str] = set()
    for m in modules_app(minimum=300):
        if m.rel == "config.py":
            continue
        for fonction in [
            m.arbre,
            *(n for n in ast.walk(m.arbre) if isinstance(n, ast.FunctionDef)),
        ]:
            corps = fonction.body if isinstance(fonction, ast.FunctionDef) else []
            noeuds = (
                (x for b in corps for x in ast.walk(b))
                if isinstance(fonction, ast.FunctionDef)
                else ast.walk(fonction)
            )
            if any(isinstance(x, ast.Attribute) and x.attr == champ for x in noeuds):
                trouves.add(
                    f"{m.rel}::{fonction.name}" if isinstance(fonction, ast.FunctionDef) else m.rel
                )
    return trouves


def _couvert(lecteur: str, autorises: dict) -> bool:
    return lecteur in autorises or lecteur.split("::")[0] in autorises


def test_un_reglage_jumeau_n_est_lu_que_par_ses_lecteurs_declares():
    fautes, mortes = [], []
    for champ, (jumeau, autorises) in REGISTRE.items():
        lecteurs = _lecteurs(champ)
        #  Le module entier « lit » quand une de ses fonctions lit : on juge les fonctions.
        par_fonction = {x for x in lecteurs if "::" in x} or lecteurs
        fautes += [
            f"{x} lit `{champ}` (jumeau en base : {jumeau})"
            for x in par_fonction
            if not _couvert(x, autorises)
        ]
        mortes += [
            f"{champ} → {a}"
            for a in autorises
            if not any(a == x or x.startswith(a) for x in lecteurs)
        ]
    assert not fautes, (
        "Réglage lu à la fois en base et dans `Settings` (#2058) — une source par "
        "niveau :\n  " + "\n  ".join(fautes)
    )
    assert not mortes, f"lecteur déclaré qui ne lit plus (à retirer) : {mortes}"


def _valeurs(session) -> dict[str, str]:
    return {c.cle: c.valeur for c in session.exec(select(ConfigSite)).all()}


def test_l_amorce_reproduit_le_repli_puis_la_base_decide_seule(session, monkeypatch):
    s = get_settings()
    for champ, valeur in (
        ("mail_enabled", True),
        ("mail_server", "smtp.exemple.fr"),
        ("mail_port", 465),
        ("mail_username", "compte"),
        ("mail_password", "secret-du-env"),
        ("mail_starttls", False),
        ("mail_ssl_tls", True),
        ("mail_from", "noreply@exemple.fr"),
    ):
        monkeypatch.setattr(s, champ, valeur)
    #  Une clé déjà réglée par l'administrateur, et une case décochée : jamais touchées.
    session.add(ConfigSite(cle="smtp_server", valeur="smtp.choisi.fr"))
    session.add(ConfigSite(cle="smtp_starttls", valeur="0"))
    session.commit()

    assert smtp.amorcer(session) > 0
    session.commit()
    v = _valeurs(session)
    assert v["smtp_server"] == "smtp.choisi.fr"
    assert v["smtp_starttls"] == "0"
    assert (v["smtp_port"], v["smtp_username"], v["smtp_password"]) == (
        "465",
        "compte",
        "secret-du-env",
    )
    assert (v["smtp_enabled"], v["smtp_ssl_tls"]) == ("1", "1")
    assert v["smtp_from"] == s.mail_from
    assert envoi_actif(session) is True

    #  Une fois seulement : un champ vidé ensuite reste vide, un .env changé ne compte plus.
    ligne = session.get(ConfigSite, "smtp_username")
    ligne.valeur = ""
    session.add(ligne)
    session.commit()
    monkeypatch.setattr(s, "mail_server", "smtp.autre.fr")
    monkeypatch.setattr(s, "mail_enabled", False)
    assert smtp.amorcer(session) == 0
    connexion = smtp.connexion_smtp(smtp._get_smtp_config(session))
    assert connexion.MAIL_SERVER == "smtp.choisi.fr"
    assert connexion.MAIL_USERNAME == ""
    assert connexion.MAIL_STARTTLS is False
    assert envoi_actif(session) is True


def test_sans_smtp_enabled_rien_ne_part(session, monkeypatch):
    #  Cas zéro : `MAIL_ENABLED` vrai ne suffit plus — la base n'a pas sa case.
    monkeypatch.setattr(get_settings(), "mail_enabled", True)
    assert envoi_actif(session) is False


def test_une_copropriete_commune_ne_recoit_pas_les_identifiants_de_l_hebergeur(
    session, tmp_path, monkeypatch
):
    from app import contexte

    s = get_settings()
    monkeypatch.setattr(s, "mail_password", "secret-de-l-hebergeur")
    monkeypatch.setattr(s, "mail_enabled", True)
    with installation_commune(tmp_path, monkeypatch):
        copro = contexte.par_identifiant("chenes")
        with contexte.dans(copro):
            smtp.amorcer(session)
    session.commit()
    v = _valeurs(session)
    assert v["smtp_from"] == "contact@residence-chenes.example"
    assert v["smtp_from_name"] == "Résidence des Chênes"
    for cle in ("smtp_password", "smtp_username", "smtp_server", "smtp_enabled"):
        assert cle not in v, cle
    assert "secret-de-l-hebergeur" not in v.values()
