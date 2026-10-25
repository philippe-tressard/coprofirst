"""Périmètres — l'arbre en base, lu et parcouru au même endroit partout.

⚠️ **Ce module est la moitié « arbre » du paquet `app.utils.perimetres`.** Il ne
rend aucun libellé : le rendu vit dans `libelles.py`, qui importe celui-ci. La
dépendance est à sens unique, et elle doit le rester — l'arbre n'a pas à savoir
comment on l'affiche.

Le découpage date du 27/08/2026 : le fichier unique passait 500 lignes, seuil de
la règle de modularité (rang 1). La frontière suit celle que ce docstring
énonçait déjà — « Les primitives » ici, « Libellés » là-bas. La surface publique,
elle, N'A PAS BOUGÉ : `from app.utils.perimetres import …` continue de tout
trouver, via `__init__.py`.

## Ce que ce module remplaçait

Un périmètre (« résidence », « bat:3 », « parking ») était une **table de libellés
écrite en dur**, et elle l'était **trois fois** le 08/08/2026 :

- `app/routers/flux/commun.py` — table complète, bâtiments 1 à 9, AFUL ;
- `app/routers/tickets.py` (relance syndic) — table partielle : ni AFUL, ni
  bâtiment au-delà de ce que le préfixe `bat:` produisait ;
- `front/src/lib/utils.ts` — côté interface, arrêtée à `bat:4`.

Les tables Python ne donnaient pas le même libellé pour un même périmètre, et le
front en donnait un troisième : un ticket ciblé AFUL sortait « aful » dans l'e-mail
de relance, « AFUL » dans le fil, et un `bat:5` s'affichait « Bât. 5 » côté API mais
`bat:5` **brut** à l'écran. C'est la divergence typique décrite par
`standards/02-factorisation.md` §2.

## Ce qui gouverne ce module maintenant

**Aucun code de périmètre n'est écrit ici.** Le produit doit servir une autre
copropriété, qui n'a ni AFUL, ni quatre bâtiments, ni forcément de caves — et qui
aura peut-être une piscine et trois entrées. L'arbre vit dans la table `perimetre`,
il est reconstructible depuis l'administration, et **le vider ne casse rien** : un
périmètre vide vaut « concerne tout le monde », ce qui était déjà la règle
(`visibility.perimetre_visible`).

C'est pourquoi `parse_perimetres` ne renvoie plus la chaîne littérale
« résidence » quand le champ est vide, mais le **nœud racine à portée globale**
désigné par les données — voir `code_par_defaut`.

## Les primitives

`a_portee_globale`, `batiments_cibles` et `perimetre_du_batiment` sont les
seules fonctions qui parcourent l'arbre. Leurs
consommateurs — `utils/visibility.py` (qui voit), `utils/destinataires.py` (qui
est notifié), `routers/flux/evenements.py` (le badge « concerne mon bâtiment », supprimé
avec #1092) et
`utils/fiche_arrivant.py` (le document imprimé) — portaient auparavant chacun sa
propre copie de la liste des périmètres transverses, ou sa propre convention de
nommage.
"""

from __future__ import annotations

import json
import logging
import time
from typing import NamedTuple, Optional

from app import contexte
from app.utils.valeurs import valeur

logger = logging.getLogger("hostachy.perimetres")

#: Durée de vie du cache. Le cache est vidé explicitement à chaque écriture
#: (`invalider_cache`), mais uvicorn peut servir plusieurs *workers* : une
#: invalidation dans l'un n'atteint pas les autres. Ce délai garantit la
#: convergence sans bus de messages — un libellé corrigé dans l'administration
#: apparaît partout en moins d'une demi-minute.
_TTL_SECONDES = 30.0

_PREFIXE_BATIMENT = "bat:"


class Noeud(NamedTuple):
    """Un périmètre, tel que l'arbre le donne. Immuable, sans session attachée."""

    code: str
    libelle: str
    libelle_court: str
    description: str
    icone: Optional[str]
    parent: Optional[str]
    batiment_id: Optional[int]
    portee_globale: bool
    selectionnable: bool
    #: Ce nœud n'appartient pas à la copropriété (AFUL, voie communale…) : ce qui
    #: couvre « toute la copropriété » ne le couvre donc pas. Voir `couvre`.
    hors_copropriete: bool
    actif: bool
    ordre: int
    #: Ce que le nœud dessert (`Perimetre.desserte`) — `circulation`, `caves`,
    #: `stationnement` ou `None`. Lu par `perimetres/lots.deriver` (#2212).
    desserte: Optional[str] = None
    #: L'identifiant en base, pour qui doit ÉCRIRE une référence au nœud.
    id: Optional[int] = None


