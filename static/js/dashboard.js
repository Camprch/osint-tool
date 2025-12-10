let map;
let countryCoords = {};
let countryAliases = {};
let timelineDates = [];
let currentDate = null;
let currentCountry = null;
let markersByCountry = {};

const IS_MOBILE = window.matchMedia("(max-width: 768px)").matches;

// ---------------------------------------------------------
// Init map
// ---------------------------------------------------------
function initMap() {
    map = L.map("map", {
        worldCopyJump: true, // n'affiche qu'une seule copie du monde
        minZoom: 2,
        maxZoom: 5,
        tapTolerance: 30,
    }).setView([20, 0], 2);

    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
            attribution: "&copy; CARTO",
            noWrap: true, // empêche le wrap horizontal
        }
    ).addTo(map);
}

// ---------------------------------------------------------
// Utilitaires
// ---------------------------------------------------------
function clearMarkers() {
    Object.values(markersByCountry).forEach((m) => map.removeLayer(m));
    markersByCountry = {};
}

/**
 * Style des pastilles :
 * - rayon min 5, max ~20 (plus petit qu'avant)
 * - couleur qui varie avec le nombre d'événements
 */
function markerStyle(count) {
    const n = Math.max(1, count || 1);

    // Rayons différents selon mobile / desktop
    const minRadius = IS_MOBILE ? 10 : 5;
    const maxRadius = IS_MOBILE ? 20 : 10;

    const maxCount = 30; // adapter si nécessaire
    const ratio = Math.min(n / maxCount, 1);
    const radius = minRadius + (maxRadius - minRadius) * ratio;

    let color;
    if (n < 5) {
        color = "#22c55e"; // vert
    } else if (n < 15) {
        color = "#eab308"; // jaune
    } else {
        color = "#f97316"; // orange
    }

    return {
        radius,
        color,
        fillColor: color,
        fillOpacity: 0.85,
        weight: IS_MOBILE ? 2 : 1,
    };
}

// ---------------------------------------------------------
// Charger countries.json
// ---------------------------------------------------------
async function loadCountryData() {
    const resp = await fetch("/static/data/countries.json");
    const data = await resp.json();
    countryCoords = data.coordinates || {};
    countryAliases = data.aliases || {};
}

// ---------------------------------------------------------
// Charger les dates (timeline)
// ---------------------------------------------------------
async function loadTimeline() {
    const resp = await fetch("/api/dates");
    const data = await resp.json();
    timelineDates = data.dates || [];

    const select = document.getElementById("timeline");
    if (!select) return;

    select.innerHTML = "";

    timelineDates.forEach((dateStr) => {
        const opt = document.createElement("option");
        opt.value = dateStr;
        opt.textContent = dateStr;
        select.appendChild(opt);
    });

    if (timelineDates.length > 0) {
        currentDate = timelineDates[0];
        select.value = currentDate;
    } else {
        currentDate = null;
    }

    // Changer la date ne change plus la carte :
    // on ne recharge que les événements pour le pays sélectionné
    select.addEventListener("change", () => {
        currentDate = select.value;
        if (currentCountry) {
            loadEvents(currentCountry);
        }
    });
}

// ---------------------------------------------------------
// Charger les pays actifs (toutes les pastilles)
// ---------------------------------------------------------
async function loadActiveCountries() {
    const resp = await fetch("/api/countries/active");
    if (!resp.ok) {
        console.error("Erreur /api/countries/active", resp.status);
        return;
    }
    const countries = await resp.json(); // [{ country, events_count, last_date }, ...]

    clearMarkers();

    const missing = [];
    const alert = document.getElementById("dashboard-alert");

    countries.forEach((c) => {
        const name = c.country;
        const count = c.events_count;

        let coordKey = name;
        if (!(coordKey in countryCoords) && name in countryAliases) {
            coordKey = countryAliases[name];
        }

        if (!(coordKey in countryCoords)) {
            missing.push(name);
            return;
        }

        const [lat, lon] = countryCoords[coordKey];

        // On évite les doublons : une seule pastille par pays
        if (markersByCountry[name]) {
            return;
        }

        const style = markerStyle(count);
        const marker = L.circleMarker([lat, lon], style);

        marker.bindPopup(`<b>${name}</b><br>Événements : ${count}`);

        const baseRadius = style.radius;
        marker.on("mouseover", function () {
            this.setStyle({ radius: baseRadius * 1.15 });
        });
        marker.on("mouseout", function () {
            this.setStyle({ radius: baseRadius });
        });

        marker.on("click", () => openSidePanel(name));

        marker.addTo(map);
        markersByCountry[name] = marker;
    });

    if (alert) {
        if (missing.length > 0) {
            alert.textContent = `⚠️ Pays non géolocalisés : ${missing.join(", ")}`;
            alert.style.display = "block";
        } else {
            alert.style.display = "none";
        }
    }
}

