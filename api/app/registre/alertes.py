"""Les ALERTES de la référence sur ses installations (R4b #1960, spec §4.11).

*« La référence alerte sur : installation muette depuis plus de 48 h, mise à jour
revenue en arrière, sauvegarde trop ancienne ou sans copie hors de la machine, disque
plein à plus de 80 %, certificat proche de l'échéance, retard de version, clone, deux
références déclarées. »*

Arbitrage de l'auteur, 14/10/2026 : **toutes à l'écran**, sur la carte de
l'installation (Admin › Installations) ; **un courriel à l'opérateur** pour les
graves seulement — muette, clone, deux références (`GENRES`, `grave`), et depuis le
23/10/2026 les correctifs du système en défaut (un serveur exposé sans correctifs).

## Les règles

1. **`evaluer` est PURE** : une installation, son dernier rapport, le dernier clone
   signalé, la version de tête — et l'heure. Aucune lecture de base, aucun envoi.
2. **Une mesure inconnue n'alerte pas** : le rapport rend `None` quand il n'a pas su
   mesurer (`inscription/rapport.py`), et l'écran le montre « inconnu ». Une seule
   exception, voulue : une sauvegarde `None` dit qu'une copropriété n'a **pas** de
   sauvegarde lisible — elle manque, et cela se dit.
2 bis. **Une sauvegarde que l'installation déclare NON ATTENDUE n'alerte pas** (#1982) :
   la démo se régénère chaque nuit et sa sauvegarde est coupée exprès
   (`utils/taches.TACHES_HORS_DEMO`). C'est l'installation qui le dit
   (`Sauvegarde.attendue`) : la référence ne sait pas qu'une installation est la
   démo, et n'a pas à le deviner. Sans déclaration, rien ne change.
3. **Ni la référence ni une installation résiliée n'alertent** : la référence ne se
   rapporte pas à elle-même (ses nœuds ont `check-reliability.sh`), et une
   résiliation a rendu l'installation à son exploitant.
4. **Un courriel par FAIT, jamais deux** : le journal du registre retient qu'une
   alerte grave a été signalée (`alerte_signalee:<code>`) et qu'elle s'est levée
   (`alerte_levee:<code>`). Une alerte toujours présente ne repart pas ; une alerte
   levée puis revenue est un fait nouveau. Un envoi manqué n'est pas marqué : il
   repart au contrôle suivant (`utils/sante_plateforme`, 06:00).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from pydantic import ValidationError
from sqlmodel import Session, func, select

from app.registre.contrat import Rapport
from app.registre.decisions import consigner
from app.registre.modeles import (
    IDENTIFIANT_REFERENCE,
    DecisionRegistre,
    EtatInscription,
    Installation,
    RapportInstallation,
)
from app.utils import horloge

logger = logging.getLogger("hostachy.registre")

#: Sans signe de vie au-delà, l'installation est muette (spec §4.11).
MUETTE_APRES = timedelta(hours=48)
#: La sauvegarde est nocturne : au-delà de deux nuits, elle ne se fait plus.
SAUVEGARDE_MAX = timedelta(hours=48)
#: Au-delà de 80 % d'occupation, le disque est plein (spec §4.11).
DISQUE_PLEIN_PCT = 80
#: Un certificat se renouvelle 30 jours avant son échéance : à moins de 21, le
#: renouvellement a échoué au moins une fois.
CERTIFICAT_AVANT = timedelta(days=21)
#: Le retard de version se compte en mineures — le pas du rappel de `replica`
#: (`scripts/ci/rappel-replica.sh`, PAS=10) ; une majeure de retard en est toujours un.
RETARD_MINEURES = 10
#: Un clone signalé reste une alerte une semaine — il se signale une fois par jour au
#: plus (`routeur._signaler_clone`), donc une semaine sans signalement le lève.
CLONE_RECENT = timedelta(days=7)

#: Les issues d'une mise à jour nocturne qui sont un retour en arrière (`ISSUES_MISE_A_JOUR`).
MISES_A_JOUR_REVENUES = frozenset({"revenue", "restauree"})

#: Les états des correctifs du système qui alertent (`ETATS_CORRECTIFS`), et ce qu'on en dit.
CORRECTIFS_EN_DEFAUT = {
    "en_defaut": "Les correctifs du système ne passent plus sur le serveur.",
    "muet": "Le contrôle des correctifs du système ne rend plus compte : état inconnu.",
}

#: Les gestes du journal qui portent le suivi d'une alerte grave.
SIGNALEE, LEVEE = "alerte_signalee:", "alerte_levee:"


@dataclass(frozen=True)
class Genre:
    libelle: str
    #: grave → un courriel à l'opérateur (arbitrage du 14/10/2026)
    grave: bool = False


#: Les alertes de la spec, dans son ordre — la seule liste ; l'écran lit ce que le
#: serveur rend, il n'en tient pas une seconde.
GENRES: dict[str, Genre] = {
    "muette": Genre("Installation muette", grave=True),
    "mise_a_jour_revenue": Genre("Mise à jour revenue en arrière"),
    "sauvegarde_ancienne": Genre("Sauvegarde trop ancienne"),
    "sans_copie_hors_machine": Genre("Sauvegarde sans copie hors de la machine"),
    "disque_plein": Genre("Disque plein"),
    "certificat_echeance": Genre("Certificat proche de l'échéance"),
    "retard_version": Genre("Retard de version"),
    #  Un serveur exposé qui ne reçoit plus ses correctifs de sécurité : grave
    #  (arbitrage du 23/10/2026, « fais selon tes recommandations »).
    "correctifs_systeme": Genre("Correctifs du système en défaut", grave=True),
    "clone": Genre("Clone", grave=True),
    "deux_references": Genre("Deux références", grave=True),
}


@dataclass(frozen=True)
class Alerte:
    code: str
    message: str

    @property
    def grave(self) -> bool:
        return GENRES[self.code].grave


_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _version(texte: Optional[str]) -> Optional[tuple[int, int, int]]:
    """`2.150.1` → (2, 150, 1) ; un commit ou « inconnue » ne se compare pas."""
    m = _SEMVER.match((texte or "").strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def version_de_tete(versions: Iterable[Optional[str]]) -> Optional[tuple[int, int, int]]:
    """La plus avancée des versions LISIBLES du registre — l'étalon du retard.

    La référence ne s'y compare pas : elle tourne sur un commit de `main`, pas sur une
    version promue (`utils/installation.version_logicielle`).
    """
    lues = [v for v in map(_version, versions) if v]
    return max(lues) if lues else None


def _naif(instant: datetime) -> datetime:
    """Un instant du rapport en UTC naïf, comme `horloge.maintenant()`."""
    if instant.tzinfo is None:
        return instant
    return instant.astimezone(timezone.utc).replace(tzinfo=None)


def _en_retard(version: tuple[int, int, int], tete: tuple[int, int, int]) -> bool:
    return version[0] < tete[0] or (
        version[0] == tete[0] and tete[1] - version[1] >= RETARD_MINEURES
    )


def _alertes_de_sauvegarde(sauv, maintenant: datetime) -> dict[str, str]:
    """Les deux alertes d'une sauvegarde ATTENDUE (règles 2 et 2 bis)."""
    trouvees: dict[str, str] = {}
    if sauv.derniere_reussie_le is None:
        trouvees["sauvegarde_ancienne"] = "Aucune sauvegarde réussie déclarée."
    elif maintenant - _naif(sauv.derniere_reussie_le) > SAUVEGARDE_MAX:
        jours = (maintenant - _naif(sauv.derniere_reussie_le)).days
        trouvees["sauvegarde_ancienne"] = f"Dernière sauvegarde réussie il y a {jours} jour(s)."
    if sauv.copie_hors_machine is False:
        trouvees["sans_copie_hors_machine"] = "La sauvegarde ne quitte pas la machine."
    return trouvees


