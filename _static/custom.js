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
    const docRootUrl = getDocRootUrl();
    const versionsInfo = await fetchVersions(docRootUrl);
    if (!versionsInfo) {
      return;
    }
    insertSelector(versionsInfo, docRootUrl);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }
})();
