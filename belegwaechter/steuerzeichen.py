"""Zentrale Normalisierung extrahierter Textwerte gegen C0-Steuerzeichen.

PDF-Textebenen koennen Steuerzeichen enthalten (z.B. NUL als Spaltentrenner
einer Tabellenzeile). Solche Zeichen duerfen nie persistiert, ueber die API
ausgeliefert oder exportiert werden -- sie erscheinen in UI und CSV als
Kaestchen. Ein Steuerzeichen ZWISCHEN zwei nicht-leeren Textteilen wird zu
einem sichtbaren Bindestrich (nichts wird kommentarlos zusammengeklebt),
alle uebrigen Steuerzeichen werden entfernt, danach wird Whitespace
normalisiert. Zeilenumbrueche bleiben nur in mehrzeiligen Texten erhalten.
"""
from __future__ import annotations

import re

# Alle C0-Steuerzeichen ausser Tab/Zeilenumbruch/Wagenruecklauf, plus DEL.
# Tab und Zeilenumbruch sind KEINE Trenner-Steuerzeichen: sie werden in
# Feldwerten wie gewoehnlicher Whitespace zu Leerzeichen kollabiert.
_C0_OHNE_UMBRUCH = "\x00-\x08\x0b\x0c\x0e-\x1f\x7f"

_MITTIG = re.compile(rf"(?<=\S)[{_C0_OHNE_UMBRUCH}]+(?=\S)")
_REST = re.compile(rf"[{_C0_OHNE_UMBRUCH}]+")


def feldwert_bereinigen(wert: str | None) -> str | None:
    """Einzeiliger Feldwert (Anbieter, Referenz, Zeitraum, ...): Steuerzeichen
    zwischen zwei nicht-leeren Teilen werden zum sichtbaren Trenner '-',
    uebrige entfernt, Whitespace (inkl. Tab/Umbruch) zu einfachen
    Leerzeichen kollabiert. None bleibt None; ein leer gewordener Wert
    wird None (fehlend statt leer)."""
    if wert is None:
        return None
    text = _MITTIG.sub("-", wert)
    text = _REST.sub(" ", text)
    text = " ".join(text.split())
    return text or None


def flusstext_bereinigen(text: str) -> str:
    """Mehrzeiliger Text (z.B. eine komplette PDF-Textebene oder ein
    Mailtext): Zeilenumbrueche und Tabs bleiben fachlich erhalten, alle
    anderen C0-Steuerzeichen werden mittig zu '-' und sonst entfernt."""
    if not text:
        return text
    bereinigt = _MITTIG.sub("-", text)
    return _REST.sub("", bereinigt)
