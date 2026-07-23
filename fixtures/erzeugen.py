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


def _pdf_schreiben(pfad: Path, zeilen: list[str]) -> None:
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

    pfad.write_bytes(b"".join(out) + b"".join(xref) + trailer)


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
    _screenshot_schreiben(HIER / "mobiltel_screenshot.png")
    print("7 Fixtures erzeugt in", HIER)


if __name__ == "__main__":
    main()
