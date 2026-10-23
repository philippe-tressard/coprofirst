"""**Le sommaire du PDF du manuel vise l'id d'un titre qui en porte déjà un** (#2173).

v3.12.0 a ajouté au manuel un `<h3 id="fusion-correction">` ; `titres_ancres` lui
posait un second `id="som-27"`, seul le premier compte, et l'entrée du sommaire
pointait dans le vide — WeasyPrint journalisait « No anchor #som-27 » à chaque
préchauffage. Le garde-fou sur le manuel réel est dans `test_manuel_pdf.py`
(aucun titre à deux `id`) ; ce fichier tient le cas, sur un document minimal.
"""

from app.utils.manuel_pdf import titres_ancres


def test_un_titre_qui_porte_deja_un_id_garde_le_sien():
    """Le cas qui a cassé le sommaire du PDF : un titre ciblé par un lien du
    manuel (`<h3 id="fusion-correction">`). Le sommaire vise son `id`, et la
    balise n'en reçoit pas un second ; le compteur des autres ne bouge pas."""
    html = (
        '<html><body><main><h2>Un</h2><h3 id="cible">Deux</h3><h3>Trois</h3></main></body></html>'
    )
    corps, releve = titres_ancres(html)
    assert [a for _, _, a in releve] == ["som-0", "cible", "som-2"]
    assert '<h3 id="cible">Deux</h3>' in corps
    assert '<h3 id="som-2">Trois</h3>' in corps
