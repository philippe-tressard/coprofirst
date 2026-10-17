"""L'hôte COMMUN d'une installation commune : il ne fait que REDIRIGER (#1894, §4.1 bis).

Trois routes sous le préfixe `/plateforme/`, qui échappe à la résolution des
copropriétés (`contexte.PREFIXE_PLATEFORME`) — l'hôte commun n'est l'hôte d'aucune :

- `GET /plateforme/aiguillage` — « suis-je sur l'hôte commun ? » : l'écran de
  connexion y montre l'aiguillage (code postal + nom) au lieu du formulaire ;
- `POST /plateforme/aiguillage` — code postal + nom, ou l'alias lu dans un chemin
  `/<alias>` : l'adresse de la copropriété, où le navigateur est renvoyé ;
- `GET /plateforme/aiguillage/hote` — la garde des pages, appelée par le
  `forward_auth` de Caddy sur l'installation commune (`deploiement/standard/commune/`) :
  un ANCIEN alias renvoie (308) vers l'adresse actuelle, chemin compris, et les liens
  déjà envoyés restent valables (règle 4) ; un hôte qui désigne une copropriété, et
  l'hôte commun, passent (204) ; tout autre reçoit 421.

Ce qu'elles garantissent (règles 2, 5 et 6) :
- aucune ne lit la base d'une copropriété, ni ne pose de cookie ;
- l'aiguillage exige la correspondance EXACTE de l'alias, sans liste ni complétion,
  et plafonne les tentatives par adresse (`LIMITE_AIGUILLAGE`) ;
- tout échec — alias inconnu, copropriété suspendue, saisie malformée, corps
  illisible — reçoit la MÊME réponse (`ECHEC`) ;
- une installation propre à une copropriété répond 404 partout, comme à une route
  inconnue : ni aiguillage, ni adresse dérivée — SAUF la question de l'écran de
  connexion (`GET`), qui rend `{"hote_commun": false}` : l'écran la pose à chaque
  visite, et un 404 à chaque chargement salissait les journaux et la télémétrie des
  erreurs de la référence (constat de production du 18/10/2026).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app import contexte
from app.installation_commune.alias import alias_de, est_alias
from app.installation_commune.declaration import Declaration, DeclarationInvalide, declaration
from app.utils.limiter import LIMITE_AIGUILLAGE, limiter
from app.utils.recuperer import present_ou_404

router = APIRouter(prefix="/plateforme/aiguillage", tags=["aiguillage"])

#: La réponse à TOUT échec de l'aiguillage — le même texte et le même statut, qu'on
#: ait mal saisi, visé une copropriété inconnue ou une copropriété suspendue.
ECHEC = "Aucune copropriété ne correspond à ce code postal et ce nom."

#: Une demande d'aiguillage pèse quelques dizaines d'octets.
TAILLE_MAX = 1024


def _commune() -> Declaration:
    """La déclaration de l'installation commune ; 404 pour une installation propre."""
    try:
        commune = declaration()
    except DeclarationInvalide:
        raise HTTPException(503, "Ce serveur est mal configuré.") from None
    return present_ou_404(commune, "Not Found")


def _sur_l_hote_commun(request: Request) -> Declaration:
    commune = _commune()
    sur_place = contexte.nom_d_hote(request.headers.get("host", "")) == commune.hote_commun
    return present_ou_404(commune if sur_place else None, "Not Found")


def alias_demande(corps: bytes) -> str | None:
    """L'alias que demande le corps — `{"code_postal", "nom"}` ou `{"alias"}` —, ou `None`."""
    if len(corps) > TAILLE_MAX:
        return None
    try:
        demande = json.loads(corps)
    except ValueError:
        return None
    if not isinstance(demande, dict):
        return None
    alias, cp, nom = demande.get("alias"), demande.get("code_postal"), demande.get("nom")
    if isinstance(alias, str):
        alias = alias.strip().lower()
        return alias if est_alias(alias) else None
    if isinstance(cp, str) and isinstance(nom, str):
        return alias_de(cp, nom)
    return None


@router.get("")
def hote_commun(request: Request) -> dict[str, bool]:
    """L'écran de connexion est-il celui de l'hôte commun ? Une réponse, jamais une erreur :
    `false` ailleurs — sous l'adresse d'une copropriété comme sur une installation propre.
    Elle ne dit rien de plus que l'hôte que le visiteur a lui-même demandé."""
    try:
        _sur_l_hote_commun(request)
    except HTTPException:
        return {"hote_commun": False}
    return {"hote_commun": True}


@router.post("")
@limiter.limit(LIMITE_AIGUILLAGE)
async def aiguiller(request: Request) -> dict[str, str]:
    commune = _sur_l_hote_commun(request)
    alias = alias_demande(await request.body())
    entree = present_ou_404(commune.destination(alias) if alias else None, ECHEC)
    return {"destination": f"{commune.adresse(entree)}/"}


def _chemin_transmis(request: Request) -> str:
    """Le chemin de la page demandée, que Caddy transmet — un chemin interne, sinon `/`."""
    chemin = request.headers.get("x-forwarded-uri", "/")
    interne = chemin.startswith("/") and not chemin.startswith(("//", "/\\"))
    return chemin if interne else "/"


@router.get("/hote", status_code=204)
def garde_des_pages(request: Request) -> Response:
    commune = _commune()
    hote = contexte.nom_d_hote(request.headers.get("host", ""))
    if hote == commune.hote_commun or contexte.copropriete_de_l_hote(hote) is not None:
        return Response(status_code=204)
    suffixe = f".{commune.hote_commun}"
    if hote.endswith(suffixe):
        #  L'alias ACTUEL est résolu ci-dessus : il ne reste ici que les anciens.
        entree = commune.destination(hote.removesuffix(suffixe))
        if entree is not None:
            cible = commune.adresse(entree) + _chemin_transmis(request)
            return RedirectResponse(cible, status_code=308)
    return JSONResponse({"detail": contexte.HOTE_INCONNU}, status_code=421)
