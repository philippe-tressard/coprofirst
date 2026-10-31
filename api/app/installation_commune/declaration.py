"""Le registre des copropriétés d'une installation COMMUNE — un fichier déclaratif (#1894).

Spec §4.2 : *la liste des copropriétés et de quoi résoudre leur contexte
(identifiant, hôtes, état actif ou suspendu, références vers les secrets), et
l'alias de chaque copropriété — code postal et nom normalisés, unique, anciens
alias conservés*. Arbitré le 17/10/2026 : un FICHIER JSON de l'installation
(`COPROPRIETES_FICHIER`), monté en lecture seule — ni table ni écran avant que
l'hébergeur de la phase 3 soit choisi.

```json
{"coproprietes": [{
  "identifiant": "tilleuls",
  "code_postal": "75015", "nom": "Les Tilleuls",
  "anciens_alias": ["75015-tilleuls"],
  "hotes": ["residence-tilleuls.fr"],
  "suspendue": false,
  "base": "TILLEULS_DATABASE_URL", "secret": "TILLEULS_SECRET_KEY",
  "racine_fichiers": "/app/uploads/tilleuls",
  "expediteur": "contact@residence-tilleuls.fr", "nom_expediteur": "Les Tilleuls",
  "operateurs": ["exploitation@hebergeur.example"]
}]}
```

- **Les secrets n'y sont jamais écrits** : `base` et `secret` NOMMENT les variables
  d'environnement qui les portent (le coffre de l'hébergeur, §4.2).
- **`operateurs`** : les adresses des comptes de CETTE copropriété qui sont
  opérateurs de l'instance — l'exploitant les désigne, jamais un administrateur
  de copropriété (`auth/operateur`, spec §4.7). Facultatif : sans lui, personne
  ne supervise l'instance depuis cette copropriété.
- **L'hôte commun est celui de l'`ORIGIN`** — l'URL publique de l'installation
  (arbitrage du 17/10/2026) ; l'adresse dérivée d'une copropriété est
  `<alias>.<hôte commun>`.
- **Tout ou rien** : un fichier déclaré mais illisible, ou qui viole une règle
  (alias en double, nom d'hôte invalide, secret absent…), lève `DeclarationInvalide`
  — l'installation ne sert alors AUCUNE copropriété (503), jamais celle de sa
  configuration par repli : elle servirait la même à tous les hôtes.

Le fichier est relu quand il change (date et taille), sans redémarrage.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.auth.adresse_compte import normaliser_adresse
from app.config import defaut_du_secret, get_settings
from app.contexte import IDENTIFIANT_UNIQUE, Copropriete, nom_d_hote
from app.installation_commune.alias import alias_de, est_alias, est_nom_d_hote

_IDENTIFIANT = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_VARIABLE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


class DeclarationInvalide(ValueError):
    """Le fichier des copropriétés est déclaré, mais ne peut pas servir tel quel."""


class _CoproprieteDeclaree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifiant: str
    code_postal: str
    nom: str = Field(min_length=1, max_length=120)
    anciens_alias: list[str] = []
    hotes: list[str] = []
    suspendue: bool = False
    base: str
    secret: str
    racine_fichiers: str
    expediteur: str
    nom_expediteur: str = ""
    operateurs: list[str] = []


class _Fichier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coproprietes: list[_CoproprieteDeclaree]


@dataclass(frozen=True)
class Entree:
    """Une copropriété de l'installation commune, telle que le contexte la sert."""

    copropriete: Copropriete
    alias: str
    anciens_alias: frozenset[str]
    #: Ses domaines propres, dans l'ordre déclaré — le premier est son ADRESSE.
    hotes_propres: tuple[str, ...]
    suspendue: bool
    #: Le NOM de la variable qui porte l'URL de sa base — jamais sa valeur : la
    #: mise à jour nocturne exporte chaque base par `env:<nom>` (#2053).
    variable_base: str = ""
    #: Les adresses (normalisées) de ses comptes que l'exploitant déclare opérateurs.
    operateurs: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Declaration:
    hote_commun: str
    schema: str
    entrees: tuple[Entree, ...]

    def adresse_derivee(self, entree: Entree) -> str:
        return f"{entree.alias}.{self.hote_commun}"

    def hotes_de(self, entree: Entree) -> frozenset[str]:
        """Les hôtes qui DÉSIGNENT la copropriété : ses domaines et son adresse dérivée.

        Ses anciens alias n'y sont pas : ils redirigent (`routeur`), ils ne servent pas.
        """
        return frozenset(entree.hotes_propres) | {self.adresse_derivee(entree)}

    def adresse(self, entree: Entree) -> str:
        """L'URL où l'on renvoie : son propre domaine s'il en a un, sinon l'adresse dérivée
        — calculée une fois, à la lecture (`Copropriete.adresse`)."""
        return entree.copropriete.adresse

    def destination(self, alias: str) -> Entree | None:
        """La copropriété qu'un alias — actuel ou ancien — désigne, si elle peut être une
        DESTINATION : une copropriété suspendue ne l'est jamais (règle 5)."""
        for e in self.entrees:
            if not e.suspendue and (alias == e.alias or alias in e.anciens_alias):
                return e
        return None


