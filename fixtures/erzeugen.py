"""Erzeugt die synthetischen Demo-Fixtures fuer den Belegwaechter.

Alle Anbieter, Rechnungsnummern und Betraege sind vollstaendig erfunden.
PDFs werden in reiner PDF-1.4-Syntax von Hand geschrieben (keine
Zusatzbibliothek fuer die Erzeugung noetig). Das Screenshot-PNG wird mit
Pillow erzeugt (nur zur Fixture-Erzeugung; Pillow ist keine Laufzeit-
Abhaengigkeit des Belegwaechters selbst).

Aufruf: python fixtures/erzeugen.py
"""
from __future__ import annotations

from pathlib import Path

HIER = Path(__file__).resolve().parent


def _escape(s: str) -> str:
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _pdf_bytes(zeilen: list[str]) -> bytes:
    content_lines = ["BT", "/F1 11 Tf"]
    y = 780
    for text in zeilen:
        content_lines.append(f"1 0 0 1 50 {y} Tm ({_escape(text)}) Tj")
        y -= 20
    content = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n".encode("latin-1")
        + content
        + b"\nendstream",
    ]

    out = [b"%PDF-1.4\n"]
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(sum(len(b) for b in out))
        out.append(f"{i} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n")

    xref_offset = sum(len(b) for b in out)
    n = len(objects) + 1
    xref = [f"xref\n0 {n}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref.append(f"{off:010d} 00000 n \n".encode("latin-1"))
    trailer = f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("latin-1")

    return b"".join(out) + b"".join(xref) + trailer


def _pdf_schreiben(pfad: Path, zeilen: list[str]) -> None:
    pfad.write_bytes(_pdf_bytes(zeilen))


def _boundaries_fixieren(msg) -> None:
    """EmailMessage erzeugt MIME-Boundaries per Zufall. Fuer deterministische
    Fixtures (DeterminismusTest, stabile Git-Diffs) werden alle Boundaries
    nach dem Aufbau auf feste Werte gesetzt."""
    zaehler = 0
    for teil in msg.walk():
        if teil.is_multipart():
            zaehler += 1
            teil.set_boundary(f"belegwaechter-fixture-boundary-{zaehler:02d}")


def _eml_schreiben(pfad: Path, msg) -> None:
    _boundaries_fixieren(msg)
    pfad.write_bytes(msg.as_bytes())


def _eml_cloudbasis_rechnung_und_zahlung():
    """EML mit zwei PDF-Anhaengen: Rechnung und Zahlungsbeleg desselben
    Vorgangs. Der Zahlungsbeleg ist absichtlich als application/octet-stream
    deklariert (Typ-Erkennung muss den Magic-Bytes trauen, nicht dem
    MIME-Header). Der Textkoerper ist Begleittext, base64-kodiert."""
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "CloudBasis GmbH <abrechnung@cloudbasis.example>"
    msg["To"] = "demo@belegwaechter.invalid"
    msg["Subject"] = "Ihre CloudBasis Rechnung August 2026"
    msg["Date"] = "Sat, 01 Aug 2026 08:00:00 +0200"
    msg["Message-ID"] = "<fixture-cloudbasis-august@cloudbasis.example>"
    msg.set_content(
        "Guten Tag,\n\nim Anhang finden Sie Ihre Rechnung und den Zahlungsbeleg "
        "fuer August 2026.\n\nIhre CloudBasis GmbH\n",
        cte="base64",
    )
    msg.add_alternative(
        "<html><body><table><tr><td>Guten Tag,</td></tr>"
        "<tr><td>im Anhang finden Sie Ihre Rechnung und den Zahlungsbeleg "
        "fuer August 2026.</td></tr>"
        "<tr><td>Ihre CloudBasis GmbH</td></tr></table></body></html>",
        subtype="html",
        cte="quoted-printable",
    )
    msg.add_attachment(
        _pdf_bytes(
            [
                "CloudBasis GmbH",
                "Rechnung Nr. RE-3301-08",
                "Datum: 01.08.2026",
                "Leistungszeitraum: 01.08.2026 - 31.08.2026",
                "Tarif: Standard",
                "Betrag: 23,00 EUR",
                "Waehrung: EUR",
            ]
        ),
        maintype="application",
        subtype="pdf",
        filename="cloudbasis_august_rechnung.pdf",
    )
    msg.add_attachment(
        _pdf_bytes(
            [
                "CloudBasis GmbH",
                "Zahlungsbeleg",
                "Zahlung erhalten zur Rechnung Nr. RE-3301-08",
                "Datum: 01.08.2026",
                "Leistungszeitraum: 01.08.2026 - 31.08.2026",
                "Tarif: Standard",
                "Betrag: 23,00 EUR",
                "Waehrung: EUR",
            ]
        ),
        maintype="application",
        subtype="octet-stream",
        filename="cloudbasis_august_zahlungsbeleg.pdf",
    )
    return msg


def _eml_schreibki_abo_bestaetigung():
    """Abo-Bestaetigung mit explizitem Verlaengerungsdatum, nur als HTML-Teil
    in multipart/alternative (kein text/plain-Fallback, kein Anhang)."""
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "SchreibKI Plus <service@schreibki.example>"
    msg["To"] = "demo@belegwaechter.invalid"
    msg["Subject"] = "Ihre Abo-Bestaetigung"
    msg["Date"] = "Sun, 05 Jul 2026 10:00:00 +0200"
    msg["Message-ID"] = "<fixture-schreibki-abo@schreibki.example>"
    msg.make_alternative()
    msg.add_alternative(
        "<html><head><style>td { color: #000; }</style></head><body>"
        '<table style="width:100%"><tr><td>SchreibKI Plus</td></tr>'
        "<tr><td>Abo-Bestaetigung</td></tr>"
        "<tr><td>Ihr Abo verlaengert sich am 05.08.2026.</td></tr>"
        "<tr><td>Tarif:</td><td>Plus</td></tr>"
        "<tr><td>Betrag:</td><td>12,00 EUR</td></tr>"
        "<tr><td>Waehrung:</td><td>EUR</td></tr></table>"
        '<img src="https://tracking.invalid/pixel.gif" width="1" height="1">'
        "</body></html>",
        subtype="html",
        cte="quoted-printable",
    )
    return msg


def _eml_mobiltel_zahlungsbestaetigung():
    """Reine Zahlungsbestaetigung ohne Rechnung und ohne Anhang (text/plain,
    nicht multipart)."""
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "MobilTel Kundenservice <service@mobiltel.example>"
    msg["To"] = "demo@belegwaechter.invalid"
    msg["Subject"] = "Zahlungsbestaetigung"
    msg["Date"] = "Tue, 18 Aug 2026 12:00:00 +0200"
    msg["Message-ID"] = "<fixture-mobiltel-zahlung@mobiltel.example>"
    msg.set_content(
        "MobilTel Kundenservice\n"
        "Zahlungsbestaetigung\n"
        "Wir haben Ihre Zahlung erhalten.\n"
        "Datum: 18.08.2026\n"
        "Betrag: 24,99 EUR\n"
        "Waehrung: EUR\n"
    )
    return msg


def _eml_domainly_nur_html_rechnung():
    """Rechnung ausschliesslich im HTML-Textkoerper: nicht multipart, direkt
    text/html mit Tabellenlayout, Inline-CSS und Tracking-Pixel (das nie
    geladen wird). Kein Anhang."""
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Domainly GmbH <billing@domainly.example>"
    msg["To"] = "demo@belegwaechter.invalid"
    msg["Subject"] = "Rechnung Hosting Basic August 2026"
    msg["Date"] = "Sat, 01 Aug 2026 06:30:00 +0200"
    msg["Message-ID"] = "<fixture-domainly-august@domainly.example>"
    msg.set_content(
        "<html><head><title>Rechnung</title></head><body>"
        '<img src="https://tracking.invalid/open.gif" width="1" height="1">'
        '<table style="border:0"><tr><td>Domainly GmbH</td></tr>'
        "<tr><td>Rechnung Nr. RE-9001-08</td></tr>"
        "<tr><td>Datum:</td><td>01.08.2026</td></tr>"
        "<tr><td>Leistungszeitraum:</td><td>monatlich</td></tr>"
        "<tr><td>Tarif:</td><td>Hosting Basic</td></tr>"
        "<tr><td>Betrag:</td><td>9,00 EUR</td></tr>"
        "<tr><td>Waehrung:</td><td>EUR</td></tr></table>"
        "</body></html>",
        subtype="html",
        cte="quoted-printable",
    )
    return msg


def _screenshot_schreiben(pfad: Path) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (420, 260), color=(246, 247, 249))
    d = ImageDraw.Draw(img)
    d.text((20, 20), "MobilTel App", fill=(20, 24, 30))
    d.text((20, 50), "Ihre Abbuchung: 24,99 EUR", fill=(20, 24, 30))
    d.text((20, 80), "18.07.2026", fill=(20, 24, 30))
    d.text((20, 110), "Vertrag: Smart L", fill=(20, 24, 30))
    d.text((20, 230), "[unterer Bildrand abgeschnitten]", fill=(140, 140, 140))
    img.save(pfad)


