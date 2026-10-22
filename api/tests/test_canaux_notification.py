"""Garde-fous du canal WhatsApp côté API (08/08/2026).

Pendant backend de `front/scripts/check-notifications.mjs`. Deux défauts réels,
tous deux invisibles à la relecture d'un diff :

1. **La liste des clés de configuration WhatsApp était écrite quatre fois** — et
   la copie de `publications.py` contenait `site_url` que les trois autres
   n'avaient pas. Conséquence concrète : le lien « consultez l'application »
   d'un message restreint ne pouvait apparaître que dans une actualité. Une
   notion, une écriture (`standards/02-factorisation.md` §2).

2. **Le groupe WhatsApp est un canal de diffusion vers tous les résidents.**
   L'ouvrir à l'auteur d'un ticket quelconque en ferait un mégaphone : le
   partage doit rester réservé au CS et aux admins, contrôlé **côté serveur**,
   la case de l'interface n'étant qu'un confort (`standards/03-securite.md` §1).
"""

import ast
import pathlib

from tests.aides_sources import modules_app

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Les clés qui composent la configuration du canal.
_MARQUEURS = ("whatsapp_api_url", "whatsapp_group_jid", "whatsapp_enabled")


def test_les_cles_de_configuration_whatsapp_ne_sont_ecrites_qu_une_fois():
    """Un seul module a le droit d'énumérer les clés du canal WhatsApp."""
    porteurs = {
        module.rel
        for module in modules_app()
        #  Deux marqueurs au moins : une mention isolée (un log, un commentaire,
        #  une lecture ciblée comme celle du moniteur de santé) n'est pas une
        #  redéfinition de l'ensemble.
        if sum(m in module.source for m in _MARQUEURS) >= 2
    }
    #  Le registre des services (#1718) porte l'ACTIVATION du canal et nomme le
    #  réglage sans lequel il ne fonctionne pas : il ne redéfinit pas l'ensemble,
    #  il en est la source pour la clé d'activation. Déclaré, et il doit servir.
    attendus = {"utils/whatsapp.py", "utils/services.py"}
    assert porteurs == attendus, (
        "Les clés de configuration WhatsApp doivent vivre dans `app/utils/whatsapp.py` "
        "(`CLES_CONFIG`) — et l'activation dans `utils/services.py` — nulle part ailleurs. "
        f"Écart : {sorted(porteurs ^ attendus)}. Utiliser `config_whatsapp(session)`."
    )


def _condition_resolue(fonction: ast.AST, test: ast.AST) -> str:
    """La condition d'un `if`, variables locales d'un niveau remplacées.

    Sans cela, extraire `est_cs = user.has_role(...)` — parfaitement légitime
    quand le rôle sert six fois dans la même fonction — sortirait l'autorisation
    du champ du contrôle. C'est le même angle mort que celui corrigé sur le fil
    d'activité le 08/08/2026 : un garde-fou ne doit pas obliger à dupliquer pour
    rester visible.
    """
    affectations: dict[str, ast.AST] = {}
    for n in ast.walk(fonction):
        if isinstance(n, ast.Assign):
            for cible in n.targets:
                if isinstance(cible, ast.Name):
                    affectations[cible.id] = n.value
    #  TRANSITIVE depuis le 23/09/2026 (#1164) : `partage = … and est_cs` puis
    #  `est_cs = est_moderateur(user)` — un seul niveau voyait `est_cs` et non le
    #  rôle, et obligeait à réécrire le prédicat en ligne pour rester visible.
    morceaux = [ast.unparse(test)]
    vus: set[str] = set()
    a_lire = [test]
    while a_lire:
        noeud = a_lire.pop()
        for n in ast.walk(noeud):
            if isinstance(n, ast.Name) and n.id in affectations and n.id not in vus:
                vus.add(n.id)
                morceaux.append(ast.unparse(affectations[n.id]))
                a_lire.append(affectations[n.id])
    return " ".join(morceaux)


