"""Tâches de maintenance exécutables directement depuis l'API."""

import json
from datetime import timedelta
from app.utils import horloge

from sqlmodel import select

from app.auth.jetons_rafraichissement import purger as purger_jetons
from app.utils.noeud import noeud_courant
from app.utils.requete_liee import requete_liee
from app.utils.declenchement import AUTOMATIQUE
from app.utils.llm_journal import limite_conservation
from app.utils.courriel_journal import CONSERVATION_RELEVES_JOURS
from app import contexte
from app.dialecte import compacter, taille_base
from app.models.core import (
    HistoriqueMaintenance,
    WhatsAppLog,
)

#: Durée de conservation de l'historique des envois (#1073). La politique de
#: confidentialité l'annonce : `test_politique_confidentialite_couvre_le_code`
#: compare les deux, pour que le texte ne mente plus dans aucun sens.
CONSERVATION_COURRIELS_JOURS = 90


def _supprimer(sql: str, **params) -> int:
    """Un DELETE lié, dans sa propre connexion ; rend le nombre de lignes ôtées.

    Les dates passent par `requete_liee`, jamais en chaîne (#1298)."""
    with contexte.moteur().connect() as conn:
        n = conn.execute(requete_liee(sql, **params)).rowcount
        conn.commit()
    return n


def purger() -> tuple[dict[str, int], list[str]]:
    """Les purges de la maintenance, DANS le process de l'API (#1232).

    Deux appelants, une écriture : `run_maintenance` (déclenchement manuel) et
    `POST /admin/maintenance/purges`, que `maintenance.sh` appelle chaque
    dimanche. Une étape en échec n'arrête pas les suivantes : elle s'inscrit
    dans `erreurs`, et le compte de ce qui a réussi reste juste.
    """
    #  UTC NAÏF, la forme des dates en base — et des `datetime`, jamais leur
    #  `isoformat()` : comparées en chaînes, elles se trompaient d'un jour (#1298).
    maintenant = horloge.maintenant()
    il_y_a_90_j = maintenant - timedelta(days=90)
    comptes = dict.fromkeys(
        (
            "tokens",
            "prt",
            "verifications",
            "notifications",
            "historique",
            "emails",
            "ia",
            "whatsapp",
            "releves",
        ),
        0,
    )
    erreurs: list[str] = []

    #  Les jetons de rafraîchissement ont leur propre règle — un jeton échangé
    #  reste jusqu'à son expiration — écrite une fois, pour les deux purges.
    try:
        with contexte.nouvelle_session() as s:
            comptes["tokens"] = purger_jetons(s, maintenant)
            s.commit()
    except Exception as exc:
        erreurs.append(f"purge tokens: {exc}")

    #  `TRUE`, jamais `1` : PostgreSQL ne compare pas un booléen à un entier.
    etapes = (
        (
            "prt",
            "purge password reset tokens",
            "DELETE FROM password_reset_token WHERE expires_at < :now OR used = TRUE",
            {"now": maintenant},
        ),
        #  Les jetons de VÉRIFICATION d'e-mail : la seule famille qu'aucune purge
        #  ne touchait (#1382) — un par inscription, gardé à jamais.
        (
            "verifications",
            "purge email verification tokens",
            "DELETE FROM email_verification_token WHERE expires_at < :now OR used = TRUE",
            {"now": maintenant},
        ),
        (
            "notifications",
            "purge notifications",
            "DELETE FROM notification WHERE lue = TRUE AND cree_le < :cutoff",
            {"cutoff": il_y_a_90_j},
        ),
        (
            "historique",
            "purge historique",
            "DELETE FROM historique_maintenance WHERE cree_le < :cutoff",
            {"cutoff": maintenant - timedelta(days=365)},
        ),
        (
            "emails",
            "purge historique emails",
            "DELETE FROM historique_email WHERE cree_le < :cutoff",
            {"cutoff": maintenant - timedelta(days=CONSERVATION_COURRIELS_JOURS)},
        ),
        #  Le journal de l'assistant IA : treize mois de détail (#1383).
        (
            "ia",
            "purge journal IA",
            "DELETE FROM appel_ia WHERE cree_le < :cutoff",
            {"cutoff": limite_conservation(maintenant)},
        ),
        #  Le journal des messages relevés porte l'adresse de l'expéditeur (#1447).
        (
            "releves",
            "purge journal des relèves",
            "DELETE FROM courriel_releve WHERE releve_le < :cutoff",
            {"cutoff": maintenant - timedelta(days=CONSERVATION_RELEVES_JOURS)},
        ),
    )
    for cle, libelle, sql, params in etapes:
        try:
            comptes[cle] = _supprimer(sql, **params)
        except Exception as exc:
            erreurs.append(f"{libelle}: {exc}")

    # Logs WhatsApp : garder les 6 derniers.
    try:
        with contexte.nouvelle_session() as s:
            anciens = s.exec(select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc())).all()[6:]
            for old in anciens:
                s.delete(old)
            s.commit()
            comptes["whatsapp"] = len(anciens)
    except Exception as exc:
        erreurs.append(f"logs WhatsApp: {exc}")

    #  🔴 Plus de purge des « évolutions archivées » (#1381, 27/09/2026). Elle
    #  supprimait les lignes de `publication_evolution` de plus de 90 jours —
    #  archivées ou non, malgré son nom —, et depuis la migration 0210 cette
    #  table n'est plus lue : les évolutions des actualités vivent dans
    #  `ticket_evolution`, l'historique des affaires, qu'aucune purge ne touche.
    #  La purge effaçait donc la copie gelée que 0210 gardait par prudence. La
    #  table elle-même a été supprimée le 30/09/2026 (#1177, migration 0238).

    return comptes, erreurs


