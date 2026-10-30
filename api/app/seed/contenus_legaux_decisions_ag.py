"""Gabarit légal : les décisions d'AG, et la transcription d'un PV par l'assistant (29/10/2026).

Deux transmissions neuves vers le service de modèle de langage : les décisions
d'assemblée validées partent avec le règlement à chaque question, et un PV d'AG
part ENTIER quand l'assistant le transcrit — avec les noms qu'il porte. Tant que
l'usage `transcription_pv_ag` existe, `test_politique_confidentialite_couvre_le_code.py`
exige que la politique le nomme.

Une seule rédaction, lue par `contenus_legaux.DEFAULT_LEGAL` (bases neuves) et par
la migration 0318 (textes déjà servis). À faire relire (`standards/14`). Un module
à part : `contenus_legaux.py` frôle le plafond de 500 lignes.
"""

#: Elle suit la phrase des questions au règlement, dans la même entrée.
DECISIONS_AG = (
    "Les <strong>décisions d'assemblée générale</strong> validées par l'administrateur — "
    "les résolutions seules, sans la feuille de présence ni le nom des votants — sont "
    "transmises avec le règlement. Pour les obtenir, l'administrateur peut faire "
    "<strong>transcrire un procès-verbal d'assemblée</strong> par l'assistant, d'office pour "
    "un procès-verbal récent\xa0: le procès-verbal est alors transmis en entier, noms "
    "compris s'il en porte, et sa transcription n'est lue des questions qu'une fois relue "
    "et validée par l'administrateur. "
)
