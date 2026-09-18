/**
 * script.js
 * ---------
 * Polls /api/active every few seconds so the entry gate and exit gate
 * screens stay in sync without needing a manual page refresh.
 */

const REFRESH_INTERVAL_MS = 4000;

function formatDateTime(isoString) {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit"
    });
}

function photoCell(v) {
    return v.photo_filename
        ? `<img src="/captures/${v.photo_filename}" class="thumb" alt="Vehicle photo">`
        : "-";
}

function renderActiveTableRows(vehicles) {
    if (vehicles.length === 0) {
        return `<tr><td colspan="7" class="empty">No vehicles currently inside.</td></tr>`;
    }
    return vehicles.map(v => `
        <tr>
            <td>${photoCell(v)}</td>
            <td><strong>${v.plate_number}</strong></td>
            <td>${v.vehicle_name}${v.color ? " (" + v.color + ")" : ""}</td>
            <td>${v.owner_name}</td>
            <td>${v.phone_number || "-"}</td>
            <td>${v.destination || "-"}</td>
            <td>${formatDateTime(v.time_in)}</td>
        </tr>
    `).join("");
}

function renderCheckoutTableRows(vehicles) {
    if (vehicles.length === 0) {
        return `<tr><td colspan="7" class="empty">No matching vehicles currently inside.</td></tr>`;
    }
    return vehicles.map(v => `
        <tr>
            <td>${photoCell(v)}</td>
            <td><strong>${v.plate_number}</strong></td>
            <td>${v.vehicle_name}${v.color ? " (" + v.color + ")" : ""}</td>
            <td>${v.owner_name}</td>
            <td>${v.destination || "-"}</td>
            <td>${formatDateTime(v.time_in)}</td>
            <td>
                <form method="post" action="/checkout/${v.id}">
                    <button type="submit" class="checkout-btn">Check Out</button>
                </form>
            </td>
        </tr>
    `).join("");
}

function startAutoRefresh(tableId, renderFn) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const tbody = table.querySelector("tbody");

    async function refresh() {
        try {
            const res = await fetch("/api/active");
            if (!res.ok) return;
            const vehicles = await res.json();
            tbody.innerHTML = renderFn(vehicles);
        } catch (err) {
            console.error("GATEMAN sync error:", err);
        }
    }

    setInterval(refresh, REFRESH_INTERVAL_MS);
}
