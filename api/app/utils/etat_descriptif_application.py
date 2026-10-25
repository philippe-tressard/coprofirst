"""L'état descriptif, de la table de passage au patrimoine (#2213).

Les règles de lecture et de contrôle sont PURES et vivent dans `utils/etat_descriptif` ;
ce module-ci les branche sur la base : poser un fichier dans la table de passage,
confronter ses lignes à l'application, puis — tous contrôles passés — écrire la
désignation de chaque lot, ses tantièmes, et re-dériver ses périmètres.

## Les règles de résolution (spec `lots-et-perimetres.md` §8)

- une **place** ou une **cave** est située dans le bâtiment que le fichier nomme (ou
  dans aucun) et desservie par la circulation qu'il nomme — **plus jamais** par le
  bâtiment de son propriétaire, comme le faisait la liste du syndic ;
- une circulation vide ou « / » : accès direct ;
- un **logement** garde son bâtiment (un écart est un constat bloquant, jamais une
  correction silencieuse), et sa circulation est son bâtiment ;
- un double emplacement reste **un** lot ;
- rejouer le même fichier ne crée rien en double : il met à jour les numérateurs et
  dit ce qui a changé.
"""

from __future__ import annotations

import json
from sqlmodel import Session, delete, select

from app.models.charges import CleDeCharges, QuotePartLot
from app.models.copropriete import Batiment, Lot, NatureLot
from app.models.etat_descriptif import ImportEtatDescriptif, LigneEtatDescriptif
from app.utils import horloge
from app.utils.constats import applicable
from app.utils.designation_lot import nature_du_lot
from app.utils.etat_descriptif import (
    Cle,
    Lecture,
    Ligne,
    LotConnu,
    controler,
    lettre_de,
    lire,
    nature_de,
    niveau_de,
    numero_de_lot,
)
from app.utils.import_xlsx import normaliser
from app.utils.lecture import lire_objet
from app.utils.perimetres import perimetre_du_batiment
from app.utils.perimetres.lots import rederiver


class EtatDescriptifRefuse(Exception):
    """L'application est refusée : un contrôle bloque, ou rien n'est en attente."""


def en_attente(session: Session) -> ImportEtatDescriptif | None:
    """Le dernier fichier téléversé — appliqué ou non."""
    return session.exec(
        select(ImportEtatDescriptif).order_by(ImportEtatDescriptif.id.desc())
    ).first()


def poser(session: Session, rows: list) -> ImportEtatDescriptif:
    """Remplace le fichier en attente par celui-ci (le dernier appliqué reste en trace)."""
    lecture = lire(rows)
    for ancien in session.exec(
        select(ImportEtatDescriptif).where(ImportEtatDescriptif.applique_le.is_(None))  # type: ignore[union-attr]
    ).all():
        session.exec(delete(LigneEtatDescriptif).where(LigneEtatDescriptif.import_id == ancien.id))
        session.delete(ancien)
    imp = ImportEtatDescriptif(
        entete_json=json.dumps(
            {
                "cles": [c.model_dump() for c in lecture.cles],
                "avec_circulation": lecture.avec_circulation,
                "erreurs": lecture.erreurs,
            },
            ensure_ascii=False,
        )
    )
    session.add(imp)
    session.flush()
    for ligne in lecture.lignes:
        session.add(
            LigneEtatDescriptif(
                import_id=imp.id,
                quotes_json=json.dumps(ligne.quotes),
                **ligne.model_dump(exclude={"quotes"}),
            )
        )
    session.flush()
    return imp


def relire(session: Session, imp: ImportEtatDescriptif) -> Lecture:
    """La lecture telle que la table de passage la garde."""
    entete = json.loads(imp.entete_json or "{}")
    lignes = session.exec(
        select(LigneEtatDescriptif)
        .where(LigneEtatDescriptif.import_id == imp.id)
        .order_by(LigneEtatDescriptif.rang)
    ).all()
    return Lecture(
        cles=[Cle(**c) for c in entete.get("cles", [])],
        lignes=[lire_objet(Ligne, lu, quotes=json.loads(lu.quotes_json or "{}")) for lu in lignes],
        avec_circulation=bool(entete.get("avec_circulation", True)),
        erreurs=list(entete.get("erreurs", [])),
    )


def lettres_connues(session: Session) -> dict[str, int]:
    """Lettre RCP normalisée → `batiment.id`, pour les bâtiments qui en ont une."""
    return {
        normaliser(b.lettre_rcp): b.id
        for b in session.exec(select(Batiment)).all()
        if b.lettre_rcp and normaliser(b.lettre_rcp)
    }


