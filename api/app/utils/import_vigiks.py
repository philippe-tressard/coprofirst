"""
Utilitaire d'import des vigiks depuis un fichier Excel (.xlsx).

Structure attendue du fichier (première ligne = en-tête ignorée) :
  Colonne A : numéro de bâtiment   (ex. « 3 »)
  Colonne B : numéro d'appartement (ex. « 102 »)
  Colonne C : nom du copropriétaire (requis)
  Colonne D : nom du locataire (optionnel)
  Colonne E : N° CLÉS — référence du vigik

Usage depuis le conteneur :
  docker compose exec -u app api python -c "
  from app.utils.import_vigiks import importer_depuis_fichier
  importer_depuis_fichier('/chemin/vers/vigik.xlsx')
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

from app.models.core import Batiment, Lot, StatutImport, VigikImport


# ── Noms à ignorer automatiquement ────────────────────────────────────────
#  Le classeur des vigiks n'ajoute rien au noyau commun : il s'y réduit.
#  L'écrire ainsi plutôt que de recopier les trois noms fait que le jour où un
#  quatrième non-résident apparaît, il apparaît ICI AUSSI, sans qu'on y pense.
_NOMS_IGNORES = NOMS_NON_RESIDENTS


#:  Ce que « Remplacer » efface — et, par omission, ce qu'il PRÉSERVE (#824).
#:  Seul le non-traité, comme pour les télécommandes : `proprietaire_lie` porte
#:  un rapprochement à demi fait sur un code déjà confié.
_PURGES_PAR_REMPLACER = (StatutImport.en_attente,)


def _traiter_rows(rows: list, session: Session, remplacer: bool) -> dict:
    """Traite les lignes du classeur et insère les VigikImport."""
    data_rows = rows[1:]  # ignorer l'en-tête
    stats: dict = {"importes": 0, "ignores": 0, "doublons": 0, "erreurs": []}

    if remplacer:
        purger_staging(session, VigikImport, _PURGES_PAR_REMPLACER)

    # Pré-charger l'index lot (batiment_numero, lot_numero) → lot_id
    lot_index = _build_lot_index(session)

    for i, row in enumerate(data_rows, start=2):
        if len(row) < 5:
            continue

        batiment_raw = str(row[0]).strip() if row[0] else None
        appt_raw = str(row[1]).strip() if row[1] else None
        nom_prop_raw = str(row[2]).strip() if row[2] else None
        nom_loc_raw = str(row[3]).strip() if row[3] else None
        code_raw = str(row[4]).strip() if row[4] else None

        if not nom_prop_raw:
            continue

        nom_prop_norm = normaliser(nom_prop_raw)

        if nom_prop_norm in _NOMS_IGNORES:
            stats["ignores"] += 1
            _creer_import(
                session,
                batiment_raw,
                appt_raw,
                nom_prop_raw,
                nom_loc_raw,
                code_raw,
                statut=StatutImport.ignore,
                notes_admin=f"Ignoré automatiquement (hors résidents) — ligne Excel {i}",
            )
            continue

        # Déduplique propriétaire-occupant
        if nom_loc_raw and normaliser(nom_loc_raw) == nom_prop_norm:
            nom_loc_raw = None

        # Éviter les doublons exacts (même propriétaire + même code)
        if code_raw:
            doublon = session.exec(
                select(VigikImport).where(
                    VigikImport.nom_proprietaire == nom_prop_raw,
                    VigikImport.code == code_raw,
                )
            ).first()
            if doublon:
                stats["doublons"] += 1
                continue

        # Tentative de résolution automatique du lot
        lot_id: Optional[int] = None
        if batiment_raw and appt_raw:
            lot_id = lot_index.get((normaliser(batiment_raw), normaliser(appt_raw)))

        _creer_import(
            session, batiment_raw, appt_raw, nom_prop_raw, nom_loc_raw, code_raw, lot_id=lot_id
        )
        stats["importes"] += 1

    return stats


#  Les deux points d'entrée d'un import — le mécanisme est dans `import_xlsx`.
importer_depuis_bytes, importer_depuis_fichier = importeurs(_traiter_rows)


def _build_lot_index(session: Session) -> dict[tuple[str, str], int]:
    """Construit un dictionnaire (batiment_num_norm, lot_num_norm) → lot_id."""
    index: dict[tuple[str, str], int] = {}
    batiments = session.exec(select(Batiment)).all()
    bat_map = {b.id: normaliser(b.numero) for b in batiments}
    lots = session.exec(select(Lot)).all()
    for lot in lots:
        bat_num = bat_map.get(lot.batiment_id, "")
        lot_num = normaliser(lot.numero)
        if bat_num and lot_num:
            index[(bat_num, lot_num)] = lot.id
    return index


def _creer_import(
    session: Session,
    batiment_raw: Optional[str],
    appartement_raw: Optional[str],
    nom_proprietaire: str,
    nom_locataire: Optional[str],
    code: Optional[str],
    lot_id: Optional[int] = None,
    statut: StatutImport = StatutImport.en_attente,
    notes_admin: Optional[str] = None,
) -> VigikImport:
    record = VigikImport(
        batiment_raw=batiment_raw,
        appartement_raw=appartement_raw,
        nom_proprietaire=nom_proprietaire,
        nom_locataire=nom_locataire or None,
        code=code or None,
        lot_id=lot_id,
        statut=statut,
        notes_admin=notes_admin,
        importe_le=horloge.maintenant(),
    )
    session.add(record)
    return record
