"""Licences tierces — la politique, en un seul endroit (#1542, #1543).

Lue par `licences_tierces.py` (dépendances de `front/`, `whatsapp-bridge/` et
`api/`) et par `contenus_tiers.py` (fichiers repris d'un projet tiers et
recopiés dans le dépôt). C'est aussi d'ici que `docs/licences-tierces.md` tire
ses motifs : rien de ce qui suit ne se recopie ailleurs.

🔴 CE FICHIER NE TRANCHE RIEN DE JURIDIQUE. La liste blanche nomme les licences
dites permissives, qui n'imposent que de conserver les mentions ; tout le reste
est une EXCEPTION, déclarée nommément avec ce qu'on en sait. Une exception
n'est pas une autorisation : c'est une question posée par écrit, et le champ
`statut` dit à qui elle est posée.

Règles que les deux contrôles appliquent :
  - une dépendance dont la licence n'est pas admise et qu'aucune exception ne
    couvre fait ÉCHOUER la CI ;
  - une exception qui ne couvre plus rien (paquet retiré, licence changée) fait
    ÉCHOUER aussi : elle se retire, sinon elle couvrirait demain autre chose ;
  - une exception porte sur une licence PRÉCISE : si `libsignal` changeait de
    licence, l'exception ne le couvrirait plus et la CI le dirait.
"""

from __future__ import annotations

# ── Liste blanche ───────────────────────────────────────────────────────────
#  Identifiants SPDX, plus `BSD` : le classifieur Python « BSD License » ne dit
#  pas quelle variante, et toutes sont permissives — il est admis tel quel
#  plutôt que réécrit en une variante qu'on aurait devinée.
ADMISES = frozenset(
    {
        "0BSD",
        "Apache-2.0",
        "BlueOak-1.0.0",
        "BSD",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "CC0-1.0",
        "CNRI-Python",
        "ISC",
        "MIT",
        "MIT-0",
        "MIT-CMU",
        "PSF-2.0",
        "Python-2.0",
        "Unlicense",
        "Zlib",
    }
)


def _compatible(pourquoi: str) -> str:
    """Le statut d'une exception dont la compatibilité est TRANCHÉE (#1726).

    Le projet passe sous AGPL-3.0-or-later le 08/10/2026. Les exceptions dont la
    compatibilité était « À VALIDER » avec l'ancienne licence ont été analysées
    contre la nouvelle, et l'analyse a été validée par l'auteur. Elle n'est pas
    un avis juridique : le motif est écrit pour être relu.
    """
    return f"compatible avec l'AGPL-3.0-or-later ({pourquoi}) — analyse du 08/10/2026, validée par l'auteur"


