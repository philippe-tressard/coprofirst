"""Les ALERTES de la référence sur ses installations (R4b #1960, spec §4.11).

Arbitrage de l'auteur, 14/10/2026 : toutes à l'écran, sur la carte de
l'installation ; un courriel à l'opérateur pour les trois graves seulement —
installation muette, clone, deux références.

`registre/alertes.evaluer` est PURE : chaque alerte se prouve ici par un cas qui
la déclenche, et le cas zéro — une installation saine, ou des mesures inconnues —
n'en déclenche aucune. Le courriel ne part qu'UNE fois par fait (journal du
registre) : la mémoire « jamais deux fois le même mail ».
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.registre import alertes, migrer
from app.registre.contrat import (
    VERSION_CONTRAT,
    Consommation,
    Hebergement,
    Identite,
    Posture,
    Rapport,
    Sauvegarde,
)
from app.registre.decisions import consigner
from app.registre.modeles import (
    DecisionRegistre,
    EtatInscription,
    Installation,
    RapportInstallation,
)
from app.utils import horloge, sante_plateforme
from tests.aides_registre import registre_allume

MAINTENANT = horloge.maintenant()


def _installation(**kw) -> Installation:
    valeurs = dict(
        identifiant="CF-000002",
        etat=EtatInscription.active,
        canal="replica",
        cree_le=MAINTENANT - timedelta(days=30),
        vue_le=MAINTENANT - timedelta(hours=2),
    )
    return Installation(**{**valeurs, **kw})


def _rapport(version="2.150.0", reference=None, hebergement=None, sauvegarde=None, maj=None):
    return Rapport(
        version_contrat=VERSION_CONTRAT,
        identite=Identite(
            identifiant="CF-000002",
            canal="replica",
            version_logicielle=version,
            se_declare_reference=reference,
            derniere_mise_a_jour=maj,
        ),
        hebergement=hebergement or Hebergement(disque_total_mo=1000, disque_occupe_mo=500),
        sauvegarde=sauvegarde or Sauvegarde(derniere_reussie_le=MAINTENANT - timedelta(hours=6)),
        posture=Posture(),
        consommation=Consommation(),
    )


def _codes(inst=None, rapport="sain", clone_le=None, tete=(2, 150, 0)) -> set[str]:
    rapport = _rapport() if rapport == "sain" else rapport
    return {
        a.code
        for a in alertes.evaluer(
            inst or _installation(),
            rapport,
            clone_signale_le=clone_le,
            version_de_tete=tete,
            maintenant=MAINTENANT,
        )
    }


# ── Le cas zéro : rien de faux, rien d'inventé ────────────────────────────────


def test_une_installation_saine_n_a_aucune_alerte():
    assert _codes() == set()


def test_une_mesure_inconnue_ne_fabrique_pas_d_alerte():
    """`None` dit « on n'a pas su mesurer » (inscription/rapport) — ni sain, ni malade."""
    rapport = _rapport(
        version="a1b2c3d4e5f6",
        hebergement=Hebergement(),
        sauvegarde=Sauvegarde(derniere_reussie_le=MAINTENANT - timedelta(hours=1)),
    )
    assert _codes(rapport=rapport, tete=None) == set()


@pytest.mark.parametrize(
    "inst",
    [
        _installation(identifiant="CF-000000", vue_le=None, canal="main"),
        _installation(etat=EtatInscription.resiliee, vue_le=MAINTENANT - timedelta(days=60)),
    ],
    ids=["la référence", "une résiliée"],
)
def test_ni_la_reference_ni_une_resiliee_n_alertent(inst):
    assert _codes(inst=inst, rapport=None) == set()


# ── Chaque alerte de la spec se déclenche ────────────────────────────────────


@pytest.mark.parametrize(
    "vue_le, muette",
    [(timedelta(hours=47), False), (timedelta(hours=49), True)],
)
def test_muette_au_dela_de_48_heures(vue_le, muette):
    inst = _installation(vue_le=MAINTENANT - vue_le)
    assert ("muette" in _codes(inst=inst)) is muette


def test_jamais_revenue_depuis_son_inscription_est_muette():
    inst = _installation(vue_le=None, cree_le=MAINTENANT - timedelta(days=3))
    assert "muette" in _codes(inst=inst)


