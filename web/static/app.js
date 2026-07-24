/* Belegwaechter — echte Oberflaeche, spricht mit der lokalen JSON-API unter
   /api/*. Keine simulierten Daten, keine externen Aufrufe. */

"use strict";

const $ = (id) => document.getElementById(id);

const AUSGANG_LABEL = {
  uebernommen: ["Fertig", "badge-fertig"],
  review: ["Bitte ansehen", "badge-review"],
  dublette: ["Doppelt, aussortiert", "badge-dublette"],
  original_anfordern: ["Original angefordert", "badge-original"],
  fehlgeschlagen: ["Fehlgeschlagen", "badge-review"],
};

const QUELLE_LABEL = {
  original_vorhanden: "Original vorhanden",
  erfassungsnachweis: "Erfassungsnachweis",
  hinweis: "Hinweis, kein Beleg",
};

const RADAR_LABEL = {
  neu: ["Noch kein Vergleich", "badge-quelle"],
  stabil: ["Stabil", "badge-fertig"],
  veraendert_eindeutig: ["Preis verändert", "badge-review"],
  vergleich_erforderlich: ["Vergleich erforderlich", "badge-review"],
  beleg_fehlt: ["Rechnung fehlt", "badge-dublette"],
};

const FELD_LABEL = {
  anbieter: "Rechnungsaussteller",
  produkt: "Produkt",
  tarif: "Tarif",
  datum: "Datum",
  betrag: "Betrag",
  waehrung: "Währung",
  zeitraum: "Leistungszeitraum",
  referenz: "Referenz",
  abrechnungskanal: "Abrechnung über",
  zahlungsdienst: "Bezahlt über",
  abrechnungsintervall: "Abrechnung",
  naechste_abbuchung: "Nächste Abbuchung",
  naechste_rechnung: "Nächste Rechnung erwartet",
};

const DOKUMENTART_LABEL = {
  rechnung: "Rechnung",
  zahlungsbeleg: "Zahlungsbeleg",
  abo_bestaetigung: "Abo-Bestätigung",
  sonstiger_kostennachweis: "Kostennachweis",
};

let letzteBelege = [];
let letzteVorgaenge = [];

function aktivitaetBadge(v) {
  if (v.naechste_aktivitaet_status === "bestaetigt" && v.naechste_aktivitaet_art === "zahlung") {
    return badge(`Nächste Abbuchung: ${v.naechste_aktivitaet_datum} (belegt)`, "badge-fertig");
  }
  if (v.naechste_aktivitaet_status === "erwartet" && v.naechste_aktivitaet_art === "beleg") {
    const bis = v.naechste_aktivitaet_datum ? `: bis ${v.naechste_aktivitaet_datum}` : "";
    return badge(`Nächste Rechnung erwartet${bis}`, "badge-quelle");
  }
  return badge("Nächste Aktivität unbekannt", "badge-quelle");
}

function belegNachId(id) {
  return letzteBelege.find((b) => b.id === id) || null;
}

function badge(text, klasse) {
  const span = document.createElement("span");
  span.className = `badge ${klasse}`;
  span.textContent = text;
  return span;
}

function fehlerZeigen(text) {
  const el = $("fehler-hinweis");
  el.textContent = text;
  el.hidden = false;
}

function fehlerVerstecken() {
  $("fehler-hinweis").hidden = true;
}

/* ---------- Laden und Rendern ---------- */

async function ladeAlles() {
  const [ergebnis, radar, audit] = await Promise.all([
    fetch("/api/ergebnis").then((r) => r.json()),
    fetch("/api/radar").then((r) => r.json()),
    fetch("/api/audit").then((r) => r.json()),
  ]);
  letzteBelege = ergebnis.belege;
  letzteVorgaenge = ergebnis.vorgaenge || [];
  renderBelege(letzteBelege);
  renderRadar(radar.radar);
  renderAudit(audit.audit);
}

function pdfOriginalLink(b, klassen) {
  // Die URL kommt ausschliesslich aus der API; der Server hat die
  // Verfuegbarkeit (echtes PDF, sicher aufloesbar, %PDF-Signatur) bereits
  // berechnet. Ohne original_pdf_verfuegbar wird nie ein Button gerendert.
  const link = document.createElement("a");
  link.className = klassen;
  link.href = b.original_pdf_url;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "Original-PDF";
  link.setAttribute(
    "aria-label",
    `Original-PDF von ${b.felder.anbieter.wert || b.dateiname} in neuem Tab öffnen`
  );
  return link;
}

function emlOriginalLink(b, klassen) {
  const link = document.createElement("a");
  link.className = klassen;
  link.href = b.original_eml_url;
  link.setAttribute("download", "");
  link.rel = "noopener";
  link.textContent = "Original-E-Mail";
  link.setAttribute(
    "aria-label",
    `Original-E-Mail zu ${b.felder.anbieter.wert || b.dateiname} herunterladen`
  );
  return link;
}

