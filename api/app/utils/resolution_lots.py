"""Transformer un `LotImport` rapproché en `Lot` + `UserLot` — écrit UNE fois.

## Le défaut (#829, 08/09/2026)

Ce geste était écrit **deux fois**, et les deux chemins sont atteignables depuis
l'interface :

============================  ===============================================
Admin › Imports, auto-match   ``routers/lots.py::_auto_resoudre_…_batch``
Validation d'un compte        ``auto_match_service::_auto_resoudre_…_utilisateur``
============================  ===============================================

Le bloc « trouver ou créer le lot » y était identique au caractère près. **Trois
règles, non** — et le résultat dépendait donc du bouton employé, sans que rien à
l'écran ne le dise :

1. **le locataire.** L'un sautait tout import dont un occupant était locataire ;
   l'autre le traitait, en n'excluant que le LIEN locataire. Arbitrage du
   08/09/2026 : **traiter**. Le second portait quatre lignes de commentaire
   expliquant que le blocage était devenu redondant — le premier n'avait jamais
   reçu la décision.

2. 🔴 **le garde-fou anti-pollution.** Le second revalide le nom du compte contre
   la ligne du classeur avant de poser un `UserLot`, et **supprime** un lien qui
   ne correspond plus. Le premier créait le lien à l'aveugle, depuis
   `utilisateurs_json`. Or un `UserLot` donne accès au lot, à ses badges et à ses
   documents : c'est une décision d'autorisation, et une seule des deux voies la
   vérifiait. C'est aussi ce que l'onglet **Audit des lots** existe pour nettoyer
   *après coup*.

3. **le comptage.** `skipped_no_lot` était déclaré et jamais incrémenté — un
   chiffre toujours nul, que l'écran affichait comme un constat.

⚠️ Ce module vit à part de `auto_match_service` : rapprocher des NOMS et résoudre
un IMPORT sont deux responsabilités, et la seconde faisait déjà dépasser le
premier de son plafond de modularité (884 lignes).
"""

from __future__ import annotations

import json
from app.utils import horloge

from sqlmodel import Session, select

from app.utils.import_xlsx import etage_de_lot, type_de_lot

#: Les liens qui donnent droit à une résolution automatique.
#:
#: Un `locataire` est exclu du LIEN, pas de l'import : le lot est créé, ses
#: copropriétaires liés, et le rattachement du locataire reste au workflow de
#: bail. C'est l'arbitrage du 08/09/2026 (#829).
TYPES_COPROPRIETAIRES = {"propriétaire", "bailleur", "mandataire"}


def _lien(valeur: str):
    """Le `TypeLien` d'une chaîne — `propriétaire` si elle est inconnue.

    ⚠️ Le repli est volontaire : une valeur inattendue dans `utilisateurs_json`
    ne doit pas interrompre la résolution de tout un classeur.
    """
    from app.models.core import TypeLien

    try:
        return TypeLien(valeur)
    except ValueError:
        return TypeLien.propriétaire


def _occupants(imp) -> list[dict]:
    """Les occupants d'une ligne d'import, ou `[]` si le JSON est illisible."""
    try:
        valeur = json.loads(imp.utilisateurs_json or "[]")
    except (ValueError, TypeError):
        return []
    return valeur if isinstance(valeur, list) else []


def _lot_de_import(session: Session, imp):
    """Le `Lot` de cette ligne d'import — trouvé, ou créé s'il n'existe pas.

    ⚠️ Un parking n'a pas de bâtiment : la recherche se fait alors parmi les lots
    dont `batiment_id` est nul, et non par une égalité SQL avec `None`, qui ne
    correspondrait à rien.
    """
    from app.models.core import Lot

    lot = session.get(Lot, imp.lot_id) if imp.lot_id else None
    if not lot:
        if imp.batiment_id:
            lot = session.exec(
                select(Lot).where(Lot.batiment_id == imp.batiment_id, Lot.numero == imp.numero)
            ).first()
        else:
            lot = session.exec(
                select(Lot).where(Lot.batiment_id.is_(None), Lot.numero == imp.numero)  # type: ignore
            ).first()
    if not lot:
        type_lot, type_appartement = type_de_lot(imp.type_raw)
        lot = Lot(
            batiment_id=imp.batiment_id,  # None pour un parking
            numero=imp.numero,
            type=type_lot,
            type_appartement=type_appartement,
            etage=etage_de_lot(imp.etage_raw),
        )
        session.add(lot)
        session.flush()
    return lot


