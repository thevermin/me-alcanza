#!/usr/bin/env python3
"""Arma index.html (la página completa para GitHub Pages) a partir de pagina.html."""
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
cuerpo = (raiz / "pagina.html").read_text(encoding="utf-8")
cabecera = (
    "<!doctype html>\n<html lang=\"es\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
)
corte = cuerpo.index('<div class="wrap">')
html = cabecera + cuerpo[:corte] + "</head>\n<body>\n" + cuerpo[corte:] + "\n</body>\n</html>\n"
(raiz / "index.html").write_text(html, encoding="utf-8")
print("index.html listo")