function exportBadges(b) {
  // Exportbereitschaft kommt ausschliesslich aus dem serverseitig
  // berechneten Feld (zentrale Exportregel), nie aus Statuswerten.
  const badges = [];
  if (b.exportbereit) {
    badges.push(badge("Für Export bereit", "badge-fertig"));
    if (b.reviewstatus === "offen") {
      badges.push(badge("Prüfung empfohlen", "badge-review"));
    }
  } else if (b.dokumentart === "rechnung" || b.dokumentart === "sonstiger_kostennachweis") {
    badges.push(badge("Nicht exportbereit", "badge-quelle"));
  }
  return badges;
}

function belegKarte(b) {
  // Kompakte Karte: Titel, Betrag/Datum, Dokumentart, Status, offene
  // Aufgabe und Aktionen. Der vollstaendige Entscheidungstext, Dateiname
  // und Technikdetails stehen in der Detailansicht.
  const karte = document.createElement("div");
  karte.className = "beleg";
  // Der Nutzer sieht das Produkt, nicht primaer die juristische
  // Gesellschaft; ohne belastbares Produkt ehrlich "Produkt nicht
  // eindeutig" mit dem Dateinamen zur Unterscheidung.
  const titel = (b.felder.produkt && b.felder.produkt.wert)
    || b.felder.anbieter.wert || "Produkt nicht eindeutig";
  const [label, klasse] = AUSGANG_LABEL[b.ausgang] || [b.ausgang, "badge-quelle"];

  const z1 = document.createElement("div");
  z1.className = "beleg-zeile1";
  const name = document.createElement("span");
  name.className = "beleg-anbieter";
  name.textContent = titel;
  z1.appendChild(name);
  const metaTeile = [];
  if (b.felder.betrag.wert) {
    metaTeile.push(`${b.felder.betrag.wert} ${b.felder.waehrung.wert || ""}`.trim());
  }
  if (b.felder.datum.wert) metaTeile.push(b.felder.datum.wert);
  if (!b.felder.anbieter.wert && !(b.felder.produkt && b.felder.produkt.wert)) {
    metaTeile.push(b.dateiname);
  }
  if (metaTeile.length > 0) {
    const meta = document.createElement("span");
    meta.className = "beleg-meta";
    meta.textContent = metaTeile.join(" · ");
    z1.appendChild(meta);
  }
  z1.appendChild(badge(label, klasse));
  if (b.dokumentart && DOKUMENTART_LABEL[b.dokumentart]) {
    z1.appendChild(badge(DOKUMENTART_LABEL[b.dokumentart], "badge-quelle"));
  }
  exportBadges(b).forEach((eintrag) => z1.appendChild(eintrag));
  karte.appendChild(z1);

  if (b.reviewstatus === "offen" && b.review_aufgabe) {
    const aufgabe = document.createElement("div");
    aufgabe.className = "beleg-aufgabe";
    aufgabe.textContent = `Nächster Schritt: ${b.review_aufgabe}`;
    karte.appendChild(aufgabe);
  }

  const aktionen = document.createElement("div");
  aktionen.className = "beleg-aktionen";
  const detailsBtn = document.createElement("button");
  detailsBtn.type = "button";
  detailsBtn.className = "btn btn-sekundaer btn-klein";
  detailsBtn.textContent = "Details";
  detailsBtn.setAttribute("aria-label", `Details zu ${titel} öffnen (Status: ${label})`);
  detailsBtn.addEventListener("click", () => detailOeffnen(b));
  aktionen.appendChild(detailsBtn);
  if (b.original_pdf_verfuegbar && b.original_pdf_url) {
    aktionen.appendChild(pdfOriginalLink(b, "btn btn-pdf btn-klein"));
  }
  if (b.original_eml_verfuegbar && b.original_eml_url) {
    aktionen.appendChild(emlOriginalLink(b, "btn btn-pdf btn-klein"));
  }
  karte.appendChild(aktionen);
  return karte;
}

