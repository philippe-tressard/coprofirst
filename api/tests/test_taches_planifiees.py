"""Historique des tâches planifiées : nœud, portée, détails, et détection des absences.

POURQUOI CE TEST — mesuré le 02/08/2026 sur la production :

Le standby exécutait une hygiène locale réelle (3,358 Go de cache de build purgés,
66 338 lignes de log rotées) qui n'apparaissait **nulle part** dans l'application :
`maintenance.sh` poste sur `http://localhost/api/...`, or il n'y a pas d'API sur le
nœud passif. Et sans colonne `noeud`, une ligne ne disait pas *qui* avait agi.

Pire, une absence de ligne confondait trois causes très différentes : pas exécutée,
échouée, ou exécutée sans avoir pu s'enregistrer. C'est le « battement manquant »
de standards/04-fiabilite-des-controles.md §4, appliqué à l'interface.

Ces tests verrouillent le contrat : les nouveaux champs existent, avec des
défauts rétrocompatibles, et chaque tâche attendue a une périodicité tenable et
un producteur. La règle qui déclare une exécution `manquante` se teste, elle, là
où elle vit (`utils/sante_taches.py`) : `test_sante_taches_periodes.py`.
"""

import re

from app.models.core import HistoriqueMaintenance, PorteeExecution, TachePlanifiee
from tests.conftest import scripts_shell_versionnes


def test_defauts_retrocompatibles():
    """Un rapport qui n'envoie aucun des nouveaux champs reste une maintenance
    applicative — c'est exactement ce que décrivent les lignes déjà en base, et
    ce qu'enverra un nœud dont le script n'a pas encore été redéployé."""
    ligne = HistoriqueMaintenance()
    assert ligne.tache == TachePlanifiee.maintenance.value
    assert ligne.portee == PorteeExecution.applicative.value
    assert ligne.noeud is None
    assert ligne.details is None


def test_portee_distingue_actif_et_standby():
    """L'actif fait la maintenance applicative, le standby l'hygiène locale.

    Sans cette distinction, une ligne de standby se lirait comme une maintenance
    applicative incomplète — donc comme une anomalie qui n'en est pas une.
    """
    assert PorteeExecution.applicative.value != PorteeExecution.hygiene_locale.value
    standby = HistoriqueMaintenance(noeud="rpi2", portee=PorteeExecution.hygiene_locale.value)
    assert standby.portee == "hygiene_locale"
    assert standby.noeud == "rpi2"


def test_taches_couvrent_les_crons_reels():
    """L'énumération couvre les tâches planifiées réellement en production."""
    valeurs = {t.value for t in TachePlanifiee}
    assert {"maintenance", "backup", "bascule"} <= valeurs
    assert {"health_watch", "reliability", "auto_deploy"} <= valeurs
    # Ajoutée le 04/08/2026 : seule tâche lancée depuis le POSTE et non par un
    # cron des RPi. Ce qui compte pour la surveillance n'est pas d'où part la
    # tâche, mais qu'on puisse constater son absence.
    assert "export_hors_site" in valeurs


