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
  neu: ["Neu erfasst", "badge-fertig"],
  stabil: ["Stabil", "badge-fertig"],
  veraendert_eindeutig: ["Preis verändert", "badge-review"],
  vergleich_erforderlich: ["Vergleich erforderlich", "badge-review"],
  beleg_fehlt: ["Beleg fehlt", "badge-dublette"],
};

const REVIEWSTATUS_LABEL = {
  offen: ["Prüfung offen", "badge-review"],
};

let letzteBelege = [];

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
  renderBelege(letzteBelege);
  renderRadar(radar.radar);
  renderAudit(audit.audit);
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

  belege.forEach((b) => {
    const li = document.createElement("li");
    if (b.ausgang === "review" || b.ausgang === "original_anfordern" || b.ausgang === "fehlgeschlagen") {
      li.className = "review-zuerst";
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "beleg";
    const [label, klasse] = AUSGANG_LABEL[b.ausgang] || [b.ausgang, "badge-quelle"];
    btn.setAttribute("aria-label", `${b.felder.anbieter.wert || b.dateiname}, Status: ${label}. Details öffnen.`);

    const z1 = document.createElement("div");
    z1.className = "beleg-zeile1";
    const name = document.createElement("span");
    name.className = "beleg-anbieter";
    name.textContent = b.felder.anbieter.wert || b.dateiname;
    const meta = document.createElement("span");
    meta.className = "beleg-meta";
    const betragTeil = b.felder.betrag.wert ? `${b.felder.betrag.wert} ${b.felder.waehrung.wert || ""} · ` : "";
    const datumTeil = b.felder.datum.wert ? `${b.felder.datum.wert} · ` : "";
    meta.textContent = `${betragTeil}${datumTeil}${b.dateiname}`;
    z1.append(name, meta, badge(label, klasse));
    z1.appendChild(badge(QUELLE_LABEL[b.quellenstatus] || b.quellenstatus, "badge-quelle"));
    if (b.reviewstatus === "offen" && REVIEWSTATUS_LABEL[b.reviewstatus]) {
      const [reviewLabel, reviewKlasse] = REVIEWSTATUS_LABEL[b.reviewstatus];
      z1.appendChild(badge(reviewLabel, reviewKlasse));
    }

    const beg = document.createElement("div");
    beg.className = "beleg-begruendung";
    beg.textContent =
      b.ausgang === "uebernommen" && b.reviewstatus === "offen"
        ? "Beleg vorbereitet. Preisvergleich benötigt Prüfung."
        : b.begruendung;

    btn.append(z1, beg);
    btn.addEventListener("click", () => detailOeffnen(b));
    li.appendChild(btn);
    liste.appendChild(li);
  });
}

function renderRadar(radar) {
  const liste = $("radar-liste");
  liste.textContent = "";
  $("radar-leer").hidden = radar.length > 0;
  radar.forEach((r) => {
    const li = document.createElement("li");
    li.className = "radar-karte";
    const z1 = document.createElement("div");
    z1.className = "radar-zeile1";
    const name = document.createElement("span");
    name.className = "radar-name";
    name.textContent = `${r.anbieter} (${r.zeitraum || "unbekannt"})`;
    const rechts = document.createElement("span");
    rechts.className = "radar-betrag";
    rechts.textContent = r.betrag ? `${r.betrag} ${r.waehrung || ""} ` : "";
    const [label, klasse] = RADAR_LABEL[r.einschaetzung] || [r.einschaetzung, "badge-quelle"];
    rechts.appendChild(badge(label, klasse));
    z1.append(name, rechts);
    const beg = document.createElement("div");
    beg.className = "radar-begruendung";
    beg.textContent = r.begruendung;
    li.append(z1, beg);
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
  const anbieter = b.felder.anbieter.wert || b.dateiname;
  const [label] = AUSGANG_LABEL[b.ausgang] || [b.ausgang];
  $("detail-titel").textContent = `${anbieter} — ${label}`;

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
    dt.textContent = feld;
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

  $("detail-entscheidung").textContent = b.begruendung;

  const reviewHinweis = $("detail-review-hinweis");
  if (b.ausgang === "uebernommen" && b.reviewstatus === "offen") {
    reviewHinweis.textContent = `Beleg vorbereitet. Preisvergleich benötigt Prüfung: ${b.review_aufgabe || "Preisänderung prüfen"}.`;
    reviewHinweis.hidden = false;
  } else {
    reviewHinweis.hidden = true;
  }

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

  $("detail-overlay").hidden = false;
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

/* ---------- Detail-, Reset- und Export-Ereignisse ---------- */

$("detail-schliessen").addEventListener("click", detailSchliessen);
$("detail-overlay").addEventListener("click", (e) => { if (e.target === $("detail-overlay")) detailSchliessen(); });

$("reset-btn").addEventListener("click", () => { $("reset-overlay").hidden = false; $("reset-nein").focus(); });
$("reset-nein").addEventListener("click", () => { $("reset-overlay").hidden = true; });
$("reset-overlay").addEventListener("click", (e) => { if (e.target === $("reset-overlay")) $("reset-overlay").hidden = true; });
$("reset-ja").addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  $("reset-overlay").hidden = true;
  $("schritte").hidden = true;
  window.__letzteSchritte = [];
  await ladeAlles();
});

$("export-btn").addEventListener("click", () => {
  $("export-status").textContent = "belegwaechter_export.csv wird heruntergeladen …";
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!$("detail-overlay").hidden) detailSchliessen();
    if (!$("reset-overlay").hidden) $("reset-overlay").hidden = true;
  }
});

ladeAlles();
