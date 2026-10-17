"""`texte_brut` décode TOUTES les entités HTML, en une passe (17/10/2026).

Il ne remplaçait que cinq entités nommées : l'apostrophe que l'éditeur écrit
`&#x27;` restait en clair, et « L&#x27;Art des toits » s'affichait sous le titre
d'une affaire au Suivi des entretiens périodiques — l'aperçu du relevé passe
par lui, comme le PDF et le courriel de relance.
"""

import pytest

from app.utils.annonce_hall import texte_brut


@pytest.mark.parametrize(
    "html, attendu",
    [
        ("<p>L&#x27;Art des toits — Entretien</p>", "L'Art des toits — Entretien"),
        ("L&#39;entretien", "L'entretien"),
        ("<p>A&nbsp;&amp;&nbsp;B</p>", "A & B"),
        ("&lt;b&gt; &quot;cité&quot;", '<b> "cité"'),
        ("<p>un</p><p>deux</p>", "un deux"),
        # Une seule passe : un `&` échappé ne se décode pas une seconde fois.
        ("&amp;lt;", "&lt;"),
        ("", ""),
    ],
)
def test_texte_brut_decode_les_entites(html, attendu):
    assert texte_brut(html) == attendu
