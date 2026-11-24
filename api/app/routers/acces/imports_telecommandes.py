"""L'import Excel des télécommandes de parking, et son appariement.

Le fichier du prestataire arrive en STAGING (`TelecommandeImport`), puis chaque
ligne est rapprochée d'un lot et d'un compte — automatiquement quand le nom
concorde, à la main sinon. La résolution crée la `Telecommande` réelle.

⚠️ Ce module ne porte plus **que** les chemins d'URL et ce qui lui est propre. Le
cycle lui-même — appariement, correction, résolution — vit dans `socle_imports`,
avec le récit de ce qu'il a coûté d'en avoir eu deux copies (#847).
"""

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import (
    TelecommandeImport,
    Utilisateur,
)

from .commun import (
    _ignorer_import,
    _supprimer_import,
    _lister_imports,
    _remettre_en_attente_import,
    _stats_socle,
)
from app.utils.resolution_acces import rattacher_les_reconnues
from app.utils.types_acces import TELECOMMANDE
from app.utils.fichiers import lire_tableur_recu
from . import socle_imports
from .socle_imports import PatchImportBody

router = APIRouter()

#: Le type d'accès, décrit UNE fois dans `utils/types_acces` — la chaîne
#: d'import n'en est qu'un usage. Un second descripteur vivait ici
#: (`TypeImportAcces`) et redisait cinq de ses six champs sous d'autres
#: noms, en exportant une constante du MÊME nom : deux objets pour une
#: notion, et le risque qu'ils divergent sans bruit (18/09/2026, #779).

# ── Import Excel télécommandes ──────────────────────────────────────────────


@router.post("/admin/imports/upload", status_code=201)
async def upload_import_excel(
    file: UploadFile = File(...),
    remplacer: bool = Query(False, description="Supprimer les imports en_attente avant ré-import"),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Upload un fichier Excel et importe les télécommandes dans la table de staging."""
    from app.utils.import_telecommandes import importer_depuis_bytes

    contenu = await lire_tableur_recu(file)
    return importer_depuis_bytes(contenu, session=session, remplacer=remplacer)


@router.get("/admin/imports")
def list_imports(
    statut: str = Query(None),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Liste les imports, optionnellement filtrés par statut."""
    return _lister_imports(TELECOMMANDE, statut, session)


@router.post("/admin/imports/auto-match")
def auto_match_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Apparie les imports en attente : leur lot, puis les comptes inscrits.

    Le fichier des télécommandes ne porte ni bâtiment ni appartement : le lot se
    retrouve par le nom du copropriétaire, dans le fichier des lots
    (`utils/lot_des_imports`).
    """
    return socle_imports.auto_match(TELECOMMANDE, session)


@router.post("/admin/imports/rattacher")
def rattacher_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Le rattachement en masse : chaque ligne dont le lot est connu (#1194)."""
    return rattacher_les_reconnues(TELECOMMANDE, session)


@router.patch("/admin/imports/{import_id}")
def patch_import(
    import_id: int,
    body: PatchImportBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Met à jour les liaisons d'un import (utilisateurs, lot, possession).
    Fonctionne même si l'import est déjà résolu (correction après coup)."""
    return socle_imports.patch(TELECOMMANDE, import_id, body, session)


@router.post("/admin/imports/{import_id}/resoudre")
def resoudre_import(
    import_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Rattache la télécommande de cette ligne à son lot.

    Ses porteurs s'en déduisent : les copropriétaires du lot, conjoint compris,
    et le locataire si elle lui a été remise (`utils/porteurs_acces`).
    """
    return socle_imports.resoudre(TELECOMMANDE, import_id, session)


#  ── Les gestes de STATUT d'un import, écrits UNE fois (#576) ────────────────
#  Deux tables, un seul CYCLE. Écrits deux fois, ils ont produit le défaut de
#  #576 : `remettre-en-attente` n'existait que côté télécommandes, et un import
#  Vigik ignoré par erreur était définitivement perdu. Écrits une fois, la
#  symétrie est STRUCTURELLE ; `test_symetrie_imports_acces.py` garde le reste.


@router.post("/admin/imports/{import_id}/ignorer")
def ignorer_import(
    import_id: int,
    body: BaseModel = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Marque un import comme ignoré (accès non-résidentiel, doublon, etc.)."""
    return _ignorer_import(TelecommandeImport, import_id, session)


@router.post("/admin/imports/{import_id}/remettre-en-attente")
def remettre_en_attente_import(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Remet un import ignoré en statut 'en attente' pour traitement ultérieur."""
    return _remettre_en_attente_import(TelecommandeImport, import_id, session)


@router.post("/admin/imports/{import_id}/refuser-locataire")
def refuser_telecommande_locataire(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Le locataire a refusé la télécommande — elle reste/revient chez le propriétaire.

    ⚠️ Propre aux télécommandes : elles se remettent en main propre, et le refus
    est un geste du quotidien. L'asymétrie est déclarée dans
    `test_symetrie_imports_acces.py`.

    Il passe par `socle_imports.patch` et non par une écriture directe : sur un
    import DÉJÀ RÉSOLU, le refus doit redescendre sur la télécommande elle-même,
    sinon l'objet continue d'affirmer qu'elle est chez le locataire. La réponse,
    elle, garde sa forme d'origine — c'est un contrat, pas un détail.
    """
    socle_imports.patch(
        TELECOMMANDE, import_id, PatchImportBody(refuse_par_locataire=True), session
    )
    return {"refuse_par_locataire": True, "chez_locataire": False}


@router.get("/admin/imports/stats")
def stats_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Statistiques synthétiques sur les imports."""
    lignes, stats = _stats_socle(TELECOMMANDE, session)
    stats["avec_reference"] = sum(1 for i in lignes if i.reference)
    return stats


@router.delete("/admin/imports/{import_id}", status_code=204)
def supprimer_ligne_import_tc(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """🔒 Supprimer une ligne erronée — le badge éventuel reste au parc."""
    _supprimer_import(TelecommandeImport, import_id, session)
