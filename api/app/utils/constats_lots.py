"""Les constats du patrimoine des lots — Admin › Copropriété › Lots (#2216).

Ce qu'aucun écran ne montrait : un lot sans propriétaire, une place sans
circulation, une clé de charges dont la somme ne tombe pas juste, un bâtiment sans
la lettre de l'acte, un lot que le dernier état descriptif ne connaît pas, un
total de lots qui n'est pas celui de la fiche.

La décision est PURE (`constater`, sur un `Releve`) ; la lecture en base est à
part (`relever`). Un patrimoine vide ne se contrôle pas : il rend INCONNU, jamais
« aucun constat » (`standards/04` §2).

🔴 Aucune donnée personnelle dans un constat : il cite des NUMÉROS de lots, et
compte les comptes — il ne les nomme pas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, func, select

from app.utils.constats import AVERTISSEMENT, INCONNU, INFORMATION, Constat, constat
from app.utils.designation_lot import est_annexe


@dataclass
class Releve:
    """Ce que la base dit du patrimoine, réduit à ce que les constats lisent."""

    #: `(numéro, est une annexe, a une circulation)` pour chaque lot.
    lots: list[tuple[str, bool, bool]]
    lots_avec_proprietaire: set[str] = field(default_factory=set)
    comptes_proprietaires_sans_lot: int = 0
    #: `(libellé, dénominateur, somme des numérateurs)` pour chaque clé.
    cles: list[tuple[str, int, int]] = field(default_factory=list)
    batiments_sans_lettre: list[str] = field(default_factory=list)
    #: Les numéros du dernier état descriptif APPLIQUÉ ; `None` s'il n'y en a pas.
    etat_descriptif: Optional[set[str]] = None
    nb_lots_fiche: Optional[int] = None


def constater(r: Releve) -> list[Constat]:
    """Les constats d'un relevé — fonction PURE."""
    if not r.lots:
        return [constat("aucun_lot", INCONNU, "Aucun lot en base : rien ne peut se contrôler.")]
    numeros = [numero for numero, _, _ in r.lots]
    trouves: list[Constat] = []

    def _si(code, gravite, message, lots=()):
        if lots:
            trouves.append(constat(code, gravite, message, sorted(lots)))

    _si(
        "sans_proprietaire",
        AVERTISSEMENT,
        "Lot sans propriétaire actif : personne n'y est rattaché comme copropriétaire.",
        [n for n in numeros if n not in r.lots_avec_proprietaire],
    )
    if n := r.comptes_proprietaires_sans_lot:
        #  Accordé, jamais « compte(s) » : une parenthèse se relit deux fois (#2252).
        qui = "1 compte copropriétaire n'a" if n == 1 else f"{n} comptes copropriétaires n'ont"
        trouves.append(
            constat(
                "proprietaire_sans_lot",
                AVERTISSEMENT,
                f"{qui} aucun lot actif (Admin › Personnes › Utilisateurs).",
            )
        )
    #  Sans état descriptif appliqué, une annexe sans circulation n'a simplement pas
    #  été désignée ; après, c'est un accès direct déclaré — à savoir, pas à corriger.
    _si(
        "annexe_sans_circulation",
        AVERTISSEMENT if r.etat_descriptif is None else INFORMATION,
        "Cave ou place sans circulation : accès direct, ou état descriptif non importé.",
        [n for n, annexe, circulation in r.lots if annexe and not circulation],
    )
    for libelle, denominateur, somme in r.cles:
        if somme != denominateur:
            trouves.append(
                constat(
                    "somme_cle",
                    AVERTISSEMENT,
                    f"« {libelle} » : les tantièmes en base font {somme} pour un "
                    f"dénominateur de {denominateur}.",
                )
            )
    if r.batiments_sans_lettre:
        trouves.append(
            constat(
                "batiment_sans_lettre",
                INFORMATION,
                "Bâtiment sans la lettre de l'acte : " + ", ".join(r.batiments_sans_lettre) + ".",
            )
        )
    if r.etat_descriptif is not None:
        _si(
            "hors_etat_descriptif",
            INFORMATION,
            "Lot absent du dernier état descriptif appliqué.",
            [n for n in numeros if n not in r.etat_descriptif],
        )
    if r.nb_lots_fiche and r.nb_lots_fiche != len(numeros):
        trouves.append(
            constat(
                "total_fiche",
                INFORMATION,
                f"{len(numeros)} lot(s) en base, {r.nb_lots_fiche} sur la fiche de la "
                "copropriété (Admin › Copropriété › Identité).",
            )
        )
    return trouves


def relever(session: Session) -> Releve:
    """Le relevé du patrimoine — quelques requêtes groupées, jamais une par lot."""
    from app.models.charges import CleDeCharges, QuotePartLot
    from app.models.copropriete import Batiment, Copropriete, Lot
    from app.models.core import TypeLien, UserLot, Utilisateur
    from app.models.etat_descriptif import ImportEtatDescriptif, LigneEtatDescriptif
    from app.models.roles import RoleUtilisateur
    from app.utils.batiments import libelle_batiment
    from app.utils.etat_descriptif import numero_de_lot

    lots = session.exec(select(Lot)).all()
    proprietaires = {TypeLien.propriétaire, TypeLien.bailleur}
    liens = session.exec(
        select(UserLot.lot_id, UserLot.user_id, UserLot.type_lien).where(
            UserLot.actif == True  # noqa: E712
        )
    ).all()
    lots_detenus = {lot_id for lot_id, _, lien in liens if lien in proprietaires}
    comptes_avec_lot = {user_id for _, user_id, _ in liens}
    comptes_proprietaires = [
        u.id
        for u in session.exec(select(Utilisateur)).all()
        if u.has_role(RoleUtilisateur.propriétaire)
    ]
    sommes = dict(
        session.exec(
            select(QuotePartLot.cle_id, func.sum(QuotePartLot.numerateur)).group_by(
                QuotePartLot.cle_id
            )
        ).all()
    )
    applique = session.exec(
        select(ImportEtatDescriptif)
        .where(ImportEtatDescriptif.applique_le.is_not(None))  # type: ignore[union-attr]
        .order_by(ImportEtatDescriptif.applique_le.desc())  # type: ignore[union-attr]
    ).first()
    copro = session.exec(select(Copropriete)).first()
    return Releve(
        lots=[
            (numero_de_lot(lot.numero), est_annexe(lot), lot.circulation_perimetre_id is not None)
            for lot in lots
        ],
        lots_avec_proprietaire={
            numero_de_lot(lot.numero) for lot in lots if lot.id in lots_detenus
        },
        comptes_proprietaires_sans_lot=sum(
            1 for user_id in comptes_proprietaires if user_id not in comptes_avec_lot
        ),
        cles=[
            (cle.libelle, cle.denominateur, int(sommes.get(cle.id) or 0))
            for cle in session.exec(select(CleDeCharges).order_by(CleDeCharges.ordre)).all()
        ],
        batiments_sans_lettre=[
            libelle_batiment(b)
            for b in session.exec(select(Batiment).order_by(Batiment.id)).all()
            if not (b.lettre_rcp or "").strip()
        ],
        etat_descriptif=(
            set(
                session.exec(
                    select(LigneEtatDescriptif.lot).where(
                        LigneEtatDescriptif.import_id == applique.id
                    )
                ).all()
            )
            if applique
            else None
        ),
        nb_lots_fiche=copro.nb_lots_total if copro else None,
    )