def _cache() -> dict:
    """L'arbre de LA copropriété servie et l'instant où il a été lu (#1744, spec §4.5).

    Clés `arbre` et `pose` ; vide tant que rien n'est lu ou après `invalider_cache`.
    """
    return contexte.etat("perimetres.arbre")


def invalider_cache() -> None:
    """À appeler après toute écriture dans la table `perimetre`."""
    _cache().clear()


def arbre() -> dict[str, Noeud]:
    """L'arbre entier, indexé par code **en minuscules**.

    Renvoie un dictionnaire vide si la table n'existe pas encore (premier
    démarrage, avant `create_db_and_tables`) ou si elle est vide — et c'est un état
    valide, pas une erreur : une copropriété qui n'a pas encore configuré ses
    périmètres n'en restreint aucun.
    """
    cache = _cache()
    lu = cache.get("arbre")
    if lu is not None and (time.monotonic() - cache["pose"]) < _TTL_SECONDES:
        return lu

    #  Imports différés : ce module est importé par `utils/visibility.py`, lui-même
    #  importé très tôt. Charger la base au moment de l'appel, pas de l'import.
    try:
        from sqlmodel import select

        from app.models.perimetre import Perimetre

        with contexte.nouvelle_session() as session:
            lignes = session.exec(select(Perimetre)).all()
            #  Le parent est exposé par son CODE et non son id : tout le reste du
            #  produit raisonne en codes, et un cache qui mélangerait les deux
            #  obligerait chaque appelant à faire la conversion.
            code_par_id = {ligne.id: ligne.code.lower() for ligne in lignes}
            construit = {
                ligne.code.lower(): Noeud(
                    code=ligne.code,
                    libelle=ligne.libelle,
                    libelle_court=ligne.libelle_court or ligne.libelle,
                    description=ligne.description or "",
                    icone=ligne.icone,
                    parent=code_par_id.get(ligne.parent_id),
                    batiment_id=ligne.batiment_id,
                    portee_globale=bool(ligne.portee_globale),
                    selectionnable=bool(ligne.selectionnable),
                    hors_copropriete=bool(getattr(ligne, "hors_copropriete", False)),
                    actif=bool(ligne.actif),
                    ordre=ligne.ordre or 0,
                    desserte=valeur(ligne.desserte),
                    id=ligne.id,
                )
                for ligne in lignes
            }
    except Exception as exc:
        #  Table absente ou base indisponible. On ne met **pas** le résultat en
        #  cache : la table apparaîtra au prochain démarrage, et figer un arbre
        #  vide pour 30 s masquerait le rétablissement.
        #
        #  Conséquence à connaître, et c'est pourquoi ce journal est en `error` :
        #  un arbre illisible ne permet plus de résoudre un périmètre, donc les
        #  contenus qui en citent un deviennent invisibles des résidents (le
        #  conseil syndical et l'administration continuent de tout voir). C'est le
        #  sens choisi : un contrôle qui ne peut pas s'exécuter ne renvoie pas OK
        #  (`standards/04`). L'inverse aurait rendu lisible, sur un simple hoquet
        #  de base, un document réservé à un autre bâtiment.
        logger.error(
            "Arbre des périmètres illisible (%s) — les contenus à périmètre "
            "deviennent invisibles des résidents jusqu'au rétablissement",
            exc,
        )
        return {}

    cache.update(arbre=construit, pose=time.monotonic())
    return construit


# ── Parcours de l'arbre : les trois primitives ────────────────────────────────


def _chaine(code: str, noeuds: dict[str, Noeud]) -> list[Noeud]:
    """Le nœud puis ses ancêtres, du plus proche au plus lointain.

    Renvoie une liste **vide** si le code est inconnu : un contenu qui cite un
    périmètre supprimé n'accorde aucun droit — il n'en retire pas non plus, il ne
    compte simplement pas. Un `parent_id` orphelin ou un cycle arrête la remontée
    sans lever : `visited` est le garde-fou, parce qu'une boucle dans l'arbre ne
    doit jamais pouvoir suspendre une requête (`standards/04` — un contrôle qui ne
    peut pas s'exécuter ne renvoie pas OK).
    """
    depart = noeuds.get(code.strip().lower())
    if depart is None:
        return []
    chaine = [depart]
    vus = {depart.code.lower()}
    courant = depart
    while courant.parent:
        suivant = noeuds.get(courant.parent)
        if suivant is None or suivant.code.lower() in vus:
            break
        chaine.append(suivant)
        vus.add(suivant.code.lower())
        courant = suivant
    return chaine


