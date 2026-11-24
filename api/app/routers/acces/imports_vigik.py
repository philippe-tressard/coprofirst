"""L'import Excel des badges Vigik, et son appariement.

Jumeau de `imports_telecommandes`. Le CYCLE des deux est écrit une seule fois
dans `socle_imports` — voir son en-tête, et le défaut de possession qui a prouvé
que ce n'étaient pas deux ressemblances de hasard (#847).

Ce qui reste ici et **nulle part ailleurs** : la résolution du lot par
`batiment_raw` + `appartement_raw`. Le fichier Vigik porte ces deux colonnes, le
fichier des télécommandes ne les a pas.
"""

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlmodel import Session, select

from app.auth.deps import require_admin, require_cs_or_admin
from app.database import get_session
from app.models.copropriete import Lot
from app.models.core import LotImport, Utilisateur, VigikImport
from app.utils.batiments import libelle_lot
from app.utils.valeurs import valeur

from .commun import (
    _ignorer_import,
    _supprimer_import,
    _lister_imports,
    _remettre_en_attente_import,
    _stats_socle,
)
from app.utils.resolution_acces import rattacher_les_reconnues
from app.utils.types_acces import VIGIK
from app.utils.fichiers import lire_tableur_recu
from . import socle_imports
from .socle_imports import PatchImportBody

router = APIRouter()

#: Le type d'accès, décrit UNE fois dans `utils/types_acces` — la chaîne
#: d'import n'en est qu'un usage. Un second descripteur vivait ici
#: (`TypeImportAcces`) et redisait cinq de ses six champs sous d'autres
#: noms, en exportant une constante du MÊME nom : deux objets pour une
#: notion, et le risque qu'ils divergent sans bruit (18/09/2026, #779).

# ── Import Excel vigiks ────────────────────────────────────────────────────


@router.post("/admin/imports-vigik/upload", status_code=201)
async def upload_import_vigik_excel(
    file: UploadFile = File(...),
    remplacer: bool = Query(False, description="Supprimer les imports en_attente avant ré-import"),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Upload un fichier Excel et importe les vigiks dans la table de staging."""
    from app.utils.import_vigiks import importer_depuis_bytes

    contenu = await lire_tableur_recu(file)
    return importer_depuis_bytes(contenu, session=session, remplacer=remplacer)


@router.get("/admin/imports-vigik/stats")
def stats_imports_vigik(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Statistiques synthétiques sur les imports vigik."""
    lignes, stats = _stats_socle(VIGIK, session)
    stats["avec_code"] = sum(1 for i in lignes if i.code)
    stats["avec_lot"] = sum(1 for i in lignes if i.lot_id)
    return stats


@router.get("/admin/imports-vigik")
def list_imports_vigik(
    statut: str = Query(None),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Liste les imports vigik, optionnellement filtrés par statut."""
    return _lister_imports(VIGIK, statut, session)


@router.get("/admin/imports-lots")
def lots_a_choisir(
    session: Session = Depends(get_session),
    #  Le CONSEIL aussi : l'Espace CS (`BadgesCopropriete`) choisit un lot dans cette
    #  liste. Les imports eux-mêmes sont réservés à l'administrateur (#3012).
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les lots, pour choisir celui d'une ligne d'import — les DEUX écrans (#1194).

    Chaque lot porte le nom de son copropriétaire tel que le **fichier des lots**
    l'écrit : c'est le seul nom qu'un lot sans compte possède, et c'est le cas
    courant. `/copropriete/lots`, ouverte à tout résident, ne le donne pas — et
    ne doit pas : ce nom ne regarde que le conseil syndical, qui voit déjà les
    fichiers du syndic.
    """
    noms: dict[int, str] = {}
    for li in session.exec(select(LotImport).where(LotImport.lot_id != None)).all():  # noqa: E711
        if li.nom_coproprietaire:
            noms.setdefault(li.lot_id, li.nom_coproprietaire)
    return [
        {
            "id": lot.id,
            "libelle": libelle_lot(lot),
            "type": valeur(lot.type),
            "coproprietaire": noms.get(lot.id),
        }
        for lot in session.exec(select(Lot)).all()
    ]


@router.post("/admin/imports-vigik/auto-match")
def auto_match_imports_vigik(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Apparie les imports vigik en attente : leur lot, puis les comptes inscrits."""
    return socle_imports.auto_match(VIGIK, session)


@router.post("/admin/imports-vigik/rattacher")
def rattacher_imports_vigik(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Le rattachement en masse : chaque ligne dont le lot est connu (#1194)."""
    return rattacher_les_reconnues(VIGIK, session)


@router.patch("/admin/imports-vigik/{import_id}")
def patch_import_vigik(
    import_id: int,
    body: PatchImportBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Met à jour les liaisons d'un import vigik.
    Fonctionne même si l'import est déjà résolu (correction après coup)."""
    return socle_imports.patch(VIGIK, import_id, body, session)


@router.post("/admin/imports-vigik/{import_id}/resoudre")
def resoudre_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Rattache le badge de cette ligne à son lot. Ses porteurs s'en déduisent —
    les copropriétaires du lot, conjoint compris (`utils/porteurs_acces`)."""
    return socle_imports.resoudre(VIGIK, import_id, session)


@router.post("/admin/imports-vigik/{import_id}/remettre-en-attente")
def remettre_en_attente_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Remet un import vigik ignoré en 'en attente' — absent jusqu'à #576."""
    return _remettre_en_attente_import(VigikImport, import_id, session)


@router.post("/admin/imports-vigik/{import_id}/ignorer")
def ignorer_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Marque un import vigik comme ignoré."""
    return _ignorer_import(VigikImport, import_id, session)


@router.delete("/admin/imports-vigik/{import_id}", status_code=204)
def supprimer_ligne_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """🔒 Supprimer une ligne erronée — le badge éventuel reste au parc."""
    _supprimer_import(VigikImport, import_id, session)
