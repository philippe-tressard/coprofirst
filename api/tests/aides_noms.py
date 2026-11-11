"""Les cas de la règle « Prénom NOM » (`utils/noms.nom_affiche`) — partagés par
`test_noms_affichage.py` (la règle) et `test_nom_servi.py` (le nom SERVI, #2633)."""

CAS = [
    #  (prénom, nom, rendu attendu)
    ("Jean-Baptiste", "ForT", "Jean-Baptiste FORT"),
    ("Christine", "Verdière", "Christine VERDIÈRE"),
    ("Marie", "de La Tour", "Marie DE LA TOUR"),
    ("  Paul  ", "  Durand  ", "Paul DURAND"),
    ("Anne", "", "Anne"),
    ("", "Martin", "MARTIN"),
    ("", "", ""),
]