def _poser_liens(session: Session, imp, lot, occupants: list[dict]) -> None:
    """Crée les `UserLot` des occupants copropriétaires — et RETIRE les faux.

    🔴 Le garde-fou anti-pollution, que l'une des deux voies n'avait pas.
    `utilisateurs_json` est écrit par le rapprochement automatique ; une entrée
    devenue fausse — nom corrigé dans le classeur, homonyme écarté — y reste.
    Sans revalidation, elle produit un `UserLot`, c'est-à-dire l'accès d'une
    personne au lot d'une autre, à ses badges et à ses documents.

    Le nom du compte est donc confronté à la ligne du classeur, et un lien qui ne
    correspond plus est **supprimé**, pas seulement ignoré.
    """
    from app.models.core import UserLot, Utilisateur
    from app.utils.rapprochement_noms import _matches_user, _split_name_candidates, _user_keys

    noms_du_classeur = _split_name_candidates(imp.nom_coproprietaire or "")
    for occupant in occupants:
        uid = occupant.get("user_id")
        type_lien = occupant.get("type_lien", "propriétaire")
        if not uid or type_lien not in TYPES_COPROPRIETAIRES:
            continue
        existant = session.exec(
            select(UserLot).where(UserLot.user_id == uid, UserLot.lot_id == lot.id)
        ).first()
        compte = session.get(Utilisateur, uid)
        if not compte:
            continue
        if noms_du_classeur:
            cles = _user_keys(compte.nom, compte.prenom)
            if not any(_matches_user(nom, cles) for nom in noms_du_classeur):
                if existant:
                    session.delete(existant)
                continue
        if not existant:
            session.add(UserLot(user_id=uid, lot_id=lot.id, type_lien=_lien(type_lien), actif=True))


def resoudre_imports(session: Session, *, pour_user=None) -> dict:
    """Résout les imports rapprochés. Rend le compte de ce qui s'est passé.

    `pour_user` restreint aux imports où **ce compte** figure comme
    copropriétaire — c'est le chemin de la validation d'un compte. Sans lui, tous
    les imports résolvables sont traités : c'est le bouton « Auto-résoudre » de
    l'administration.

    ⚠️ **Ne committe pas.** L'appelant décide de la portée de sa transaction : la
    validation d'un compte enchaîne d'autres écritures dans la même.
    """
    from app.models.core import LotImport, StatutLotImport

    imports = session.exec(
        select(LotImport).where(
            LotImport.statut.in_([StatutLotImport.utilisateur_lie, StatutLotImport.lot_lie])
        )
    ).all()

    stats: dict = {"resolus": 0, "sans_occupant": 0, "hors_perimetre": 0, "erreurs": []}
    for imp in imports:
        occupants = _occupants(imp)
        if not occupants:
            stats["sans_occupant"] += 1
            continue
        if pour_user is not None and not any(
            o.get("user_id") == pour_user.id
            and o.get("type_lien", "propriétaire") in TYPES_COPROPRIETAIRES
            for o in occupants
        ):
            stats["hors_perimetre"] += 1
            continue
        try:
            lot = _lot_de_import(session, imp)
            _poser_liens(session, imp, lot, occupants)
        except Exception as exc:  # noqa: BLE001
            #  Une ligne fautive est rapportée, les autres passent : un import
            #  qui s'arrête à la première erreur oblige à recommencer autant de
            #  fois qu'il y a de fautes de frappe dans le classeur.
            stats["erreurs"].append(f"lot {imp.numero} : {exc}")
            continue
        imp.lot_id = lot.id
        imp.statut = StatutLotImport.resolu
        imp.resolu_le = horloge.maintenant()
        session.add(imp)
        stats["resolus"] += 1
    return stats