def test_toute_tache_attendue_a_un_producteur():
    """Une tâche inscrite au tableau d'attente doit avoir quelqu'un qui la poste.

    POURQUOI (04/08/2026) : `bascule` figurait dans `_PERIODICITE_ATTENDUE_H`, mais
    **aucun script ne postait jamais `tache=bascule`**. La ligne « Bascule
    actif/standby » affichait donc « Jamais exécutée » en permanence, alors que la
    bascule réussissait chaque nuit depuis avril.

    Deux dégâts, et le second est le vrai : la ligne apprenait une chose fausse, et
    surtout **elle serait restée identique si la bascule s'était arrêtée pour de
    bon**. Un rouge permanent ne peut plus rien signaler — c'est une alerte qu'on
    apprend à ignorer, donc un contrôle mort (standards/07 §5).

    Ce test verrouille la classe et non le cas : toute tâche ajoutée au tableau sans
    producteur échouera ici, avant d'aller peindre un faux rouge sur l'écran.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H

    #  Portée du scan : source unique dans conftest — un glob local ici avait
    #  cessé de voir les scripts déplacés dans `scripts/` (#337).
    scripts = {p.name: p.read_text(encoding="utf-8") for p in scripts_shell_versionnes()}
    assert len(scripts) >= 10, "chemin de scan cassé — ce test serait vert à vide"

    # Trois formes possibles : la charge utile mutualisée (`rapport_payload <tache>`,
    # cf. lib-rapport.sh), un `printf` local, ou — depuis le 30/10/2026 — la tâche
    # POSÉE par un script qui rend compte par `lib-notification.sh`
    # (`NOTIFICATION_TACHE=<tache>`, ou son défaut `:-<tache>` dans le module).
    # Ne chercher qu'une des formes rendrait ce test faux au premier refactor —
    # et un test faux est pire qu'aucun test.
    for tache in _PERIODICITE_ATTENDUE_H:
        producteurs = [
            nom
            for nom, src in scripts.items()
            if f'"tache":"{tache}"' in src
            or f"rapport_payload {tache} " in src
            or re.search(rf'NOTIFICATION_TACHE="?(\$\{{NOTIFICATION_TACHE:-)?{tache}\b', src)
        ]
        assert producteurs, (
            f"la tâche « {tache} » est attendue toutes les "
            f"{_PERIODICITE_ATTENDUE_H[tache]}h mais AUCUN script ne la poste : "
            f"elle affichera « Jamais exécutée » pour toujours, et son passage au "
            f"rouge ne voudra jamais rien dire. Soit un script la rapporte "
            f"(cf. lib-rapport.sh), soit elle sort du tableau."
        )


def test_export_hors_site_est_attendu_avec_une_cadence_tenable():
    """La copie hors site est suivie — mais à un rythme réellement soutenable.

    Elle est lancée à la main depuis un poste qui n'est pas allumé en
    permanence : l'attendre toutes les 24 h ferait crier ce contrôle presque
    tous les jours, et une alerte qui crie tout le temps finit ignorée. C'est
    ainsi qu'un contrôle meurt (standards/07 §5) — le seuil hebdomadaire est
    donc un choix, pas un réglage par défaut, et il est verrouillé ici.

    À l'inverse, ne PAS l'inscrire au tableau la rendrait invisible : son
    absence se lirait comme du calme, ce qui est précisément le « battement
    manquant » de standards/04 §4.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H

    #  La clé se lit dans l'énumération, jamais recopiée : un renommage de
    #  `TachePlanifiee.export_hors_site` qui oublierait ce tableau rendrait la
    #  copie hors site invisible — et le mail d'alerte contredirait l'écran.
    cle = TachePlanifiee.export_hors_site.value
    assert _PERIODICITE_ATTENDUE_H.get(cle) == 7 * 24, (
        f"« {cle} » attendue toutes les {_PERIODICITE_ATTENDUE_H.get(cle)} h, pas 7 × 24"
    )