def a_portee_globale(codes: list[str]) -> bool:
    """L'un de ces périmètres concerne-t-il tous les résidents ?

    Vrai dès qu'un nœud cité — ou l'un de ses ancêtres — porte `portee_globale`.
    L'héritage est ce qui permet de cibler « Parking › Portail d'accès » sans avoir
    à rappeler que le parking concerne tout le monde.
    """
    noeuds = arbre()
    if not noeuds:
        return False
    return any(n.portee_globale for code in codes for n in _chaine(code, noeuds))


def _hors_copropriete(chaine: list["Noeud"]) -> bool:
    """Ce périmètre — ou l'un de ses ancêtres — appartient-il à un tiers ?

    Le drapeau se lit sur toute la LIGNÉE : un sous-espace de l'AFUL n'a pas à
    redire qu'il n'appartient pas à la copropriété.
    """
    return any(n.hors_copropriete for n in chaine)


def couvre(codes_portee: list[str], demande: Optional[str]) -> bool:
    """Ces périmètres englobent-ils celui qu'on demande ?

    C'est la question d'un **filtre** : *cette ligne entre-t-elle dans ce que
    l'utilisateur a choisi de regarder ?* Trois façons d'y entrer :

    1. **le même code** — un contrat sur « Parking » sous un filtre « Parking » ;
    2. **un ancêtre du demandé** — « Bât. 3 » couvre « Bât. 3 › Toit », parce que
       le toit du bâtiment 3 fait partie du bâtiment 3 ;
    3. **une portée globale** — un contrat de nettoyage qui couvre toute la
       résidence entretient AUSSI le parking.

    🔴 **La réciproque est fausse, et doit le rester** : « Bât. 3 » n'entre pas
    dans un filtre « Parking ». Une portée large englobe une portée étroite,
    jamais l'inverse. Confondre les deux sens ferait tout apparaître partout, ce
    qui est la façon la plus discrète de rendre un filtre inutile.

    ⚠️ Une liste de codes **vide** couvre tout : ne rien déclarer, c'est ne rien
    restreindre. C'est ce que valait implicitement `batiment_id IS NULL` avant que
    les contrats aient un périmètre (10/09/2026).

    ⚠️ `demande=None` — aucun filtre — couvre tout aussi, et cette symétrie est
    volontaire : l'appelant n'a pas à traiter le cas « pas de filtre » à part.
    """
    if demande is None:
        return True
    if not codes_portee:
        return True
    noeuds = arbre()
    if not noeuds:
        #  Arbre vide : on ne peut RIEN décider. Ne rien filtrer plutôt que tout
        #  masquer — un carnet vide se lirait comme une absence de données
        #  (`standards/04` : une mesure impossible ne rend pas un verdict).
        return True
    chaine = _chaine(demande, noeuds)
    lignee = {n.code.lower() for n in chaine}
    for code in codes_portee:
        if code.strip().lower() in lignee:
            return True
    #  🔴 CE QUI N'APPARTIENT PAS À LA COPROPRIÉTÉ N'EST PAS COUVERT PAR ELLE
    #  (13/09/2026, #943) — signalé à l'écran :
    #
    #  > « Il y a une exception pour la sélection de l'AFUL : elle n'est pas
    #  >   incluse dans "toute copropriété". »
    #
    #  Un contrat de nettoyage qui couvre toute la résidence entretient AUSSI le
    #  parking de la résidence — c'est le troisième chemin ci-dessous, et il est
    #  juste. Il ne l'est plus dès que le périmètre demandé appartient à un tiers :
    #  l'AFUL est une association distincte, ce que la copropriété entretient « en
    #  entier » ne l'entretient pas. Le filtre « AFUL » du carnet remontait
    #  pourtant toutes les lignes « Copropriété entière ».
    #
    #  ⚠️ Le drapeau est cherché sur TOUTE la lignée du demandé : un sous-espace
    #  de l'AFUL en hérite, sans avoir à le redire. Et il est ADMINISTRÉ — aucun
    #  code ici ne connaît « aful » par son nom, une autre copropriété n'en a pas.
    #
    #  ⚠️ Ne touche QUE ce chemin-là : un contenu explicitement marqué AFUL entre
    #  toujours dans le filtre AFUL (deuxième chemin, ci-dessus). Sans cette
    #  borne, la correction viderait le filtre au lieu de le corriger.
    #  ⚠️ La règle vaut dans les DEUX SENS, et c'est plus simple à énoncer ainsi :
    #  la portée globale ne franchit pas la frontière de propriété. Ce que la
    #  copropriété couvre « en entier » ne couvre pas l'AFUL ; et un contenu
    #  marqué AFUL — qui concerne pourtant tous les résidents — n'apparaît pas
    #  pour autant sous le filtre « Parking » de la copropriété.
    #
    #  Un seul sens aurait été un demi-correctif : `portee_globale` répond à
    #  « qui VOIT », et s'en servir pour « ce qui COUVRE » faisait entrer l'AFUL
    #  partout, exactement comme la résidence entrait dans l'AFUL.
    if _hors_copropriete(chaine) != any(
        _hors_copropriete(_chaine(code, noeuds)) for code in codes_portee
    ):
        return False
    return a_portee_globale(codes_portee)