@pytest.mark.parametrize(
    "issue, revenue",
    [("revenue", True), ("restauree", True), ("reussie", False), ("echouee", False)],
)
def test_mise_a_jour_revenue_en_arriere(issue, revenue):
    """Revenue à l'image d'avant, ou à la sauvegarde d'avant : un retour (#1981)."""
    assert ("mise_a_jour_revenue" in _codes(rapport=_rapport(maj=issue))) is revenue


def test_sauvegarde_trop_ancienne_ou_inconnue():
    vieille = Sauvegarde(derniere_reussie_le=MAINTENANT - timedelta(hours=49))
    assert "sauvegarde_ancienne" in _codes(rapport=_rapport(sauvegarde=vieille))
    #  Le rapport rend `None` quand une copropriété n'a PAS de sauvegarde lisible :
    #  c'est une sauvegarde qui manque, et elle se dit.
    absente = Sauvegarde(derniere_reussie_le=None)
    assert "sauvegarde_ancienne" in _codes(rapport=_rapport(sauvegarde=absente))


def test_une_sauvegarde_non_attendue_ne_fait_pas_alerte():
    """#1982 : la démo se régénère chaque nuit, sa sauvegarde est coupée EXPRÈS
    (`utils/taches.TACHES_HORS_DEMO`) — l'installation le DÉCLARE, la référence se tait.
    Sans déclaration (réplique d'avant), le comportement ne change pas."""
    sans = Sauvegarde(derniere_reussie_le=None, copie_hors_machine=False, attendue=False)
    assert {"sauvegarde_ancienne", "sans_copie_hors_machine"}.isdisjoint(
        _codes(rapport=_rapport(sauvegarde=sans))
    )
    muette = Sauvegarde(derniere_reussie_le=None, copie_hors_machine=False)
    assert {"sauvegarde_ancienne", "sans_copie_hors_machine"} <= _codes(
        rapport=_rapport(sauvegarde=muette)
    )


def test_sauvegarde_sans_copie_hors_de_la_machine():
    seule = Sauvegarde(
        derniere_reussie_le=MAINTENANT - timedelta(hours=2), copie_hors_machine=False
    )
    assert "sans_copie_hors_machine" in _codes(rapport=_rapport(sauvegarde=seule))


@pytest.mark.parametrize("occupe, plein", [(800, False), (801, True)])
def test_disque_plein_au_dela_de_80_pour_cent(occupe, plein):
    h = Hebergement(disque_total_mo=1000, disque_occupe_mo=occupe)
    assert ("disque_plein" in _codes(rapport=_rapport(hebergement=h))) is plein


@pytest.mark.parametrize("jours, proche", [(22, False), (20, True)])
def test_certificat_proche_de_l_echeance(jours, proche):
    h = Hebergement(certificat_expire_le=MAINTENANT + timedelta(days=jours))
    assert ("certificat_echeance" in _codes(rapport=_rapport(hebergement=h))) is proche


@pytest.mark.parametrize(
    "version, en_retard",
    [("2.141.0", False), ("2.140.9", True), ("1.199.0", True), ("2.150.0", False)],
)
def test_retard_de_version_sur_la_plus_avancee_du_registre(version, en_retard):
    assert ("retard_version" in _codes(rapport=_rapport(version=version))) is en_retard


def test_clone_signale_dans_la_semaine():
    assert "clone" in _codes(clone_le=MAINTENANT - timedelta(days=6))
    assert "clone" not in _codes(clone_le=MAINTENANT - timedelta(days=8))


def test_une_autre_installation_qui_se_declare_reference():
    assert "deux_references" in _codes(rapport=_rapport(reference=True))
    assert "deux_references" not in _codes(rapport=_rapport(reference=False))


def test_seules_les_graves_partent_par_courriel():
    """Les arbitrages du 14/10/2026 et du 23/10/2026, écrits une fois : le registre des genres."""
    assert {c for c, g in alertes.GENRES.items() if g.grave} == {
        "muette",
        "clone",
        "deux_references",
        "correctifs_systeme",
    }


@pytest.mark.parametrize(
    "etat, alerte",
    [("en_defaut", True), ("muet", True), ("a_jour", False), (None, False)],
)
def test_correctifs_du_systeme_en_defaut_ou_muets(etat, alerte):
    """Un serveur qui ne reçoit plus ses correctifs, ou dont le contrôle se tait, alerte ;
    une installation qui n'a pas posé le contrôle (`None`) ne dit rien."""
    rapport = _rapport()
    rapport.identite.correctifs_systeme = etat
    assert ("correctifs_systeme" in _codes(rapport=rapport)) is alerte
    assert all(e in alertes.CORRECTIFS_EN_DEFAUT for e in ("en_defaut", "muet"))


