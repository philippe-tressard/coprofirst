"""
Utilitaire d'import des télécommandes depuis un fichier Excel (.xlsx).

Structure attendue du fichier (première ligne = en-tête ignorée) :
  Colonne A : nom du copropriétaire (requis)
  Colonne B : nom du locataire (optionnel)
  Colonne C : référence de la télécommande (optionnel sur quelques lignes spéciales)

Usage depuis le conteneur :
  docker compose exec -u app api python -c "
  from app.utils.import_telecommandes import importer_depuis_fichier
  importer_depuis_fichier('/chemin/vers/fichier.xlsx')
  "
"""

from __future__ import annotations

from app.utils import horloge
from typing import Optional

from sqlmodel import Session, select

#  La mécanique d'un import (ouverture du classeur, transaction, normalisation)
#  vit dans `import_xlsx` : elle était écrite à l'identique dans les trois modules.
#  Ce qui reste ici est la seule chose qui leur soit propre — comment lire les
#  colonnes. `normaliser` est ré-exporté : `acces.py` et `auto_match_service.py`
#  l'importent depuis ce module.
from app.utils.import_xlsx import (  # noqa: F401  (ré-export de `normaliser`)
    NOMS_NON_RESIDENTS,
    importeurs,
    normaliser,
    purger_staging,
)

from app.models.core import StatutImport, TelecommandeImport


# ── Noms à ignorer automatiquement (accès non-résidents) ──────────────────
#  🔴 Le noyau commun, ENRICHI de ce qui est propre à ce classeur-ci : deux
#  références de commande datées, qui ne désignent personne. Elles ne valent que
#  pour le fichier des télécommandes — les remonter dans le socle ferait ignorer
#  une ligne du classeur vigik au nom identique, ce qui n'arrivera pas, mais on
#  ne partage pas une exception « au cas où ».
_NOMS_IGNORES = NOMS_NON_RESIDENTS | {
    "CDE 22/06/2023",
    "- CDE 02/07/2024",
}


#:  Ce que « Remplacer » efface — et, par omission, ce qu'il PRÉSERVE (#824).
#:  Seul le non-traité. `proprietaire_lie` est un rapprochement à demi fait sur
#:  un objet déjà remis à quelqu'un : le refaire coûte plus qu'un réimport.
_PURGES_PAR_REMPLACER = (StatutImport.en_attente,)


def _traiter_rows(rows: list, session: Session, remplacer: bool) -> dict:
    """Traite les lignes du classeur et insère les TelecommandeImport."""
    data_rows = rows[1:]  # ignorer l'en-tête
    stats: dict = {"importes": 0, "ignores": 0, "doublons": 0, "erreurs": []}

    if remplacer:
        purger_staging(session, TelecommandeImport, _PURGES_PAR_REMPLACER)

    for i, row in enumerate(data_rows, start=2):
        nom_prop_raw = str(row[0]).strip() if row[0] else None
        nom_loc_raw = str(row[1]).strip() if row[1] else None
        reference_raw = str(row[2]).strip() if row[2] else None

        if not nom_prop_raw:
            continue

        nom_prop_norm = normaliser(nom_prop_raw)

        if nom_prop_norm in _NOMS_IGNORES:
            stats["ignores"] += 1
            _creer_import(
                session,
                nom_prop_raw,
                nom_loc_raw,
                reference_raw,
                statut=StatutImport.ignore,
                notes_admin=f"Ignoré automatiquement (hors résidents) — ligne Excel {i}",
            )
            continue

        if nom_loc_raw and normaliser(nom_loc_raw) == nom_prop_norm:
            nom_loc_raw = None  # proprio-occupant

        if reference_raw:
            doublon = session.exec(
                select(TelecommandeImport).where(
                    TelecommandeImport.nom_proprietaire == nom_prop_raw,
                    TelecommandeImport.reference == reference_raw,
                )
            ).first()
            if doublon:
                stats["doublons"] += 1
                continue

        _creer_import(session, nom_prop_raw, nom_loc_raw, reference_raw)
        stats["importes"] += 1

    return stats


#  Les deux points d'entrée d'un import — le mécanisme est dans `import_xlsx`.
importer_depuis_bytes, importer_depuis_fichier = importeurs(_traiter_rows)


def _creer_import(
    session: Session,
    nom_proprietaire: str,
    nom_locataire: Optional[str],
    reference: Optional[str],
    statut: StatutImport = StatutImport.en_attente,
    notes_admin: Optional[str] = None,
) -> TelecommandeImport:
    record = TelecommandeImport(
        nom_proprietaire=nom_proprietaire,
        nom_locataire=nom_locataire or None,
        reference=reference or None,
        statut=statut,
        notes_admin=notes_admin,
        importe_le=horloge.maintenant(),
    )
    session.add(record)
    return record