def batiments_cibles(codes: list[str]) -> set[int]:
    """Les identifiants de bâtiments réellement visés par ces périmètres.

    Pour chaque code, on retient le `batiment_id` du nœud ou, à défaut, celui du
    plus proche ancêtre qui en porte un — c'est ainsi que « Bât. 2 › Hall d'entrée »
    concerne le bâtiment 2 sans le répéter sur chaque espace.
    """
    noeuds = arbre()
    if not noeuds:
        return set()
    cibles: set[int] = set()
    for code in codes:
        for n in _chaine(code, noeuds):
            if n.batiment_id is not None:
                cibles.add(n.batiment_id)
                break
    return cibles


def perimetre_du_batiment(batiment_id: Optional[int]) -> Optional[Noeud]:
    """Le nœud de l'arbre qui **est** ce bâtiment — chemin inverse de `batiments_cibles`.

    Sert à tout ce qui part d'un bâtiment (un membre du conseil syndical, un lot)
    et doit le **nommer** : le nom et l'icône viennent alors de l'arbre, donc de
    l'administration, au lieu d'être fabriqués par un `f"Bât. {numero}"` recopié.
    Cette convention-là existait dans sept fichiers le 14/08/2026 ; le document
    imprimé était le seul endroit où elle produisait un libellé qu'aucun
    renommage ne rattrapait, puisqu'il ne passe par aucun écran.

    Renvoie `None` si l'arbre est vide, si le bâtiment n'y figure pas, ou si son
    nœud est inactif — l'appelant garde alors son propre repli. Ne jamais faire
    lever : un document doit se produire même sur un arbre incomplet.

    Seul le nœud « bâtiment » porte un `batiment_id` ; ses espaces (hall,
    ascenseur…) l'héritent de leur ancêtre, ce que `batiments_cibles` exploite.
    Si plusieurs nœuds actifs le portaient malgré tout — données reprises à la
    main — on retient le plus prioritaire, jamais un au hasard.
    """
    if batiment_id is None:
        return None
    candidats = [n for n in arbre().values() if n.batiment_id == batiment_id and n.actif]
    if not candidats:
        return None
    return min(candidats, key=lambda n: (n.ordre, n.code))


# ── Analyse des champs stockés ────────────────────────────────────────────────


def code_par_defaut() -> Optional[str]:
    """Le périmètre qu'un contenu sans périmètre explicite désigne implicitement.

    C'est la racine à portée globale la plus prioritaire — « Copropriété entière »
    sur l'arbre livré. Cette fonction existe pour que la valeur par défaut soit une
    **donnée** et non la chaîne « résidence » écrite dans le code : une
    copropriété qui renomme ou supprime ce nœud ne doit pas casser l'application.

    Renvoie `None` sur un arbre vide, et alors `parse_perimetres` rend une liste
    vide — que `perimetre_visible` traite déjà comme « visible de tous ».
    """
    candidats = [n for n in arbre().values() if n.portee_globale and n.parent is None and n.actif]
    if not candidats:
        return None
    return min(candidats, key=lambda n: (n.ordre, n.code)).code