function renderBelege(belege) {
  const liste = $("beleg-liste");
  liste.textContent = "";
  $("leerzustand").hidden = belege.length > 0;
  $("zaehler").hidden = belege.length === 0;

  if (belege.length > 0) {
    const zaehlung = {};
    belege.forEach((b) => { zaehlung[b.ausgang] = (zaehlung[b.ausgang] || 0) + 1; });
    const teile = Object.entries(zaehlung).map(
      ([ausgang, n]) => `${n} ${(AUSGANG_LABEL[ausgang] || [ausgang])[0].toLowerCase()}`
    );
    $("zaehler").textContent = `${belege.length} Belege verarbeitet: ${teile.join(", ")}.`;
  }

  const vorgangJeId = {};
  letzteVorgaenge.forEach((v) => { vorgangJeId[v.id] = v; });
  const gezeigteVorgaenge = new Set();

  // Aussortierte Duplikate erscheinen nicht als eigene grosse Karte,
  // sondern kompakt zusammengefasst am Listenende. Datenbank, Audit und
  // Detailansicht behalten den vollstaendigen Nachweis.
  const dubletten = belege.filter((b) => b.ausgang === "dublette");
  const sichtbare = belege.filter((b) => b.ausgang !== "dublette");

  sichtbare.forEach((b) => {
    // Gruppenkopf: alle Dokumente eines E-Mail-Vorgangs stehen zusammen,
    // mit Betreff, Absender und der naechsten Aktivitaet (nur mit Evidenz).
    if (b.vorgang_id && vorgangJeId[b.vorgang_id] && !gezeigteVorgaenge.has(b.vorgang_id)) {
      gezeigteVorgaenge.add(b.vorgang_id);
      const v = vorgangJeId[b.vorgang_id];
      const kopf = document.createElement("li");
      kopf.className = "vorgang-kopf";
      const zeile = document.createElement("div");
      zeile.className = "vorgang-zeile";
      const titel = document.createElement("span");
      titel.className = "vorgang-titel";
      titel.textContent = `E-Mail-Vorgang: ${v.betreff || v.eml_dateiname}`;
      const absender = document.createElement("span");
      absender.className = "vorgang-absender";
      absender.textContent = v.absender || "";
      zeile.append(titel, absender, aktivitaetBadge(v));
      kopf.appendChild(zeile);
      if (v.naechste_aktivitaet_begruendung) {
        const beg = document.createElement("div");
        beg.className = "vorgang-begruendung";
        beg.textContent = v.naechste_aktivitaet_begruendung;
        kopf.appendChild(beg);
      }
      liste.appendChild(kopf);
    }

    const li = document.createElement("li");
    if (b.vorgang_id) li.classList.add("vorgang-mitglied");
    // Offene Faelle stehen vor fertigen Faellen.
    if (
      b.ausgang === "review" || b.ausgang === "original_anfordern" ||
      b.ausgang === "fehlgeschlagen" || b.reviewstatus === "offen"
    ) {
      li.classList.add("review-zuerst");
    }
    li.appendChild(belegKarte(b));
    liste.appendChild(li);
  });

  if (dubletten.length > 0) {
    const li = document.createElement("li");
    li.className = "dubletten-kompakt";
    const kopf = document.createElement("div");
    kopf.className = "dubletten-titel";
    kopf.textContent =
      dubletten.length === 1
        ? "1 Duplikat erkannt und aussortiert"
        : `${dubletten.length} Duplikate erkannt und aussortiert`;
    li.appendChild(kopf);
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Aussortierte Duplikate anzeigen";
    details.appendChild(summary);
    const ul = document.createElement("ul");
    dubletten.forEach((b) => {
      const zeile = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "dublette-link";
      btn.textContent = b.dateiname;
      btn.setAttribute("aria-label", `Details zum aussortierten Duplikat ${b.dateiname} öffnen`);
      btn.addEventListener("click", () => detailOeffnen(b));
      zeile.appendChild(btn);
      zeile.appendChild(document.createTextNode(` — ${b.begruendung}`));
      ul.appendChild(zeile);
    });
    details.appendChild(ul);
    li.appendChild(details);
    liste.appendChild(li);
  }
}

function aboKostenText(r) {
  if (!r.betrag) return null;
  const betrag = `${r.betrag} ${r.waehrung || ""}`.trim();
  // Vorsichtige Wortwahl: nur bei belastbarem Intervall "je Monat/Jahr";
  // eine Abo-Bestätigung nennt einen Preis, aber keine exportierten Kosten.
  if (r.typ === "abo_bestaetigung") return `Preis laut Bestätigung: ${betrag}`;
  if (r.abrechnung === "monatlich") return `${betrag} je Monat`;
  if (r.abrechnung === "jährlich") return `${betrag} je Jahr`;
  return `Letzter Rechnungsbetrag: ${betrag}`;
}

function aboEreignisText(r) {
  // "Nächste Abbuchung" nur bei ausdrücklich belegtem Datum; eine aus dem
  // Leistungszeitraum abgeleitete Erwartung ist keine Zahlungszusage.
  if (r.naechste_abbuchung) return `Nächste Abbuchung: ${r.naechste_abbuchung}`;
  if (r.naechste_rechnung) return `Nächste Rechnung erwartet: ${r.naechste_rechnung}`;
  return null;
}

