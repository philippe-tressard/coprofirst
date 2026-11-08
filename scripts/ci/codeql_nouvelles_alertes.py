#!/usr/bin/env python3
"""Les alertes CodeQL qu'une PR vers `dev` AJOUTE, jugées avant la PR dev→main (#2571).

POURQUOI — CodeQL tourne en « configuration par défaut » de GitHub, qui n'analyse que
les PR vers la branche par défaut (`main`). Une alerte neuve n'apparaissait donc qu'à la
PR dev→main, quand tout le cycle de la MEP était engagé : le ReDoS de #2569 en a coûté
un complet (~45 min). `.github/workflows/codeql-avant-dev.yml` analyse la PR vers `dev`
SANS envoyer le résultat — GitHub refuse un envoi d'une analyse « avancée » tant que la
configuration par défaut est active —, et ce script compare ce résultat à la dernière
analyse de `main`, lue par l'API.

LA COMPARAISON — par (règle, fichier) et par COMPTE : une alerte est neuve quand la PR
en porte plus que `main` pour la même règle dans le même fichier. Ni la ligne (elle bouge
au moindre ajout au-dessus), ni le libellé (il change d'une version de CodeQL à l'autre)
n'entrent dans la clé. Ce que cela ne voit pas, et c'est assumé : une alerte corrigée et
une autre ajoutée, même règle, même fichier, dans la même PR — la PR dev→main la verra.
L'empreinte de ligne (`primaryLocationLineHash`), quand les deux côtés la portent, ne sert
qu'à NOMMER les résultats neufs ; sans elle, tous ceux de la clé sont cités.

CE QUI BLOQUE — le seuil par défaut du contrôle de GitHub, pour ne refuser sur `dev` que
ce que `main` refuserait : une alerte de SÉCURITÉ (elle porte `security-severity`) à 7,0
ou plus (élevée, critique) ; une alerte ordinaire au niveau `error`. Le reste s'affiche en
avertissement, sans bloquer.

Une référence absente ou illisible rend INCONNU — code 2 —, jamais « aucune alerte neuve »
(`standards/04` §1) : une comparaison à rien dirait toujours oui.

Usage : codeql_nouvelles_alertes.py <sarif de la PR> <sarif de référence (main)>
        codeql_nouvelles_alertes.py --selftest
Codes : 0 rien de bloquant · 1 au moins une alerte neuve bloquante · 2 INCONNU
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from collections import Counter

#: Seuil de GitHub pour une alerte de sécurité : « High or higher ».
SEUIL_SECURITE = 7.0


class Inconnu(Exception):
    """La comparaison ne peut pas se faire : fichier absent, illisible ou sans analyse."""


def _regles(run: dict) -> dict[str, dict]:
    """Descripteur de chaque règle, par identifiant — pilote et extensions (packs)."""
    outil = run.get("tool") or {}
    composants = [outil.get("driver") or {}, *(outil.get("extensions") or [])]
    return {r["id"]: r for c in composants for r in c.get("rules") or [] if "id" in r}


def _chemin(resultat: dict) -> str:
    try:
        return resultat["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    except (KeyError, IndexError, TypeError):
        return "?"


def _ligne(resultat: dict) -> int:
    try:
        return int(resultat["locations"][0]["physicalLocation"]["region"]["startLine"])
    except (KeyError, IndexError, TypeError, ValueError):
        return 1


def lire_resultats(sarif: dict) -> list[dict]:
    """Chaque résultat, aplati : règle, fichier, ligne, empreinte, message, s'il bloque."""
    if not isinstance(sarif, dict) or not isinstance(sarif.get("runs"), list) or not sarif["runs"]:
        raise Inconnu("SARIF sans analyse (`runs` absent ou vide)")
    lus = []
    for run in sarif["runs"]:
        regles = _regles(run)
        for r in run.get("results") or []:
            regle_id = r.get("ruleId") or (r.get("rule") or {}).get("id") or "?"
            regle = regles.get(regle_id, {})
            proprietes = regle.get("properties") or {}
            niveau = r.get("level") or (regle.get("defaultConfiguration") or {}).get("level")
            gravite = proprietes.get("security-severity")
            if gravite is not None:
                bloque = float(gravite) >= SEUIL_SECURITE
            else:
                bloque = (niveau or "warning") == "error"
            lus.append(
                {
                    "regle": regle_id,
                    "chemin": _chemin(r),
                    "ligne": _ligne(r),
                    "empreinte": (r.get("partialFingerprints") or {}).get(
                        "primaryLocationLineHash"
                    ),
                    "message": ((r.get("message") or {}).get("text") or "").strip(),
                    "gravite": gravite,
                    "bloque": bloque,
                }
            )
    return lus


def nouvelles_alertes(pr: list[dict], reference: list[dict]) -> list[dict]:
    """Les résultats de la PR qui n'existent pas sur la référence (fonction PURE)."""
    compte_ref = Counter((r["regle"], r["chemin"]) for r in reference)
    empreintes_ref = {r["empreinte"] for r in reference if r["empreinte"]}
    par_cle: dict[tuple[str, str], list[dict]] = {}
    for r in pr:
        par_cle.setdefault((r["regle"], r["chemin"]), []).append(r)
    neuves = []
    for cle, resultats in sorted(par_cle.items()):
        if len(resultats) <= compte_ref[cle]:
            continue
        nommes = [r for r in resultats if r["empreinte"] and r["empreinte"] not in empreintes_ref]
        neuves.extend(nommes or resultats)
    return neuves


def _annotation(r: dict) -> str:
    niveau = "error" if r["bloque"] else "warning"
    gravite = f", gravité {r['gravite']}" if r["gravite"] is not None else ""
    message = r["message"].replace("%", "%25").replace("\r", "").replace("\n", " ")
    return (
        f"::{niveau} file={r['chemin']},line={r['ligne']},title=CodeQL {r['regle']}{gravite}"
        f"::{message}"
    )