# ── Exceptions nominatives ──────────────────────────────────────────────────
#  `source` : front | whatsapp-bridge | api. `paquets` : noms, motifs `*`
#  admis. `licences` : expressions EXACTES telles que l'inventaire les lit —
#  chacune doit encore servir, sinon la CI échoue.
EXCEPTIONS = (
    {
        "source": "whatsapp-bridge",
        "paquets": ("libsignal",),
        "licences": ("GPL-3.0",),
        "motif": (
            "Protocole de chiffrement Signal, tiré par `baileys` (seule bibliothèque "
            "WhatsApp Web maintenue de l'écosystème Node), non substituable. Copyleft "
            "fort. Il s'exécute dans le bridge, conteneur distinct de l'API et du "
            "front, avec lesquels il ne communique que par HTTP."
        ),
        "statut": _compatible(
            "la GPLv3 et l'AGPLv3 se combinent l'une avec l'autre (§13 de chacune) ; "
            "programme distinct, joint par HTTP"
        ),
    },
    {
        "source": "whatsapp-bridge",
        "paquets": ("@img/sharp-libvips-*", "@img/sharp-win32-*", "@img/sharp-wasm32"),
        "licences": (
            "LGPL-3.0-or-later",
            "Apache-2.0 AND LGPL-3.0-or-later",
            "Apache-2.0 AND LGPL-3.0-or-later AND MIT",
        ),
        "motif": (
            "Binaires de libvips embarqués par `sharp`, dépendance pair de `baileys` "
            "(traitement d'images). Copyleft faible ; une seule variante de plateforme "
            "est installée dans l'image (Linux musl). Même conteneur que libsignal."
        ),
        "statut": _compatible("la LGPL-3.0-or-later l'est par construction"),
    },
    {
        "source": "front",
        "paquets": ("caniuse-lite",),
        "licences": ("CC-BY-4.0",),
        "motif": (
            "Table de compatibilité des navigateurs lue par `browserslist` au moment "
            "de la construction (devDependencies). Licence de données, qui demande "
            "l'attribution."
        ),
        "statut": _compatible(
            "la CC-BY-4.0 est compatible avec la GPLv3 ; outil de construction, non "
            "distribué ; attribution portée par cet inventaire"
        ),
    },
    {
        "source": "front",
        "paquets": ("lightningcss", "lightningcss-*"),
        "licences": ("MPL-2.0",),
        "motif": (
            "Minifieur CSS de Vite 8 (#2205), dépendance directe de `vite` : il n'est pas "
            "substituable sans quitter la chaîne de construction. Copyleft faible au "
            "niveau du fichier ; utilisé sans modification. Les binaires de plateforme "
            "(un par système) sont des paquets optionnels, dont un seul est installé."
        ),
        "statut": _compatible(
            "la MPL-2.0 admet la GPL et l'AGPL comme « Secondary Licenses » ; outil de "
            "construction, présent dans node_modules de l'image sans être modifié"
        ),
    },
    {
        "source": "api",
        "paquets": ("psycopg", "psycopg-binary"),
        "licences": ("LGPL-3.0-only",),
        "motif": (
            "Pilote PostgreSQL (DI-7, #1759 ; tests depuis P2-5, #1747), employé tel "
            "quel par SQLAlchemy. Copyleft faible ; les roues binaires embarquent libpq "
            "(licence PostgreSQL) et ses dépendances. Seul pilote qui rend une clé "
            "violée en `IntegrityError` — pg8000, sous BSD, ne le faisait pas."
        ),
        "statut": _compatible(
            "la LGPL-3.0 permet l'usage d'une bibliothèque par une œuvre sous GPLv3 ou "
            "AGPLv3 (§4 et §5 de la LGPL), qui la distribue avec sa licence et son source"
        ),
    },
    {
        "source": "api",
        "paquets": ("certifi",),
        "licences": ("MPL-2.0",),
        "motif": (
            "Magasin de certificats racine (tiré par httpx). Copyleft faible au niveau "
            "du fichier ; utilisé sans modification."
        ),
        "statut": _compatible("la MPL-2.0 admet la GPL et l'AGPL comme « Secondary Licenses »"),
    },
    {
        "source": "api",
        "paquets": ("pyphen",),
        "licences": ("GPL-2.0-or-later | LGPL-2.0-or-later | MPL-1.1 (classifieurs multiples)",),
        "motif": (
            "Césure des mots, tirée par WeasyPrint (documents PDF). Le paquet se dit "
            "« GPL 2.0+/LGPL 2.1+/MPL 1.1 tri-license » (fichier LICENSE installé) ; "
            "ses dictionnaires viennent de LibreOffice sous GPL, LGPL et/ou MPL."
        ),
        "statut": _compatible("par son option GPL-2.0-or-later ou LGPL-2.1-or-later"),
    },
    {
        "source": "api",
        "paquets": ("dkimpy",),
        "licences": ("BSD-like",),
        "motif": (
            "Vérification DKIM des réponses par courriel. Les métadonnées disent "
            "« BSD-like » ; le fichier LICENSE installé porte le texte de la licence "
            "zlib, qui est permissive."
        ),
        "statut": "métadonnées imprécises — le texte installé est celui de la licence zlib",
    },
)

