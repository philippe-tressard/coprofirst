"""Les fichiers de gouvernance disent la vérité sur la licence (#1033).

## Pourquoi ce contrôle — 🔴 RANG 1 (`standards/14`)

`CONTRIBUTING.md` promettait, en toutes lettres et depuis l'origine du dépôt, que
« *contributions will be licensed under the MIT License* ». Le dépôt était alors
sous Licence 5Hostachy — source-available, clauses commerciales — et il est,
depuis le 08/10/2026 (#1726), sous **AGPL-3.0-or-later**.
Un contributeur qui s'y fiait cédait son travail sous une attente **inverse** de
la licence réelle.

Ce n'était pas une faute d'inattention isolée : rien, nulle part, ne confrontait
le nom de licence écrit dans les fichiers publics à celui que le dépôt accorde.
`reuse lint` vérifie que chaque fichier **porte** une licence, jamais que les
textes publics **nomment** la bonne.

## Ce que le contrôle confronte

| Source de vérité | Ce qu'elle porte |
|---|---|
| `REUSE.toml` | l'identifiant SPDX réellement accordé (`AGPL-3.0-or-later`) |
| `LICENSES/<identifiant>.txt` | le texte, exigé par REUSE à cet emplacement |
| `LICENSE` | le même texte, au nom que GitHub reconnaît |

Le nom de la licence n'est **pas écrit ici** : il est dérivé de `REUSE.toml`.
Un nom recopié dans un test diverge le jour où la licence change, et le contrôle
défendrait alors l'ancienne (`standards/13` §1).

## Les deux copies du texte, et pourquoi elles restent

Le texte de licence existe en **deux exemplaires identiques**. C'est une
duplication, et elle est **imposée de l'extérieur** : GitHub ne reconnaît que
`LICENSE`, REUSE n'accepte que `LICENSES/<SPDX>.txt`. Il y en avait trois sous
la Licence 5Hostachy, qui exigeait en plus de conserver `LICENSE-5Hostachy.md`.

Ce qui peut être supprimé, ce n'est pas la copie — c'est la **divergence** :
`test_les_trois_copies_de_la_licence_sont_identiques` échoue à l'octet près. Une
licence modifiée à deux endroits sur trois est exactement le défaut que
`REUSE.toml` avait déjà connu avec ses douze motifs (#774).

## Français exclusif

`CONTRIBUTING.md` et `SECURITY.md` étaient intégralement en anglais alors que la
consigne du poste est « français exclusif », et que `README.md`, `NOTICE.md` et
`LICENSE` le respectaient. La règle n'avait aucun garde-fou : elle tenait sur
l'attention de qui écrivait.

Le contrôle ne juge pas une langue — il compte des mots **exclusivement**
anglais, hors blocs de code, liens et URL. Calibré avant d'être écrit : 0
occurrence sur les trois fichiers français, 33 et 23 sur les deux anglais.
"""

from __future__ import annotations

import pathlib
import re
import sys

import yaml

_RACINE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "scripts" / "ci"))

from licences_spdx import licence_du_projet  # noqa: E402

#: Le descriptif « About » du dépôt sur GitHub, versionné (#1771). C'est le
#: premier texte public qu'on lit du projet, et il disait encore « Licence
#: 5Hostachy (source-available… + clauses commerciales) » le 09/10/2026, un
#: jour après le passage à l'AGPL : rien ne le confrontait à la licence. Il est
#: jugé ici comme les autres fichiers publics ; `scripts/ci/descriptif_depot.py`
#: vérifie en CI que GitHub affiche bien CE texte.
DESCRIPTIF = ".github/descriptif-depot.txt"

