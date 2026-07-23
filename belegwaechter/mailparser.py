"""Lokale EML-Zerlegung fuer den Belegwaechter (nur Standardbibliothek).

Liest eine hochgeladene .eml-Datei vollstaendig offline mit dem stdlib-Paket
`email` (BytesParser, policy.default): Quoted-Printable, Base64 und Charsets
werden dort dekodiert, es gibt keinen Codepfad, der eine Netzwerkressource
laedt. Remote-Bilder oder Tracking-Pixel im HTML werden nie abgerufen; der
HTML-Teil wird ausschliesslich als String in Text umgewandelt.

Der HTML-zu-Text-Umwandler ist bewusst KEIN allgemeiner Parser fuer beliebige
Mail-Layouts: Er erzeugt aus Blocktags und Tabellenzeilen "Label: Wert"-Zeilen,
wie sie die bestehende regelbasierte Feldextraktion erwartet (siehe
belegwaechter/extrahieren.py). Was er nicht lesen kann, bleibt fail-closed leer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

# Headernamen, die eine echte E-Mail-Datei tragen. EML hat keine Magic-Bytes;
# die Erkennung verlangt deshalb mindestens zwei bekannte Header vor der
# ersten Leerzeile, damit eine beliebige "Label: Wert"-Textdatei nicht
# faelschlich als E-Mail gilt.
_BEKANNTE_HEADER = (
    "from:", "to:", "subject:", "date:", "mime-version:",
    "received:", "return-path:", "message-id:", "content-type:",
)

_HEADERZEILE = re.compile(r"^[!-9;-~]+:[ \t]")


@dataclass
class EmlAnhang:
    dateiname: str
    inhalt: bytes
    deklarierter_typ: str


@dataclass
class EmlInhalt:
    betreff: str
    absender: str
    mail_datum: str
    text: str
    text_quelle: str  # "text/plain" | "text/html" | "keine"
    anhaenge: list[EmlAnhang] = field(default_factory=list)


def ist_eml(inhalt: bytes) -> bool:
    """Header-Heuristik: erste nichtleere Zeile muss eine RFC-5322-Headerzeile
    sein und vor der ersten Leerzeile muessen mindestens zwei bekannte
    Headernamen stehen. PDF/PNG/JPEG sind vorher bereits per Magic-Bytes
    erkannt (siehe dateien.dateityp_erkennen) und erreichen diese Pruefung nie."""
    kopf = inhalt[:4096].decode("latin-1", errors="replace")
    zeilen = kopf.splitlines()

    erste_inhaltszeile = None
    for zeile in zeilen:
        if zeile.strip():
            erste_inhaltszeile = zeile
            break
    if erste_inhaltszeile is None or not _HEADERZEILE.match(erste_inhaltszeile):
        return False

    treffer = 0
    for zeile in zeilen:
        if not zeile.strip():
            break
        klein = zeile.lower()
        if any(klein.startswith(name) for name in _BEKANNTE_HEADER):
            treffer += 1
    return treffer >= 2


class _HtmlZuText(HTMLParser):
    """Wandelt Mail-HTML in auswertbare Textzeilen um: Blocktags und
    Tabellenzeilen werden Zeilenumbrueche, Zellen werden mit Leerzeichen
    verbunden, script/style/head werden vollstaendig verworfen. Bild- und
    Link-URLs erzeugen keinen Text (ein Tracking-Pixel hinterlaesst nichts)."""

    _BLOCKTAGS = {"p", "br", "div", "tr", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"}
    _IGNORIERTE_BEREICHE = {"script", "style", "head", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._teile: list[str] = []
        self._ignorier_tiefe = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._IGNORIERTE_BEREICHE:
            self._ignorier_tiefe += 1
        elif tag in self._BLOCKTAGS:
            self._teile.append("\n")
        elif tag in ("td", "th"):
            self._teile.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._IGNORIERTE_BEREICHE and self._ignorier_tiefe > 0:
            self._ignorier_tiefe -= 1
        elif tag in self._BLOCKTAGS:
            self._teile.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignorier_tiefe == 0:
            self._teile.append(data)

    def text(self) -> str:
        roh = "".join(self._teile)
        zeilen = [" ".join(z.split()) for z in roh.splitlines()]
        return "\n".join(z for z in zeilen if z)


def html_zu_text(html: str) -> str:
    parser = _HtmlZuText()
    parser.feed(html)
    parser.close()
    return parser.text()


def _header_text(msg, name: str) -> str:
    """Roher, dekodierter Headerwert als Anzeigetext (kein Datums-Parsen,
    keine Interpretation)."""
    wert = msg.get(name)
    if wert is None:
        return ""
    try:
        return str(wert).strip()
    except (UnicodeError, ValueError):
        return ""


def zerlegen(inhalt: bytes) -> EmlInhalt:
    """Zerlegt eine EML-Datei in Textkoerper und Anhaenge. Textprioritaet:
    text/plain vor text/html; ist nur HTML vorhanden, wird es lokal in Text
    umgewandelt. Anhaenge werden als Rohbytes geliefert; der tatsaechliche
    Dateityp wird spaeter per Magic-Bytes bestimmt (nie ueber den
    deklarierten MIME-Typ, siehe dateien.dateityp_erkennen)."""
    msg = BytesParser(policy=policy.default).parsebytes(inhalt)

    text = ""
    text_quelle = "keine"
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is not None:
        try:
            roh = body.get_content()
        except (LookupError, UnicodeError, ValueError):
            roh = ""
        if isinstance(roh, str) and roh.strip():
            if body.get_content_type() == "text/html":
                text = html_zu_text(roh)
                text_quelle = "text/html"
            else:
                text = roh.strip()
                text_quelle = "text/plain"

    anhaenge: list[EmlAnhang] = []
    for index, teil in enumerate(msg.iter_attachments(), start=1):
        rohdaten = teil.get_payload(decode=True)
        if not isinstance(rohdaten, bytes) or not rohdaten:
            continue
        name = teil.get_filename() or f"anhang_{index}"
        anhaenge.append(
            EmlAnhang(
                dateiname=name,
                inhalt=rohdaten,
                deklarierter_typ=teil.get_content_type(),
            )
        )

    return EmlInhalt(
        betreff=_header_text(msg, "Subject"),
        absender=_header_text(msg, "From"),
        mail_datum=_header_text(msg, "Date"),
        text=text,
        text_quelle=text_quelle,
        anhaenge=anhaenge,
    )