# ── Licences déclarées pour ce que le poste ne peut pas installer ───────────
#  Une dépendance de l'IMAGE (Linux) qu'aucune plateforme du poste (Windows)
#  ne peut installer rend le jugement INCONNU au rejeu local — et le point 16
#  du pré-check refuserait alors toute MEP depuis le poste. Sa licence se
#  DÉCLARE ici, et la déclaration ne sert qu'à ce cas :
#    - sur le poste, paquet absent et non installable : licence déclarée
#      retenue, la sortie dit « vérifiée par la CI » ;
#    - en CI (Linux), le paquet est installé : sa licence LUE doit être celle
#      déclarée, sinon ÉCHEC ;
#    - une entrée dont le paquet quitte l'image, ou devient installable sur le
#      poste, fait ÉCHOUER : elle se retire.
#  `licence` : l'expression telle que l'inventaire la LIT (même règle que
#  `licences_spdx.licence_python`), pas une reformulation.
LICENCES_HORS_POSTE = {
    "uvloop": {
        "licence": "MIT",
        "raison": (
            "Boucle d'événements d'uvicorn[standard], exclue de Windows par son marqueur "
            "(sys_platform != 'win32'). PyPI, uvloop 0.23.0 : champ License « MIT "
            "License » (lu « MIT »), classifieurs MIT et Apache — double licence."
        ),
        "date": "2026-10-02",
    },
    "greenlet": {
        "licence": "MIT AND PSF-2.0",
        "raison": (
            "Dépendance de SQLAlchemy, exclue du Mac (arm64) par son marqueur, qui ne nomme "
            "que aarch64, x86_64, amd64… (#2419). greenlet 3.5.6 : License-Expression "
            "« MIT AND PSF-2.0 », lue telle quelle."
        ),
        "date": "2026-11-01",
    },
}

# ── Ce que les Dockerfile installent hors de pip et npm (#2389) ─────────────
#  L'inventaire ci-dessus ne voit ni les paquets Debian d'une image, ni ce
#  qu'une roue EMBARQUE : `pillow-heif` se lit « BSD-3-Clause », alors que ses
#  roues PyPI portent libx265 (GPLv2). `licences_image.py` confronte les
#  Dockerfile à ce qui suit ; l'image construite, elle, est jugée par
#  `api/scripts/verifier_heif.py`. Seules les bibliothèques ENTRÉES pour une
#  raison nommée sont déclarées ici, pas tout ce que porte l'image de base.
BIBLIOTHEQUES_SYSTEME = (
    {
        "dockerfile": "api/Dockerfile",
        "paquets": ("libheif1", "libheif-plugin-libde265"),
        "licences": ("LGPL-3.0-or-later",),
        "motif": (
            "Décodage des photos HEIC/HEIF d'iPhone (#2389), par `pillow-heif` compilé "
            "contre elles. Tirent `libde265-0` (LGPL-3.0-or-later) et "
            "`libheif-plugin-dav1d` + `libdav1d7` (BSD-2-Clause). Debian (`copyright`) : "
            "les bibliothèques sont LGPL-3+ ; seuls scripts, tests et l'outil `dec265`, "
            "non installés, sont sous GPL-3+. Bibliothèques partagées, liées "
            "dynamiquement, non modifiées ; aucun encodeur."
        ),
        "statut": (
            "compatible avec l'AGPL-3.0-or-later (la LGPL-3.0-or-later l'est par "
            "construction, comme les bibliothèques de sharp) — voie « décodage seul, "
            "sans x265 » validée par l'auteur le 31/10/2026"
        ),
    },
)

#: Paquets Debian qu'aucune étape d'aucune image n'installe (motifs `fnmatch`).
INTERDITS_DANS_LES_IMAGES = {
    "*x265*": (
        "encodeur HEVC sous GPLv2, que la distribution publique des images "
        "(ghcr.io) ferait distribuer ; le site ne fait que décoder (#2389)"
    ),
}