#: Les fichiers publics qui *parlent* de la licence et de la méthode du projet.
#:
#: `LICENSE` n'en fait plus partie (#1726) : c'est le texte OFFICIEL de
#: l'AGPL, en anglais — la FSF ne reconnaît aucune traduction, et le modifier
#: pour le franciser le rendrait faux. Il est tenu à l'octet près par
#: `test_les_copies_de_la_licence_sont_identiques`, et sa nature par
#: `test_le_texte_de_licence_est_celui_de_l_identifiant`.
GOUVERNANCE = ("README.md", "CONTRIBUTING.md", "SECURITY.md", "NOTICE.md", DESCRIPTIF)

#: Les licences qu'un fichier de gouvernance ne peut pas promettre, puisque le
#: dépôt ne les accorde pas.
#:
#: `AGPL` n'y est pas : c'est la licence accordée depuis le 08/10/2026 (#1726).
#:
#: ⚠️ Le jour où `NOTICE.md` devrait nommer la licence d'une dépendance tierce,
#: ce test échouerait — et l'exception s'écrirait alors, avec sa raison et sa
#: date (`standards/05` §2). Ce jour est venu : voir `SECTIONS_TIERS`.
LICENCES_NON_ACCORDEES = (
    "MIT",
    "Apache",
    "BSD",
    "ISC",
    "LGPL",
    "MPL",
    "Unlicense",
    "WTFPL",
    "CC0",
    "Creative Commons",
)

#: L'exception, et la seule (#1542, #1543 — 02/10/2026) : la section de
#: `NOTICE.md` qui NOMME les composants tiers. Elle cite des licences que le
#: dépôt n'accorde pas — il les REÇOIT avec les icônes Lucide, le logo WhatsApp
#: et les bibliothèques ; les taire serait la faute, ISC et MIT exigeant que
#: leur mention accompagne chaque copie. Le reste du fichier reste contrôlé, et
#: le test échoue si la section disparaît : une exception qui ne sert plus se
#: retire.
SECTIONS_TIERS = {"NOTICE.md": "## 6. Composants tiers"}

#: Ce qui décrit l'ANCIENNE licence (« Licence 5Hostachy », jusqu'à la 2.115.0)
#: — des mots qu'aucun identifiant SPDX ne porte, donc que
#: `LICENCES_NON_ACCORDEES` ne voyait pas : le descriptif GitHub les a gardés
#: un jour entier après le changement (#1771). « AGPL-like » y est : une
#: licence « comme » l'AGPL n'est pas l'AGPL.
REGIMES_NON_ACCORDES = (
    r"source[- ]available",
    r"clauses? (?:d'usage )?commercial(?:e|es)?\b",
    r"Licence 5Hostachy",
    r"\w*GPL-like",
)

#: L'exception, et la seule : la section de `NOTICE.md` qui RACONTE le
#: changement de licence. Les versions jusqu'à la 2.115.0 restent sous
#: l'ancienne ; la nommer y est une obligation, pas un oubli.
SECTIONS_HISTORIQUE = {"NOTICE.md": "## 2. Changement de licence (08/10/2026)"}

#: GitHub refuse un descriptif plus long.
LONGUEUR_MAX_DESCRIPTIF = 350

#: Un numéro de version : le descriptif n'est pas bumpé avec `package.json`, et
#: celui du 09/10/2026 disait « v1.0.0 » pour la v2.122.0.
VERSION = r"\bv?\d+\.\d+(?:\.\d+)?\b"

#: Mots dont aucun n'a de sens en français. Ils ne mesurent pas un style : leur
#: présence dit qu'une phrase entière est en anglais.
MOTS_ANGLAIS = (
    r"\b(the|you|your|this|these|with|will|and|for|from|that|are|have|our"
    r"|use|using|when|where|which|please)\b"
)


def _lire(chemin: str) -> str:
    fichier = _RACINE / chemin
    assert fichier.exists(), (
        f"{chemin} introuvable — le contrôle a perdu sa portée, "
        "il ne devient pas vert pour autant (`standards/04` §1)"
    )
    return fichier.read_text(encoding="utf-8")


