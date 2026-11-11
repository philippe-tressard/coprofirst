"""La RÈGLE de la pastille de lecture — pure (voir le paquet, `__init__.py`)."""

from __future__ import annotations

import json
from typing import Optional, Union

from app.utils.lecture_pastille.modele import ApercuLecture, Lecture
from app.utils.lecture_pastille.vocabulaire import (
    CONCERNE as VOCABLE_CONCERNE,
    CS,
    PROFILS,
    PROFILS_DU_CODE,
    TOUS_PROFILS,
    minuscule,
    qui_de,
    vocable_de,
)
from app.utils.nature_affaire import ACTUALITE
from app.utils.valeurs import valeur
from app.utils.visibility.defauts_affaire import (
    CODES_COPROPRIETAIRES,
    CONCERNE,
    defauts_de_nature,
)

TOUS_LES_RESIDENTS = "résidents"

AVERTISSEMENT_PERIMETRE = "Le périmètre est choisi mais pas réservé : toute la copropriété la lira."


def codes_destinataires(brut: Union[list[str], str, None]) -> list[str]:
    """Les codes d'un public cible, en liste ou en chaîne JSON (ancien CSV toléré)."""
    if isinstance(brut, list):
        return [str(c) for c in brut]
    if not isinstance(brut, str) or not brut.strip():
        return []
    try:
        lus = json.loads(brut)
        return [str(c) for c in lus] if isinstance(lus, list) else []
    except ValueError:
        return [c.strip() for c in brut.split(",") if c.strip()]


def _concerne_tous_les_residents(codes: list[str]) -> bool:
    return not codes or codes == [TOUS_LES_RESIDENTS]


def lecture_de(
    *,
    actualite: bool,
    confidentiel: bool,
    public_cible: Union[list[str], str, None],
    perimetre_restreint: bool,
    reserve_perimetre: bool,
    categorie: Optional[str] = None,
    statut: Optional[str] = None,
    masculin: bool = False,
) -> Lecture:
    """Qui lit, d'après ce que l'objet dit de ses lecteurs. PURE."""
    #  Une affaire lit ses Destinataires quand le conseil en a CHOISI (#1343) ;
    #  vides, ceux de sa nature — comme `ticket_visible`.
    explicites = codes_destinataires(public_cible)
    codes = (
        explicites if actualite or explicites else defauts_de_nature(actualite, categorie, statut)
    )
    cs_seul = confidentiel or codes == ["conseil_syndical"]
    profils: list[str] = []
    if not cs_seul:
        if _concerne_tous_les_residents(codes):
            profils = list(TOUS_PROFILS)
        else:
            vises = {p for c in codes for p in PROFILS_DU_CODE.get(c, [])}
            profils = [p for p in TOUS_PROFILS if p in vises]
    #  Qui lit HORS du périmètre : une actualité, sauf réserve ; une affaire au
    #  défaut, ses copropriétaires sauf réserve (`lus_dans_toute_la_residence`) ;
    #  un choix, personne.
    au_defaut = not actualite and not explicites
    if not perimetre_restreint:
        partout = profils
    elif actualite:
        partout = [] if reserve_perimetre else profils
    elif au_defaut and not reserve_perimetre:
        partout = [
            p
            for p in profils
            if any(c in CODES_COPROPRIETAIRES and p in PROFILS_DU_CODE.get(c, []) for c in codes)
        ]
    else:
        partout = []
    perimetre_reserve = bool(profils) and perimetre_restreint and not partout
    seuls = [p for p in profils if p not in partout] if partout else []
    concerne = not actualite and (confidentiel or codes == [CONCERNE])
    v = vocable_de(profils) if profils else (VOCABLE_CONCERNE if concerne else CS)
    tous = v.cle == "tous"

    pas: list[str] = []
    lue = "Lu" if masculin else "Lue"
    if concerne:
        phrase = (
            "Lue par la personne concernée — son auteur, ou celle pour qui elle a été "
            "saisie — et par le conseil syndical, personne d’autre."
        )
    elif not profils:
        phrase = (
            f"Personne d’autre que le conseil syndical ne {'le' if masculin else 'la'} lit, "
            "à part son auteur."
        )
    else:
        ou = ", dans le périmètre seulement." if perimetre_reserve else "."
        if seuls:
            phrase = (
                f"{lue} par {qui_de(partout)} dans toute la copropriété, "
                f"et par {qui_de(seuls)} du périmètre seulement."
            )
        elif tous:
            phrase = f"{lue} par tous{ou}"
        else:
            phrase = (
                f"{lue} par {qui_de(profils)}"
                f"{ou if perimetre_reserve else ', dans toute la copropriété.'}"
            )
        pas += ["les " + minuscule(p.long) for p in PROFILS if p.code not in profils]
        if perimetre_reserve:
            pas.append("les personnes hors du périmètre")
        if seuls:
            pas.append(f"{qui_de(seuls)} hors du périmètre")

    du_perimetre = minuscule(vocable_de(seuls).court) if seuls else ""
    if perimetre_reserve:
        titre = v.long + " · du périmètre seulement"
    else:
        titre = v.long + (f" · {du_perimetre} du périmètre seulement" if du_perimetre else "")
    return Lecture(
        cle=v.cle,
        icones=list(v.icones),
        court=v.court,
        long=v.long,
        titre=titre,
        profils=profils,
        perimetre_reserve=perimetre_reserve,
        hors_perimetre=list(partout),
        du_perimetre=du_perimetre,
        phrase=phrase,
        exclus=f"Pas {', ni '.join(pas)}." if pas else "",
        par_defaut=tous and not perimetre_reserve,
        avertissement=(
            AVERTISSEMENT_PERIMETRE
            if actualite and profils and perimetre_restreint and not reserve_perimetre
            else ""
        ),
    )


def lecture_ciblee(
    *, public_cible: Union[list[str], str, None], perimetre_restreint: bool, masculin: bool = False
) -> Lecture:
    """Qui lit un objet CIBLÉ — annonce, idée, sondage (#1373) : `cible_visible`
    restreint TOUJOURS au périmètre, et des Destinataires vides valent « Tous » —
    la mécanique d'une actualité réservée à son périmètre, réemployée."""
    return lecture_de(
        actualite=True,
        confidentiel=False,
        public_cible=public_cible,
        perimetre_restreint=perimetre_restreint,
        reserve_perimetre=True,
        masculin=masculin,
    )


__all__ = ["apercu_de", "codes_destinataires", "lecture_ciblee", "lecture_de"]


def apercu_de(
    *,
    categorie: Optional[str],
    statut: Optional[str],
    confidentiel: bool,
    public_cible: Union[list[str], str, None],
    perimetre_restreint: bool,
    reserve_perimetre: bool,
) -> ApercuLecture:
    """L'aperçu d'une saisie (`POST /lectures/apercu`) : sa pastille, ses
    Destinataires par défaut, et « lue du seul conseil » — périmètre mis à part.
    PURE : le périmètre arrive tranché."""
    actualite = valeur(categorie) == ACTUALITE
    nature = dict(
        actualite=actualite,
        confidentiel=confidentiel,
        public_cible=public_cible,
        categorie=valeur(categorie),
        statut=valeur(statut),
    )
    sans_perimetre = lecture_de(**nature, perimetre_restreint=False, reserve_perimetre=False)
    return ApercuLecture(
        lecture=lecture_de(
            **nature, perimetre_restreint=perimetre_restreint, reserve_perimetre=reserve_perimetre
        ),
        destinataires_par_defaut=[] if actualite else defauts_de_nature(False, categorie, statut),
        lue_du_seul_conseil=not sans_perimetre.profils,
    )
