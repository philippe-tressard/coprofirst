"""Router lots — l'import (staging) des lots, réservé au conseil et à l'admin.

Extrait de `lots.py` le 09/09/2026, sur refus du contrôle de modularité : ce
fichier a franchi les 500 lignes en recevant l'écriture de l'étage d'un lot
(#835), et la règle est « au fil de l'eau ».

La coupe suit la nature des endpoints, pas l'arithmétique. `lots.py` répond à
« quels sont MES lots, et que puis-je en dire » — consultation, commandes
d'accès, l'étage de son propre logement. Ce module-ci est un **atelier
d'administration** : téléverser un tableur, rapprocher ses lignes de comptes
existants, arbitrer les cas douteux. Deux publics, deux rythmes de changement.

⚠️ Les routes ne bougent PAS : ce module expose son propre `APIRouter`, que
`lots.py` inclut à la fin du sien. `main.py` ne change pas, et les chemins
`/lots/admin/imports/…` restent identiques — un déplacement de fichier ne doit
rien changer à ce que le front appelle.

⚠️ L'inclusion est faite **après** `/{lot_id}`, comme la déclaration l'était :
FastAPI résout dans l'ordre de déclaration, et l'ordre relatif est ici sans
conséquence (ces chemins ont trois segments ou plus, `/{lot_id}` un seul) — mais
le préserver évite d'avoir à le redémontrer au prochain ajout.
"""

from __future__ import annotations

import json
from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.utils.batiments import libelle_batiment
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Batiment,
    Lot,
    LotImport,
    StatutLotImport,
    TypeLien,
    UserLot,
    Utilisateur,
)
from app.utils.import_xlsx import etage_de_lot, type_de_lot
from app.utils.resolution_lots import rapprocher_imports, resoudre_imports
from app.utils.recuperer import ou_404
from app.utils.valeurs import valeur
from app.utils.fichiers import lire_tableur_recu

router = APIRouter()


#  Ces deux lecteurs venaient de `lots.py` et sont VENUS AVEC l'atelier : ils n'y
#  servaient qu'à lui. Une extraction qui laisse une copie derrière elle n'a rien
#  extrait — elle a dupliqué (`standards/02` §5).


def _parse_users(utilisateurs_json: str) -> list[dict]:
    """Retourne la liste [{user_id, type_lien}] ou [] en cas d'erreur."""
    try:
        val = json.loads(utilisateurs_json or "[]")
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _type_lien_from_str(s: str) -> TypeLien:
    try:
        return TypeLien(s)
    except ValueError:
        return TypeLien.propriétaire


def _lier_utilisateurs(session: Session, entrees: list[dict], lot_id: int) -> None:
    """Crée le `UserLot` de chaque utilisateur lié qui n'en a pas encore sur ce lot.

    Écrit deux fois (résolution d'une ligne, puis resynchronisation d'une ligne
    déjà résolue) jusqu'au 02/10/2026 (#1564). Une entrée sans `user_id` est
    ignorée, un lien déjà présent n'est jamais dupliqué ni modifié.
    """
    for entree in entrees:
        uid = entree.get("user_id")
        type_lien = _type_lien_from_str(entree.get("type_lien", "propriétaire"))
        if not uid:
            continue
        if type_lien == TypeLien.locataire:
            #  Le lien ET les badges du lot : la seule porte (#2267). Rattaché
            #  ici, un locataire avait son lot sans ses Vigik ni ses télécommandes.
            from app.utils.rattachement_locataire import lier_locataire

            lier_locataire(session, uid, [ou_404(session, Lot, lot_id, "Lot")])
            continue
        existant = session.exec(
            select(UserLot).where(UserLot.user_id == uid, UserLot.lot_id == lot_id)
        ).first()
        if not existant:
            session.add(UserLot(user_id=uid, lot_id=lot_id, type_lien=type_lien, actif=True))


#  Import staging  endpoints