function renderRadar(radar) {
  const liste = $("radar-liste");
  liste.textContent = "";
  $("radar-leer").hidden = radar.length > 0;
  radar.forEach((r) => {
    const li = document.createElement("li");
    const karte = document.createElement("details");
    karte.className = "abo-karte";
    const kopf = document.createElement("summary");
    kopf.className = "abo-kopf";
    kopf.setAttribute("aria-expanded", "false");
    karte.addEventListener("toggle", () => {
      kopf.setAttribute("aria-expanded", String(karte.open));
    });

    const name = document.createElement("div");
    name.className = "radar-name";
    name.textContent = r.produkt || "Produkt nicht eindeutig";
    kopf.appendChild(name);

    const zeile2 = document.createElement("div");
    zeile2.className = "radar-zeile2";
    const teile = [];
    if (r.tarif) teile.push(r.tarif);
    if (r.abrechnung) teile.push(`Abrechnung: ${r.abrechnung}`);
    const kosten = aboKostenText(r);
    if (kosten) teile.push(kosten);
    if (teile.length > 0) {
      const meta = document.createElement("span");
      meta.className = "radar-betrag";
      meta.textContent = teile.join(" · ");
      zeile2.appendChild(meta);
    }
    // r.einschaetzung ist null, wenn der Abovergleich fuer diesen Beleg
    // bewusst deaktiviert war. Dann keinen Badge erfinden.
    const eintrag = RADAR_LABEL[r.einschaetzung];
    if (eintrag) {
      const [label, klasse] = eintrag;
      zeile2.appendChild(badge(label, klasse));
    }
    kopf.appendChild(zeile2);

    const ereignis = aboEreignisText(r);
    if (ereignis) {
      const zeile3 = document.createElement("div");
      zeile3.className = "radar-ereignis";
      zeile3.textContent = ereignis;
      kopf.appendChild(zeile3);
    }
    karte.appendChild(kopf);

    const details = document.createElement("div");
    details.className = "abo-details";
    const dl = document.createElement("dl");
    dl.className = "abo-feldliste";
    [
      ["Rechnungsaussteller", r.rechnungsaussteller],
      ["Abrechnung über", r.abrechnungskanal],
      ["Bezahlt über", r.zahlungsdienst],
      ["Letzte Rechnung", r.letzte_rechnung],
      ["Leistungszeitraum", r.zeitraum],
      ["Nächste Abbuchung", r.naechste_abbuchung],
      ["Nächste Rechnung erwartet", r.naechste_rechnung],
      ["Nächster Schritt", r.reviewstatus === "offen" ? r.review_aufgabe : null],
    ].forEach(([label, wert]) => {
      if (!wert) return;
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = wert;
      dl.append(dt, dd);
    });
    details.appendChild(dl);
    if (r.begruendung) {
      const beg = document.createElement("div");
      beg.className = "radar-begruendung";
      beg.textContent = r.begruendung;
      details.appendChild(beg);
    }
    if (r.dokumente && r.dokumente.length > 0) {
      const doks = document.createElement("div");
      doks.className = "abo-dokumente";
      doks.textContent = "Dokumente: ";
      r.dokumente.forEach((d, index) => {
        if (index > 0) doks.appendChild(document.createTextNode(", "));
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dublette-link";
        btn.textContent = d.dateiname;
        btn.addEventListener("click", () => {
          const beleg = belegNachId(d.beleg_id);
          if (beleg) detailOeffnen(beleg);
        });
        doks.appendChild(btn);
      });
      details.appendChild(doks);
    }
    const aktionen = document.createElement("div");
    aktionen.className = "beleg-aktionen";
    if (r.original_pdf_url) {
      const link = document.createElement("a");
      link.className = "btn btn-pdf btn-klein";
      link.href = r.original_pdf_url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "Original-PDF";
      aktionen.appendChild(link);
    }
    const detailsBtn = document.createElement("button");
    detailsBtn.type = "button";
    detailsBtn.className = "btn btn-sekundaer btn-klein";
    detailsBtn.textContent = "Details und Agentendetails";
    detailsBtn.addEventListener("click", () => {
      const beleg = belegNachId(r.beleg_id);
      if (beleg) detailOeffnen(beleg);
    });
    aktionen.appendChild(detailsBtn);
    details.appendChild(aktionen);
    karte.appendChild(details);

    li.appendChild(karte);
    liste.appendChild(li);
  });
}

function renderAudit(audit) {
  const liste = $("audit-liste");
  liste.textContent = "";
  audit.forEach((a) => {
    const li = document.createElement("li");
    const zeit = document.createElement("span");
    zeit.className = "audit-zeit";
    zeit.textContent = (a.zeit || "").replace("T", " ").slice(0, 19);
    li.appendChild(zeit);
    li.appendChild(document.createTextNode(`${a.aktion}: ${a.objekt}`));
    liste.appendChild(li);
  });
}

