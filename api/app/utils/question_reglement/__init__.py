"""Questions au règlement de copropriété — l'avis d'un juriste, extraits à l'appui.

L'administration charge le texte de travail du règlement (Markdown) ; le conseil
syndical — et les copropriétaires quand l'usage leur est ouvert — pose une
question ; l'assistant répond par un verdict, une réponse argumentée, des
extraits cités mot pour mot et des réserves. Le CODE vérifie
que chaque extrait figure dans le texte et en déduit la page.

| Module | Ce qu'il porte |
|---|---|
| `format` | le prompt d'origine, la forme de la réponse, sa relecture — pur |
| `extraits` | la recherche des citations et leur repère de page — pur |
| `texte` | charger une version du texte, lire celle en vigueur |
| `documents` | les actes de la bibliothèque montrés à côté du texte, choisis par l'administration |
| `production` | l'appel à l'assistant et la trace de la réponse |
"""