def run_maintenance(history_id: int | None = None) -> None:
    """La maintenance lancée depuis l'administration : `purger()`, puis VACUUM.

    Met à jour (ou crée) l'entrée HistoriqueMaintenance correspondante. La
    maintenance HEBDOMADAIRE, elle, est celle de `maintenance.sh`, qui demande
    les mêmes purges à l'API (`POST /admin/maintenance/purges`) puis compacte
    la base API arrêtée — aucun planificateur n'appelle cette fonction.
    """
    start = horloge.maintenant()

    with contexte.nouvelle_session() as session:
        entry: HistoriqueMaintenance | None = None
        if history_id:
            entry = session.get(HistoriqueMaintenance, history_id)
        if not entry:
            #  🔴 AUTOMATIQUE, et avec le nœud (18/09/2026). Ce repli est le
            #  chemin d'un appel SANS entrée préexistante — prévu pour un
            #  planificateur, qu'aucun `add_job` ne branche au 24/09/2026 (#1232). Il posait « manuelle » et aucun
            #  nœud — une maintenance automatique s'affichait donc comme
            #  déclenchée à la main, sur un nœud inconnu, dans la colonne que
            #  `TachesPlanifiees` montre. C'est le défaut que l'endpoint de
            #  lancement disait avoir corrigé en v2.32.0, resté entier ici.
            entry = HistoriqueMaintenance(declenchee_par=AUTOMATIQUE, noeud=noeud_courant())
            session.add(entry)
            session.commit()
            session.refresh(entry)

        comptes, erreurs = purger()
        tokens_supprimes = comptes["tokens"]

        # Compactage — après les purges, qu'il récupère (`dialecte.compacter`).
        try:
            with (
                contexte.moteur().execution_options(isolation_level="AUTOCOMMIT").connect() as conn
            ):
                compacter(conn)
        except Exception as exc:
            erreurs.append(f"VACUUM: {exc}")

        # Taille de la base après compactage — inconnue (None) si la lecture échoue
        taille_db: int | None = None
        try:
            with contexte.moteur().connect() as conn:
                taille_db = taille_base(conn)
        except Exception:
            pass

        end = horloge.maintenant()
        entry.statut = "erreur" if erreurs else "succes"
        entry.tokens_supprimes = tokens_supprimes
        #  🔴 Les COMPTES, comme le rapport du script (27/09/2026, signalé à
        #  l'écran) : l'exécution manuelle n'écrivait aucun détail, et
        #  l'historique montrait « — » là où la hebdomadaire dit ce qu'elle a purgé.
        entry.details = json.dumps(comptes, ensure_ascii=False)
        entry.taille_db_octets = taille_db
        entry.duree_secondes = max(1, int((end - start).total_seconds()))
        entry.erreur = " | ".join(erreurs) if erreurs else None
        entry.terminee_le = end
        session.add(entry)
        session.commit()