/* ---------- Detailansicht ---------- */

function detailOeffnen(b) {
  const titel = (b.felder.produkt && b.felder.produkt.wert)
    || b.felder.anbieter.wert || "Produkt nicht eindeutig";
  const [label, klasse] = AUSGANG_LABEL[b.ausgang] || [b.ausgang, "badge-quelle"];
  $("detail-titel").textContent = titel;

  // Sofort sichtbare Meta-Zeile: Dokumentart, Status, Betrag und Datum.
  const metaZeile = $("detail-meta");
  metaZeile.textContent = "";
  if (b.dokumentart && DOKUMENTART_LABEL[b.dokumentart]) {
    metaZeile.appendChild(badge(DOKUMENTART_LABEL[b.dokumentart], "badge-quelle"));
  }
  metaZeile.appendChild(badge(label, klasse));
  exportBadges(b).forEach((eintrag) => metaZeile.appendChild(eintrag));
  const metaTeile = [];
  if (b.felder.betrag.wert) {
    metaTeile.push(`${b.felder.betrag.wert} ${b.felder.waehrung.wert || ""}`.trim());
  }
  if (b.felder.datum.wert) metaTeile.push(b.felder.datum.wert);
  if (metaTeile.length > 0) {
    const metaText = document.createElement("span");
    metaText.className = "beleg-meta";
    metaText.textContent = metaTeile.join(" · ");
    metaZeile.appendChild(metaText);
  }

  const q = $("detail-quelle-inhalt");
  q.textContent = "";
  const karte = document.createElement("div");
  karte.className = "quelle-karte";
  [
    ["Datei", b.dateiname],
    ["Typ", b.dateityp],
    ["Datei-Hash", b.dateihash.slice(0, 16) + "…"],
    ["Quellenstatus", QUELLE_LABEL[b.quellenstatus] || b.quellenstatus],
    ["Erfasst am", (b.erfasst_am || "").replace("T", " ")],
  ].forEach(([k, v]) => {
    const zeile = document.createElement("div");
    const key = document.createElement("strong");
    key.textContent = k + ": ";
    zeile.append(key, document.createTextNode(v));
    karte.appendChild(zeile);
  });
  q.appendChild(karte);

  const dl = $("detail-felder-liste");
  dl.textContent = "";
  Object.entries(b.felder).forEach(([feld, info]) => {
    const dt = document.createElement("dt");
    dt.textContent = FELD_LABEL[feld] || feld;
    const dd = document.createElement("dd");
    if (info.wert === null) {
      const fehlt = document.createElement("span");
      fehlt.className = "feld-fehlt";
      fehlt.textContent = "fehlt";
      dd.appendChild(fehlt);
    } else {
      dd.textContent = info.wert + " ";
      const h = document.createElement("span");
      h.className = "feld-herkunft";
      if (info.herkunft.startsWith("manuell") || info.herkunft.startsWith("im Original")) {
        h.classList.add("feld-manuell");
      }
      h.textContent = `(${info.herkunft})`;
      dd.appendChild(h);
    }
    dl.append(dt, dd);
  });

  const cl = $("detail-checkliste");
  cl.textContent = "";
  b.checkliste.forEach((punkt) => {
    const li = document.createElement("li");
    if (!punkt.erfuellt) li.className = "check-fehlt";
    li.textContent = punkt.name;
    cl.appendChild(li);
  });
  if (b.checkliste.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Keine Checkliste angewendet (kein lesbarer Originalbeleg).";
    cl.appendChild(li);
  }

  const feldwerte = Object.values(b.felder);
  const erkannt = feldwerte.filter((f) => f.wert !== null).length;
  const kritische = b.checkliste.filter((p) => p.kategorie === "kritisch");
  const nichtVorhanden = b.checkliste.filter((p) => p.nicht_vorhanden).map((p) => p.name);
  let zusammenfassung = `${erkannt} von ${feldwerte.length} Angaben erkannt.`;
  if (kritische.length > 0) {
    const kritischOk = kritische.filter((p) => p.erfuellt).length;
    zusammenfassung = `${kritischOk} von ${kritische.length} kritischen Angaben vollständig. ` + zusammenfassung;
  }
  if (nichtVorhanden.length > 0) {
    zusammenfassung += ` Im Original nicht vorhanden: ${nichtVorhanden.join(", ")}.`;
  }
  $("detail-erkannt").textContent = zusammenfassung;

  $("detail-entscheidung").textContent = b.begruendung;

  const reviewHinweis = $("detail-review-hinweis");
  if (b.reviewstatus === "offen") {
    reviewHinweis.textContent = `Nächste Aktion: ${b.review_aufgabe || "Beleg prüfen"}.`;
    reviewHinweis.hidden = false;
  } else {
    reviewHinweis.hidden = true;
  }

  // PDF-Button nur, wenn der Server die Verfuegbarkeit bestaetigt hat
  // (echtes PDF, sicher aufloesbar, %PDF-Signatur). MAILTEXT, Bilder und
  // unbekannte Typen bekommen nie einen (auch keinen deaktivierten) Button.
  const pdfBtn = $("detail-pdf-btn");
  if (b.original_pdf_verfuegbar && b.original_pdf_url) {
    pdfBtn.href = b.original_pdf_url;
    pdfBtn.hidden = false;
  } else {
    pdfBtn.removeAttribute("href");
    pdfBtn.hidden = true;
  }
  const emlBtn = $("detail-eml-btn");
  if (b.original_eml_verfuegbar && b.original_eml_url) {
    emlBtn.href = b.original_eml_url;
    emlBtn.hidden = false;
  } else {
    emlBtn.removeAttribute("href");
    emlBtn.hidden = true;
  }
  const korrekturBtn = $("detail-korrektur-btn");
  korrekturBtn.hidden = !(b.reviewstatus === "offen" &&
    (b.ausgang === "review" || b.ausgang === "uebernommen"));
  aktuellerKorrekturBeleg = b;

  const planContainer = $("detail-plan");
  planContainer.textContent = "";
  (b.plaene || []).forEach((plan, index) => {
    const box = document.createElement("div");
    box.className = "plan-karte";
    if (index > 0) {
      const revision = document.createElement("p");
      revision.className = "plan-revision";
      revision.textContent = `Plan aktualisiert: ${plan.revisionsgrund || ""}`;
      box.appendChild(revision);
    }
    const ziel = document.createElement("p");
    ziel.textContent = `Ziel: ${plan.ziel}`;
    box.appendChild(ziel);
    const quelle = document.createElement("p");
    quelle.textContent = `Quellenklasse: ${plan.quellenklasse}`;
    box.appendChild(quelle);

    const werkzeugeListe = document.createElement("ul");
    (plan.werkzeuge || []).forEach((w) => {
      const li = document.createElement("li");
      li.textContent = `${w.ausfuehren ? "Aktiv" : "Übersprungen"} — ${w.name} (${w.werkzeug}): ${w.begruendung}`;
      werkzeugeListe.appendChild(li);
    });
    box.appendChild(werkzeugeListe);

    if ((plan.stopbedingungen || []).length > 0) {
      const stop = document.createElement("p");
      stop.textContent = `Stop-/Reviewbedingungen: ${plan.stopbedingungen.join(", ")}`;
      box.appendChild(stop);
    }
    planContainer.appendChild(box);
  });

  const schritteListe = $("detail-schritte");
  schritteListe.textContent = "";
  const schritteFuerBeleg = (window.__letzteSchritte || []).filter((s) => s.beleg_id === b.id);
  schritteFuerBeleg.forEach((s) => {
    const li = document.createElement("li");
    const zeit = document.createElement("span");
    zeit.className = "audit-zeit";
    zeit.textContent = (s.start || "").replace("T", " ").slice(11, 19);
    li.appendChild(zeit);
    li.appendChild(document.createTextNode(`${s.schritt} [${s.status}, ${s.werkzeug}]: ${s.begruendung}`));
    schritteListe.appendChild(li);
  });

  // Pruefnachweis und Technikbereich starten bei jedem Oeffnen eingeklappt.
  $("pruefnachweis-details").open = false;
  $("technik-details").open = false;

  $("detail-overlay").hidden = false;
  document.querySelector(".detail-inhalt").scrollTop = 0;
  $("detail-schliessen").focus();
}