def test_la_version_de_tete_est_la_plus_avancee_des_versions_lisibles():
    assert alertes.version_de_tete(["2.9.0", "2.150.1", "a1b2c3", None, "2.150.0"]) == (2, 150, 1)
    assert alertes.version_de_tete(["a1b2c3", None]) is None


# ── Le courriel de l'opérateur : une fois par fait ───────────────────────────


@pytest.fixture
def registre(monkeypatch):
    with registre_allume(monkeypatch) as moteur:
        with Session(moteur) as s:
            migrer.inscrire_reference(s)
            muette = _installation(identifiant="CF-000002", vue_le=MAINTENANT - timedelta(days=3))
            s.add(muette)
            s.commit()
        yield moteur


@pytest.fixture
def envois(monkeypatch):
    monkeypatch.setattr(get_settings(), "courriel_operateur", "operateur@example.org")
    monkeypatch.setattr(get_settings(), "mail_enabled", True)
    monkeypatch.setattr(get_settings(), "mail_from_plateforme", "plateforme@example.com")
    partis: list = []
    monkeypatch.setattr(sante_plateforme, "_envoyer", lambda dest, pb: partis.append(pb))
    from app.registre import sauvegarde

    monkeypatch.setattr(sauvegarde, "probleme_copie_hors_site", lambda: [])
    return partis


def _journal(moteur) -> list[str]:
    with Session(moteur) as s:
        return [
            d.geste
            for d in s.exec(select(DecisionRegistre).order_by(DecisionRegistre.id)).all()
            if d.geste.startswith("alerte")
        ]


def test_une_alerte_grave_part_une_seule_fois(registre, envois):
    sante_plateforme.run_controle_plateforme()
    assert len(envois) == 1 and any("CF-000002" in p and "muette" in p.lower() for p in envois[0])
    assert _journal(registre) == ["alerte_signalee:muette"]

    sante_plateforme.run_controle_plateforme()
    assert len(envois) == 1, "le même fait est reparti une seconde fois"


def test_une_alerte_levee_se_journalise_et_repart_si_elle_revient(registre, envois):
    sante_plateforme.run_controle_plateforme()
    with Session(registre) as s:
        inst = s.exec(select(Installation).where(Installation.identifiant == "CF-000002")).one()
        inst.vue_le = horloge.maintenant()
        s.add(inst)
        s.commit()
    sante_plateforme.run_controle_plateforme()
    assert _journal(registre) == ["alerte_signalee:muette", "alerte_levee:muette"]
    assert len(envois) == 1

    with Session(registre) as s:
        inst = s.exec(select(Installation).where(Installation.identifiant == "CF-000002")).one()
        inst.vue_le = horloge.maintenant() - timedelta(days=3)
        s.add(inst)
        s.commit()
    sante_plateforme.run_controle_plateforme()
    assert len(envois) == 2


def test_un_envoi_manque_n_est_pas_marque_signale(registre, envois, monkeypatch):
    monkeypatch.setattr(get_settings(), "courriel_operateur", "")
    sante_plateforme.run_controle_plateforme()
    assert _journal(registre) == [], "une alerte non envoyée passe pour signalée"


def test_une_alerte_non_grave_ne_part_pas_par_courriel(registre, envois):
    with Session(registre) as s:
        inst = s.exec(select(Installation).where(Installation.identifiant == "CF-000002")).one()
        inst.vue_le = horloge.maintenant()
        s.add(inst)
        vieille = _rapport(
            sauvegarde=Sauvegarde(derniere_reussie_le=MAINTENANT - timedelta(days=5))
        )
        s.add(RapportInstallation(installation_id=inst.id, corps=vieille.model_dump_json()))
        s.commit()
    sante_plateforme.run_controle_plateforme()
    assert envois == []


def test_le_clone_du_journal_devient_une_alerte_grave(registre, envois):
    with Session(registre) as s:
        inst = s.exec(select(Installation).where(Installation.identifiant == "CF-000002")).one()
        inst.vue_le = horloge.maintenant()
        s.add(inst)
        consigner(s, inst, "clone_signale", "une autre clé a demandé le bail de cet identifiant")
        s.commit()
    sante_plateforme.run_controle_plateforme()
    assert _journal(registre) == ["alerte_signalee:clone"]
