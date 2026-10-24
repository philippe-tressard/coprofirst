"""Admin — canal machine-à-machine des scripts d'exploitation.

Les scripts cron des nœuds (`maintenance.sh`, `bascule.sh`, `export-hors-site.sh`,
`check-reliability.sh`) déposent leurs rapports et lisent leurs dates ici. C'est le
SEUL endroit de l'API authentifié par un **secret partagé** et non par une session :
ces appels n'ont pas d'utilisateur.

Extrait de `exploitation.py` le 11/08/2026, au fil de l'eau — le fichier atteignait
542 lignes et le garde-fou de modularité a refusé le push, à raison. La frontière
n'est pas arbitraire : ces deux routes ont une raison de changer qui leur est
propre (le protocole des scripts), et un régime d'authentification qui n'est celui
d'aucune autre route du projet. Les isoler rend ce régime visible plutôt que noyé
au milieu d'endpoints protégés par `require_admin`.
"""

import json
from datetime import datetime, timedelta
from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlmodel import Session, select

from app.inscription.client import constat_pour_la_mise_a_jour
from app.inscription.constat import version_a_installer
from app.utils.declenchement import normaliser
from app.auth.cle_maintenance import exiger_cle_maintenance
from app.database import get_session
from app.models.core import HistoriqueEmail, HistoriqueMaintenance
from app.utils.sante_taches import STATUT_EN_COURS

from .exploitation import _purger_anciens_rapports
from app.utils.conservation_copie import accuser_copies
from app.utils.maintenance import purger
from app.utils.recuperer import present_ou_404

router = APIRouter()


class RapportMaintenance(BaseModel):
    statut: str = "succes"
    tokens_supprimes: int = 0
    taille_db_octets: Optional[int] = None
    duree_secondes: Optional[int] = None
    erreur: Optional[str] = None
    declenchee_par: str = "cron"
    cree_le: Optional[datetime] = None
    terminee_le: Optional[datetime] = None
    # Ajoutés en v2.32 — un rapport sans ces champs reste valide (défauts
    # identiques au comportement d'avant), donc un nœud dont le script n'a pas
    # encore été redéployé continue d'être accepté.
    tache: str = "maintenance"
    noeud: Optional[str] = None  # rpi1 | rpi2
    portee: str = "applicative"  # applicative | hygiene_locale
    details: Optional[dict] = None  # chiffres propres à la tâche


#  🔴 `_exiger_cle_maintenance` a été DÉPLACÉE le 19/09/2026 (#1028) dans
#  `app/auth/cle_maintenance.py`. C'est un moyen de s'authentifier — une clé
#  partagée — et c'était le seul qui ne vivait pas dans `auth/`, donc le seul que
#  `test_autorisation.py` ne pouvait pas raisonner comme une porte : il rangeait
#  ces quatre routes parmi les « publiques assumées », ce qui est faux.
#
#  La conséquence était un faux vert : une route déclarée publique reste verte si
#  l'on retire son contrôle d'authentification. Le test les classe à part
#  désormais, et vérifie que chacune appelle bien la fonction.