function detailSchliessen() {
  $("detail-overlay").hidden = true;
}

/* ---------- Upload ---------- */

async function dateienVerarbeiten(dateiListe) {
  if (!dateiListe || dateiListe.length === 0) return;
  fehlerVerstecken();
  const formData = new FormData();
  for (const datei of dateiListe) formData.append("dateien", datei, datei.name);

  $("upload-zone").disabled = true;
  $("schritte").hidden = false;
  $("schritte-status").textContent = `Agent verarbeitet ${dateiListe.length} Datei(en) …`;

  try {
    const resp = await fetch("/api/verarbeiten", { method: "POST", body: formData });
    const daten = await resp.json();
    if (!resp.ok) {
      fehlerZeigen(daten.fehler || "Verarbeitung fehlgeschlagen.");
    } else {
      window.__letzteSchritte = daten.schritte || [];
      $("schritte-status").textContent = `Zuletzt verarbeitet: ${daten.belege.length} Datei(en).`;
      await ladeAlles();
    }
  } catch (err) {
    fehlerZeigen("Verbindung zum lokalen Agenten fehlgeschlagen: " + err.message);
  } finally {
    $("upload-zone").disabled = false;
  }
}

$("upload-zone").addEventListener("click", () => $("datei-input").click());
$("datei-input").addEventListener("change", (e) => {
  dateienVerarbeiten(e.target.files);
  e.target.value = "";
});

