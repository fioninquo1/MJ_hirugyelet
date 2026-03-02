// === Configuration ===
// Use raw GitHub content for fresh data (Pages CDN caches for 10 min)
const DATA_URL_PRIMARY = "https://raw.githubusercontent.com/fioninquo1/MJ_hirugyelet/master/docs/data/news.json";
const DATA_URL_FALLBACK = "data/news.json";
const REFRESH_INTERVAL = 5 * 60 * 1000;
const STORAGE_KEY_FILTERS = "mj_portal_filters";
const STORAGE_KEY_VIEW = "mj_view_mode";
const STORAGE_KEY_NOTIFY = "mj_notifications";

// === State ===
let newsData = null;
let previousUrls = new Set();
let newUrls = new Set();
let activeView = localStorage.getItem(STORAGE_KEY_VIEW) || "columns";
let portalFilters = JSON.parse(localStorage.getItem(STORAGE_KEY_FILTERS) || "{}");
let notificationsEnabled = localStorage.getItem(STORAGE_KEY_NOTIFY) === "true";
let searchQuery = "";
let refreshTimer = null;
let isFirstLoad = true;

// === Init ===
document.addEventListener("DOMContentLoaded", () => {
    setupViewSwitcher();
    setupRefreshButton();
    setupSearch();
    setupNotifications();
    loadData();
    startAutoRefresh();
});

// === Data Loading ===
async function loadData() {
    showLoading(true);
    hideError();
    try {
        let response;
        try {
            response = await fetch(DATA_URL_PRIMARY + "?t=" + Date.now(), { cache: "no-store" });
        } catch (e) {
            // CORS or network error - fall back to local file
            response = await fetch(DATA_URL_FALLBACK + "?t=" + Date.now());
        }
        if (!response.ok) {
            response = await fetch(DATA_URL_FALLBACK + "?t=" + Date.now());
        }
        if (!response.ok) throw new Error("HTTP " + response.status);
        const newData = await response.json();

        // Track new articles
        const currentUrls = new Set();
        newData.portals.forEach(p => p.articles.forEach(a => currentUrls.add(a.url)));

        if (isFirstLoad) {
            previousUrls = currentUrls;
            newUrls = new Set();
            isFirstLoad = false;
        } else {
            newUrls = new Set();
            currentUrls.forEach(url => {
                if (!previousUrls.has(url)) newUrls.add(url);
            });

            // Send notifications for new articles
            if (newUrls.size > 0 && notificationsEnabled) {
                sendNotifications(newData, newUrls);
            }

            previousUrls = currentUrls;
        }

        newsData = newData;
        buildFilterBar();
        render();
        updateLastUpdated();
        updateNewCount();
    } catch (err) {
        showError("Nem sikerult betolteni az adatokat. Futtasd a scrapert: python -m scraper.main");
    } finally {
        showLoading(false);
    }
}

// === Notifications ===
function setupNotifications() {
    const btn = document.getElementById("notify-btn");
    updateNotifyButton();
    btn.addEventListener("click", async () => {
        if (!notificationsEnabled) {
            if ("Notification" in window) {
                const perm = await Notification.requestPermission();
                if (perm === "granted") {
                    notificationsEnabled = true;
                } else {
                    return;
                }
            } else {
                return;
            }
        } else {
            notificationsEnabled = false;
        }
        localStorage.setItem(STORAGE_KEY_NOTIFY, notificationsEnabled);
        updateNotifyButton();
    });
}

function updateNotifyButton() {
    const btn = document.getElementById("notify-btn");
    btn.classList.toggle("active", notificationsEnabled);
    btn.title = notificationsEnabled ? "Ertesitesek bekapcsolva" : "Ertesitesek kikapcsolva";
}