def main() -> None:
    _pdf_schreiben(
        HIER / "domainly_juli.pdf",
        [
            "Domainly GmbH",
            "Rechnung Nr. RE-9001-07",
            "Datum: 01.07.2026",
            "Leistungszeitraum: monatlich",
            "Tarif: Hosting Basic",
            "Betrag: 9,00 EUR",
            "Waehrung: EUR",
        ],
    )
    _pdf_schreiben(
        HIER / "cloudbasis_juni.pdf",
        [
            "CloudBasis GmbH",
            "Rechnung Nr. RE-3301-06",
            "Datum: 01.06.2026",
            "Leistungszeitraum: monatlich",
            "Tarif: Standard",
            "Betrag: 19,00 EUR",
            "Waehrung: EUR",
        ],
    )
    _pdf_schreiben(
        HIER / "cloudbasis_juli.pdf",
        [
            "CloudBasis GmbH",
            "Rechnung Nr. RE-3301-07",
            "Datum: 01.07.2026",
            "Leistungszeitraum: monatlich",
            "Tarif: Standard",
            "Betrag: 23,00 EUR",
            "Waehrung: EUR",
        ],
    )
    _pdf_schreiben(
        HIER / "cloudbasis_juli_dublette.pdf",
        [
            "CloudBasis GmbH",
            "Erneuter Versand Ihrer Rechnung",
            "Rechnung Nr. RE-3301-07",
            "Datum: 01.07.2026",
            "Leistungszeitraum: monatlich",
            "Tarif: Standard",
            "Betrag: 23,00 EUR",
            "Waehrung: EUR",
        ],
    )
    _pdf_schreiben(
        HIER / "schreibki_monatlich.pdf",
        [
            "SchreibKI Plus",
            "Rechnung Nr. INV-99050",
            "Datum: 05.06.2026",
            "Leistungszeitraum: monatlich",
            "Tarif: Plus",
            "Betrag: 12,00 EUR",
            "Waehrung: EUR",
        ],
    )
    _pdf_schreiben(
        HIER / "schreibki_jahresrechnung.pdf",
        [
            "SchreibKI Plus",
            "Rechnung Nr. INV-99120",
            "Datum: 05.07.2026",
            "Leistungszeitraum: jaehrlich",
            "Tarif: Plus",
            "Betrag: 120,00 EUR",
            "Waehrung: EUR",
        ],
    )
    screenshot_pfad = HIER / "mobiltel_screenshot.png"
    try:
        _screenshot_schreiben(screenshot_pfad)
    except ModuleNotFoundError:
        # Pillow ist nur fuer die PNG-Erzeugung noetig (keine Laufzeit-
        # Abhaengigkeit). Ohne Pillow bleibt ein bereits vorhandenes PNG
        # unveraendert; fehlt es ganz, ist das ein echter Fehler.
        if not screenshot_pfad.exists():
            raise
        print("Hinweis: Pillow nicht installiert, vorhandenes PNG-Fixture unveraendert gelassen.")
    _eml_schreiben(HIER / "cloudbasis_rechnung_und_zahlung.eml", _eml_cloudbasis_rechnung_und_zahlung())
    _eml_schreiben(HIER / "schreibki_abo_bestaetigung.eml", _eml_schreibki_abo_bestaetigung())
    _eml_schreiben(HIER / "mobiltel_zahlungsbestaetigung.eml", _eml_mobiltel_zahlungsbestaetigung())
    _eml_schreiben(HIER / "domainly_nur_html_rechnung.eml", _eml_domainly_nur_html_rechnung())
    print("11 Fixtures erzeugt in", HIER)


if __name__ == "__main__":
    main()