["dragover", "dragenter"].forEach((ev) =>
  $("upload-zone").addEventListener(ev, (e) => { e.preventDefault(); $("upload-zone").classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  $("upload-zone").addEventListener(ev, (e) => {
    e.preventDefault();
    $("upload-zone").classList.remove("drag");
    if (ev === "drop" && e.dataTransfer.files.length > 0) {
      dateienVerarbeiten(e.dataTransfer.files);
    }
  })
);

/* ---------- Korrektur-Dialog: Angaben prüfen und ergänzen ---------- */

let aktuellerKorrekturBeleg = null;

const KORREKTUR_FELDER = [
  ["produkt", "Produkt"],
  ["anbieter", "Rechnungsaussteller"],
  ["referenz", "Referenz oder Rechnungsnummer"],
  ["datum", "Datum"],
  ["betrag", "Betrag"],
  ["waehrung", "Währung"],
  ["zeitraum", "Leistungszeitraum"],
  ["tarif", "Tarif oder Beschreibung"],
  ["abrechnungsintervall", "Abrechnung"],
  ["naechste_abbuchung", "Nächste Abbuchung (nur wenn im Original belegt)"],
];

const KORREKTUR_AKTIONEN = [
  ["unveraendert", "Unverändert lassen"],
  ["setzen", "Wert eintragen"],
  ["bestaetigen", "Erkannten Wert bestätigen"],
  ["nicht_vorhanden", "Im Original nicht vorhanden"],
  ["zuruecksetzen", "Zurück zum erkannten Wert"],
];

function korrekturZeile(feld, labelText, info) {
  const zeile = document.createElement("div");
  zeile.className = "korrektur-zeile";
  const kopf = document.createElement("div");
  kopf.className = "korrektur-feldkopf";
  const label = document.createElement("span");
  label.className = "korrektur-label";
  label.textContent = labelText;
  const aktuell = document.createElement("span");
  aktuell.className = "korrektur-aktuell";
  aktuell.textContent = info.wert === null ? `fehlt (${info.herkunft})` : `${info.wert} (${info.herkunft})`;
  kopf.append(label, aktuell);

  const auswahl = document.createElement("select");
  auswahl.className = "korrektur-aktion";
  auswahl.setAttribute("aria-label", `Aktion für ${labelText}`);
  KORREKTUR_AKTIONEN.forEach(([wert, text]) => {
    const option = document.createElement("option");
    option.value = wert;
    option.textContent = text;
    auswahl.appendChild(option);
  });

  const eingabe = document.createElement("div");
  eingabe.className = "korrektur-eingabe";
  eingabe.hidden = true;
  if (feld === "zeitraum") {
    const von = document.createElement("input");
    von.type = "text";
    von.placeholder = "von, z.B. 01.08.2026";
    von.setAttribute("aria-label", "Leistungszeitraum von");
    von.dataset.teil = "von";
    const bis = document.createElement("input");
    bis.type = "text";
    bis.placeholder = "bis, z.B. 31.08.2026";
    bis.setAttribute("aria-label", "Leistungszeitraum bis");
    bis.dataset.teil = "bis";
    eingabe.append(von, bis);
  } else {
    const input = document.createElement("input");
    input.type = "text";
    input.maxLength = 200;
    input.setAttribute("aria-label", `Neuer Wert für ${labelText}`);
    eingabe.appendChild(input);
  }
  auswahl.addEventListener("change", () => {
    eingabe.hidden = auswahl.value !== "setzen";
  });

  zeile.append(kopf, auswahl, eingabe);
  zeile.dataset.feld = feld;
  return zeile;
}

function korrekturOeffnen() {
  const b = aktuellerKorrekturBeleg;
  if (!b) return;
  const container = $("korrektur-felder");
  container.textContent = "";

  // Standardmaessig sichtbar sind nur fehlende, unsichere oder
  // pruefenswerte Felder; belastbar erkannte Werte liegen im geschlossenen
  // Bereich "Bereits erkannt".
  const problematisch = (feld) => {
    const info = b.felder[feld];
    if (!info || info.wert === null) return true;
    const punkt = b.checkliste.find((p) => p.feld === feld);
    return punkt ? !punkt.erfuellt : false;
  };

  const erkannt = document.createElement("details");
  erkannt.className = "korrektur-erkannt";
  const erkanntTitel = document.createElement("summary");
  erkanntTitel.textContent = "Bereits erkannt";
  erkannt.appendChild(erkanntTitel);

  let offene = 0;
  KORREKTUR_FELDER.forEach(([feld, labelText]) => {
    const info = b.felder[feld] || { wert: null, herkunft: "fehlt" };
    const zeile = korrekturZeile(feld, labelText, info);
    if (problematisch(feld)) {
      offene += 1;
      container.appendChild(zeile);
    } else {
      erkannt.appendChild(zeile);
    }
  });
  if (offene === 0) {
    const hinweis = document.createElement("p");
    hinweis.className = "korrektur-hinweis";
    hinweis.textContent = "Keine offenen Angaben. Bereits erkannte Werte lassen sich unten prüfen.";
    container.appendChild(hinweis);
  }
  if (erkannt.childElementCount > 1) {
    container.appendChild(erkannt);
  }
  $("korrektur-fehler").hidden = true;
  $("detail-overlay").hidden = true;
  $("korrektur-overlay").hidden = false;
  $("korrektur-schliessen").focus();
}

function korrekturSchliessen() {
  $("korrektur-overlay").hidden = true;
}

async function korrekturSpeichern() {
  const b = aktuellerKorrekturBeleg;
  if (!b) return;
  const felder = {};
  document.querySelectorAll("#korrektur-felder .korrektur-zeile").forEach((zeile) => {
    const aktion = zeile.querySelector(".korrektur-aktion").value;
    if (aktion === "unveraendert") return;
    const feld = zeile.dataset.feld;
    if (aktion === "setzen") {
      if (feld === "zeitraum") {
        const von = zeile.querySelector('input[data-teil="von"]').value.trim();
        const bis = zeile.querySelector('input[data-teil="bis"]').value.trim();
        felder[feld] = { aktion, wert: { von, bis } };
      } else {
        felder[feld] = { aktion, wert: zeile.querySelector("input").value.trim() };
      }
    } else {
      felder[feld] = { aktion };
    }
  });
  if (Object.keys(felder).length === 0) {
    korrekturSchliessen();
    return;
  }
  $("korrektur-speichern").disabled = true;
  try {
    const resp = await fetch(`/api/belege/${encodeURIComponent(b.id)}/korrekturen`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ felder }),
    });
    const daten = await resp.json();
    if (!resp.ok) {
      const fehlerEl = $("korrektur-fehler");
      fehlerEl.textContent = daten.fehler || "Speichern fehlgeschlagen.";
      fehlerEl.hidden = false;
      return;
    }
    korrekturSchliessen();
    await ladeAlles();
    detailOeffnen(daten.beleg);
  } catch (err) {
    const fehlerEl = $("korrektur-fehler");
    fehlerEl.textContent = "Verbindung zum lokalen Agenten fehlgeschlagen: " + err.message;
    fehlerEl.hidden = false;
  } finally {
    $("korrektur-speichern").disabled = false;
  }
}

