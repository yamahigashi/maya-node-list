(function () {
  "use strict";

  function getDocRootUrl() {
    const rel =
      (window.DOCUMENTATION_OPTIONS && window.DOCUMENTATION_OPTIONS.URL_ROOT) ||
      document.documentElement.getAttribute("data-content_root") ||
      "./";
    return new URL(rel, window.location.href);
  }

  async function fetchVersions(docRootUrl) {
    const rootSegments = docRootUrl.pathname.split("/").filter(Boolean);
    const currentRootSegment = rootSegments[rootSegments.length - 1] || "";
    const isVersionRoot =
      /^\d{4}$/.test(currentRootSegment) || currentRootSegment === "latest";
    const candidates = isVersionRoot
      ? [
          new URL("../versions/versions.json", docRootUrl),
          new URL("versions/versions.json", docRootUrl),
          new URL("../../versions/versions.json", docRootUrl),
        ]
      : [
          new URL("versions/versions.json", docRootUrl),
          new URL("../versions/versions.json", docRootUrl),
          new URL("../../versions/versions.json", docRootUrl),
        ];

    for (const url of candidates) {
      try {
        const response = await fetch(url.toString(), { cache: "no-store" });
        if (!response.ok) {
          continue;
        }
        const data = await response.json();
        if (!data || !Array.isArray(data.versions)) {
          continue;
        }
        return { data, url };
      } catch (_error) {
        // Try the next candidate.
      }
    }

    return null;
  }

  async function fetchJson(url) {
    try {
      const response = await fetch(url.toString(), { cache: "no-store" });
      if (!response.ok) {
        return null;
      }
      return await response.json();
    } catch (_error) {
      return null;
    }
  }

  function getSiteRootUrl(versionsJsonUrl) {
    return new URL("../", versionsJsonUrl);
  }

  function getRelativePathFromDocRoot(docRootUrl) {
    const rootPath = docRootUrl.pathname.endsWith("/")
      ? docRootUrl.pathname
      : docRootUrl.pathname + "/";
    const currentPath = window.location.pathname;
    if (currentPath.startsWith(rootPath)) {
      const relative = currentPath.slice(rootPath.length);
      return relative || "index.html";
    }
    return "index.html";
  }

  function normalizePathPrefix(path) {
    return path.endsWith("/") ? path : path + "/";
  }

  function getCurrentVersion(siteRootUrl, versions, latestAlias) {
    const siteRootPath = normalizePathPrefix(siteRootUrl.pathname);
    const currentPath = window.location.pathname;
    const relative = currentPath.startsWith(siteRootPath)
      ? currentPath.slice(siteRootPath.length)
      : "";
    const firstSegment = relative.split("/").filter(Boolean)[0];

    if (!firstSegment) {
      return "__latest__";
    }
    if (firstSegment === latestAlias) {
      return "__latest__";
    }
    if (versions.includes(firstSegment)) {
      return firstSegment;
    }
    return "__latest__";
  }

  function buildTargetUrl(
    selectedVersion,
    relativePath,
    siteRootUrl,
    latestAlias
  ) {
    let target;
    if (selectedVersion === "__latest__") {
      target = new URL(latestAlias + "/" + relativePath, siteRootUrl);
    } else {
      target = new URL(selectedVersion + "/" + relativePath, siteRootUrl);
    }

    target.search = window.location.search;
    target.hash = window.location.hash;
    return target.toString();
  }

  function resolveCurrentVersion(currentVersionMarker, versionsInfo) {
    if (currentVersionMarker !== "__latest__") {
      return currentVersionMarker;
    }

    if (versionsInfo.data.latest) {
      return versionsInfo.data.latest;
    }
    if (Array.isArray(versionsInfo.data.versions) && versionsInfo.data.versions.length) {
      return versionsInfo.data.versions[0];
    }
    return "";
  }

  function resolveComparisonPair(currentVersion, versions) {
    if (!currentVersion || !Array.isArray(versions) || versions.length < 2) {
      return null;
    }
    const currentIndex = versions.indexOf(currentVersion);
    if (currentIndex < 0) {
      return null;
    }
    const previous = versions[currentIndex + 1];
    if (!previous) {
      return null;
    }
    return {
      current: currentVersion,
      previous: previous,
    };
  }

  function createDiffPanel(options) {
    const panel = document.createElement("div");
    panel.className = "version-diff-panel";

    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = options.metaText;
    panel.appendChild(meta);

    if (options.mainText) {
      const status = document.createElement("span");
      status.className = "status";
      status.textContent = options.mainText;
      panel.appendChild(status);
    }

    if (options.extraHtml) {
      const extra = document.createElement("span");
      extra.innerHTML = options.extraHtml;
      panel.appendChild(extra);
    }

    if (options.detailHtml) {
      const detail = document.createElement("div");
      detail.className = "detail";
      detail.innerHTML = options.detailHtml;
      panel.appendChild(detail);
    }

    return panel;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildHtmlList(items) {
    const rows = (items || [])
      .map(function (item) {
        return "<li>" + item + "</li>";
      })
      .join("");
    return "<ul class='diff-item-list'>" + rows + "</ul>";
  }

  function buildExpandableHtmlList(items, limit) {
    if (!Array.isArray(items) || !items.length) {
      return "";
    }

    const shown = items.slice(0, limit);
    const hidden = items.slice(limit);
    let html = buildHtmlList(shown);
    if (hidden.length) {
      html +=
        "<details class='diff-more'>" +
        "<summary>&lt;more +" +
        String(hidden.length) +
        "&gt;</summary>" +
        buildHtmlList(hidden) +
        "</details>";
    }
    return html;
  }

  function extractTypeIdFromHref(href) {
    if (!href) {
      return "";
    }
    const match = href.match(/(0x[0-9a-fA-F]+)\.html(?:$|[?#])/);
    return match ? match[1].toLowerCase() : "";
  }

  function extractTypeIdFromText(text) {
    const match = String(text || "").match(/\((0x[0-9a-fA-F]+)\)/);
    return match ? match[1].toLowerCase() : "";
  }

  function normalizeNumericToken(text) {
    const value = String(text || "").trim();
    if (!value) {
      return "";
    }

    if (/^[+-]?0x[0-9a-f]+$/i.test(value)) {
      const parsedHex = parseInt(value, 16);
      if (Number.isFinite(parsedHex)) {
        return String(parsedHex);
      }
    }

    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return value;
    }
    if (Number.isInteger(parsed)) {
      return String(parsed);
    }
    return value;
  }

  function parseDefaultValueText(defaultElement) {
    if (!defaultElement) {
      return "";
    }
    const text = String(defaultElement.textContent || "").trim();
    return text.replace(/^default:\s*/i, "").trim();
  }

  function parseCurrentValueText(currentElement) {
    if (!currentElement) {
      return "";
    }
    return String(currentElement.textContent || "").trim();
  }

  function splitEnumToken(token, nextValue) {
    const raw = String(token || "").trim();
    if (!raw) {
      return null;
    }

    let name = raw;
    let value = "";
    let next = nextValue;

    if (raw.indexOf("=") >= 0) {
      const parts = raw.split("=", 2);
      name = String(parts[0] || "").trim();
      value = String(parts[1] || "").trim();
      const parsed = parseInt(value, 10);
      next = Number.isFinite(parsed) ? parsed + 1 : null;
    } else if (nextValue !== null) {
      value = String(nextValue);
      next = nextValue + 1;
    } else {
      next = null;
    }

    if (!name) {
      return null;
    }

    return {
      name: name,
      value: value,
      nextValue: next,
    };
  }

  function buildEnumList(enumText, defaultValue) {
    const normalized = String(enumText || "")
      .replace(/^choices:\s*/i, "")
      .trim();
    if (!normalized) {
      return null;
    }

    const tokens = normalized
      .split(",")
      .map(function (token) {
        return String(token || "").trim();
      })
      .filter(Boolean);
    if (!tokens.length) {
      return null;
    }

    const defaultName = String(defaultValue || "").trim().toLowerCase();
    const defaultNorm = normalizeNumericToken(defaultValue).toLowerCase();
    const list = document.createElement("ul");
    list.className = "attr_enum_list";

    let nextValue = 0;
    for (const token of tokens) {
      const parsed = splitEnumToken(token, nextValue);
      if (!parsed) {
        continue;
      }
      nextValue = parsed.nextValue;

      const item = document.createElement("li");
      item.className = "attr_enum_item";

      const valueNorm = normalizeNumericToken(parsed.value).toLowerCase();
      const isDefault =
        !!defaultName &&
        (parsed.name.toLowerCase() === defaultName ||
          (parsed.value && valueNorm === defaultNorm));

      let label = parsed.name;
      if (parsed.value) {
        label = parsed.name + " (" + parsed.value + ")";
      }

      item.textContent = label;
      if (isDefault) {
        item.classList.add("default");
        const marker = document.createElement("span");
        marker.className = "enum_default";
        marker.textContent = " (default)";
        item.appendChild(marker);
      }
      list.appendChild(item);
    }

    return list;
  }

  function normalizeEnumDisplay() {
    const enumBlocks = Array.from(
      document.querySelectorAll("table.attribute td.attr_value .attr_enum")
    );
    for (const enumBlock of enumBlocks) {
      const cell = enumBlock.closest("td.attr_value");
      if (!cell) {
        continue;
      }

      const defaultElement = cell.querySelector(".attr_default");
      const currentElement = cell.querySelector(".attr_current");
      let defaultValue = parseDefaultValueText(defaultElement);
      if (!defaultValue) {
        defaultValue = parseCurrentValueText(currentElement);
      }
      const enumList = buildEnumList(enumBlock.textContent || "", defaultValue);
      if (!enumList) {
        continue;
      }

      enumBlock.replaceWith(enumList);

      if (defaultElement) {
        defaultElement.remove();
      }
    }
  }

  function removeNodeDiffSummary() {
    const container = document.getElementById("node-diff-summary");
    if (container) {
      container.remove();
    }
  }

  function getIndexNodeAnchors() {
    return Array.from(
      document.querySelectorAll(
        "div.body[role='main'] #all-nodes a.reference.internal, " +
          "div.body[role='main'] #by-category-classification a.reference.internal"
      )
    );
  }

  function collectIndexNodeLinkMap() {
    const map = {};
    const anchors = getIndexNodeAnchors();
    for (const anchor of anchors) {
      const href = anchor.getAttribute("href") || "";
      let typeId = extractTypeIdFromHref(href);
      if (!typeId) {
        typeId = extractTypeIdFromText(anchor.textContent || "");
      }
      if (!typeId) {
        continue;
      }

      if (!map[typeId]) {
        map[typeId] = {
          href: href,
          text: (anchor.textContent || "").trim(),
        };
      }
    }
    return map;
  }

  function makeLinkHtml(href, text) {
    return "<a href='" + escapeHtml(href) + "'>" + escapeHtml(text) + "</a>";
  }

  function renderTypeIdLabel(typeId) {
    return "(" + String(typeId || "").toLowerCase() + ")";
  }

  function buildRemovedNodeHref(siteRootUrl, previousVersion, node) {
    const plugin = encodeURIComponent(String(node.plugin || "_default"));
    const typeId = String(node.typeId || "").toLowerCase();
    if (!typeId) {
      return "";
    }
    const relative =
      previousVersion + "/nodes/" + plugin + "/" + encodeURIComponent(typeId) + ".html";
    return new URL(relative, siteRootUrl).toString();
  }

  function appendDiffBadge(anchor, kind) {
    if (!anchor || !kind) {
      return;
    }
    if (anchor.dataset && anchor.dataset.diffBadge === "1") {
      return;
    }

    const badge = document.createElement("span");
    badge.className = "diff-badge diff-" + kind;
    badge.textContent = kind;
    anchor.insertAdjacentElement("afterend", badge);
    if (anchor.dataset) {
      anchor.dataset.diffBadge = "1";
    }
  }

  function annotateIndexNodeLinks(diffData) {
    if (!diffData || !diffData.node_diff) {
      return;
    }

    const nodeDiff = diffData.node_diff;
    const added = new Set(
      (nodeDiff.added_type_ids || []).map(function (value) {
        return String(value).toLowerCase();
      })
    );
    const changed = new Set(
      Object.keys(nodeDiff.changed || {}).map(function (value) {
        return String(value).toLowerCase();
      })
    );
    const failed = new Set(
      (nodeDiff.failed_new_type_ids || []).map(function (value) {
        return String(value).toLowerCase();
      })
    );

    for (const anchor of getIndexNodeAnchors()) {
      const href = anchor.getAttribute("href") || "";
      let typeId = extractTypeIdFromHref(href);
      if (!typeId) {
        typeId = extractTypeIdFromText(anchor.textContent || "");
      }
      if (!typeId) {
        continue;
      }

      if (failed.has(typeId)) {
        appendDiffBadge(anchor, "failed");
      } else if (added.has(typeId)) {
        appendDiffBadge(anchor, "added");
      } else if (changed.has(typeId)) {
        appendDiffBadge(anchor, "changed");
      }
    }
  }

  function insertOrReplaceDiffPanel(container, panel) {
    if (!container || !panel) {
      return;
    }
    container.innerHTML = "";
    container.appendChild(panel);
  }

  function getOrCreateIndexDiffContainer() {
    const body = document.querySelector("div.body[role='main']");
    if (!body) {
      return null;
    }
    let container = document.getElementById("version-index-diff-summary");
    if (container) {
      return container;
    }

    const h1 = body.querySelector("h1");
    if (!h1) {
      return null;
    }

    container = document.createElement("div");
    container.id = "version-index-diff-summary";
    container.className = "version-diff-box";
    h1.insertAdjacentElement("afterend", container);
    return container;
  }

  function getNodeIdFromPage() {
    const h1 = document.querySelector("div.body[role='main'] h1");
    if (!h1) {
      return "";
    }
    const match = (h1.textContent || "").match(/\((0x[0-9a-fA-F]+)\)/);
    return match ? match[1].toLowerCase() : "";
  }

  function renderIndexDiffSummary(
    diffData,
    currentVersion,
    previousVersion,
    siteRootUrl
  ) {
    const isIndexPage =
      !!document.getElementById("all-nodes") ||
      !!document.getElementById("welcome-to-maya-nodes-s-documentation");
    if (!isIndexPage) {
      return;
    }

    const container = getOrCreateIndexDiffContainer();
    if (!container || !diffData || !diffData.summary) {
      return;
    }

    const summary = diffData.summary || {};
    const nodeDiff = diffData.node_diff || {};
    const linkMap = collectIndexNodeLinkMap();
    const changedMap = nodeDiff.changed || {};

    const extraHtml =
      "<span class='added'>+" +
      String(summary.added || 0) +
      " added</span> " +
      "<span class='removed'>-" +
      String(summary.removed || 0) +
      " removed</span> " +
      "<span class='changed'>~" +
      String(summary.changed || 0) +
      " changed</span>" +
      ((summary.failed_new || 0) > 0
        ? " <span class='removed'>!" +
          String(summary.failed_new || 0) +
          " failed</span>"
        : "");

    const detailParts = [];

    const addedNodes = Array.isArray(nodeDiff.added_nodes)
      ? nodeDiff.added_nodes
      : [];
    if (addedNodes.length) {
      const addedItems = addedNodes.map(function (node) {
        const nodeId = String(node.typeId || "").toLowerCase();
        const linked = linkMap[nodeId];
        if (linked && linked.href) {
          return makeLinkHtml(linked.href, linked.text);
        }
        const text =
          (node.typeName ? String(node.typeName) + " " : "") + renderTypeIdLabel(nodeId);
        return escapeHtml(text.trim());
      });
      detailParts.push(
        "<div class='diff-detail-row'><span class='added'>added</span>: " +
          buildExpandableHtmlList(addedItems, 8) +
          "</div>"
      );
    }

    const changedIds = Object.keys(changedMap || {}).sort();
    if (changedIds.length) {
      const changedItems = changedIds.map(function (typeId) {
        const linked = linkMap[typeId];
        const entry = changedMap[typeId] || {};
        const attrSummary = entry.attribute_summary || {};
        const changeInfo =
          "(+" +
          String(attrSummary.added || 0) +
          "/-" +
          String(attrSummary.removed || 0) +
          "/~" +
          String(attrSummary.changed || 0) +
          " attrs)";
        if (linked && linked.href) {
          return makeLinkHtml(linked.href, linked.text) + " " + escapeHtml(changeInfo);
        }
        const fallbackText =
          (entry.typeName ? String(entry.typeName) + " " : "") +
          renderTypeIdLabel(typeId) +
          " " +
          changeInfo;
        return escapeHtml(fallbackText.trim());
      });
      detailParts.push(
        "<div class='diff-detail-row'><span class='changed'>changed</span>: " +
          buildExpandableHtmlList(changedItems, 8) +
          "</div>"
      );
    }

    const removedNodes = Array.isArray(nodeDiff.removed_nodes)
      ? nodeDiff.removed_nodes
      : [];
    if (removedNodes.length) {
      const removedItems = removedNodes.map(function (node) {
        const href = buildRemovedNodeHref(siteRootUrl, previousVersion, node);
        const nodeId = String(node.typeId || "").toLowerCase();
        const text =
          (node.typeName ? String(node.typeName) + " " : "") + renderTypeIdLabel(nodeId);
        if (href) {
          return makeLinkHtml(href, text.trim());
        }
        return escapeHtml(text.trim());
      });
      detailParts.push(
        "<div class='diff-detail-row'><span class='removed'>removed</span>: " +
          buildExpandableHtmlList(removedItems, 8) +
          "</div>"
      );
    }

    const panel = createDiffPanel({
      metaText: "Diff " + currentVersion + " vs " + previousVersion,
      mainText: "",
      extraHtml: extraHtml,
      detailHtml: detailParts.join(""),
    });

    insertOrReplaceDiffPanel(container, panel);
  }

  function annotateNodeAttributeRows(diffData) {
    const nodeId = getNodeIdFromPage();
    if (!nodeId || !diffData || !diffData.node_diff) {
      return;
    }

    const nodeDiff = diffData.node_diff;
    const changedMap = nodeDiff.changed || {};
    const changedEntry = changedMap[nodeId];
    if (!changedEntry) {
      return;
    }

    const attrs = changedEntry.attributes || {};
    const addedNames = new Set(
      (attrs.added || []).map(function (name) {
        return String(name || "").toLowerCase();
      })
    );
    const changedNames = new Set(
      Object.keys(attrs.changed || {}).map(function (name) {
        return String(name || "").toLowerCase();
      })
    );

    function getAttrNameFromRow(row) {
      const fromData = String(row.getAttribute("data-attr-name") || "").trim();
      if (fromData) {
        return fromData.toLowerCase();
      }

      const label = row.querySelector(".attr_label");
      if (!label) {
        return "";
      }
      const text = String(label.textContent || "").trim();
      const match = text.match(/^(.*)\s+\([^)]+\)\s*$/);
      const rawName = match ? match[1] : text;
      return String(rawName || "").trim().toLowerCase();
    }

    const rows = Array.from(
      document.querySelectorAll("table.attribute tr")
    );
    for (const row of rows) {
      const attrName = getAttrNameFromRow(row);
      if (!attrName) {
        continue;
      }

      const label = row.querySelector(".attr_label");
      if (!label) {
        continue;
      }

      if (addedNames.has(attrName)) {
        appendDiffBadge(label, "added");
        row.classList.add("diff-row-added");
      } else if (changedNames.has(attrName)) {
        appendDiffBadge(label, "changed");
        row.classList.add("diff-row-changed");
      }
    }
  }

  function renderNodeMetadataDiff(diffData, currentVersion, previousVersion) {
    const nodeId = getNodeIdFromPage();
    if (!nodeId || !diffData || !diffData.node_diff) {
      return;
    }

    const fieldList = document.querySelector("dl.field-list.simple");
    if (!fieldList) {
      return;
    }

    for (const elem of Array.from(fieldList.querySelectorAll(".node-diff-field"))) {
      elem.remove();
    }

    const nodeDiff = diffData.node_diff;
    const changedMap = nodeDiff.changed || {};
    const changedEntry = changedMap[nodeId] || {};
    const added = Array.isArray(nodeDiff.added_type_ids)
      ? nodeDiff.added_type_ids.indexOf(nodeId) >= 0
      : false;
    const removed = Array.isArray(nodeDiff.removed_type_ids)
      ? nodeDiff.removed_type_ids.indexOf(nodeId) >= 0
      : false;
    const changed = !!changedMap[nodeId];
    const failedNew = Array.isArray(nodeDiff.failed_new_type_ids)
      ? nodeDiff.failed_new_type_ids.indexOf(nodeId) >= 0
      : false;

    let statusClass = "unchanged";
    let statusText = "unchanged";
    let detailHtml = "";

    if (failedNew) {
      statusClass = "failed";
      statusText = "unavailable (dump failure)";
    } else if (added) {
      statusClass = "added";
      statusText = "added";
    } else if (removed) {
      statusClass = "removed";
      statusText = "removed";
    } else if (changed) {
      statusClass = "changed";
      statusText = "changed";
      const attrSummary = changedEntry.attribute_summary || {};
      detailHtml =
        " " +
        "<span class='added'>+" +
        String(attrSummary.added || 0) +
        "</span>" +
        " / " +
        "<span class='removed'>-" +
        String(attrSummary.removed || 0) +
        "</span>" +
        " / " +
        "<span class='changed'>~" +
        String(attrSummary.changed || 0) +
        "</span> attrs";
    }

    const dt = document.createElement("dt");
    dt.className = "node-diff-field";
    dt.textContent = "diff:";

    const dd = document.createElement("dd");
    dd.className = "node-diff-field node-diff-value";
    dd.innerHTML =
      "<p>" +
      "<span class='status " +
      statusClass +
      "'>" +
      escapeHtml(statusText) +
      "</span>" +
      detailHtml +
      " <span class='meta'>(vs " +
      escapeHtml(previousVersion) +
      " -> " +
      escapeHtml(currentVersion) +
      ")</span>" +
      "</p>";

    fieldList.appendChild(dt);
    fieldList.appendChild(dd);
  }

  async function renderDiffSummary(versionsInfo) {
    const latestAlias = "latest";
    const versions = versionsInfo.data.versions || [];
    if (versions.length < 2) {
      return;
    }

    const siteRootUrl = getSiteRootUrl(versionsInfo.url);
    const currentMarker = getCurrentVersion(siteRootUrl, versions, latestAlias);
    const currentVersion = resolveCurrentVersion(currentMarker, versionsInfo);
    const pair = resolveComparisonPair(currentVersion, versions);
    if (!pair) {
      return;
    }

    const diffUrl = new URL(
      "versions/diff/" + pair.current + "-vs-" + pair.previous + ".json",
      siteRootUrl
    );
    const diffData = await fetchJson(diffUrl);
    if (!diffData) {
      return;
    }

    renderIndexDiffSummary(diffData, pair.current, pair.previous, siteRootUrl);
    annotateIndexNodeLinks(diffData);
    annotateNodeAttributeRows(diffData);
    renderNodeMetadataDiff(diffData, pair.current, pair.previous);
  }

  function insertSelector(versionsInfo, docRootUrl) {
    const topNavList = document.querySelector("div.related ul");
    if (!topNavList) {
      return;
    }

    const versions = versionsInfo.data.versions;
    if (!versions.length) {
      return;
    }

    const latestAlias = "latest";
    const siteRootUrl = getSiteRootUrl(versionsInfo.url);
    const currentVersion = getCurrentVersion(siteRootUrl, versions, latestAlias);
    const relativePath = getRelativePathFromDocRoot(docRootUrl);

    const item = document.createElement("li");
    item.className = "maya-version-switcher";

    const label = document.createElement("label");
    label.setAttribute("for", "maya-version-select");
    label.textContent = "Maya";

    const select = document.createElement("select");
    select.id = "maya-version-select";
    select.name = "maya-version-select";

    const latestOption = document.createElement("option");
    latestOption.value = "__latest__";
    latestOption.textContent = versionsInfo.data.latest
      ? "latest (" + versionsInfo.data.latest + ")"
      : "latest";
    select.appendChild(latestOption);

    for (const version of versions) {
      const option = document.createElement("option");
      option.value = version;
      option.textContent = version;
      select.appendChild(option);
    }

    select.value = currentVersion;
    select.addEventListener("change", function () {
      const target = buildTargetUrl(
        select.value,
        relativePath,
        siteRootUrl,
        latestAlias
      );
      window.location.href = target;
    });

    item.appendChild(label);
    item.appendChild(select);
    topNavList.prepend(item);
  }

  async function main() {
    removeNodeDiffSummary();
    normalizeEnumDisplay();

    const docRootUrl = getDocRootUrl();
    const versionsInfo = await fetchVersions(docRootUrl);
    if (!versionsInfo) {
      return;
    }
    insertSelector(versionsInfo, docRootUrl);
    await renderDiffSummary(versionsInfo);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }
})();