def test_periodicite_exclut_les_crons_a_haute_frequence():
    """Les crons à haute fréquence ne doivent PAS être attendus en base.

    health-watch tourne toutes les 5 min, reliability toutes les 15 : enregistrer
    chaque tick produirait des milliers de lignes par jour dans la table la plus
    écrite de la base. C'est ce profil d'écriture qui a corrompu `telemetry_event`
    deux fois en juin 2026 — ils n'enregistrent que leurs anomalies et actions.

    ⚠️ `reliability` est ATTENDU depuis le 27/09/2026 — et c'est ce test qui dit
    à quelle condition : il ne rend compte que quand ses constats changent, et
    au moins une fois par jour (`lib-notification.sh`). Sans ce plafond, il
    écrirait 192 lignes par jour ; avec, quelques-unes. Le plafond est donc
    exigé ICI, là où l'interdit était écrit : le retirer ferait échouer ce test.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H

    assert "health_watch" not in _PERIODICITE_ATTENDUE_H
    assert "auto_deploy" not in _PERIODICITE_ATTENDUE_H
    assert _PERIODICITE_ATTENDUE_H["maintenance"] == 7 * 24

    assert _PERIODICITE_ATTENDUE_H["reliability"] == 24
    notif = next(p for p in scripts_shell_versionnes() if p.name == "lib-notification.sh")
    src = notif.read_text(encoding="utf-8")
    assert "rapport_payload reliability " in src
    assert 'decision_rapport_ecran "$sig"' in src, (
        "check-reliability rend compte sans passer par sa décision de plafond : "
        "chaque passage (*/15, deux nœuds) écrirait une ligne"
    )


def test_sauvegarde_nest_pas_dupliquee_dans_la_table_maintenance():
    """La sauvegarde garde SA table — elle n'est pas recopiée ici.

    `historique_sauvegarde` existe déjà, est alimentée in-process par
    `run_backup` et dispose de son propre onglet. L'ajouter à
    `_PERIODICITE_ATTENDUE_H` reviendrait à écrire deux fois le même fait, avec
    deux chemins d'écriture différents : c'est la duplication que la règle de
    factorisation interdit, et c'est elle qui fabrique les divergences.

    La vue de santé agrège les deux sources **à la lecture** — sa périodicité
    vit donc dans une constante distincte.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H, _PERIODICITE_SAUVEGARDE_H

    assert "backup" not in _PERIODICITE_ATTENDUE_H, (
        "le backup ne doit pas être attendu dans historique_maintenance : il a sa propre table"
    )
    assert _PERIODICITE_SAUVEGARDE_H == 24


def test_telemetrie_nest_pas_dupliquee_dans_la_table_maintenance():
    """Même règle pour l'agrégation de télémétrie — `historique_telemetrie`.

    Ajoutée le 02/08/2026 : ce job tourne aussi toutes les nuits (02:00), et
    s'il s'arrête, les statistiques d'usage deviennent silencieusement fausses
    sans qu'aucun écran ne le signale — même besoin que la maintenance ou la
    sauvegarde, donc le même traitement générique
    (`_etat_tache_a_table_propre`) plutôt qu'un troisième bloc dupliqué.
    """
    from app.routers.admin import (
        _PERIODICITE_ATTENDUE_H,
        _PERIODICITE_TELEMETRIE_H,
        _etat_tache_a_table_propre,
    )

    assert "telemetrie" not in _PERIODICITE_ATTENDUE_H
    assert _PERIODICITE_TELEMETRIE_H == 24
    assert callable(_etat_tache_a_table_propre)


def test_retention_bornee_et_purgee_in_process():
    """Seuls les 10 derniers rapports sont conservés, et la purge est in-process.

    Elle se fait dans l'API, par la route que `maintenance.sh` appelle — jamais
    par un process tiers entré dans le conteneur.

    La limite d'affichage est bornée par la même constante : afficher plus que
    ce qu'on conserve n'aurait aucun sens.
    """
    import inspect

    from app.routers import admin

    #  ⚠️ On vérifie que le quota EXISTE et qu'il est borné, pas sa VALEUR.
    #  Le test l'a recopiée — `== 10` — et il a donc échoué le jour où elle est
    #  passée à 20, pour une raison parfaitement légitime : chaque exécution de
    #  maintenance écrit désormais DEUX lignes (#488), et dix lignes ne valaient
    #  plus dix exécutions.
    #
    #  Un test qui recopie une constante mesure la constante, pas la propriété.
    #  Ce qui compte ici est qu'un quota s'applique — sinon la table croît sans
    #  fin — et qu'il reste d'un ordre de grandeur raisonnable.
    assert 5 <= admin._RAPPORTS_CONSERVES <= 100, (
        f"quota de rétention aberrant : {admin._RAPPORTS_CONSERVES}"
    )
    assert callable(admin._purger_anciens_rapports)
    # La purge est appelée à la réception d'un rapport, pas par un script externe.
    source = inspect.getsource(admin.maintenance_rapport)
    assert "_purger_anciens_rapports" in source, (
        "la rétention doit être appliquée à chaque rapport reçu"
    )