def _prose_seule(texte: str) -> str:
    """Le texte sans ce qui n'est pas de la prose : code, URL — **pas** les libellés.

    Un bloc ```bash``, un `cp .env.example .env` ou un `example.com` ne sont pas
    de l'anglais — ce sont des identifiants techniques, que la consigne laisse
    tels quels.

    🔴 Le libellé d'un lien markdown est de la prose, et de la prose lue. Une
    première version de cette fonction jetait `[texte](url)` en entier : le
    « MIT » de `[MIT License](LICENSE)` disparaissait donc **avant** le
    contrôle, qui passait au vert sur le défaut même qu'il devait attraper. Le
    cas zéro l'a montré — c'est pour ça qu'on l'écrit d'abord
    (`standards/04` §2).
    """
    texte = re.sub(r"```.*?```", " ", texte, flags=re.S)
    texte = re.sub(r"`[^`]*`", " ", texte)
    texte = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", texte)
    texte = re.sub(r"https?://\S+", " ", texte)
    return texte


def _sans_section(nom: str, texte: str, sections: dict[str, str] = SECTIONS_TIERS) -> str:
    """Le texte privé de la section que `sections` lui déclare en exception, s'il en a une."""
    titre = sections.get(nom)
    if titre is None:
        return texte
    debut = texte.find(f"\n{titre}\n")
    assert debut >= 0, f"{nom} n'a plus de section « {titre} » : retirer son exception"
    suite = texte.find("\n## ", debut + len(titre) + 1)
    return texte[:debut] + ("" if suite < 0 else texte[suite:])


def identifiant_spdx_accorde() -> str:
    """L'identifiant que le dépôt accorde réellement, lu dans `REUSE.toml`."""
    return licence_du_projet(_lire("REUSE.toml"))


def nom_lisible_de_la_licence() -> str:
    """« GNU AFFERO GENERAL PUBLIC LICENSE » — le titre du texte, pas une constante."""
    return _lire("LICENSE").splitlines()[0].strip()


def test_aucun_fichier_public_ne_promet_une_licence_non_accordee():
    """Le défaut exact du 19/09/2026 : « MIT » dans `CONTRIBUTING.md`."""
    fautes = []
    for nom in GOUVERNANCE:
        prose = _prose_seule(_sans_section(nom, _lire(nom)))
        for licence in LICENCES_NON_ACCORDEES:
            for trouve in re.finditer(rf"\b{re.escape(licence)}\b", prose, re.I):
                debut = max(0, trouve.start() - 60)
                fautes.append(f"  {nom} : …{prose[debut : trouve.end() + 40].strip()}…")

    assert not fautes, (
        "Un fichier public nomme une licence que le dépôt n'accorde pas "
        f"(il accorde « {nom_lisible_de_la_licence()} », "
        f"SPDX {identifiant_spdx_accorde()}) :\n" + "\n".join(fautes)
    )


def _regimes_non_accordes(texte: str) -> list[re.Match]:
    return [t for motif in REGIMES_NON_ACCORDES for t in re.finditer(motif, texte, re.I)]


def test_aucun_fichier_public_ne_decrit_l_ancienne_licence():
    """Le défaut exact du 09/10/2026 : le descriptif GitHub, resté source-available."""
    fautes = []
    for nom in GOUVERNANCE:
        prose = _prose_seule(_sans_section(nom, _lire(nom), SECTIONS_HISTORIQUE))
        for trouve in _regimes_non_accordes(prose):
            debut = max(0, trouve.start() - 60)
            fautes.append(f"  {nom} : …{prose[debut : trouve.end() + 40].strip()}…")

    assert not fautes, (
        "Un fichier public décrit l'ancienne licence — le dépôt accorde "
        f"{identifiant_spdx_accorde()} depuis la 2.116.0 :\n" + "\n".join(fautes)
    )


