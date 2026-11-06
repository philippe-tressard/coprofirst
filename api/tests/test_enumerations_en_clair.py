"""Une énumération ne se montre jamais BRUTE à une personne : ni dans un courriel, ni dans une notification.

## Pourquoi ce test (05/11/2026, signalé à l'écran)

Admin › Télémétrie affichait « copropriétaire_résident » dans la colonne Type.
Côté front, `lint:categorie-brute` tient cette règle ; côté serveur, rien ne la
tenait, et la recherche a trouvé la même valeur brute dans ce que l'API
COMPOSE elle-même :

    sonner(titre=f"Nouvelle demande de {body.type}")          → « … de vigik »
    sonner_systeme(titre=f"Commande {cmd.type} : {valeur(cmd.statut)}")
                                                               → « Commande vigik : acceptee »
    context={"type": cmd.type}                                 → le courriel « Votre demande de telecommande »
    context={"utilisateur": …, statut=str(valeur(user.statut))}
    context={"ticket": {…, "categorie": ticket.categorie}}     → « etude_travaux » dans un courriel

Un slug avec un tiret bas est un nom interne. Le libellé existe pour chacun
(`roles_libelles`, `categories_ticket`, `types_acces`, `libelles_lot`) ; rien
n'obligeait à le prendre.

## Ce qu'il refuse

Dans `app/routers/` et `app/utils/` — là où l'API compose ce qu'une personne lit :

1. une **f-string** qui interpole `x.type`, `x.statut`, `x.categorie`, `x.role`,
   `x.priorite` ou `x.etat` tel quel, ou par `valeur(x.statut)`, ou `x.etat.value` ;
2. le **`context=`** d'un `send_email` / `send_email_group` dont une valeur, à
   quelque profondeur, est l'un de ces attributs tel quel.

Il ne regarde ni une comparaison, ni une clé de dictionnaire, ni un champ de
réponse JSON : servir un CODE à un client est normal — c'est lui qui le traduit
(`LotRead.libelle_type` à côté de `type`). Seul ce que l'API ÉCRIT pour un humain
est en cause.

## Les exceptions — déclarées, avec leur raison

Une interpolation qui n'est pas lue par une personne se déclare dans
`EXCEPTIONS`, par module et par texte exact. Une exception qui ne sert plus
fait échouer le test : une exception périmée est un oubli qui ressemble à une
décision.
"""

from __future__ import annotations

import ast

from tests.aides_sources import modules_app

#: Les champs dont la valeur est une énumération (`models/*` : `class X(str, Enum)`).
CHAMPS = frozenset({"type", "statut", "categorie", "role", "priorite", "etat"})

#: Les fonctions dont le `context=` nourrit un gabarit lu par une personne.
ENVOIS = frozenset({"send_email", "send_email_group"})

#: module → { texte de l'interpolation : raison }. Le texte est celui de
#: `ast.unparse` sur l'expression interpolée.
EXCEPTIONS: dict[str, dict[str, str]] = {
    "utils/sources_affiche.py": {
        "self.type": "une CLÉ technique (`type:id`), lue par un `<select>`, jamais affichée",
    },
}


def _attribut_enum(noeud: ast.AST) -> ast.AST | None:
    """L'expression fautive si `noeud` rend une énumération brute, sinon `None`."""
    #  x.statut.value → on juge `x.statut`
    if isinstance(noeud, ast.Attribute) and noeud.attr == "value":
        noeud = noeud.value
    #  valeur(x.statut), str(valeur(x.statut)), str(x.statut)
    while (
        isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id in {"valeur", "str"}
        and len(noeud.args) == 1
    ):
        noeud = noeud.args[0]
    if isinstance(noeud, ast.Attribute) and noeud.attr in CHAMPS:
        return noeud
    return None


def _dans_les_f_strings(arbre: ast.AST) -> list[tuple[int, str]]:
    trouves = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.JoinedStr):
            continue
        for partie in n.values:
            if isinstance(partie, ast.FormattedValue):
                fautif = _attribut_enum(partie.value)
                if fautif is not None:
                    trouves.append((n.lineno, ast.unparse(fautif)))
    return trouves


def _valeurs_du_dict(d: ast.AST):
    """Les valeurs d'un dictionnaire littéral, dictionnaires imbriqués compris."""
    if not isinstance(d, ast.Dict):
        return
    for v in d.values:
        if v is None:
            continue
        if isinstance(v, ast.Dict):
            yield from _valeurs_du_dict(v)
        else:
            yield v


def _dans_les_contextes(arbre: ast.AST) -> list[tuple[int, str]]:
    trouves = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call):
            continue
        nom = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
        if nom not in ENVOIS:
            continue
        for kw in n.keywords:
            if kw.arg != "context":
                continue
            for v in _valeurs_du_dict(kw.value):
                fautif = _attribut_enum(v)
                if fautif is not None:
                    trouves.append((v.lineno, ast.unparse(fautif)))
    return trouves


def _releve() -> dict[str, list[tuple[int, str]]]:
    releve: dict[str, list[tuple[int, str]]] = {}
    for module in (*modules_app("routers"), *modules_app("utils")):
        trouves = _dans_les_f_strings(module.arbre) + _dans_les_contextes(module.arbre)
        if trouves:
            releve[module.rel] = sorted(trouves)
    return releve


def test_aucune_enumeration_brute_dans_un_texte_ou_un_courriel():
    releve = _releve()
    fautes = []
    for rel, trouves in releve.items():
        admis = EXCEPTIONS.get(rel, {})
        for ligne, texte in trouves:
            if texte not in admis:
                fautes.append(f"{rel}:{ligne} — {{{texte}}}")
    assert not fautes, (
        "Une énumération est écrite BRUTE dans un texte lu par une personne — "
        "prendre son libellé (`libelle_statut`, `libelle_categorie`, `libelle_type_acces`, "
        "`libelle_type_lot`…) :\n  " + "\n  ".join(fautes)
    )


def test_les_exceptions_servent_encore():
    releve = _releve()
    perimees = []
    for rel, admis in EXCEPTIONS.items():
        textes = {texte for _, texte in releve.get(rel, [])}
        for texte in admis:
            if texte not in textes:
                perimees.append(f"{rel} — {{{texte}}}")
    assert not perimees, (
        "Exception(s) de EXCEPTIONS qui ne servent plus — à retirer :\n  " + "\n  ".join(perimees)
    )


def test_le_releve_sait_lire_les_formes_connues():
    """Le cas zéro : chaque forme que ce test a trouvée le 05/11/2026 est encore reconnue."""
    source = (
        'a = f"Nouvelle demande de {body.type}"\n'
        'b = f"Commande {cmd.type} : {valeur(cmd.statut)}"\n'
        'c = f"état inconnu : {inst.etat.value}"\n'
        'd = f"{str(user.statut)}"\n'
        'send_email(code="x", to=t, context={"ticket": {"categorie": ticket.categorie}, "type": cmd.type})\n'
        'ok = f"{libelle_statut(user.statut)} {nom} {lot.numero}"\n'
        'send_email(code="y", to=t, context={"ticket": {"categorie": libelle_categorie(ticket.categorie)}})\n'
    )
    arbre = ast.parse(source)
    assert [t for _, t in _dans_les_f_strings(arbre)] == [
        "body.type",
        "cmd.type",
        "cmd.statut",
        "inst.etat",
        "user.statut",
    ]
    assert [t for _, t in _dans_les_contextes(arbre)] == ["ticket.categorie", "cmd.type"]