#: Paquets pip dont la roue PyPI embarque un interdit : l'image les compile
#: (`--no-binary`), et `PIP_NO_BINARY` empêche la roue de revenir par les exigences.
ROUES_A_COMPILER = {
    "pillow-heif": {
        "dockerfile": "api/Dockerfile",
        "exigences": "api/requirements.txt",
        "raison": "ses roues PyPI embarquent libx265 (GPLv2)",
    },
}

# ── Contenus tiers recopiés dans le dépôt (#1543) ───────────────────────────
#  Ce que `reuse lint` ne peut pas voir : un fichier qui porte des tracés
#  repris ailleurs reçoit la licence du motif `**` de REUSE.toml, et le
#  contrôle reste vert. `contenus_tiers.py` exige que REUSE.toml attribue à
#  chacun de ces fichiers les licences et titulaires déclarés ici, et cherche
#  par leurs EMPREINTES les fichiers qui les recopieraient sans déclaration.
CATALOGUE_ICONES = "front/src/lib/icones-svg.json"

#  Icônes du catalogue qui ne viennent PAS de Lucide. Comparé le 02/10/2026 aux
#  versions 0.200, 0.300, 0.400 et 1.50 de `lucide-static` : 59 icônes sur 61
#  sont des tracés Lucide (ou Feather, dont Lucide dérive), les deux autres sont
#  celles-ci. Une entrée qui disparaît du catalogue fait échouer le contrôle.
#  Le 03/10/2026, quatre tracés Lucide sont entrés (`circle`, `circle-check`,
#  `circle-x`, `refresh-cw` — la chronologie d'une synthèse, #1643).
#  Le 10/10/2026, dix-sept tracés de `lucide-static` 0.460.0 sont entrés (`undo-2`,
#  `redo-2`,
#  `plus`, `x`, `check`, `flag`, `save`, `mail`… — les actions au trait du site, #1819).
#  Le 13/10/2026, `copy` (Lucide) — dupliquer un périmètre et ses enfants.
#  Le 17/10/2026, `external-link` (`lucide-static` 0.460.0) — les liens du pied
#  de page qui sortent du site (#2040).
#  Le 01/11/2026, vingt et un tracés de `lucide-static` 0.460.0 (`trash`,
#  `fire-extinguisher`, `wind`, `fan`, `cctv`, `mailbox`… — les grilles d'icônes
#  des équipements et des périmètres, extraits du paquet, jamais redessinés).
ICONES_HORS_LUCIDE = {
    "whatsapp": "Simple Icons",
    "stairs": "absente de Lucide — présumée dessinée pour le projet, à confirmer par l'auteur",
}

CONTENUS_TIERS = (
    {
        "nom": "Lucide",
        "origine": "https://lucide.dev — tracés recopiés à la main, aucune dépendance npm",
        "licences": ("ISC", "MIT"),
        "titulaires": ("Lucide Icons and Contributors", "Cole Bemis"),
        "icones": None,  # tout le catalogue, hors ICONES_HORS_LUCIDE
        "fichiers": (
            "front/src/lib/icones-svg.json",
            "api/app/utils/icones-svg.json",
            "docs/manuel-utilisateur.html",
            "front/static/manuel-utilisateur.html",
            "infra/cloudflare-worker.js",
        ),
        "detail": (
            "ISC pour Lucide ; MIT pour les icônes dérivées de Feather (Cole Bemis), "
            "dont la licence de Lucide donne la liste — `calendar`, `clock`, `lock`, "
            "`search`, `trash-2`… en font partie."
        ),
    },
    {
        "nom": "Simple Icons — logo WhatsApp",
        "origine": "https://simpleicons.org — tracé de l'icône `whatsapp`",
        "licences": ("CC0-1.0",),
        "titulaires": (),
        "icones": ("whatsapp",),
        "fichiers": ("front/src/lib/icones-svg.json", "api/app/utils/icones-svg.json"),
        "detail": (
            "Le TRACÉ est versé au domaine public (CC0-1.0), mais CC0 ne cède aucun "
            "droit de marque : le logo reste une marque de son titulaire. Son usage "
            "pour désigner le canal WhatsApp de la résidence est À VALIDER par l'auteur."
        ),
    },
)