$("detail-korrektur-btn").addEventListener("click", korrekturOeffnen);
$("korrektur-schliessen").addEventListener("click", korrekturSchliessen);
$("korrektur-abbrechen").addEventListener("click", korrekturSchliessen);
$("korrektur-speichern").addEventListener("click", korrekturSpeichern);
$("korrektur-overlay").addEventListener("click", (e) => {
  if (e.target === $("korrektur-overlay")) korrekturSchliessen();
});

/* ---------- Detail-, Reset- und Export-Ereignisse ---------- */

$("detail-schliessen").addEventListener("click", detailSchliessen);
$("detail-overlay").addEventListener("click", (e) => { if (e.target === $("detail-overlay")) detailSchliessen(); });

$("reset-btn").addEventListener("click", () => { $("reset-overlay").hidden = false; $("reset-nein").focus(); });
$("reset-nein").addEventListener("click", () => { $("reset-overlay").hidden = true; });
$("reset-schliessen").addEventListener("click", () => { $("reset-overlay").hidden = true; });
$("reset-overlay").addEventListener("click", (e) => { if (e.target === $("reset-overlay")) $("reset-overlay").hidden = true; });
$("reset-ja").addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  $("reset-overlay").hidden = true;
  $("schritte").hidden = true;
  window.__letzteSchritte = [];
  await ladeAlles();
});

$("export-btn").addEventListener("click", () => {
  $("export-status").textContent = "optitax_export.csv wird heruntergeladen …";
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!$("detail-overlay").hidden) detailSchliessen();
    if (!$("reset-overlay").hidden) $("reset-overlay").hidden = true;
    if (!$("korrektur-overlay").hidden) korrekturSchliessen();
  }
});

ladeAlles();