@router.get("/maintenance/dernier-rapport")
def maintenance_dernier_rapport(
    tache: str = "maintenance",
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    """Date du dernier rapport reçu, par nœud, pour UNE tâche.

    **Pourquoi cette route existe** (11/08/2026). Deux sondes indépendantes
    mesurent la maintenance hebdomadaire et se contredisaient sans que personne
    ne les confronte :

      - le **journal du nœud** — `check-reliability.sh` C17 y lit la ligne
        « Garde-fou » horodatée, et savait que la maintenance avait tourné ;
      - la **base** — l'écran d'administration n'y trouvait aucun rapport et
        affichait « Aucun rapport reçu », en rouge, depuis des jours.

    Les deux disaient vrai : le script tournait, et son rapport n'arrivait pas
    (la rotation des journaux déliait son propre inode et tuait le script avant
    l'envoi — corrigé en v2.46.8). Mais aucun contrôle ne comparait les deux, si
    bien que le seul symptôme était un badge rouge illisible, qu'on pouvait aussi
    bien attribuer à une tâche qui n'avait pas tourné.

    `check-reliability.sh` C19 interroge donc cette route pour dire la différence
    (`standards/04-fiabilite-des-controles.md` : deux sondes indépendantes, et
    c'est leur DÉSACCORD qui porte l'information).

    Authentifiée par la clé des scripts, pas par une session : le contrôle tourne
    en cron sur les nœuds, sans utilisateur. Elle ne rend que des dates
    d'exécution — aucune donnée personnelle.
    """
    exiger_cle_maintenance(x_maintenance_key)
    lignes = session.exec(
        select(HistoriqueMaintenance)
        .where(HistoriqueMaintenance.tache == tache)
        .order_by(HistoriqueMaintenance.cree_le.desc())
        .limit(50)
    ).all()
    par_noeud: dict = {}
    for ligne in lignes:
        cle = ligne.noeud or "inconnu"
        if cle not in par_noeud:  # la première vue est la plus récente
            par_noeud[cle] = ligne.cree_le
    return {"tache": tache, "noeuds": par_noeud, "genere_le": horloge.maintenant()}


def _details_en_base(details: Optional[dict]) -> Optional[str]:
    """La colonne `details` : du JSON lisible (accents gardés), ou rien."""
    return json.dumps(details, ensure_ascii=False) if details else None


def enregistrer_rapport(session: Session, body: RapportMaintenance) -> HistoriqueMaintenance:
    """Une EXÉCUTION, une ligne : le rapport de fin reprend celle de son battement.

    🔴 27/09/2026 (#1367, signalé à l'écran) : depuis que le battement de début
    est enregistré, chaque maintenance laissait DEUX lignes — le battement, vide
    (« en_cours », 0 s, aucun détail), puis le rapport. L'historique montrait des
    lignes sans rien d'écrit, et elles mangeaient la moitié du quota de
    `_purger_anciens_rapports` : dix lignes ne couvraient plus que cinq semaines.

    Le battement et le rapport d'une même exécution partagent la tâche, le nœud,
    la portée et l'heure de DÉBUT (`$MAINTE_DEBUT`) : c'est la clé. Un rapport de
    fin qui trouve son battement le COMPLÈTE ; sinon, il crée sa ligne — le cas
    d'une tâche sans battement (bascule, export) et celui d'un battement perdu.
    🔒 `test_rapport_remplace_battement.py`.
    """
    entry = None
    if body.statut != STATUT_EN_COURS and body.cree_le:
        entry = session.exec(
            select(HistoriqueMaintenance).where(
                HistoriqueMaintenance.tache == body.tache,
                HistoriqueMaintenance.noeud == body.noeud,
                HistoriqueMaintenance.portee == body.portee,
                HistoriqueMaintenance.statut == STATUT_EN_COURS,
                HistoriqueMaintenance.cree_le == body.cree_le,
            )
        ).first()
    if entry is None:
        entry = HistoriqueMaintenance()
    entry.tache = body.tache
    entry.noeud = body.noeud
    entry.portee = body.portee
    #  Normalisé à la FRONTIÈRE : un script déployé continue d'envoyer
    #  « cron », et la colonne que l'utilisateur lit garde un seul mot.
    entry.declenchee_par = normaliser(body.declenchee_par)
    entry.statut = body.statut
    entry.tokens_supprimes = body.tokens_supprimes
    entry.taille_db_octets = body.taille_db_octets
    entry.duree_secondes = body.duree_secondes
    entry.details = _details_en_base(body.details)
    entry.erreur = body.erreur
    entry.cree_le = body.cree_le or horloge.maintenant()
    entry.terminee_le = body.terminee_le
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.post("/maintenance/rapport", status_code=201)
def maintenance_rapport(
    body: RapportMaintenance,
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    exiger_cle_maintenance(x_maintenance_key)
    entry = enregistrer_rapport(session, body)
    _purger_anciens_rapports(session)
    return entry


class BattementTache(BaseModel):
    tache: str
    noeud: str
    #  #1805 : les constats DU PASSAGE. Absents (script pas encore redéployé),
    #  la ligne garde les siens ; présents, ils la remplacent avec `erreur`.
    details: Optional[dict] = None
    erreur: Optional[str] = None
    #  #2199 : la durée du passage qui prolonge la ligne. Absente (script pas
    #  encore redéployé), la ligne garde la sienne.
    duree_secondes: Optional[int] = None


@router.post("/maintenance/battement")
def maintenance_battement(
    body: BattementTache,
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    """« J'ai tourné, et rien n'a changé » — sans créer de ligne (#1396).

    `check-reliability.sh` ne rend un rapport que quand l'ensemble de ses
    constats CHANGE : la table n'en garde que vingt par tâche, et un rapport par
    passage (96 par jour et par nœud) aurait chassé tout le reste. L'écran
    affichait donc l'heure du dernier CHANGEMENT, et le 27/09/2026 on a cru que
    les contrôles ne tournaient plus — « rapport de 17:06 » lu à 17:29.

    Le passage qui n'a rien de neuf prolonge la ligne de son dernier rapport :
    `cree_le` reste « constats depuis », `terminee_le` devient « dernier
    contrôle ». Un UPDATE d'une ligne par quart d'heure et par nœud, dans le
    process de l'API — jamais une ouverture de la base par un tiers.

    🔴 Il porte aussi les constats du passage (#1805, 10/10/2026). La signature
    qui décide du rapport ignore les CHIFFRES — « disque à 61 % » puis « 62 % »
    n'est pas un changement —, si bien que le texte de la ligne restait celui du
    premier relevé jusqu'à 23 h : l'écran disait « 1 erreur sur 965 requêtes »
    sous « dernier contrôle 13:21 », quand le contrôle en comptait 3 sur 1904.
    `details` et `erreur` vont ensemble : un `erreur` vide dit « plus d'échec »,
    il ne s'écrit donc que quand les constats l'accompagnent.

    404 quand il n'y a rien à prolonger : le script efface alors sa mémoire, et
    le passage suivant envoie un rapport complet.
    """
    exiger_cle_maintenance(x_maintenance_key)
    ligne = present_ou_404(
        session.exec(
            select(HistoriqueMaintenance)
            .where(
                HistoriqueMaintenance.tache == body.tache,
                HistoriqueMaintenance.noeud == body.noeud,
            )
            .order_by(HistoriqueMaintenance.cree_le.desc())
        ).first(),
        "Aucun rapport à prolonger pour ce nœud",
    )
    ligne.terminee_le = horloge.maintenant()
    if body.duree_secondes is not None:
        ligne.duree_secondes = body.duree_secondes
    if body.details is not None:
        ligne.details = _details_en_base(body.details)
        ligne.erreur = body.erreur
    session.add(ligne)
    session.commit()
    return {"tache": ligne.tache, "noeud": ligne.noeud, "terminee_le": ligne.terminee_le}


class BailMiseAJour(BaseModel):
    #: reference · essai · limitee · active · suspendue (`inscription/constat`)
    etat: str
    raison: str
    canal: Optional[str] = None
    #: la version que la référence fait installer — vide : aucune (D18)
    version_cible: Optional[str] = None


@router.post("/maintenance/bail", response_model=BailMiseAJour)
def maintenance_bail(
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
):
    """Le bail renouvelé, et la version qu'il fait installer (R5 #1881).

    `deploiement/standard/mise-a-jour.sh` le demande avant de décider : une réplique
    suit la version cible de son bail CRU — signature, époque, clé et échéance
    vérifiées ici —, et sans bail valide n'installe rien (D18). Ne rend que l'état
    et une version : rien de la copropriété.
    """
    exiger_cle_maintenance(x_maintenance_key)
    verdict = constat_pour_la_mise_a_jour()
    return BailMiseAJour(
        etat=verdict.etat,
        raison=verdict.raison,
        canal=verdict.canal,
        version_cible=version_a_installer(verdict),
    )


class CopiesArchivesAffaires(BaseModel):
    #: nom de l'archive → empreinte SHA-256 de la copie sur le PC
    copies: dict[str, str]


@router.post("/maintenance/archives-affaires/copiees")
def maintenance_archives_affaires_copiees(
    body: CopiesArchivesAffaires,
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    """L'accusé de `export-hors-site.sh` : ces archives d'affaires sont copiées sur le PC
    (#2014, lot L3). Une empreinte qui n'est pas celle du serveur n'accuse rien.

    Ne reçoit et ne rend que des noms d'archives et des empreintes — aucune donnée de
    copropriétaire, la portée de ce canal. Le serveur retirera sa copie 30 jours plus
    tard (`utils/conservation_copie`).
    """
    exiger_cle_maintenance(x_maintenance_key)
    return accuser_copies(session, body.copies, horloge.maintenant())


@router.post("/maintenance/purges")
def maintenance_purges(
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
):
    """Les purges hebdomadaires, exécutées DANS ce process (#1232).

    `maintenance.sh` les demande ici chaque dimanche, et reçoit les comptes pour
    son rapport. Ne rend que des nombres et des messages d'erreur techniques —
    aucune donnée de copropriétaire, la portée de ce canal.
    """
    exiger_cle_maintenance(x_maintenance_key)
    comptes, erreurs = purger()
    return {"comptes": comptes, "erreurs": erreurs}


@router.get("/emails/echecs-recents")
def emails_echecs_recents(
    jours: int = 7,
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    """Combien d'e-mails ont échoué ces derniers jours, et de quels modèles.

    **Pourquoi cette route existe.** Le point 9 du pré-check MEP — « e-mails sans
    échec récent » — sortait `INCONNU` à *chaque* exécution : l'historique
    s'interroge in-process et exigeait une session admin, donc il fallait ouvrir
    l'écran à la main. Personne ne le faisait. Un contrôle qu'on ne fait jamais ne
    protège rien, et celui-là garde la seule trace d'une classe de défaut qui s'est
    reproduite **trois fois** : un e-mail dont le gabarit Jinja ne se rend pas part
    en échec **sans que rien ne remonte à l'expéditeur** — l'envoi est une
    `BackgroundTask`. Le 28/07/2026, six membres du conseil syndical n'ont rien
    reçu et cela ne se voyait nulle part ailleurs.

    **Ce qu'elle rend, et ce qu'elle ne rend pas.** Des comptes et des codes de
    modèles. **Jamais d'adresse ni de sujet** : ce canal est authentifié par un
    secret partagé, pas par une session, et il n'a aucune raison de laisser sortir
    une donnée personnelle pour répondre à « combien ». C'est la même discipline
    que `dernier-rapport`, qui ne rend que des dates.

    `total = 0` est la réponse attendue ; toute autre valeur fait échouer le point 9.
    """
    exiger_cle_maintenance(x_maintenance_key)
    #  Borné : une valeur aberrante passée par un script ne doit pas balayer toute
    #  la table, que la purge garde à 90 jours.
    jours = max(1, min(int(jours), 90))
    depuis = horloge.maintenant() - timedelta(days=jours)

    lignes = session.exec(
        select(HistoriqueEmail).where(
            HistoriqueEmail.statut == "erreur", HistoriqueEmail.cree_le >= depuis
        )
    ).all()

    par_code: dict[str, int] = {}
    for ligne in lignes:
        par_code[ligne.code] = par_code.get(ligne.code, 0) + 1

    return {
        "jours": jours,
        "total": len(lignes),
        "par_code": par_code,
        "dernier": max((ligne.cree_le for ligne in lignes), default=None),
        "genere_le": horloge.maintenant(),
    }