def _contexte(session: Session):
    lots = session.exec(select(Lot)).all()
    lettres = lettres_connues(session)
    avec_noeud = {b.id for b in session.exec(select(Batiment)).all() if perimetre_du_batiment(b.id)}
    connus = [LotConnu(numero_de_lot(lu.numero), lu.batiment_id, nature_du_lot(lu)) for lu in lots]
    return lots, lettres, avec_noeud, connus


def constats(session: Session, imp: ImportEtatDescriptif):
    lecture = relire(session, imp)
    _, lettres, avec_noeud, connus = _contexte(session)
    return lecture, controler(lecture, connus, lettres, avec_noeud)


def appliquer(session: Session) -> dict:
    """Écrit l'état descriptif en attente dans le patrimoine ; lève s'il est bloqué.

    L'appelant valide la transaction : tout ou rien.
    """
    imp = en_attente(session)
    if imp is None or imp.applique_le is not None:
        raise EtatDescriptifRefuse("Aucun état descriptif en attente.")
    lecture = relire(session, imp)
    lots, lettres, avec_noeud, connus = _contexte(session)
    if not applicable(controler(lecture, connus, lettres, avec_noeud)):
        raise EtatDescriptifRefuse("Un contrôle bloque l'application.")

    cles: dict[str, CleDeCharges] = {c.code: c for c in session.exec(select(CleDeCharges)).all()}
    cles_creees = 0
    for rang, cle in enumerate(lecture.cles):
        existante = cles.get(cle.code)
        if existante is None:
            existante = CleDeCharges(
                code=cle.code, libelle=cle.libelle, denominateur=cle.denominateur, ordre=rang
            )
            cles_creees += 1
        else:
            existante.libelle, existante.denominateur, existante.ordre = (
                cle.libelle,
                cle.denominateur,
                rang,
            )
        session.add(existante)
        cles[cle.code] = existante
    session.flush()

    par_numero = {numero_de_lot(lu.numero): lu for lu in lots}
    ids_des_cles = [cles[c.code].id for c in lecture.cles]
    parts = {
        (p.lot_id, p.cle_id): p
        for p in session.exec(
            select(QuotePartLot).where(QuotePartLot.cle_id.in_(ids_des_cles))  # type: ignore[union-attr]
        ).all()
    }
    touches: list[Lot] = []
    quotes_modifiees = 0
    for ligne in lecture.lignes:
        lot = par_numero.get(ligne.lot)
        if lot is None:
            continue  # lot d'origine divisé : il reste en historique
        nature = nature_de(ligne.nature)
        lot.nature = nature
        lot.numero_usage = ligne.numero_usage
        niveau = niveau_de(ligne.niveau)
        if niveau is not None:
            lot.etage = niveau
        lettre_bat = lettre_de(ligne.batiment)
        if nature in (NatureLot.cave, NatureLot.parking):
            lot.batiment_id = lettres.get(lettre_bat) if lettre_bat else None
            if lecture.avec_circulation:
                lettre_circ = lettre_de(ligne.circulation)
                noeud = perimetre_du_batiment(lettres.get(lettre_circ)) if lettre_circ else None
                lot.circulation_perimetre_id = noeud.id if noeud else None
        else:
            noeud = perimetre_du_batiment(lot.batiment_id)
            lot.circulation_perimetre_id = noeud.id if noeud else None
        session.add(lot)
        touches.append(lot)
        for cle in lecture.cles:
            cle_id = cles[cle.code].id
            voulu = ligne.quotes.get(cle.code)
            existante = parts.get((lot.id, cle_id))
            #  Vide ou zéro : le lot ne contribue pas à cette clé, il n'a pas de part.
            if not voulu:
                if existante is not None:
                    session.delete(existante)
                    quotes_modifiees += 1
            elif existante is None:
                session.add(QuotePartLot(lot_id=lot.id, cle_id=cle_id, numerateur=voulu))
                quotes_modifiees += 1
            elif existante.numerateur != voulu:
                existante.numerateur = voulu
                session.add(existante)
                quotes_modifiees += 1
    session.flush()
    perimetres = rederiver(session, touches)
    imp.applique_le = horloge.maintenant()
    session.add(imp)
    return {
        "lots": len(touches),
        "cles_creees": cles_creees,
        "quotes_modifiees": quotes_modifiees,
        "perimetres_modifies": perimetres,
    }