# ── Deux faux positifs constatés à l'écran le 09/08/2026 ────────────────────


def test_la_bascule_est_attendue_toutes_les_48h_car_le_role_alterne():
    """Un nœud n'agit qu'une nuit sur deux : l'attendre chaque jour est un faux rouge.

    `bascule.sh` sort immédiatement sur le standby (« Ce RPi n'est pas actif —
    rien à faire »). L'historique le montre : 05/08 rpi1, 06/08 rpi2, 07/08 rpi1,
    08/08 rpi2. Avec 24 h d'attente, **un nœud sur deux était signalé
    « Exécution manquante » tous les jours**, sur une infrastructure saine.

    Même erreur que le seuil du cache de build le 06/08 : un seuil se règle sur le
    RÉGIME de ce qu'il surveille, pas sur la fréquence du cron.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H

    assert _PERIODICITE_ATTENDUE_H["bascule"] >= 48, (
        "La bascule alterne : chaque nœud n'opère qu'une nuit sur deux. Une "
        "périodicité de 24 h peint un rouge permanent sur le nœud qui n'était pas "
        "actif — et un rouge permanent ne signale plus rien."
    )


def test_le_script_de_bascule_s_abstient_sur_le_standby():
    """Le fait sur lequel repose la périodicité de 48 h, vérifié et non supposé.

    Si `bascule.sh` se mettait à agir (et donc à rapporter) depuis les deux nœuds,
    48 h deviendrait deux fois trop permissif et l'absence cesserait de se voir.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "scripts" / "exploitation" / "bascule.sh"
    ).read_text(encoding="utf-8")
    assert 'if [ "$ACTIVE" != "$SELF" ]' in source and "exit 0" in source, (
        "bascule.sh ne s'abstient plus sur le standby : la périodicité attendue "
        "de 48 h reposait sur cette abstention."
    )


def test_une_tache_hebdomadaire_survit_aux_quotidiennes(session):
    """La rétention ne doit pas effacer la preuve que le contrôle cherche.

    Constaté à l'écran le 09/08/2026 : « Maintenance hebdomadaire : jamais
    exécutée », alors qu'elle avait tourné le matin même — la purge gardait les
    dix lignes les plus récentes **toutes tâches confondues**, et les quotidiennes
    avaient chassé l'unique ligne hebdomadaire.

    Une tâche rare est justement celle dont l'absence doit se voir.
    """
    from datetime import datetime, timedelta

    from app.models.core import HistoriqueMaintenance
    from app.routers.admin import _purger_anciens_rapports

    base = datetime(2026, 8, 2, 1, 0)
    session.add(
        HistoriqueMaintenance(tache="maintenance", noeud="rpi1", statut="succes", cree_le=base)
    )
    #  Trente exécutions quotidiennes postérieures : bien plus que le quota.
    for j in range(30):
        session.add(
            HistoriqueMaintenance(
                tache="bascule",
                noeud="rpi1" if j % 2 else "rpi2",
                statut="succes",
                cree_le=base + timedelta(days=j + 1),
            )
        )
    session.commit()

    _purger_anciens_rapports(session)

    from sqlmodel import select

    restantes = session.exec(
        select(HistoriqueMaintenance).where(HistoriqueMaintenance.tache == "maintenance")
    ).all()
    assert len(restantes) == 1, (
        "La ligne hebdomadaire a été chassée par les quotidiennes : l'écran "
        "affichera « jamais exécutée » pour une tâche qui tourne."
    )
    bascules = session.exec(
        select(HistoriqueMaintenance).where(HistoriqueMaintenance.tache == "bascule")
    ).all()
    #  Le quota se LIT, il ne se recopie pas — même raison que ci-dessus.
    from app.routers import admin as _admin

    assert len(bascules) == _admin._RAPPORTS_CONSERVES, (
        f"{len(bascules)} lignes de bascule conservées pour un quota de "
        f"{_admin._RAPPORTS_CONSERVES} — le quota par tâche ne s'applique plus, "
        "et la table croîtra sans fin."
    )