def evaluer(
    inst: Installation,
    rapport: Optional[Rapport],
    *,
    clone_signale_le: Optional[datetime],
    version_de_tete: Optional[tuple[int, int, int]],
    maintenant: datetime,
) -> list[Alerte]:
    """Les alertes d'une installation, dans l'ordre de `GENRES` — PURE (règle 1)."""
    if inst.identifiant == IDENTIFIANT_REFERENCE or inst.etat == EtatInscription.resiliee:
        return []
    trouvees: dict[str, str] = {}

    dernier_signe = inst.vue_le or inst.cree_le
    if dernier_signe and maintenant - dernier_signe > MUETTE_APRES:
        heures = int((maintenant - dernier_signe).total_seconds() // 3600)
        trouvees["muette"] = f"Aucun signe de vie depuis {heures} h."

    if clone_signale_le and maintenant - clone_signale_le <= CLONE_RECENT:
        trouvees["clone"] = "Une autre clé a demandé le bail de cet identifiant."

    if rapport is not None:
        ident, heb, sauv = rapport.identite, rapport.hebergement, rapport.sauvegarde
        if ident.derniere_mise_a_jour in MISES_A_JOUR_REVENUES:
            trouvees["mise_a_jour_revenue"] = (
                "La dernière mise à jour a restauré la sauvegarde d'avant."
                if ident.derniere_mise_a_jour == "restauree"
                else "La dernière mise à jour est revenue à la version précédente."
            )
        if sauv.attendue is not False:  # règle 2 bis
            trouvees.update(_alertes_de_sauvegarde(sauv, maintenant))
        if heb.disque_total_mo and heb.disque_occupe_mo is not None:
            pct = heb.disque_occupe_mo * 100 / heb.disque_total_mo
            if pct > DISQUE_PLEIN_PCT:
                trouvees["disque_plein"] = f"Disque occupé à {pct:.0f} %."
        if heb.certificat_expire_le is not None:
            reste = _naif(heb.certificat_expire_le) - maintenant
            if reste < CERTIFICAT_AVANT:
                trouvees["certificat_echeance"] = (
                    f"Le certificat TLS expire dans {max(reste.days, 0)} jour(s)."
                )
        version = _version(ident.version_logicielle)
        if version and version_de_tete and _en_retard(version, version_de_tete):
            tete = ".".join(map(str, version_de_tete))
            trouvees["retard_version"] = (
                f"v{ident.version_logicielle}, quand le registre a v{tete}."
            )
        if ident.se_declare_reference is True:
            trouvees["deux_references"] = "Elle se déclare installation de référence."
        if ident.correctifs_systeme in CORRECTIFS_EN_DEFAUT:
            trouvees["correctifs_systeme"] = CORRECTIFS_EN_DEFAUT[ident.correctifs_systeme]

    return [Alerte(code, trouvees[code]) for code in GENRES if code in trouvees]


# ── Lecture du registre ──────────────────────────────────────────────────────


def _lire(ligne: Optional[RapportInstallation]) -> Optional[Rapport]:
    if ligne is None:
        return None
    try:
        return Rapport.model_validate_json(ligne.corps)
    except ValidationError:
        logger.warning("registre : rapport %s illisible au contrat en vigueur", ligne.id)
        return None


def alertes_du_registre(
    session: Session, maintenant: Optional[datetime] = None
) -> dict[int, list[Alerte]]:
    """Les alertes de chaque installation du registre, par `Installation.id`."""
    maintenant = maintenant or horloge.maintenant()
    installations = session.exec(select(Installation)).all()
    recents = (
        select(RapportInstallation.installation_id, func.max(RapportInstallation.id).label("id"))
        .group_by(RapportInstallation.installation_id)
        .subquery()
    )
    derniers = {
        r.installation_id: r
        for r in session.exec(
            select(RapportInstallation).join(recents, RapportInstallation.id == recents.c.id)
        ).all()
    }
    clones = dict(
        session.exec(
            select(DecisionRegistre.installation_id, func.max(DecisionRegistre.cree_le))
            .where(DecisionRegistre.geste == "clone_signale")
            .group_by(DecisionRegistre.installation_id)
        ).all()
    )
    rapports = {i: _lire(r) for i, r in derniers.items()}
    tete = version_de_tete(
        r.identite.version_logicielle for r in rapports.values() if r is not None
    )
    return {
        inst.id: evaluer(
            inst,
            rapports.get(inst.id),
            clone_signale_le=clones.get(inst.id),
            version_de_tete=tete,
            maintenant=maintenant,
        )
        for inst in installations
    }


# ── Le courriel de l'opérateur : une fois par fait (règle 4) ──────────────────


@dataclass(frozen=True)
class AlerteGrave:
    installation_id: int
    identifiant: str
    alerte: Alerte

    @property
    def ligne(self) -> str:
        """Une ligne du courriel de la plateforme — un identifiant, jamais un nom."""
        return f"{self.identifiant} — {GENRES[self.alerte.code].libelle} : {self.alerte.message}"


def _signalees(session: Session) -> set[tuple[int, str]]:
    """(installation, code) signalés et pas encore levés — relu dans le journal."""
    ouvertes: set[tuple[int, str]] = set()
    journal = session.exec(
        select(DecisionRegistre)
        .where(DecisionRegistre.geste.startswith("alerte_"))
        .order_by(DecisionRegistre.cree_le, DecisionRegistre.id)
    ).all()
    for d in journal:
        if d.geste.startswith(SIGNALEE):
            ouvertes.add((d.installation_id, d.geste.removeprefix(SIGNALEE)))
        elif d.geste.startswith(LEVEE):
            ouvertes.discard((d.installation_id, d.geste.removeprefix(LEVEE)))
    return ouvertes


def graves_a_signaler(session: Session) -> list[AlerteGrave]:
    """Les alertes graves NOUVELLES ; celles qui se sont levées s'inscrivent au journal."""
    par_installation = alertes_du_registre(session)
    installations = {i.id: i for i in session.exec(select(Installation)).all()}
    presentes = {
        (inst_id, a.code): a
        for inst_id, liste in par_installation.items()
        for a in liste
        if a.grave
    }
    deja = _signalees(session)
    for inst_id, code in sorted(deja - set(presentes)):
        consigner(session, installations[inst_id], LEVEE + code, GENRES[code].libelle)
    session.commit()
    return [
        AlerteGrave(inst_id, installations[inst_id].identifiant, alerte)
        for (inst_id, _), alerte in sorted(presentes.items())
        if (inst_id, alerte.code) not in deja
    ]


def marquer_signalees(session: Session, graves: list[AlerteGrave]) -> None:
    """Après l'envoi SEULEMENT : le journal retient que l'opérateur a été prévenu."""
    for g in graves:
        inst = session.get(Installation, g.installation_id)
        consigner(session, inst, SIGNALEE + g.alerte.code, g.alerte.message)
    session.commit()
