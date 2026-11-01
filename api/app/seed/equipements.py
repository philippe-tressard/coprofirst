"""Les équipements de départ (#2442) — une proposition, que l'administration remplace.

Ils reprennent les dix-huit valeurs de l'ancienne énumération `TypeEquipement`,
avec le libellé, l'icône au trait et le mot de gouttière que l'écran leur
donnait. Posés sur une table VIDE seulement (`seed.equipements_par_defaut`) :
les reposer à chaque démarrage ferait revenir ce que l'administrateur a
supprimé.
"""

#: (code, libellé, icône du catalogue, abréviation, description)
_EQUIPEMENTS: list[tuple[str, str, str, str, str | None]] = [
    ("ascenseur", "Ascenseur", "arrow-up-down", "ASC.", None),
    ("chauffage_collectif", "Chauffage collectif", "flame", "CHAUF.", None),
    ("eau", "Eau", "droplet", "EAU", None),
    ("electricite", "Électricité", "zap", "ÉLEC.", None),
    ("espaces_verts", "Espaces verts", "trees", "VERTS", None),
    ("extincteurs", "Extincteurs", "shield-half", "EXTINC.", None),
    ("interphone_digicode", "Interphone/Digicode", "bell", "INTERPH.", None),
    ("menuiseries", "Menuiseries", "door-closed", "MENUIS.", None),
    ("nettoyage", "Nettoyage", "wrench", "NETT.", None),
    ("plomberie", "Plomberie", "droplet", "PLOMB.", None),
    ("pompe", "Pompe", "settings", "POMPE", None),
    ("porte_parking", "Porte parking", "square-parking", "PARK.", None),
    ("serrurerie", "Serrurerie", "key-round", "SERR.", None),
    ("toiture", "Toiture", "home", "TOIT.", None),
    ("vmc", "VMC", "wrench", "VMC", None),
    (
        "assurance",
        "Assurance",
        "shield",
        "ASSUR.",
        "Classe les contrats d'assurance de l'immeuble. Jamais proposé dans une affaire.",
    ),
    (
        "syndic",
        "Syndic",
        "building-2",
        "SYNDIC",
        "Classe le mandat du syndic. Jamais proposé dans une affaire.",
    ),
    (
        "autre",
        "Autre",
        "wrench",
        "AUTRE",
        "Sans catégorie : le carnet range alors le contrat selon la spécialité du prestataire.",
    ),
]

EQUIPEMENTS: list[dict] = [
    {
        "code": code,
        "libelle": libelle,
        "icone": icone,
        "abreviation": abreviation,
        "description": description,
        "ordre": rang,
    }
    for rang, (code, libelle, icone, abreviation, description) in enumerate(_EQUIPEMENTS, 1)
]