function sendNotifications(data, urls) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;

    // Only notify for enabled portals
    const newArticles = [];
    data.portals.forEach(portal => {
        if (!portalFilters[portal.id]) return;
        portal.articles.forEach(article => {
            if (urls.has(article.url)) {
                newArticles.push({ ...article, portalName: portal.name });
            }
        });
    });

    if (newArticles.length === 0) return;

    if (newArticles.length <= 3) {
        newArticles.forEach(a => {
            new Notification(a.portalName, { body: a.title, tag: a.url });
        });
    } else {
        new Notification("MJ hirügyelet", {
            body: newArticles.length + " uj cikk (" +
                [...new Set(newArticles.map(a => a.portalName))].join(", ") + ")",
            tag: "mj-batch",
        });
    }
}

// === Search ===
function setupSearch() {
    const input = document.getElementById("search-input");
    input.addEventListener("input", () => {
        searchQuery = input.value.trim().toLowerCase();
        if (newsData) render();
    });
    // Ctrl+K / Cmd+K shortcut
    document.addEventListener("keydown", e => {
        if ((e.ctrlKey || e.metaKey) && e.key === "k") {
            e.preventDefault();
            input.focus();
        }
        if (e.key === "Escape") {
            input.value = "";
            searchQuery = "";
            input.blur();
            if (newsData) render();
        }
    });
}

function filterBySearch(articles) {
    if (!searchQuery) return articles;
    return articles.filter(a =>
        a.title.toLowerCase().includes(searchQuery) ||
        (a.description && a.description.toLowerCase().includes(searchQuery)) ||
        (a.category && a.category.toLowerCase().includes(searchQuery))
    );
}

// === New Count Badge ===
function updateNewCount() {
    const badge = document.getElementById("new-count");
    if (newUrls.size > 0) {
        badge.textContent = newUrls.size + " uj";
        badge.style.display = "inline-block";
    } else {
        badge.style.display = "none";
    }
}

function isNewArticle(url) {
    return newUrls.has(url);
}

// === Filter Bar ===
function buildFilterBar() {
    const bar = document.getElementById("filter-bar");
    bar.innerHTML = "";

    newsData.portals.forEach(portal => {
        if (portalFilters[portal.id] === undefined) {
            portalFilters[portal.id] = true;
        }

        const label = document.createElement("label");
        label.className = "filter-label" + (portalFilters[portal.id] ? " active" : "");
        label.style.setProperty("--portal-color", portal.color);

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = portalFilters[portal.id];
        checkbox.addEventListener("change", () => {
            portalFilters[portal.id] = checkbox.checked;
            label.classList.toggle("active", checkbox.checked);
            localStorage.setItem(STORAGE_KEY_FILTERS, JSON.stringify(portalFilters));
            render();
        });

        const dot = document.createElement("span");
        dot.className = "filter-dot";

        const badge = document.createElement("span");
        badge.className = "filter-badge";
        if (portal.status === "error") badge.classList.add("filter-badge-error");
        badge.textContent = portal.name;

        const count = document.createElement("span");
        count.className = "filter-count";
        count.textContent = portal.article_count;

        label.appendChild(checkbox);
        label.appendChild(dot);
        label.appendChild(badge);
        label.appendChild(count);
        bar.appendChild(label);
    });
}

// === Render Dispatch ===
function render() {
    const content = document.getElementById("content");
    content.className = "content " + activeView + "-view";

    const visiblePortals = newsData.portals.filter(p => portalFilters[p.id]);

    if (visiblePortals.length === 0) {
        content.innerHTML = '<div class="empty-state"><h2>Nincs kivalasztott portal</h2><p>Hasznald a fenti szuroket a portalok bekapcsolasahoz.</p></div>';
        return;
    }

    switch (activeView) {
        case "columns":  renderColumns(content, visiblePortals); break;
        case "cards":    renderCards(content, visiblePortals); break;
        case "timeline": renderTimeline(content, visiblePortals); break;
    }
}

