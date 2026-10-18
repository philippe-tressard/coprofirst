"""Les textes légaux sont-ils RELUS par cette copropriété ? Le constat, mesuré (#2065).

Une copropriété neuve reçoit le gabarit du produit. Ses champs se remplissent de
son identité, mais le texte reste celui d'un logiciel : il n'engage le syndicat
que relu par lui. Le constat le dit à l'administrateur, et il se MESURE au lieu
de se croire :

- **relu** — l'administrateur a déclaré la relecture de CE texte : son empreinte
  est gardée avec la date et l'auteur du geste. Un texte modifié depuis n'est plus
  relu ; une identité qui change (nouveau syndic) ne défait rien, ses champs la
  suivent d'eux-mêmes ;
- **complet** — aucun champ vide, aucun champ inconnu, aucun « À RENSEIGNER »
  écrit en toutes lettres.

« À relire » = pas relu, ou pas complet. La relecture d'un texte incomplet est
refusée : déclarer relu ce qui dit encore « À RENSEIGNER » ferait mentir le constat.

🔒 `tests/test_textes_legaux_par_copropriete.py`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import NamedTuple

from sqlmodel import Session, select

from app.models.core import ConfigSite, Utilisateur
from app.seed.contenus_legaux import DEFAULT_LEGAL
from app.utils import horloge
from app.utils.config_site import ecrire_cle
from app.utils.textes_legaux.champs import (
    champs_vides,
    inconnus,
    mentions_a_renseigner,
)
from app.utils.textes_legaux.identite import IdentiteLegale, identite_legale


class Titre(NamedTuple):
    nom: str
    #: Le participe accordé au titre : « Mentions légales » est un féminin pluriel.
    relu: str


#: Les deux textes, dans l'ordre de l'écran, leur titre et son accord.
TEXTES = {
    "mentions_legales": Titre("Mentions légales", "relues"),
    "politique_confidentialite": Titre("Politique de confidentialité", "relue"),
}

#: La relecture déclarée, par texte : `{clé: {empreinte, le, par}}`. Écrite par le
#: seul geste de relecture — `PUT /config` la refuse (`routers/config.py`).
CLE_RELECTURE = "textes_legaux_relus"


@dataclass
class EtatTexte:
    cle: str
    titre: str
    #: « relue » ou « relues » — l'accord se déclare avec le titre, jamais ne se devine.
    participe_relu: str
    relu: bool
    relu_le: str | None
    complet: bool
    #: Ce qui manque, en clair : « le nom du syndic — Annuaire › Syndic ».
    manques: list[str] = field(default_factory=list)

    @property
    def a_relire(self) -> bool:
        return not (self.relu and self.complet)


def textes_sources(session: Session) -> dict[str, str]:
    """Le texte SOURCE de chaque page — champs non remplis : celui de la base, sinon le gabarit."""
    lignes = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(TEXTES))).all()
    textes = {cle: DEFAULT_LEGAL[cle] for cle in TEXTES}
    textes.update({r.cle: r.valeur for r in lignes if r.valeur})
    return textes


def empreinte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _relectures(session: Session) -> dict[str, dict]:
    ligne = session.get(ConfigSite, CLE_RELECTURE)
    try:
        lues = json.loads(ligne.valeur) if ligne and ligne.valeur else {}
    except ValueError:
        return {}
    return lues if isinstance(lues, dict) else {}


def _manques(texte: str, identite: IdentiteLegale) -> list[str]:
    manques = [f"{c.libelle} — {c.ou}" for c in champs_vides(texte, identite)]
    manques += [f"champ inconnu [[{n}]] — à corriger dans le texte" for n in inconnus(texte)]
    restants = mentions_a_renseigner(texte)
    if restants:
        manques.append(f"{restants} mention(s) « À RENSEIGNER » à rédiger dans le texte")
    return manques


def etat(session: Session) -> list[EtatTexte]:
    """Le constat, texte par texte."""
    identite = identite_legale(session)
    relectures = _relectures(session)
    rendus = []
    for cle, texte in textes_sources(session).items():
        relecture = relectures.get(cle) or {}
        manques = _manques(texte, identite)
        rendus.append(
            EtatTexte(
                cle=cle,
                titre=TEXTES[cle].nom,
                participe_relu=TEXTES[cle].relu,
                relu=relecture.get("empreinte") == empreinte(texte),
                relu_le=relecture.get("le"),
                complet=not manques,
                manques=manques,
            )
        )
    return rendus


def a_relire(session: Session) -> bool:
    return any(e.a_relire for e in etat(session))


def en_dict(etats: list[EtatTexte]) -> dict:
    """La réponse de l'API : le constat global, puis chaque texte."""
    return {
        "a_relire": any(e.a_relire for e in etats),
        "textes": [asdict(e) | {"a_relire": e.a_relire} for e in etats],
    }


class TexteIncomplet(ValueError):
    """La relecture d'un texte qui dit encore « À RENSEIGNER » est refusée."""


def declarer_relus(session: Session, user: Utilisateur) -> list[EtatTexte]:
    """Le geste « J'ai relu ces textes » : l'empreinte de chaque texte, datée et signée."""
    etats = etat(session)
    incomplets = [e for e in etats if not e.complet]
    if incomplets:
        raise TexteIncomplet(
            "Renseignez d'abord : "
            + " ; ".join(f"{e.titre} — {', '.join(e.manques)}" for e in incomplets)
        )
    le = horloge.maintenant().isoformat(timespec="seconds")
    relectures = {
        cle: {"empreinte": empreinte(texte), "le": le, "par": user.id}
        for cle, texte in textes_sources(session).items()
    }
    ecrire_cle(session, CLE_RELECTURE, json.dumps(relectures))
    session.commit()
    return etat(session)