def _sans_licence(texte: str) -> str:
    """Le texte sans l'identifiant de licence, dont le « 3.0 » n'est pas une version."""
    return texte.replace(identifiant_spdx_accorde(), " ")


def test_les_motifs_attrapent_le_descriptif_du_09_10():
    """Cas témoin : le texte fautif lui-même est refusé, motif par motif (`standards/04` §2)."""
    fautif = (
        "Application de gestion des résidents pour une copropriété multi-bâtiments "
        "avec syndic — v1.0.0, Licence 5Hostachy (source-available, copyleft "
        "AGPL-like + clauses commerciales)"
    )
    for motif in REGIMES_NON_ACCORDES:
        assert re.search(motif, fautif, re.I), f"le motif {motif!r} ne sert plus"
    assert re.search(VERSION, _sans_licence(fautif))
    assert not re.search(
        VERSION, _sans_licence(f"Logiciel libre sous {identifiant_spdx_accorde()}")
    )


def test_le_descriptif_github_nomme_la_licence_et_aucune_version():
    """Le premier texte qu'on lit du projet dit sa licence, et rien qui se périme."""
    descriptif = _lire(DESCRIPTIF).strip()
    spdx = identifiant_spdx_accorde()
    assert descriptif, f"{DESCRIPTIF} est vide : GitHub n'afficherait aucune licence"
    assert "\n" not in descriptif, f"{DESCRIPTIF} : GitHub n'affiche qu'une ligne"
    assert len(descriptif) <= LONGUEUR_MAX_DESCRIPTIF, (
        f"{DESCRIPTIF} : {len(descriptif)} caractères, GitHub en accepte {LONGUEUR_MAX_DESCRIPTIF}"
    )
    assert spdx in descriptif, f"{DESCRIPTIF} ne nomme pas la licence accordée, « {spdx} »"
    version = re.search(VERSION, _sans_licence(descriptif))
    assert not version, (
        f"{DESCRIPTIF} porte un numéro de version (« {version.group(0)} ») : "
        "il n'est pas bumpé avec le projet, et se périme à la version suivante"
    )


def test_contributing_nomme_la_licence_reelle_et_son_fichier():
    """Ne pas promettre MIT ne suffit pas : il faut dire ce qui s'applique.

    Le nom cherché est l'identifiant SPDX de `REUSE.toml` : le titre du texte
    officiel est en capitales anglaises, qu'un document français ne recopie pas.
    """
    contributing = _lire("CONTRIBUTING.md")
    spdx = identifiant_spdx_accorde()
    assert spdx in contributing, (
        f"CONTRIBUTING.md ne nomme pas « {spdx} » : un contributeur ne peut pas "
        "savoir sous quelle licence son travail est versé"
    )

    liens = re.findall(r"\]\(([^)]*LICENSE[^)]*)\)", contributing)
    assert liens, "CONTRIBUTING.md ne renvoie vers aucun fichier de licence"
    for lien in liens:
        cible = _RACINE / lien.split("#")[0]
        assert cible.exists(), f"CONTRIBUTING.md renvoie vers « {lien} », qui n'existe pas"


def test_les_copies_de_la_licence_sont_identiques():
    """Deux noms imposés de l'extérieur, un seul texte — vérifié à l'octet."""
    spdx = identifiant_spdx_accorde()
    copies = ("LICENSE", f"LICENSES/{spdx}.txt")
    for nom in copies:
        assert (_RACINE / nom).exists(), (
            f"{nom} a disparu. Les deux noms sont imposés : GitHub ne lit que "
            "LICENSE, REUSE que LICENSES/<SPDX>.txt"
        )
    contenus = {nom: (_RACINE / nom).read_bytes() for nom in copies}

    reference = contenus["LICENSE"]
    divergentes = [nom for nom, octets in contenus.items() if octets != reference]
    assert not divergentes, (
        "Le texte de licence diverge entre ses copies : "
        f"{', '.join(divergentes)} ≠ LICENSE. La licence a été modifiée à un "
        "endroit sur deux — c'est le défaut que REUSE.toml a déjà connu (#774)."
    )