#: Les appels qui font PARTIR un message sur le groupe. C'est eux qui désignent
#: un point de partage — pas le nom du champ.
#  `diffuser(` : le geste du registre des canaux depuis #1060 (28/09/2026). Ce
#  contrôle l'a signalé tout seul le jour du renommage — « le contrôle a perdu
#  sa portée » —, au lieu de passer au vert sur des envois qu'il ne voyait plus.
#  `diffuser_l_affaire` : la porte de toute affaire vers le groupe depuis le
#  22/10/2026 (`tickets/groupe.py`) — `diffuser(` ne la reconnaît pas ;
#  `diffuser_le_sondage`, celle d'un sondage, le même jour (`sondages/groupe.py`).
_ENVOIS = (
    "_partager_sur_le_groupe",
    "envoyer_whatsapp",
    "diffuser(",
    "diffuser_l_affaire(",
    "diffuser_le_sondage(",
)


def _gardes_des_envois(fonction: ast.AST) -> list[str]:
    """Pour chaque envoi WhatsApp, TOUTES les conditions qui l'englobent, résolues.

    ⚠️ **Trois repères ont été essayés avant celui-ci** (05/09/2026), chacun
    aveugle d'un côté différent :

    1. le texte écrit du `if` — aveugle à `if partage_whatsapp:`, alimenté par
       une variable locale, c'est-à-dire au point d'envoi qu'on venait de garder ;
    2. la condition **résolue** — attrapait en plus un `if` qui ne fait rien
       partir : la validation des champs réservés, qui énumère `partager_whatsapp`
       dans un tuple ;
    3. le `if` **immédiat** de l'appel — aveugle à une garde portée par un `if`
       englobant, ce qui décrit littéralement l'envoi des évolutions, niché sous
       `if whatsapp_actif(...)`.

    Un envoi n'a pas lieu « sous une condition » mais sous **la conjonction de
    toutes celles qu'il faut franchir**. C'est donc elle qu'on lit — le fait, et
    non l'un de ses symptômes.
    """
    gardes: list[str] = []

    def descendre(noeud: ast.AST, pile: list[str]) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, ast.If):
                condition = _condition_resolue(fonction, enfant.test)
                for instruction in enfant.body:
                    descendre(instruction, pile + [condition])
                #  Le `else` ne bénéficie PAS de la condition du `if`.
                for instruction in enfant.orelse:
                    descendre(instruction, pile)
                continue
            if any(m in ast.unparse(enfant) for m in _ENVOIS) and pile:
                gardes.append(" et ".join(pile))
            descendre(enfant, pile)

    descendre(fonction, [])
    return gardes


def _conditions_de_partage(arbre: ast.AST) -> list[str]:
    """Les gardes de tous les envois WhatsApp d'un module, dédoublonnées."""
    trouvees: list[str] = []
    for fonction in ast.walk(arbre):
        if isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for garde in _gardes_des_envois(fonction):
                if garde not in trouvees:
                    trouvees.append(garde)
    return trouvees