#: La dernière déclaration lue, et la signature du fichier (chemin, date, taille) qui l'a
#: produite. Elle DÉSIGNE les copropriétés, elle ne porte aucune de leurs données
#: (déclarée dans `DU_PROCESSUS`, `test_etat_module_par_copropriete.py`).
_lue: dict[str, tuple[tuple[str, int, int], Declaration]] = {}


def declaration() -> Declaration | None:
    """La déclaration de l'installation commune, ou `None` pour une installation propre
    à une copropriété. Lève `DeclarationInvalide` si le fichier ne peut pas servir."""
    s = get_settings()
    chemin = s.coproprietes_fichier.strip()
    if not chemin:
        return None
    try:
        etat = os.stat(chemin)
    except OSError as e:
        raise DeclarationInvalide(f"Fichier des copropriétés illisible : {chemin}") from e
    signature = (chemin, etat.st_mtime_ns, etat.st_size)
    deja = _lue.get("courante")
    if deja and deja[0] == signature:
        return deja[1]
    lue = lire(Path(chemin).read_text(encoding="utf-8"), s.origin, os.environ)
    _lue["courante"] = (signature, lue)
    return lue


def lire(texte: str, origine: str, environnement) -> Declaration:
    """La déclaration que porte `texte`, validée en entier — fonction pure, testée seule."""
    try:
        fichier = _Fichier.model_validate(json.loads(texte))
    except (ValueError, ValidationError) as e:
        #  Le message de pydantic peut citer une valeur : on ne dit que l'endroit.
        raise DeclarationInvalide("Fichier des copropriétés mal formé (JSON ou champs).") from e
    url = urlsplit(origine)
    hote_commun = nom_d_hote(url.netloc)
    erreurs: list[str] = []
    if not est_nom_d_hote(hote_commun):
        erreurs.append("ORIGIN doit nommer l'hôte commun de l'installation par un nom de domaine.")
    if not fichier.coproprietes:
        erreurs.append("Aucune copropriété déclarée.")
    schema = url.scheme or "https"
    entrees = [
        _entree(c, hote_commun, schema, environnement, erreurs) for c in fichier.coproprietes
    ]
    _uniques(entrees, erreurs)
    if erreurs:
        raise DeclarationInvalide(" ; ".join(erreurs))
    return Declaration(hote_commun, schema, tuple(entrees))