// ---------------------------------------------------------
// Rendu des événements dans le panel
// ---------------------------------------------------------
function renderEvents(data) {
    const eventsContainer = document.getElementById("events");

    if (!data || !data.zones || data.zones.length === 0) {
        eventsContainer.textContent = "Aucun événement.";
        return;
    }

    const html = data.zones
        .map((zone, idx) => {
            const header =
                [zone.region, zone.location].filter(Boolean).join(" – ") ||
                "Zone inconnue";

            const msgs = zone.messages
                .map((m) => {
                    const title = m.title || "(Sans titre)";
                    const fullText = m.translated_text || m.preview || "";
                    const orientation = m.orientation
                        ? ` • ${m.orientation}`
                        : "";
                    const postLink = m.url
                        ? `<a href="${m.url}" target="_blank">post n° ${m.telegram_message_id}</a>`
                        : "";
                    const timeStr = new Date(
                        m.event_timestamp || m.created_at
                    ).toLocaleString();

                    return `
                <li class="event">
                    <div class="evt-title">${title}</div>
                    <div class="evt-text">${fullText}</div>
                    <div class="evt-meta">
                        <span class="evt-source">${m.source}${orientation}</span>
                        <span class="evt-time">${timeStr}</span>
                        <span class="evt-link">${postLink}</span>
                    </div>
                </li>
            `;
                })
                .join("");

            return `
            <section class="zone-block">
                <h4 class="zone-header" data-idx="${idx}">
                    <span class="toggle-btn">▶</span> ${header}
                    <span class="evt-count">(${zone.messages_count})</span>
                </h4>
                <ul class="event-list" id="zone-list-${idx}" style="display:none;">
                    ${msgs}
                </ul>
            </section>
        `;
        })
        .join("");

    eventsContainer.innerHTML = html;

    // Listeners pour dérouler les zones
    data.zones.forEach((zone, idx) => {
        const headerEl = document.querySelector(
            `.zone-header[data-idx='${idx}']`
        );
        const listEl = document.getElementById(`zone-list-${idx}`);
        const btn = headerEl.querySelector(".toggle-btn");
        headerEl.addEventListener("click", () => {
            if (listEl.style.display === "none") {
                listEl.style.display = "";
                btn.textContent = "▼";
            } else {
                listEl.style.display = "none";
                btn.textContent = "▶";
            }
        });
    });
}

// ---------------------------------------------------------
// Sidepanel : ouverture + chargement des événements
// ---------------------------------------------------------
async function openSidePanel(country) {
    currentCountry = country;
    document.getElementById("panel-country-name").textContent = country;

    const panel = document.getElementById("sidepanel");
    panel.classList.add("visible");

    // Désactive le scroll du body sur mobile quand le panneau est ouvert
    if (IS_MOBILE) {
        document.body.classList.add("no-scroll");
    }

    await loadLatestEvents(country);
}

document.getElementById("close-panel").addEventListener("click", () => {
    document.getElementById("sidepanel").classList.remove("visible");

    // Réactive le scroll du body sur mobile quand le panneau est fermé
    if (IS_MOBILE) {
        document.body.classList.remove("no-scroll");
    }
});

// Fermer le panneau en cliquant sur le fond (PC seulement)
document.getElementById("sidepanel-backdrop").addEventListener("click", () => {
    if (!IS_MOBILE) {  // sécurité : on ne ferme pas par clic sur mobile
        document.getElementById("sidepanel").classList.remove("visible");
    }
});

// ---------------------------------------------------------
// Charger les événements du jour le plus récent pour le pays
// ---------------------------------------------------------
async function loadLatestEvents(country) {
    const eventsContainer = document.getElementById("events");
    eventsContainer.innerHTML = "Chargement...";

    const resp = await fetch(
        `/api/countries/${encodeURIComponent(country)}/latest-events`
    );

    if (!resp.ok) {
        eventsContainer.textContent = "Aucun événement pour ce pays.";
        return;
    }

    const data = await resp.json();

    // data.date = date la plus récente pour ce pays
    currentDate = data.date;

    const select = document.getElementById("timeline");
    if (select && currentDate) {
        // Si la date la plus récente n'est pas dans la liste, on l'ajoute
        let found = false;
        Array.from(select.options).forEach((opt) => {
            if (opt.value === currentDate) {
                found = true;
            }
        });
        if (!found) {
            const opt = new Option(currentDate, currentDate);
            select.add(opt, 0);
        }
        select.value = currentDate;
    }

    renderEvents(data);
}

// ---------------------------------------------------------
// Charger les événements pour le pays + currentDate
// (appelé quand on change de date dans le panel)
// ---------------------------------------------------------
async function loadEvents(country) {
    const eventsContainer = document.getElementById("events");

    if (!currentDate) {
        eventsContainer.textContent = "Aucune date sélectionnée.";
        return;
    }

    eventsContainer.innerHTML = "Chargement...";

    const resp = await fetch(
        `/api/countries/${encodeURIComponent(
            country
        )}/events?date=${currentDate}`
    );

    if (!resp.ok) {
        eventsContainer.textContent = "Erreur de chargement.";
        return;
    }

    const data = await resp.json();
    renderEvents(data);
}

// ---------------------------------------------------------
// Init
// ---------------------------------------------------------
async function init() {
    initMap();
    await loadCountryData();
    await loadTimeline();
    await loadActiveCountries();
}

window.addEventListener("load", init);