// === Columns View ===
function renderColumns(container, portals) {
    container.innerHTML = "";
    portals.forEach(portal => {
        const filtered = filterBySearch(portal.articles);

        const col = document.createElement("div");
        col.className = "portal-column";
        col.style.setProperty("--portal-color", portal.color);

        // Header
        const header = document.createElement("div");
        header.className = "column-header";
        const headerLink = document.createElement("a");
        headerLink.href = portal.url;
        headerLink.target = "_blank";
        headerLink.rel = "noopener";
        headerLink.textContent = portal.name;
        header.appendChild(headerLink);

        if (portal.status === "error") {
            const errBadge = document.createElement("span");
            errBadge.className = "error-badge";
            errBadge.title = portal.error;
            errBadge.textContent = "!";
            header.appendChild(errBadge);
        }
        col.appendChild(header);

        if (portal.status === "error") {
            const errMsg = document.createElement("div");
            errMsg.className = "column-error";
            errMsg.textContent = portal.error;
            col.appendChild(errMsg);
        }

        // Articles
        const articleList = document.createElement("div");
        articleList.className = "column-articles";

        filtered.forEach(article => {
            const item = document.createElement("a");
            item.className = "column-article";
            if (isNewArticle(article.url)) item.classList.add("article-new");
            item.href = article.url;
            item.target = "_blank";
            item.rel = "noopener";

            const timeRow = document.createElement("span");
            timeRow.className = "article-time";
            if (isNewArticle(article.url)) {
                const newTag = document.createElement("span");
                newTag.className = "new-badge";
                newTag.textContent = "UJ";
                timeRow.appendChild(newTag);
                timeRow.appendChild(document.createTextNode(" "));
            }
            timeRow.appendChild(document.createTextNode(formatTime(article.published)));

            const title = document.createElement("span");
            title.className = "article-title";
            title.textContent = article.title;

            item.appendChild(timeRow);
            item.appendChild(title);

            if (article.category) {
                const cat = document.createElement("span");
                cat.className = "article-category";
                cat.textContent = article.category;
                item.appendChild(cat);
            }

            articleList.appendChild(item);
        });

        col.appendChild(articleList);
        container.appendChild(col);
    });
}

// === Cards View ===
function renderCards(container, portals) {
    container.innerHTML = "";
    const allArticles = filterBySearch(mergeAndSort(portals));

    allArticles.forEach(({ portal, ...article }) => {
        const card = document.createElement("a");
        card.className = "news-card";
        if (isNewArticle(article.url)) card.classList.add("article-new");
        card.href = article.url;
        card.target = "_blank";
        card.rel = "noopener";
        card.style.setProperty("--portal-color", portal.color);

        // Image
        const imgDiv = document.createElement("div");
        imgDiv.className = "card-image";
        if (article.image) {
            const img = document.createElement("img");
            img.src = article.image;
            img.alt = "";
            img.loading = "lazy";
            img.onerror = function() {
                this.parentElement.classList.add("card-image-placeholder");
                this.parentElement.textContent = portal.name[0];
            };
            imgDiv.appendChild(img);
        } else {
            imgDiv.classList.add("card-image-placeholder");
            imgDiv.textContent = portal.name[0];
        }

        // Body
        const body = document.createElement("div");
        body.className = "card-body";

        const badgeRow = document.createElement("div");
        badgeRow.className = "card-badge-row";
        const badge = document.createElement("span");
        badge.className = "portal-badge";
        styleBadge(badge, portal.color);
        badge.textContent = portal.name;
        badgeRow.appendChild(badge);
        if (isNewArticle(article.url)) {
            const newTag = document.createElement("span");
            newTag.className = "new-badge";
            newTag.textContent = "UJ";
            badgeRow.appendChild(newTag);
        }

        const title = document.createElement("h3");
        title.className = "card-title";
        title.textContent = article.title;

        body.appendChild(badgeRow);
        body.appendChild(title);

        if (article.description) {
            const desc = document.createElement("p");
            desc.className = "card-desc";
            desc.textContent = article.description;
            body.appendChild(desc);
        }

        const time = document.createElement("span");
        time.className = "card-time";
        time.textContent = formatTime(article.published);
        body.appendChild(time);

        card.appendChild(imgDiv);
        card.appendChild(body);
        container.appendChild(card);
    });
}

