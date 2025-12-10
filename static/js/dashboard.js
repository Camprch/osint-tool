let map;
let countryCoords = {};
let countryAliases = {};
let timelineDates = [];
let currentDate = null;
let markers = [];

const IS_MOBILE = window.matchMedia("(max-width: 768px)").matches;

// ---------------------------------------------------------
// Init map
// ---------------------------------------------------------
function initMap() {
    map = L.map("map", {
        worldCopyJump: false,
        minZoom: 2,
        maxZoom: 5,
        tapTolerance: 30,  
    }).setView([20, 0], 2);

    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
            attribution: "&copy; CARTO",
            noWrap: false,
        }
    ).addTo(map);
}

// ---------------------------------------------------------
// Utilitaires
// ---------------------------------------------------------
function clearMarkers() {
    markers.forEach((m) => map.removeLayer(m));
    markers = [];
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
        weight: IS_MOBILE ? 2 : 1,  // un léger bord plus épais sur mobile
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
// Charger les dates
// ---------------------------------------------------------
async function loadTimeline() {
    const resp = await fetch("/api/dates");
    const data = await resp.json();
    timelineDates = data.dates;

    const select = document.getElementById("timeline");
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
    }

    select.addEventListener("change", () => {
        currentDate = select.value;
        loadCountries();
    });
}

// ---------------------------------------------------------
// Charger la heatmap par pays
// ---------------------------------------------------------
async function loadCountries() {
    if (!currentDate) return;

    const resp = await fetch(`/api/countries?date=${currentDate}`);
    const countries = await resp.json();

    clearMarkers();

    let missing = [];

    countries.forEach((c) => {
        const name = c.country;
        const count = c.events_count;

        let coordKey = name;
        if (!(coordKey in countryCoords)) {
            // Utiliser l'alias si disponible
            if (name in countryAliases) {
                coordKey = countryAliases[name];
            }
        }

        if (!(coordKey in countryCoords)) {
            missing.push(name);
            return;
        }

        const [lat, lon] = countryCoords[coordKey];

        const style = markerStyle(count);
        const marker = L.circleMarker([lat, lon], style);

        marker.bindPopup(`<b>${name}</b><br>Événements : ${count}`);

        // Effet "pop" léger au survol de la pastille
        const baseRadius = style.radius;
        marker.on("mouseover", function () {
            this.setStyle({ radius: baseRadius * 1.15 });
        });
        marker.on("mouseout", function () {
            this.setStyle({ radius: baseRadius });
        });

        marker.on("click", () => openSidePanel(name));

        marker.addTo(map);
        markers.push(marker);
    });

    const alert = document.getElementById("dashboard-alert");
    if (missing.length > 0) {
        alert.textContent = `⚠️ Pays non géolocalisés : ${missing.join(", ")}`;
        alert.style.display = "block";
    } else {
        alert.style.display = "none";
    }
}

// ---------------------------------------------------------
// Sidepanel : événements
// ---------------------------------------------------------
async function openSidePanel(country) {
    document.getElementById("panel-country-name").textContent = country;

    const panel = document.getElementById("sidepanel");
    panel.classList.add("visible");

    loadEvents(country);
}

document.getElementById("close-panel").addEventListener("click", () => {
    document.getElementById("sidepanel").classList.remove("visible");
});

// ---------------------------------------------------------
async function loadEvents(country) {
    const eventsContainer = document.getElementById("events");
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

    if (!data.zones || data.zones.length === 0) {
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
// Init
// ---------------------------------------------------------
async function init() {
    initMap();
    await loadCountryData();
    await loadTimeline();
    await loadCountries();
}

window.addEventListener("load", init);
