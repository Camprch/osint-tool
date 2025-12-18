let map;
let countryCoords = {};
let countryAliases = {};
let timelineDates = [];
let currentGlobalDate = null;
let currentPanelDate = null;
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
        maxZoom: 8,
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


    // Rayons différents selon mobile / desktop (plus petits qu'avant)
    const minRadius = IS_MOBILE ? 8 : 4;
    const maxRadius = IS_MOBILE ? 13 : 7; // taille max réduite

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

    // Global select (header)
    const selectGlobal = document.getElementById("timeline-global");
    // Panel select (sidepanel)
    const selectPanel = document.getElementById("timeline-panel");

    // Helper pour remplir un select
    function fillSelect(select, value) {
        select.innerHTML = "";
        const allOpt = document.createElement("option");
        allOpt.value = "ALL";
        allOpt.textContent = "Toutes les dates";
        select.appendChild(allOpt);
        timelineDates.forEach((dateStr) => {
            const opt = document.createElement("option");
            opt.value = dateStr;
            opt.textContent = dateStr;
            select.appendChild(opt);
        });
        select.value = value || "ALL";
    }

    // Initialisation
    currentGlobalDate = "ALL";
    currentPanelDate = "ALL";
    if (selectGlobal) fillSelect(selectGlobal, currentGlobalDate);
    if (selectPanel) fillSelect(selectPanel, currentPanelDate);

    // Synchronisation des deux sélecteurs
    if (selectGlobal && selectPanel) {
        selectGlobal.addEventListener("change", () => {
            currentGlobalDate = selectGlobal.value;
            currentPanelDate = currentGlobalDate;
            selectPanel.value = currentPanelDate;
            loadActiveCountries();
            if (currentCountry) {
                loadEvents(currentCountry);
            }
        });
        selectPanel.addEventListener("change", () => {
            currentPanelDate = selectPanel.value;
            currentGlobalDate = currentPanelDate;
            selectGlobal.value = currentGlobalDate;
            loadActiveCountries();
            if (currentCountry) {
                loadEvents(currentCountry);
            }
        });
    }
}

