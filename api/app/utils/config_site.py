"""Lire la configuration du site — les clés que tout le produit demande.

## 🔴 Pourquoi ce module (18/09/2026, #779)

`config_site` et `contexte_site` vivaient dans `routers/tickets/commun.py`,
c'est-à-dire **chez un appelant**, et dans le module d'un domaine qui n'a rien à
voir avec la configuration. Les prenaient : le démarrage de l'application, le
manuel en PDF, les courriels de ticket, les messages — et l'annonce de hall,
qui **ne les prenait pas** et avait sa propre lecture.

C'est le motif de `standards/02` §4 sexies, écrit le matin même : une règle
rangée chez un appelant oblige le suivant à un détour ou à une copie. Ici les
deux : `main.py` l'importait au milieu d'une fonction — un import différé pour
éviter le cycle — et `annonces_hall.py` avait recopié la requête.

⚠️ La copie avait **déjà dérivé**, sur ce qui ne se voit pas : elle rendait `""`
là où l'originale rend `None`. Sans conséquence ici, les deux valeurs passant
ensuite par `nom_site()` et `base_site()` qui traitent l'absence — mais c'est
par ce genre d'écart qu'une copie devient un jour un comportement différent.

## Ce que ces deux fonctions ne font pas

Elles ne décident de rien : elles lisent. Le repli sur un nom ou une URL absente
appartient à `utils/liens` (`nom_site`, `base_site`), et c'est voulu — une
lecture qui invente sa valeur par défaut la rend invisible à qui veut savoir si
la clé est posée.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.core import ConfigSite
from app.utils.liens import adresse_du_site, nom_site
from app.utils.palettes import CLE_PALETTE


def config_site(session: Session, *cles: str) -> dict:
    """Valeurs de `ConfigSite`, avec `site_nom` et la palette toujours inclus —
    l'adresse du site, elle, ne se lit plus en base : `liens.adresse_du_site()` (#2058).

    Ces deux clés alimentent le pied de chaque e-mail : les demander partout
    évitait déjà de les oublier, mais au prix de quatre requêtes écrites à la
    main. Une seule écriture ici. La palette (#2379) colore les mêmes supports —
    courriels et affiches — que le nom signe.
    """
    voulues = {"site_nom", CLE_PALETTE} | set(cles)
    lignes = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(voulues))).all()
    return {r.cle: r.valeur for r in lignes}


def ecrire_cle(session: Session, cle: str, valeur: str) -> ConfigSite:
    """Pose la valeur d'une clé, créée si elle manque — sans valider la transaction.

    `session.get` puis « sinon une ligne neuve » s'écrivait chez chaque écran
    qui enregistre un réglage (logo, consignes de l'arrivant, règlement).
    """
    ligne = session.get(ConfigSite, cle) or ConfigSite(cle=cle, valeur="")
    ligne.valeur = valeur
    session.add(ligne)
    return ligne


def contexte_site(cfg: dict) -> dict:
    """Le bloc `residence` / `app` que tous les modèles d'e-mail attendent."""
    return {
        "residence": {"nom": nom_site(cfg.get("site_nom"))},
        "app": {"url": adresse_du_site()},
    }


__all__ = ["config_site", "contexte_site", "ecrire_cle"]