def _entree(
    c: _CoproprieteDeclaree, hote_commun: str, schema: str, env, erreurs: list[str]
) -> Entree:
    qui = c.identifiant
    if not _IDENTIFIANT.fullmatch(qui) or qui == IDENTIFIANT_UNIQUE:
        erreurs.append(f"Identifiant invalide ou réservé : {qui!r}.")
    alias = alias_de(c.code_postal, c.nom) or ""
    if not alias:
        erreurs.append(f"{qui} : code postal et nom ne forment pas un alias valide.")
    elif not est_nom_d_hote(f"{alias}.{hote_commun}"):
        erreurs.append(f"{qui} : l'adresse dérivée dépasse la longueur d'un nom d'hôte.")
    for ancien in c.anciens_alias:
        if not est_alias(ancien):
            erreurs.append(f"{qui} : ancien alias invalide {ancien!r}.")
    hotes = tuple(h.strip().lower() for h in c.hotes)
    for h in hotes:
        if not est_nom_d_hote(h) or h == hote_commun or h.endswith(f".{hote_commun}"):
            #  Sous l'hôte commun, l'espace est celui des ALIAS : un domaine propre
            #  qui s'y logerait pourrait masquer l'adresse dérivée d'une autre.
            erreurs.append(f"{qui} : nom d'hôte refusé {h!r}.")
    valeurs = {}
    for champ in ("base", "secret"):
        nom = getattr(c, champ)
        valeur = env.get(nom, "") if _VARIABLE.fullmatch(nom) else ""
        if not valeur:
            erreurs.append(f"{qui} : la variable {champ} ({nom!r}) est absente ou vide.")
        valeurs[champ] = valeur
    if valeurs["secret"] and (defaut := defaut_du_secret(valeurs["secret"], c.secret)):
        erreurs.append(f"{qui} : {defaut}")
    if not PurePosixPath(c.racine_fichiers).is_absolute():  # le conteneur est Linux
        erreurs.append(f"{qui} : la racine des fichiers doit être un chemin absolu.")
    if "@" not in c.expediteur:
        erreurs.append(f"{qui} : expéditeur invalide.")
    operateurs = frozenset(normaliser_adresse(a) for a in c.operateurs)
    if any("@" not in a for a in operateurs):
        erreurs.append(f"{qui} : adresse d'opérateur invalide.")
    return Entree(
        copropriete=Copropriete(
            identifiant=qui,
            url_base=valeurs["base"],
            racine_fichiers=Path(c.racine_fichiers),
            secret=valeurs["secret"],
            expediteur=c.expediteur,
            nom_expediteur=c.nom_expediteur or c.nom,
            #  Son domaine propre s'il en a un, sinon l'adresse dérivée : celle où
            #  l'aiguillage renvoie (`Declaration.adresse`), et celle de ses liens.
            adresse=f"{schema}://{hotes[0] if hotes else alias + '.' + hote_commun}",
        ),
        alias=alias,
        anciens_alias=frozenset(c.anciens_alias),
        hotes_propres=hotes,
        suspendue=c.suspendue,
        variable_base=c.base,
        operateurs=operateurs,
    )


def _uniques(entrees: list[Entree], erreurs: list[str]) -> None:
    """Chaque identifiant, alias (anciens compris), hôte, base, secret et racine n'appartient
    qu'à UNE copropriété : un doublon est refusé dès la déclaration (règle 3)."""
    identifiants = [e.copropriete.identifiant for e in entrees]
    for qui in sorted({i for i in identifiants if identifiants.count(i) > 1}):
        erreurs.append(f"identifiant en double : {qui}.")
    vus: dict[tuple[str, str], str] = {}

    def une_fois(sorte: str, valeur: str, qui: str) -> None:
        if not valeur:
            return
        deja = vus.setdefault((sorte, valeur), qui)
        if deja != qui:
            erreurs.append(f"{sorte} en double : {qui} et {deja}.")

    for e in entrees:
        c = e.copropriete
        for alias in {e.alias, *e.anciens_alias}:
            une_fois("alias", alias, c.identifiant)
        for h in e.hotes_propres:
            une_fois("hôte", h, c.identifiant)
        une_fois("base", c.url_base, c.identifiant)
        une_fois("secret", c.secret, c.identifiant)
        une_fois("racine des fichiers", str(c.racine_fichiers), c.identifiant)
