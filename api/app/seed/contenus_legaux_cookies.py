"""La rubrique « 7. Cookies » du gabarit légal (#2174, lot S5 du mode sombre).

Elle disait que l'application utilise « exclusivement des cookies techniques
d'authentification ». Le choix du thème — Automatique, Clair ou Sombre — se retient
désormais sur l'appareil, par le cookie `theme` (`front/src/lib/theme.ts`, arbitré
le 29/10/2026 : pas de colonne en base). La phrase serait devenue fausse, sur une
page publique.

Le cookie de thème est une préférence de présentation demandée par l'utilisateur :
il ne porte qu'un mot (automatique, clair ou sombre), rien qui identifie, et n'est
lu que pour afficher les pages.

Écrite une fois : le gabarit (`contenus_legaux.DEFAULT_LEGAL`) et la migration 0319,
qui la substitue dans le texte servi, la lisent ici. 🔒
`tests/test_politique_confidentialite_couvre_le_code.py` exige que chaque cookie que
le code pose y soit nommé.

⚠️ **Projet, à faire relire**, comme les autres rubriques (`standards/14`).

Séparé de `contenus_legaux.py`, qui approche 500 lignes (modularité, rang 1).
"""

#: La phrase d'OUVERTURE de la rubrique — la seule que la migration substitue : le
#: texte servi a reçu d'autres phrases à sa suite, qu'elle ne doit pas toucher.
COOKIES = (
    "L'application n'utilise que des cookies techniques\xa0: les cookies "
    "d'authentification (<code>access_token</code>, <code>refresh_token</code>), définis en "
    "<code>HttpOnly; Secure; SameSite=Strict</code>, et un cookie de <strong>préférence "
    "d'affichage</strong> (<code>theme</code>), qui retient sur l'appareil le thème choisi "
    "dans le profil — automatique, clair ou sombre. Il n'est posé que lorsque vous faites "
    "ce choix et ne contient rien d'autre\xa0; préférence de présentation que vous demandez, "
    "il n'est pas soumis à votre consentement."
)