// ---------------------------------------------------------
// Charger les pays actifs (toutes les pastilles)
// ---------------------------------------------------------
async function loadActiveCountries() {

    // Log pour debug : pays reçus et clés du JSON
    console.log("[DEBUG] Clés countryCoords:", Object.keys(countryCoords));
    console.log("[DEBUG] Aliases:", countryAliases);

    let url = "/api/countries/active";
    if (currentGlobalDate && currentGlobalDate !== "ALL") {
        url += `?date=${encodeURIComponent(currentGlobalDate)}`;
    }
    const resp = await fetch(url);
    if (!resp.ok) {
        console.error("Erreur /api/countries/active", resp.status);
        return;
    }
    const apiData = await resp.json();
    // Nouvelle structure : { countries: [...], ignored_countries: [...] }
    const countries = apiData.countries || [];
    const ignored = apiData.ignored_countries || [];

    console.log("[DEBUG] Pays reçus de l'API:", countries.map(c => c.country));

    clearMarkers();

    const missing = [];
    const alert = document.getElementById("dashboard-alert");

    const getTolerance = () => {
        // Plus le zoom est élevé, plus la tolérance est faible
        // (valeurs à ajuster selon besoin)
        const zoom = map.getZoom();
        if (zoom >= 5) return 2000;
        if (zoom >= 4) return 6000;
        if (zoom >= 3) return 15000;
        return 30000;
    };

    countries.forEach((c) => {
        let normName = c.country; // déjà normalisé côté backend
        const count = c.events_count;

        // Cherche la clé avec emoji si besoin
        let key = normName;
        if (!(key in countryCoords)) {
            // Essaie via les aliases
            if (countryAliases[normName] && countryCoords[countryAliases[normName]]) {
                key = countryAliases[normName];
            } else {
                missing.push(normName);
                return;
            }
        }

        const [lat, lon] = countryCoords[key];

        // On évite les doublons : une seule pastille par pays
        if (markersByCountry[key]) {
            return;
        }

        const style = markerStyle(count);
        // Zone invisible cliquable en pixels (circleMarker)
        const clickableRadius = style.radius * 2.5;
        const interactiveCircle = L.circleMarker([lat, lon], {
            radius: clickableRadius,
            color: 'transparent',
            fillColor: 'transparent',
            fillOpacity: 0,
            weight: 0,
            interactive: true,
            pane: 'markerPane',
        });

        const marker = L.circleMarker([lat, lon], style);
        if (!IS_MOBILE) {
            marker.bindPopup(`<b>${key}</b><br>Événements : ${count}`);
        }

        interactiveCircle.on("mouseover", function (e) {
            marker.setStyle({ radius: style.radius * 1.15 });
            if (!IS_MOBILE) {
                marker.openPopup && marker.openPopup();
            }
        });
        interactiveCircle.on("mouseout", function (e) {
            marker.setStyle({ radius: style.radius });
            if (!IS_MOBILE) {
                marker.closePopup && marker.closePopup();
            }
        });

        // Clic = panneau direct, clé normalisée
        interactiveCircle.on("click", () => openSidePanel(key));

        interactiveCircle.addTo(map);
        marker.addTo(map);
        markersByCountry[key] = marker;
    });

    // Affichage de l'alerte : pays non géolocalisés ET pays ignorés côté backend
    if (alert) {
        let alertMsg = "";
        if (missing.length > 0) {
            alertMsg += `⚠️ Pays non géolocalisés : ${missing.join(", ")}`;
        }
        if (ignored.length > 0) {
            if (alertMsg) alertMsg += " | ";
            alertMsg += `⚠️ Pays non reconnus côté backend : ${ignored.join(", ")}`;
        }
        if (alertMsg) {
            alert.textContent = alertMsg;
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
                .map((m, mIdx) => {
                    const title = m.title || "(Sans titre)";
                    const fullText = m.translated_text || m.preview || "";
                    const orientation = m.orientation ? ` • ${m.orientation}` : "";
                    const postLink = m.url ? `<a href="${m.url}" target="_blank">post n° ${m.telegram_message_id}</a>` : "";
                    const timeStr = new Date(m.event_timestamp || m.created_at).toLocaleString();
                    return `
            <li class="event">
                <div class="evt-title" data-zone="${idx}" data-msg="${mIdx}" style="cursor:pointer;">${title}</div>
                <div class="evt-text" style="display:none;">
                    ${fullText}
                    <div class="evt-meta">
                        <span class="evt-source">${m.source}${orientation}</span>
                        <span class="evt-time">${timeStr}</span>
                        <span class="evt-link">${postLink}</span>
                    </div>
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
                // Ajout/refresh listeners à chaque ouverture
                listEl.querySelectorAll('.evt-title').forEach(titleEl => {
                    if (!titleEl.dataset.listener) {
                        titleEl.addEventListener('click', function(e) {
                            e.stopPropagation();
                            const text = this.nextElementSibling;
                            if (text.style.display === "none" || !text.style.display) {
                                text.style.display = "block";
                            } else {
                                text.style.display = "none";
                            }
                        });
                        titleEl.dataset.listener = "1";
                    }
                });
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
async function openSidePanel(normCountry) {
    currentCountry = normCountry;
    document.getElementById("panel-country-text").textContent = normCountry;

    // Synchronise le selecteur panel sur la date globale courante
    const selectPanel = document.getElementById("timeline-panel");
    if (selectPanel && currentGlobalDate) {
        selectPanel.value = currentGlobalDate;
        currentPanelDate = currentGlobalDate;
    }

    const panel = document.getElementById("sidepanel");
    panel.classList.add("visible");

    if (IS_MOBILE) {
        document.body.classList.add("no-scroll");
    }

    // Charge les événements pour la date courante (déjà synchronisée)
    await loadEvents(normCountry);
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
    currentPanelDate = data.date;

    const select = document.getElementById("timeline-panel");
    if (select && currentPanelDate) {
        // Si la date la plus récente n'est pas dans la liste, on l'ajoute
        let found = false;
        Array.from(select.options).forEach((opt) => {
            if (opt.value === currentPanelDate) {
                found = true;
            }
        });
        if (!found) {
            const opt = new Option(currentPanelDate, currentPanelDate);
            select.add(opt, 1); // après "Toutes les dates"
        }
        select.value = currentPanelDate;
    }

    renderEvents(data);
}

// ---------------------------------------------------------
// Charger les événements pour le pays + currentDate
// (appelé quand on change de date dans le panel)
// ---------------------------------------------------------
async function loadEvents(country) {
    const eventsContainer = document.getElementById("events");

    if (!currentPanelDate) {
        eventsContainer.textContent = "Aucune date sélectionnée.";
        return;
    }

    eventsContainer.innerHTML = "Chargement...";

    let url, resp, data;
    if (currentPanelDate === "ALL") {
        // Si "Toutes les dates" : on affiche tous les événements pour ce pays
        url = `/api/countries/${encodeURIComponent(country)}/all-events`;
        resp = await fetch(url);
    } else {
        url = `/api/countries/${encodeURIComponent(country)}/events?date=${currentPanelDate}`;
        resp = await fetch(url);
    }

    if (!resp.ok) {
        eventsContainer.textContent = "Erreur de chargement.";
        return;
    }

    data = await resp.json();
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
