"""Les consignes de la fiche arrivant — GABARIT DU PRODUIT (#1727).

Servies tant que rien n'a été saisi en base : `utils/consignes_arrivant` les lit
en repli. Elles restent **génériques**, sur le modèle de `contenus_legaux.py` :
le seed porte le produit, la base porte l'instance. Un nom de rue, un jour de
collecte ou le nom d'un syndic écrits ici seraient imprimés sur la fiche des
arrivants de toute autre copropriété (`specs/architecture/multi-coproprietes.md`).

Format : du TEXTE, jamais du HTML — `**gras**` pour l'emphase, une ligne par
consigne, et `{syndic}` pour le nom du syndic, lu au rendu dans le contrat
(`utils/syndic.nom_du_syndic`). Le pourquoi : `utils/consignes_arrivant`.
"""

#: La phrase d'accueil, sous « Bonjour et bienvenue ! » : même format de texte que les
#: consignes, et `{site}` pour l'adresse du site de la résidence (lue au rendu).
ACCUEIL_GABARIT = (
    "Vous venez d'emménager dans notre résidence. Ne restez pas sur le carreau\u202f! "
    "Consultez régulièrement les actualités sur le site {site} de la copropriété."
)

GABARIT: list[dict[str, str]] = [
    {
        "titre": "📦 1. Emménagement / déménagement",
        "contenu": (
            "Prévenez le conseil syndical du bâtiment concerné, **1 semaine à l'avance**, "
            "pour toute arrivée ou départ afin de permettre à ce dernier d'effectuer un état "
            "des lieux des parties communes avant et après.\n"
            "Pensez à demander l'autorisation à la mairie pour le stationnement des camions "
            "devant la copropriété.\n"
            "Protégez au mieux les parties communes lors des déménagements (ascenseur, "
            "escaliers, halls) et évacuez les cartons et encombrants rapidement, sans les "
            "laisser dans les couloirs ou les locaux à poubelles.\n"
            "Demander au syndic {syndic} de changer les noms sur la boîte aux lettres et "
            "l'interphone."
        ),
    },
    {
        "titre": "🗑 2. Sortie des poubelles et tri",
        "contenu": (
            "Déchets encombrants : **ne pas les laisser dans les parties communes**. "
            "Apportez-les à la déchèterie ou en collecte sur le trottoir, aux jours fixés "
            "par la commune pour votre rue."
        ),
    },
    {
        "titre": "🏢 3. Parties communes",
        "contenu": (
            "Gardez les couloirs, escaliers et halls propres. "
            "Ne laissez rien traîner : poubelles, poussettes, vélos, cartons, etc.\n"
            "Respectez la tranquillité des lieux : évitez de faire du bruit, surtout entre "
            "22h et 7h.\n"
            "Ne donnez pas de code ou de clé aux personnes non autorisées."
        ),
    },
]