def resoudre_pour_utilisateur(user, session: Session) -> int:
    """Le chemin de la validation d'un compte — rend le nombre d'imports résolus."""
    return resoudre_imports(session, pour_user=user)["resolus"]


def rapprocher_imports(session: Session) -> int:
    """Rapproche les imports EN ATTENTE d'un lot et de comptes — rend le compte.

    C'est l'étape qui précède `resoudre_imports` : elle ne crée **rien**, elle
    remplit `lot_id` et `utilisateurs_json`, et fait passer la ligne d'`en_attente`
    à `lot_lie` ou `utilisateur_lie`. La résolution, elle, écrit en base.

    🔴 Ce bloc était écrit **deux fois dans le même fichier** (`routers/lots.py`,
    lignes 205 et 510 avant #829), et les deux copies avaient déjà dérivé :

    * l'une écrivait ``__import__('json').dumps(…)`` — la marque d'une copie
      faite là où l'import manquait ;
    * l'affectation du statut était à **deux** branches dans l'une, à **trois**
      dans l'autre. Le repli `en_attente` est aujourd'hui inatteignable — on
      n'arrive ici qu'après avoir posé un lot ou des occupants — mais la version
      courte cessera d'être équivalente au premier ajout d'une façon de marquer
      `changed`. C'est la version à trois branches qui est retenue : elle dit ce
      qu'elle veut dire.

    ⚠️ Elle ne committe pas, pour la même raison que `resoudre_imports`.
    """
    from app.models.core import Lot, LotImport, StatutLotImport, Utilisateur
    from app.utils.rapprochement_noms import _matches_user, _split_name_candidates, _user_keys

    lots = session.exec(select(Lot)).all()
    comptes = session.exec(select(Utilisateur)).all()
    par_emplacement = {(lot.batiment_id, lot.numero): lot for lot in lots}
    cles_par_compte = {c.id: _user_keys(c.nom, c.prenom) for c in comptes}

    attente = session.exec(
        select(LotImport).where(LotImport.statut == StatutLotImport.en_attente)
    ).all()

    rapproches = 0
    for imp in attente:
        change = False
        if not imp.lot_id:
            lot = par_emplacement.get((imp.batiment_id, imp.numero))
            if lot:
                imp.lot_id = lot.id
                change = True
        #  Les occupants ne sont cherchés que si la ligne n'en porte aucun : un
        #  rapprochement déjà fait — ou corrigé à la main — ne se réécrit pas.
        if not _occupants(imp) and imp.nom_coproprietaire:
            trouves: list[dict] = []
            vus: set[int] = set()
            for nom in _split_name_candidates(imp.nom_coproprietaire):
                for compte in comptes:
                    if compte.id not in vus and _matches_user(nom, cles_par_compte[compte.id]):
                        trouves.append({"user_id": compte.id, "type_lien": "propriétaire"})
                        vus.add(compte.id)
            if trouves:
                imp.utilisateurs_json = json.dumps(trouves, ensure_ascii=False)
                change = True
        if change:
            if imp.lot_id:
                imp.statut = StatutLotImport.lot_lie
            elif _occupants(imp):
                imp.statut = StatutLotImport.utilisateur_lie
            else:
                imp.statut = StatutLotImport.en_attente
            session.add(imp)
            rapproches += 1
    return rapproches


__all__ = [
    "TYPES_COPROPRIETAIRES",
    "rapprocher_imports",
    "resoudre_imports",
    "resoudre_pour_utilisateur",
]