def test_un_ticket_reserve_au_conseil_ne_part_JAMAIS_sur_le_groupe():
    """🔴 « Visibilité au seul conseil syndical » ⇒ aucune diffusion WhatsApp.

    Demandé à l'écran le 05/09/2026 :

    > « si "Visibilité du ticket au seul conseil syndical" est sélectionné, la
    >   diffusion WhatsApp est interdite »

    Le groupe WhatsApp rassemble **tous les résidents**. Un ticket qu'on vient
    de fermer au voisinage — un litige, un impayé, un signalement nominatif —
    y serait recopié en entier : la case cochée dans l'écran promettrait une
    confidentialité que le canal annulerait aussitôt.

    ## Pourquoi un test, et pas seulement une case grisée

    L'actualité tenait la règle depuis toujours (`and not pub.brouillon` à
    chaque canal) ; le ticket, non — **trois** points d'envoi, aucun gardé.
    Griser la case à l'écran ne protège rien : `partager_whatsapp` est un
    champ du corps de la requête, qui se poste directement
    (`standards/03-securite.md` §1 — l'interface est un confort, le serveur
    est le contrôle).

    Le contrôle porte sur les **trois** modules d'envoi, et il exige la
    condition là où l'envoi se décide : c'est le FAIT, pas le symptôme.

    🔴 Depuis #1436 (28/09/2026), la condition est `reservee_au_conseil(ticket)`
    et non plus le seul drapeau : une nuisance, une question, un sinistre sont
    fermés au voisinage PAR LEUR CATÉGORIE, sans que rien soit coché — et le
    drapeau seul les laissait partir. La règle unique le contient ; exiger le
    drapeau aurait exigé l'ancienne règle, celle qui fuyait. Le contrôle
    couvrait deux modules sur trois : `mise_a_jour.py` n'y était pas.
    """
    modules = ("crud.py", "evolutions.py", "mise_a_jour.py")
    for nom in modules:
        source = (_APP / "routers" / "tickets" / nom).read_text(encoding="utf-8")
        conditions = _conditions_de_partage(ast.parse(source))
        assert conditions, (
            f"Aucune condition portant `partager_whatsapp` dans tickets/{nom} : "
            "soit le partage n'y est plus gardé, soit le contrôle a perdu sa "
            "portée — dans les deux cas, ne pas lire ce test comme vert."
        )
        for condition in conditions:
            assert "not reservee_au_conseil(ticket)" in condition, (
                f"tickets/{nom} : un ticket réservé au conseil syndical peut partir "
                "sur le groupe WhatsApp de tous les résidents. La condition doit "
                "porter `not reservee_au_conseil(ticket)` — la règle unique, qui "
                f"contient le drapeau ET le défaut de la catégorie. Trouvée : {condition}"
            )


def test_le_schema_de_creation_de_ticket_porte_le_canal_whatsapp():
    """Le champ doit exister — c'est lui qui manquait, et rien ne le signalait."""
    source = (_APP / "schemas.py").read_text(encoding="utf-8")
    arbre = ast.parse(source)
    classes = {
        n.name: {c.target.id for c in n.body if isinstance(c, ast.AnnAssign)}
        for n in ast.walk(arbre)
        if isinstance(n, ast.ClassDef)
    }
    assert "TicketCreate" in classes, "TicketCreate introuvable dans schemas.py"
    champs = classes["TicketCreate"]
    #  Les trois canaux voyagent ensemble : en perdre un se voit ici, pas à l'écran.
    for canal in ("partager_whatsapp", "destinataire_syndic", "destinataire_cs"):
        assert canal in champs, (
            f"`{canal}` absent de TicketCreate — un canal de notification a disparu "
            "du contrat d'entrée ; l'interface l'affichera sans effet."
        )


# ── #1164 : TOUTES les portes d'envoi d'une affaire, pas seulement la création ──
#
#  🔴 Le 23/09/2026 : la création réservait WhatsApp et le courriel externe au
#  conseil — et le contrôle de la création ne regardait QUE `crud.py`. Une
#  Suite (`evolutions.py`) et un message (`messages.py`) laissaient l'auteur, ou n'importe quel résident
#  qui voit l'affaire, publier sur le groupe des résidents et écrire à une
#  adresse quelconque depuis celle du site. Un contrôle limité à une porte
#  garde cette porte-là.
#
#  ⚠️ Et `_gardes_des_envois` ne relève un envoi que s'il est sous un `if`
#  (`and pile`) : un envoi SANS AUCUNE condition lui échappe entièrement. Le
#  relevé ci-dessous garde aussi les envois nus — c'est le cas le plus grave.

#: Ce qui part hors de l'application vers un public que l'auteur choisit.
_ENVOIS_RESERVES = _ENVOIS + ("envoyer_email_externe", "diffuser_actualite")

#: Le module qui DÉFINIT les envois : la garde se lit au point d'APPEL, pas dans
#: la fonction qui envoie. Déclaré, et le test échoue s'il cesse d'exister.
_MODULES_DEFINISSANT = {"courriels.py", "actualite.py", "groupe.py"}