def _lire(chemin: str) -> dict:
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise Inconnu(f"{chemin} illisible : {e}") from e


def juger(chemin_pr: str, chemin_ref: str) -> int:
    try:
        pr = lire_resultats(_lire(chemin_pr))
        reference = lire_resultats(_lire(chemin_ref))
    except Inconnu as e:
        print(f"::error title=CodeQL avant dev — INCONNU::{e}")
        return 2
    neuves = nouvelles_alertes(pr, reference)
    for r in neuves:
        print(_annotation(r))
    bloquantes = [r for r in neuves if r["bloque"]]
    print(
        f"CodeQL : {len(pr)} résultat(s) sur la PR, {len(reference)} sur main ; "
        f"{len(neuves)} neuf(s), dont {len(bloquantes)} bloquant(s)."
    )
    return 1 if bloquantes else 0


def _selftest() -> int:
    def sarif(*resultats, regles=None):
        return {
            "runs": [
                {
                    "tool": {"driver": {"rules": []}, "extensions": [{"rules": regles or []}]},
                    "results": list(resultats),
                }
            ]
        }

    def res(regle, chemin, ligne, empreinte=None, niveau=None):
        r = {
            "ruleId": regle,
            "message": {"text": f"{regle} ici"},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": chemin},
                        "region": {"startLine": ligne},
                    }
                }
            ],
        }
        if empreinte:
            r["partialFingerprints"] = {"primaryLocationLineHash": empreinte}
        if niveau:
            r["level"] = niveau
        return r

    regles = [
        {"id": "py/redos", "properties": {"security-severity": "7.5"}},
        {"id": "py/faible", "properties": {"security-severity": "5.0"}},
        {"id": "py/ordinaire", "defaultConfiguration": {"level": "warning"}},
        {"id": "py/erreur", "defaultConfiguration": {"level": "error"}},
    ]
    ref = sarif(res("py/redos", "a.py", 10, "h1"), regles=regles)
    cas = [
        #  (nom, sarif de la PR, nombre de neuves, nombre de bloquantes)
        ("identique, ligne déplacée", sarif(res("py/redos", "a.py", 40, "h1"), regles=regles), 0, 0),
        ("ReDoS neuf, autre fichier (#2569)", sarif(res("py/redos", "a.py", 10, "h1"),
                                                  res("py/redos", "b.py", 3, "h2"), regles=regles), 1, 1),
        ("second ReDoS, même fichier", sarif(res("py/redos", "a.py", 10, "h1"),
                                           res("py/redos", "a.py", 20, "h3"), regles=regles), 1, 1),
        ("sécurité moyenne : affichée, non bloquante",
         sarif(res("py/redos", "a.py", 10), res("py/faible", "c.py", 1), regles=regles), 1, 0),
        ("ordinaire au niveau warning : non bloquante",
         sarif(res("py/redos", "a.py", 10), res("py/ordinaire", "c.py", 1), regles=regles), 1, 0),
        ("ordinaire au niveau error : bloquante",
         sarif(res("py/redos", "a.py", 10), res("py/erreur", "c.py", 1), regles=regles), 1, 1),
        ("niveau du résultat prime sur la règle",
         sarif(res("py/redos", "a.py", 10), res("py/ordinaire", "c.py", 1, niveau="error"),
               regles=regles), 1, 1),
        ("alerte corrigée : rien de neuf", sarif(regles=regles), 0, 0),
    ]
    echecs = 0
    for nom, pr, attendu_neuves, attendu_bloquantes in cas:
        neuves = nouvelles_alertes(lire_resultats(pr), lire_resultats(ref))
        obtenu = (len(neuves), sum(r["bloque"] for r in neuves))
        if obtenu != (attendu_neuves, attendu_bloquantes):
            print(f"ÉCHEC {nom} : {obtenu} au lieu de {(attendu_neuves, attendu_bloquantes)}")
            echecs += 1
    #  Second ReDoS du même fichier : c'est l'empreinte inconnue qui est NOMMÉE.
    pr = sarif(res("py/redos", "a.py", 10, "h1"), res("py/redos", "a.py", 20, "h3"), regles=regles)
    nommees = nouvelles_alertes(lire_resultats(pr), lire_resultats(ref))
    if [r["ligne"] for r in nommees] != [20]:
        print(f"ÉCHEC empreinte : lignes nommées {[r['ligne'] for r in nommees]} au lieu de [20]")
        echecs += 1
    #  INCONNU : une référence vide ou sans analyse n'est jamais « rien de neuf ».
    for illisible in ({}, {"runs": []}, [], {"runs": "x"}):
        try:
            lire_resultats(illisible)
        except Inconnu:
            continue
        print(f"ÉCHEC INCONNU : {illisible!r} lu comme une analyse")
        echecs += 1
    #  Sortie tue : une annotation `::error` lue dans le job des self-tests serait un faux rouge.
    with contextlib.redirect_stdout(io.StringIO()):
        code_absent = juger("/chemin/absent.sarif", "/chemin/absent.sarif")
    if code_absent != 2:
        print("ÉCHEC INCONNU : un fichier absent ne rend pas le code 2")
        echecs += 1
    total = len(cas) + 6
    print(f"selftest codeql_nouvelles_alertes : {total - echecs}/{total} OK")
    return 1 if echecs else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(_selftest())
    if len(sys.argv) != 3:
        print(__doc__.split("Usage :")[1].split("Codes")[0].strip(), file=sys.stderr)
        sys.exit(2)
    sys.exit(juger(sys.argv[1], sys.argv[2]))