def test_le_texte_de_licence_est_celui_de_l_identifiant():
    """Les copies concordent entre elles : encore faut-il qu'elles soient la BONNE licence.

    Deux marques du texte officiel de l'AGPL v3 — son titre, et la clause
    réseau (§13) qui est sa raison d'être — et l'option « ou ultérieure » que
    l'identifiant `-or-later` promet (#1726).
    """
    spdx = identifiant_spdx_accorde()
    assert spdx == "AGPL-3.0-or-later", f"REUSE.toml accorde {spdx} : ce test ne la connaît pas"
    texte = _lire("LICENSE")
    assert texte.startswith("GNU AFFERO GENERAL PUBLIC LICENSE"), "LICENSE n'est pas l'AGPL"
    assert "13. Remote Network Interaction" in texte, "la clause réseau de l'AGPL manque"
    assert "or (at your option) any later version" in texte


def test_la_gouvernance_est_redigee_en_francais():
    """« Français exclusif » n'avait aucun garde-fou avant le 19/09/2026."""
    fautes = {}
    for nom in GOUVERNANCE:
        mots = re.findall(MOTS_ANGLAIS, _prose_seule(_lire(nom)), re.I)
        if mots:
            fautes[nom] = sorted({mot.lower() for mot in mots})

    assert not fautes, (
        "Des fichiers de gouvernance sont rédigés en anglais, alors que le "
        "projet est intégralement en français :\n"
        + "\n".join(f"  {nom} : {', '.join(mots)}" for nom, mots in fautes.items())
    )


#: Le premier mot d'un nom d'étape anglais : les noms que l'action du marché ou
#: la documentation de GitHub suggèrent, et qu'on recopie (#2979). « Lint » n'y
#: est pas : c'est le jargon reçu, écrit tel quel dans les noms de JOBS requis.
VERBES_ANGLAIS = r"^(Set up|Setup|Install|Run|Build|Checkout|Cache|Upload|Download|Login|Deploy)\b"


def noms_d_etapes_anglais(workflow: dict) -> list[str]:
    """Les noms d'ÉTAPES (jamais de jobs) écrits en anglais d'un workflow lu. PURE.

    Les noms de JOBS sont hors de portée : ce sont les contextes exigés par la
    protection de `main`, relus par `scripts/ci/arbre_deja_vert.py` — les renommer
    casserait la fusion.
    """
    return [
        f"{job_id} : {etape['name']}"
        for job_id, job in (workflow.get("jobs") or {}).items()
        for etape in job.get("steps") or []
        if isinstance(etape.get("name"), str)
        and (
            re.search(VERBES_ANGLAIS, etape["name"]) or re.search(MOTS_ANGLAIS, etape["name"], re.I)
        )
    ]


def test_le_controle_des_etapes_sait_REFUSER():
    workflow = {
        "jobs": {
            "j": {
                "name": "Build SvelteKit",
                "steps": [{"name": "Set up Python"}, {"name": "Installer Ruff"}, {"uses": "x"}],
            }
        }
    }
    assert noms_d_etapes_anglais(workflow) == ["j : Set up Python"]


def test_les_etapes_des_workflows_sont_nommees_en_francais():
    chemins = sorted((_RACINE / ".github" / "workflows").glob("*.yml"))
    assert len(chemins) >= 5, "aucun workflow lu — le contrôle a perdu sa portée"
    fautes = {
        c.name: noms
        for c in chemins
        if (noms := noms_d_etapes_anglais(yaml.safe_load(c.read_text(encoding="utf-8"))))
    }
    assert not fautes, (
        "Étape(s) de workflow nommée(s) en anglais — le projet est en français "
        f"(#2979) ; ne pas renommer les JOBS : {fautes}"
    )
