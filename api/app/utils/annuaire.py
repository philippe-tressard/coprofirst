"""L'annuaire du conseil et du syndic — la composition, écrite UNE fois.

## 🔴 Elle l'était deux fois, et elle avait déjà divergé (09/09/2026)

`routers/admin/annuaire.py` (l'écran) et `routers/admin/arrivants.py` (la fiche
d'accueil remise aux nouveaux résidents) construisaient **la même liste**, avec le
même tri, les mêmes caches et les mêmes clés. Le second l'annonçait lui-même —
*« même logique que GET /admin/annuaire »* — ce qui est la signature d'une copie
qui se sait copie et que personne ne rapproche.

Trente et une lignes identiques au caractère près, et **deux divergences déjà
installées** :

1. `est_gestionnaire_site` s'écrivait `site_manager_user_id is not None and …`
   d'un côté, `site_manager_user_id and …` de l'autre. Les deux ne disent pas la
   même chose pour l'identifiant `0` — latent aujourd'hui, faux le jour où un
   identifiant vaut zéro, et alors sur **un** des deux rendus seulement ;
2. l'écran rendait `id`, la fiche rendait `batiment_id`. Chacun avait ajouté ce
   dont il avait besoin, sans savoir que l'autre existait.

C'est la forme la plus coûteuse de la duplication d'un **rendu** : les deux
sorties décrivent le même objet — le conseil syndical — et personne ne les compare
jamais, parce qu'elles vivent sur deux écrans différents (`standards/11` §14).

## Ce que ce module rend, et pourquoi c'est un sur-ensemble

Les deux clés qui manquaient à l'un ou à l'autre sont rendues à tout le monde :
`id` **et** `batiment_id`. Retenir la version la plus disante est la règle quand
on fusionne deux copies (`standards/02` §4 bis) — une clé en trop est ignorée par
qui ne la lit pas, une clé en moins est une fonctionnalité perdue.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app.models.core import Batiment, MembreCS, MembreSyndic, Utilisateur
from app.utils.destinataires import site_manager_user_id as _site_manager_user_id
from app.utils import noms
from app.utils.etages import etage_label
from app.utils.telephones import telephones_de
from app.utils.valeurs import valeur


#: L'ordre des civilités à bâtiment égal : « Mme », puis « Mlle », puis les autres.
#: C'était la règle de l'ÉCRAN (`annuaire/+page.svelte`) ; le serveur, lui, mettait
#: « Mme » et « Mlle » à égalité et rangeait les bâtiments par identifiant — l'app
#: iOS, qui affiche l'ordre reçu, n'aurait pas montré le conseil comme le site.
#: Une seule règle désormais, servie (#2505).
ORDRE_GENRE = {"Mme": 0, "Mlle": 1}


def _ordre_genre(genre) -> int:
    """« Mme », puis « Mlle », puis toute autre civilité."""
    return ORDRE_GENRE.get(valeur(genre) or "", len(ORDRE_GENRE))


class _Caches:
    """Les deux lectures répétées d'une composition : le bâtiment et la photo.

    Elles étaient écrites en fermetures dans chacun des deux appelants, avec leur
    dictionnaire de cache. Un objet plutôt que deux fonctions libres : le cache et
    la lecture qui s'en sert ne se séparent pas.
    """

    def __init__(self, session: Session):
        self._session = session
        self._batiments: dict[int, str] = {}
        self._photos: dict[int, Optional[str]] = {}

    def batiment_nom(self, bid: Optional[int]) -> Optional[str]:
        """Le NUMÉRO du bâtiment (« A »), pas son libellé (« Bât. A »).

        ⚠️ Ce n'est volontairement pas `libelle_batiment` : les deux appelants
        rendent ici le numéro nu, que la fiche et l'écran préfixent eux-mêmes.
        Le repli sur `str(bid)` quand le bâtiment a disparu vient des deux copies
        d'origine — il vaut mieux un identifiant qu'un trou.
        """
        if bid is None:
            return None
        if bid not in self._batiments:
            bat = self._session.get(Batiment, bid)
            self._batiments[bid] = bat.numero if bat else str(bid)
        return self._batiments[bid]

    def photo(self, uid: Optional[int]) -> Optional[str]:
        if uid is None:
            return None
        if uid not in self._photos:
            u = self._session.get(Utilisateur, uid)
            self._photos[uid] = u.photo_url if u else None
        return self._photos[uid]


def membres_du_conseil(session: Session, *, pour_administration: bool = False) -> list[dict]:
    """Le conseil syndical, trié par bâtiment, puis civilité, puis nom.

    `pour_administration` change deux choses, et rien d'autre : le tri devient
    celui que l'administration a fixé (`ordre`), et deux champs de gestion
    s'ajoutent — `ordre`, pour le réordonnancement, et `user_id`, pour le
    rattachement à un compte.

    🔴 Pourquoi un paramètre plutôt qu'une seconde fonction (18/09/2026, #779) :
    `routers/admin/annuaire.py` REFAISAIT ce dictionnaire, dans le fichier même
    qui importe cette fonction et qui explique pourquoi elle existe. Le motif
    est celui que `check-client-api.mjs` décrit côté front — *une méthode trop
    pauvre ne fait pas contourner un peu, elle fait recopier en entier*. Il
    manquait deux clés et un tri ; la copie a emporté avec elle le cache des
    bâtiments et la règle du gestionnaire de site, dont ce module dit pourtant
    qu'elle avait DÉJÀ divergé sur l'identifiant 0.
    """
    caches = _Caches(session)
    gestionnaire = _site_manager_user_id(session)

    def cle_annuaire(m: MembreCS) -> tuple:
        """Bâtiment (par son numéro, sans bâtiment en dernier), civilité, puis nom."""
        numero = caches.batiment_nom(m.batiment_id)
        return (
            numero is None,
            noms.cle_de_classement(None, numero),
            _ordre_genre(m.genre),
            noms.cle_de_classement(m.prenom, m.nom),
        )

    membres = sorted(
        session.exec(select(MembreCS)).all(),
        key=(lambda m: m.ordre or 0) if pour_administration else cle_annuaire,
    )
    return [
        {
            "id": m.id,
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            #  L'identifiant EN PLUS du nom : la fiche d'accueil nomme le bâtiment
            #  d'après l'arbre des périmètres, qui s'interroge par `batiment_id`.
            #  `batiment_nom` reste son dernier repli, quand l'arbre est vide.
            "batiment_id": m.batiment_id,
            "batiment_nom": caches.batiment_nom(m.batiment_id),
            "etage": m.etage,
            #  Servis à l'écran ET à l'app iOS (#2505) : « Prénom NOM » et l'étage
            #  en clair, composés ici plutôt que dans chaque client.
            "nom_affiche": noms.nom_affiche(m.prenom, m.nom),
            "etage_libelle": etage_label(m.etage, suffixe=True),
            #  `is not None` et non la valeur de vérité : les deux copies ne
            #  disaient déjà pas la même chose pour l'identifiant 0.
            "est_gestionnaire_site": bool(
                m.est_gestionnaire_site or (gestionnaire is not None and m.user_id == gestionnaire)
            ),
            "est_president": m.est_president,
            "photo_url": caches.photo(m.user_id),
            **({"ordre": m.ordre, "user_id": m.user_id} if pour_administration else {}),
        }
        for m in membres
    ]


def membres_du_syndic(session: Session, *, pour_administration: bool = False) -> list[dict]:
    """Les interlocuteurs du syndic, dans l'ordre que l'administration a fixé.

    `pour_administration` ajoute les deux champs de gestion — voir
    `membres_du_conseil`, qui dit pourquoi ils ne sont pas rendus partout.
    """
    caches = _Caches(session)
    return [
        {
            "id": m.id,
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            "fonction": m.fonction,
            "email": m.email,
            "telephone": m.telephone,
            #  Les numéros du champ, découpés (#2505) : chaque client en fait un
            #  lien d'appel sans analyser la saisie.
            "telephones": telephones_de(m.telephone),
            "nom_affiche": noms.nom_affiche(m.prenom, m.nom),
            "est_principal": m.est_principal,
            "photo_url": caches.photo(m.user_id),
            **({"ordre": m.ordre, "user_id": m.user_id} if pour_administration else {}),
        }
        for m in sorted(session.exec(select(MembreSyndic)).all(), key=lambda m: m.ordre)
    ]


def reconcilier_membres(session: Session, modele, entrees) -> None:
    """Enregistrer la liste d'un annuaire en RÉCONCILIANT, jamais en remplaçant.

    Les deux annuaires — conseil et syndic — s'enregistrent d'un bloc : l'écran
    renvoie la liste entière, telle que le GET la lui a donnée, avec l'`id` de
    chaque membre. Une entrée dont l'`id` est connu est mise à jour EN PLACE
    (`cree_le` et `id` survivent) ; une entrée sans `id` connu est une arrivée ;
    ce que la liste ne contient plus a quitté l'annuaire.

    ## 🔴 Pourquoi une seule fonction

    Le conseil a été corrigé le 31/08/2026 : il supprimait ses sept lignes et les
    recréait à chaque enregistrement — sept « Nouveau membre du conseil
    syndical » au fil pour une correction d'étage, parce que `flux/annuaire.py`
    lit `cree_le` pour décider de ce qui est nouveau. Le correctif a été écrit
    DANS le routeur du conseil, et le syndic, quarante lignes plus bas, a gardé le
    remplacement : le 09/10/2026, deux interlocutrices inchangées sont réapparues
    au fil comme « Nouveau membre du syndic » le jour où un troisième changeait.
    Une règle rangée chez un appelant n'est pas prise par le suivant
    (`standards/02` §4 sexies).

    :param entrees: les schémas d'entrée, dans l'ordre de l'écran. Chacun porte
        un `id` (facultatif) et les champs du modèle ; `ordre` se déduit de la
        position.
    """
    existants = {m.id: m for m in session.exec(select(modele)).all()}
    gardes: set[int] = set()

    for ordre, entree in enumerate(entrees):
        valeurs = entree.model_dump(exclude={"id"}) | {"ordre": ordre}
        ancien = existants.get(entree.id) if entree.id is not None else None
        if ancien is not None:
            for champ, val in valeurs.items():
                setattr(ancien, champ, val)
            gardes.add(ancien.id)
        else:
            #  Sans identifiant connu, c'est une arrivée : elle date d'aujourd'hui
            #  et le fil a raison de l'annoncer.
            session.add(modele(**valeurs))

    for id_, membre in existants.items():
        if id_ not in gardes:
            session.delete(membre)


__all__ = ["membres_du_conseil", "membres_du_syndic", "reconcilier_membres"]