@router.post("/admin/imports/upload", status_code=201)
async def upload_import_lots(
    file: UploadFile = File(...),
    remplacer: bool = Query(False),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Upload un Excel, auto-matche et résout automatiquement les copropriétaires."""
    from app.utils.import_lots import importer_depuis_bytes

    contenu = await lire_tableur_recu(file)
    stats_import = importer_depuis_bytes(contenu, session=session, remplacer=remplacer)
    #  Rapprocher PUIS résoudre — deux étapes, une écriture chacune (#829).
    #  Ce bloc était recopié dans `auto_match_imports` juste en dessous, et les
    #  deux copies avaient déjà dérivé sur l'affectation du statut.
    rapprocher_imports(session)
    session.flush()
    # Auto-résolution copropriétaires
    stats_resolve = resoudre_imports(session)
    session.commit()
    return {**stats_import, **{"auto_" + k: v for k, v in stats_resolve.items()}}


def _imp_row(imp: LotImport, session: Session) -> dict:
    lot = session.get(Lot, imp.lot_id) if imp.lot_id else None
    bat = session.get(Batiment, imp.batiment_id) if imp.batiment_id else None

    # Libellé bâtiment
    if bat:
        bat_nom = libelle_batiment(bat)
    elif imp.batiment_id:
        bat_nom = str(imp.batiment_id)
    else:
        bat_nom = "P"  # parking sans bâtiment

    # Résoudre chaque utilisateur depuis DB
    utilisateurs_out = []
    for entry in _parse_users(imp.utilisateurs_json):
        uid = entry.get("user_id")
        tl = entry.get("type_lien", "propriétaire")
        u = session.get(Utilisateur, uid) if uid else None
        utilisateurs_out.append(
            {
                "user_id": uid,
                "type_lien": tl,
                "utilisateur": {"id": u.id, "prenom": u.prenom, "nom": u.nom} if u else None,
            }
        )

    return {
        "id": imp.id,
        "batiment_id": imp.batiment_id,
        "batiment_nom": bat_nom,
        "numero": imp.numero,
        "type_raw": imp.type_raw,
        "etage_raw": imp.etage_raw,
        "no_coproprietaire": imp.no_coproprietaire,
        "nom_coproprietaire": imp.nom_coproprietaire,
        "statut": valeur(imp.statut),
        "lot_id": imp.lot_id,
        "lot_label": (
            f"{libelle_batiment(lot.batiment)} — {lot.numero} ({valeur(lot.type)})"
            if lot and lot.batiment
            else (f"#{imp.lot_id}" if imp.lot_id else None)
        ),
        "utilisateurs": utilisateurs_out,
        "notes_admin": imp.notes_admin,
        "importe_le": imp.importe_le.isoformat() if imp.importe_le else None,
        "resolu_le": imp.resolu_le.isoformat() if imp.resolu_le else None,
    }


@router.get("/admin/imports")
def list_imports(
    statut: Optional[str] = Query(None),
    tri: Optional[str] = Query("copro", description="copro | batiment | numero"),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    stmt = select(LotImport)
    if statut:
        stmt = stmt.where(LotImport.statut == statut)
    if tri == "batiment":
        stmt = stmt.order_by(LotImport.batiment_id, LotImport.numero)
    elif tri == "numero":
        stmt = stmt.order_by(LotImport.numero)
    else:  # copro (défaut)
        stmt = stmt.order_by(
            LotImport.nom_coproprietaire,
            LotImport.no_coproprietaire,
            LotImport.batiment_id,
            LotImport.numero,
        )
    imports = session.exec(stmt).all()
    return [_imp_row(imp, session) for imp in imports]


@router.get("/admin/imports/stats")
def stats_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    all_imps = session.exec(select(LotImport)).all()
    return {
        "total": len(all_imps),
        "en_attente": sum(1 for x in all_imps if x.statut == StatutLotImport.en_attente),
        "utilisateur_lie": sum(1 for x in all_imps if x.statut == StatutLotImport.utilisateur_lie),
        "lot_lie": sum(1 for x in all_imps if x.statut == StatutLotImport.lot_lie),
        "resolu": sum(1 for x in all_imps if x.statut == StatutLotImport.resolu),
        "ignore": sum(1 for x in all_imps if x.statut == StatutLotImport.ignore),
        "avec_user": sum(1 for x in all_imps if _parse_users(x.utilisateurs_json)),
    }


class UserLienItem(BaseModel):
    user_id: int
    type_lien: str = "propriétaire"  # propriétaire | locataire


class PatchImport(BaseModel):
    lot_id: Optional[int] = None
    utilisateurs: Optional[list[UserLienItem]] = None  # remplace l'ancien user_id unique
    notes_admin: Optional[str] = None


@router.patch("/admin/imports/{imp_id}")
def patch_import(
    imp_id: int,
    body: PatchImport,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    imp = ou_404(session, LotImport, imp_id, "Import")
    if body.lot_id is not None:
        imp.lot_id = body.lot_id or None
    # Capturer les anciens user_ids AVANT mise à jour (pour diff UserLot si résolu)
    old_user_ids: set[int] = {
        e["user_id"] for e in _parse_users(imp.utilisateurs_json) if e.get("user_id")
    }
    if body.utilisateurs is not None:
        imp.utilisateurs_json = json.dumps(
            [{"user_id": u.user_id, "type_lien": u.type_lien} for u in body.utilisateurs],
            ensure_ascii=False,
        )
    if body.notes_admin is not None:
        imp.notes_admin = body.notes_admin or None
    # Recalculer le statut
    if imp.statut not in (StatutLotImport.resolu, StatutLotImport.ignore):
        imp.statut = StatutLotImport.lot_lie if imp.lot_id else StatutLotImport.en_attente
    # Si l'import est déjà résolu et qu'un lot est connu, synchroniser les UserLot :
    # - créer les nouveaux liens
    # - supprimer les liens retirés par l'admin
    if imp.statut == StatutLotImport.resolu and imp.lot_id and body.utilisateurs is not None:
        new_entries = _parse_users(imp.utilisateurs_json)
        new_user_ids: set[int] = {e["user_id"] for e in new_entries if e.get("user_id")}
        # Supprimer les UserLot retirés
        for uid_removed in old_user_ids - new_user_ids:
            ul = session.exec(
                select(UserLot).where(UserLot.user_id == uid_removed, UserLot.lot_id == imp.lot_id)
            ).first()
            if ul:
                session.delete(ul)
        _lier_utilisateurs(session, new_entries, imp.lot_id)
    session.add(imp)
    session.commit()
    session.refresh(imp)
    return _imp_row(imp, session)


@router.post("/admin/imports/{imp_id}/resoudre", status_code=200)
def resoudre_import(
    imp_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    imp = ou_404(session, LotImport, imp_id, "Import")
    if imp.statut == StatutLotImport.resolu:
        raise HTTPException(400, "Déjà résolu")

    # 1. Trouver ou créer le Lot
    lot = session.get(Lot, imp.lot_id) if imp.lot_id else None
    if not lot:
        if imp.batiment_id:
            # Lot résidentiel/cave : chercher par batiment_id + numero
            lot = session.exec(
                select(Lot).where(Lot.batiment_id == imp.batiment_id, Lot.numero == imp.numero)
            ).first()
        else:
            # Parking (batiment_id=None) : chercher par numero parmi les lots de type parking
            lot = session.exec(
                select(Lot).where(Lot.batiment_id.is_(None), Lot.numero == imp.numero)  # type: ignore
            ).first()
    if not lot:
        # Créer le Lot (parking autorisé avec batiment_id=None)
        lot_type, type_app = type_de_lot(imp.type_raw)
        lot = Lot(
            batiment_id=imp.batiment_id,  # None pour parking
            numero=imp.numero,
            type=lot_type,
            type_appartement=type_app,
            etage=etage_de_lot(imp.etage_raw),
        )
        session.add(lot)
        session.flush()
    imp.lot_id = lot.id

    # 2. Créer les UserLot pour chaque utilisateur lié
    _lier_utilisateurs(session, _parse_users(imp.utilisateurs_json), lot.id)
    session.flush()

    imp.statut = StatutLotImport.resolu
    imp.resolu_le = horloge.maintenant()
    session.add(imp)
    session.commit()
    return {"ok": True, "lot_id": lot.id, "nb_liens": len(_parse_users(imp.utilisateurs_json))}


@router.post("/admin/imports/{imp_id}/ignorer", status_code=200)
def ignorer_import(
    imp_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    imp = ou_404(session, LotImport, imp_id, "Import")
    imp.statut = StatutLotImport.ignore
    session.add(imp)
    session.commit()
    return {"ok": True}


#  🔴 `_auto_resoudre_proprietaires_batch` vit dans `utils/resolution_lots`
#  depuis #829. Cette copie-ci sautait tout import dont un occupant était
#  locataire, et posait les `UserLot` SANS revalider le nom — l'autre voie
#  faisait l'inverse des deux. Le résultat dépendait du bouton employé.


@router.post("/admin/imports/auto-resoudre", status_code=200)
def auto_resoudre_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Résout automatiquement tous les imports copropriétaires matchés (lot + user liés)."""
    stats = resoudre_imports(session)
    #  Le module ne committe pas : c'est l'appelant qui décide de la portée
    #  de sa transaction, et ici l'endpoint se termine.
    session.commit()
    return stats


@router.post("/admin/imports/auto-match", status_code=200)
def auto_match_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Tente de lier automatiquement les LotImport aux Lot et Utilisateur existants.
    Utilise l'algorithme robuste de matching (accents, tirets, noms composés, bigrammes)."""
    matches = rapprocher_imports(session)
    session.commit()
    return {"matches": matches}