// === Timeline View ===
function renderTimeline(container, portals) {
    container.innerHTML = "";
    const allArticles = filterBySearch(mergeAndSort(portals));

    const list = document.createElement("div");
    list.className = "timeline-list";

    allArticles.forEach(({ portal, ...article }) => {
        const row = document.createElement("a");
        row.className = "timeline-row";
        if (isNewArticle(article.url)) row.classList.add("article-new");
        row.href = article.url;
        row.target = "_blank";
        row.rel = "noopener";

        const time = document.createElement("span");
        time.className = "timeline-time";
        time.textContent = formatTime(article.published);

        const badge = document.createElement("span");
        badge.className = "portal-badge";
        styleBadge(badge, portal.color);
        badge.textContent = portal.name;

        const title = document.createElement("span");
        title.className = "timeline-title";
        if (isNewArticle(article.url)) {
            const newTag = document.createElement("span");
            newTag.className = "new-badge";
            newTag.textContent = "UJ";
            title.appendChild(newTag);
            title.appendChild(document.createTextNode(" "));
        }
        title.appendChild(document.createTextNode(article.title));

        row.appendChild(time);
        row.appendChild(badge);
        row.appendChild(title);

        if (article.description) {
            const desc = document.createElement("span");
            desc.className = "timeline-desc";
            desc.textContent = article.description;
            row.appendChild(desc);
        }

        list.appendChild(row);
    });

    container.appendChild(list);
}

// === Helpers ===
function mergeAndSort(portals) {
    const all = [];
    portals.forEach(portal => {
        portal.articles.forEach(article => {
            all.push({ ...article, portal });
        });
    });
    all.sort((a, b) => {
        const da = a.published ? new Date(a.published) : new Date(0);
        const db = b.published ? new Date(b.published) : new Date(0);
        return db - da;
    });
    return all;
}

function formatTime(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return "";

    const abs = formatAbsoluteTime(date);
    const rel = formatRelativeTime(date);
    return rel ? abs + " (" + rel + ")" : abs;
}

function formatAbsoluteTime(date) {
    const h = String(date.getHours()).padStart(2, "0");
    const m = String(date.getMinutes()).padStart(2, "0");

    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    if (isToday) return h + ":" + m;

    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) return "tegnap " + h + ":" + m;

    const month = date.toLocaleDateString("hu-HU", { month: "short" });
    return month + " " + date.getDate() + ". " + h + ":" + m;
}

function isLightColor(hex) {
    const c = hex.replace("#", "");
    const r = parseInt(c.substring(0, 2), 16);
    const g = parseInt(c.substring(2, 4), 16);
    const b = parseInt(c.substring(4, 6), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 180;
}

function styleBadge(el, color) {
    el.style.background = color;
    if (isLightColor(color)) el.style.color = "#111";
}

function formatRelativeTime(date) {
    const now = new Date();
    const diffMs = now - date;
    if (diffMs < 0) return null;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "most";
    if (diffMin < 60) return diffMin + " perce";
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return diffHrs + " oraja";
    return null;
}

function showLoading(show) {
    document.getElementById("loading").classList.toggle("hidden", !show);
}

function showError(msg) {
    const banner = document.getElementById("error-banner");
    banner.textContent = msg;
    banner.style.display = "block";
}

function hideError() {
    document.getElementById("error-banner").style.display = "none";
}

function updateLastUpdated() {
    const el = document.getElementById("last-updated");
    if (newsData && newsData.scraped_at) {
        el.textContent = "Utolso frissites: " + formatTime(newsData.scraped_at);
    }
}

function setupViewSwitcher() {
    document.querySelectorAll(".view-btn").forEach(btn => {
        if (btn.dataset.view === activeView) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
        btn.addEventListener("click", () => {
            document.querySelectorAll(".view-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeView = btn.dataset.view;
            localStorage.setItem(STORAGE_KEY_VIEW, activeView);
            if (newsData) render();
        });
    });
}

function setupRefreshButton() {
    const btn = document.getElementById("refresh-btn");
    btn.addEventListener("click", (e) => {
        e.preventDefault();
        btn.classList.add("loading");
        loadData().then(() => btn.classList.remove("loading"));
    });
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(loadData, REFRESH_INTERVAL);
}