def _envois_et_gardes(fonction: ast.AST, noms: tuple[str, ...]) -> list[tuple[int, str]]:
    """Chaque envoi (ligne) avec la conjonction de ses conditions — vide s'il est nu."""
    trouves: list[tuple[int, str]] = []

    def descendre(noeud: ast.AST, pile: list[str]) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, ast.If):
                condition = _condition_resolue(fonction, enfant.test)
                for instruction in enfant.body:
                    descendre(instruction, pile + [condition])
                for instruction in enfant.orelse:
                    descendre(instruction, pile)
                continue
            if isinstance(enfant, ast.Call) and any(
                n in ast.unparse(enfant.func) or n in ast.unparse(enfant) for n in noms
            ):
                trouves.append((enfant.lineno, " et ".join(pile)))
                continue
            descendre(enfant, pile)

    descendre(fonction, [])
    return trouves


def _garde_de_role(condition: str) -> bool:
    """Deux formes valables du MÊME contrôle : `est_moderateur(user)`, le prédicat
    central (depuis le 16/08/2026 — la règle était recopiée à côté de chaque
    champ), ou `has_role(conseil_syndical, admin)` écrit sur place. Ce que
    `est_moderateur` contient est vérifié par
    `test_moderateur_source_unique.py::test_la_source_existe_encore`."""
    return "est_moderateur" in condition or (
        "has_role" in condition and "conseil_syndical" in condition and "admin" in condition
    )


def _envois_reserves_non_gardes(source: str, fichier: str) -> list[str]:
    fautes = []
    for fonction in ast.walk(ast.parse(source)):
        if isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for ligne, garde in _envois_et_gardes(fonction, _ENVOIS_RESERVES):
                if not _garde_de_role(garde):
                    fautes.append(
                        f"{fichier}:{ligne} ({fonction.name}) — garde : {garde or 'AUCUNE'}"
                    )
    return fautes


def test_toutes_les_portes_d_une_affaire_reservent_whatsapp_et_l_externe_au_cs():
    dossier = _APP / "routers" / "tickets"
    modules = sorted(p for p in dossier.glob("*.py") if p.name not in _MODULES_DEFINISSANT)
    assert len(modules) >= 8, f"Portée cassée : {len(modules)} module(s) sous {dossier}."
    for nom in _MODULES_DEFINISSANT:
        assert (dossier / nom).exists(), f"`{nom}` déclaré comme module d'envoi, introuvable."

    appels = 0
    liste: list[str] = []
    for p in modules:
        source = p.read_text(encoding="utf-8")
        arbre = ast.parse(source)
        for f in ast.walk(arbre):
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                appels += len(_envois_et_gardes(f, _ENVOIS_RESERVES))
        liste += _envois_reserves_non_gardes(source, p.name)
    #  Cas zéro : un motif qui ne reconnaît plus aucun envoi rendrait vert sans
    #  rien avoir lu. Création, Suite, message, PATCH : au moins quatre.
    assert appels >= 4, f"Seulement {appels} envoi(s) relevé(s) — le relevé est cassé."
    assert not liste, (
        "Envoi WhatsApp ou courriel externe accessible hors du conseil syndical "
        "(#1164) — la garde doit porter `est_moderateur(user)` :\n  " + "\n  ".join(liste)
    )


def test_le_releve_voit_un_envoi_nu_et_un_envoi_mal_garde():
    """Le contrôle s'éprouve : sans ces deux cas, il pourrait être vert par cécité."""
    nu = "def f(body, user):\n    envoyer_email_externe(body.email_externe)\n"
    mal = (
        "def f(body, user, ticket):\n"
        "    ok = body.partager_whatsapp and not ticket.confidentiel\n"
        "    if ok:\n        envoyer_whatsapp_avec_log('x')\n"
    )
    bon = (
        "def f(body, user):\n"
        "    est_cs = est_moderateur(user)\n"
        "    if body.email_externe and est_cs:\n        envoyer_email_externe(body.email_externe)\n"
    )
    assert _envois_reserves_non_gardes(nu, "nu.py"), "un envoi sans condition doit être refusé"
    assert _envois_reserves_non_gardes(mal, "mal.py"), "une garde sans rôle doit être refusée"
    assert not _envois_reserves_non_gardes(bon, "bon.py"), "la garde par est_moderateur doit passer"