def _avec_defaut(codes: list[str]) -> list[str]:
    if codes:
        return codes
    return perimetre_defaut_liste()


# ── Le périmètre par défaut : ce qu'on écrit, et la question qu'on pose ──────
#
#  🔴 Le code de la racine n'est écrit QUE par le seed, qui pose le nœud
#  (#1567, 02/10/2026). Il l'était vingt-trois fois ailleurs côté API — défauts
#  de colonne, défauts de schéma, replis `x or ["résidence"]`, et deux
#  comparaisons dans le message du groupe —, pendant que le front n'en avait
#  plus un seul. Miroirs de `perimetreDefautListe` et `estPerimetreParDefaut`
#  (`front/src/lib/perimetres/arbre.ts`). 🔒 `test_perimetre_racine_source_unique.py`.


def perimetre_defaut_liste() -> list[str]:
    """La sélection d'un contenu à qui l'on n'en donne pas — « toute la copropriété ».

    Liste vide sur un arbre vide : c'est ce que `perimetre_visible` traite déjà
    comme « concerne tout le monde », et ce que le front envoie dans ce cas.
    """
    defaut = code_par_defaut()
    return [defaut] if defaut else []


def perimetre_cible_json(codes: Optional[list[str]] = None) -> str:
    """Une sélection sous sa forme stockée (`perimetre_cible`) — vide, le défaut.

    Remplace le `json.dumps(x or ["résidence"], ensure_ascii=False)` que six
    écritures recopiaient. Sans argument, c'est le défaut seul : elle sert alors
    de `default_factory` aux modèles, et la valeur se lit à la CRÉATION de
    l'objet — ou à l'INSERTION quand on lui a passé `None`, que l'ORM remplace
    par le défaut —, jamais à l'import : un défaut de colonne figé reprendrait
    le code en dur qu'elle remplace.

    ⚠️ Les écritures qui stockent `None` pour une sélection vide (sondage,
    évolution, accès) répondent à une autre règle : « ne restreint rien », lu
    comme tel. Elles n'ont pas à passer par ici.
    """
    return json.dumps(list(codes or []) or perimetre_defaut_liste(), ensure_ascii=False)


def perimetre_defaut_texte() -> str:
    """Le même défaut sous la forme TEXTE (`Evenement.perimetre`, lue par `parse_perimetres`)."""
    return ",".join(perimetre_defaut_liste())


def est_perimetre_par_defaut(codes: Optional[list[str]]) -> bool:
    """Cette sélection désigne-t-elle toute la copropriété ?

    Vrai pour une sélection vide, ou réduite au seul code par défaut — en toute
    casse, comme partout dans l'arbre. Faux sur un arbre vide dès qu'un code est
    cité : on ne peut pas dire qu'il désigne la racine.
    """
    liste = [c.strip() for c in (codes or []) if isinstance(c, str) and c.strip()]
    if not liste:
        return True
    defaut = code_par_defaut()
    return len(liste) == 1 and defaut is not None and liste[0].lower() == defaut.lower()


def parse_perimetres(perimetre: Optional[str]) -> list[str]:
    """Champ `perimetre` en texte (« résidence », « parking,cave »)."""
    if not perimetre:
        return _avec_defaut([])
    return _avec_defaut([s.strip() for s in perimetre.split(",") if s.strip()])


def parse_json_perimetres(perimetre_cible: Optional[str]) -> list[str]:
    """Champ `perimetre_cible` en JSON (ex. '["bat:1","bat:3"]').

    Un contenu illisible retombe sur le périmètre par défaut plutôt que de lever :
    ce champ alimente un affichage, il ne doit jamais faire échouer une requête.

    ⚠️ Ce repli est **volontairement limité à l'affichage**. Pour décider d'un
    accès, `visibility.perimetre_visible` n'utilise pas ce repli : un JSON corrompu
    ne doit pas ouvrir une visibilité, alors qu'il peut bien rendre un badge
    générique.
    """
    if not perimetre_cible:
        return _avec_defaut([])
    try:
        val = json.loads(perimetre_cible) if isinstance(perimetre_cible, str) else perimetre_cible
        codes = [str(v) for v in val] if isinstance(val, (list, tuple)) else []
    except Exception:
        codes = []
    return _avec_defaut(codes)
