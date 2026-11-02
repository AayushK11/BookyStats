(async () => {
  "use strict";

  const expectedAccount = __BOOKYSTATS_GOODREADS_ACCOUNT_JSON__;
  const columns = [
    "Title", "Author", "Goodreads_URL", "Row_Details", "ISBN", "ISBN13",
    "Description", "Publisher", "Publication_Date", "Pages", "Genres",
    "Average_Rating", "Ratings_Count", "Reviews_Count", "Cover_URL",
    "Series", "Series_Number", "Format", "Language",
  ];
  const notice = "Visible shelf capture only; not verified complete account collection.";
  let downloadLink;
  let objectURL;

  try {
    if (typeof expectedAccount !== "string" || !/^[1-9]\d*$/.test(expectedAccount)) {
      throw new Error("The generated helper must contain a configured numeric Goodreads account.");
    }

    const start = new URL(location.href);
    if (start.protocol !== "https:" ||
        !["www.goodreads.com", "goodreads.com"].includes(start.hostname) ||
        start.port || start.username || start.password) {
      throw new Error("Open your own HTTPS Goodreads shelf in the normally signed-in browser.");
    }
    const shelf = start.searchParams.get("shelf");
    if (!["read", "to-read"].includes(shelf)) {
      throw new Error("Open either the Read or to-read shelf, starting on page 1 in table view.");
    }

    function validateURL(value) {
      const url = new URL(value, start);
      const account = /^\/review\/list\/([1-9]\d*)(?:-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)?$/.exec(url.pathname);
      if (url.origin !== start.origin || url.username || url.password ||
          account?.[1] !== expectedAccount || url.hash ||
          url.searchParams.get("shelf") !== shelf ||
          (url.searchParams.has("view") && url.searchParams.get("view") !== "table")) {
        throw new Error("Stopped: a URL changed origin, account, shelf, or table view.");
      }
      const allowed = ["shelf", "page", "view", "per_page", "sort", "order", "utf8"];
      for (const key of url.searchParams.keys()) {
        if (!allowed.includes(key) || url.searchParams.getAll(key).length !== 1) {
          throw new Error("Stopped: unsupported or ambiguous shelf URL parameters.");
        }
        if ((url.searchParams.has("utf8") && url.searchParams.get("utf8") !== "✓") ||
            (url.searchParams.has("sort") && !/^[a-z][a-z0-9_]*$/.test(url.searchParams.get("sort"))) ||
            (url.searchParams.has("order") && !/^(?:a|d|asc|desc)$/.test(url.searchParams.get("order")))) {
          throw new Error("Stopped: unsupported pagination parameter values.");
        }
      }
      const page = url.searchParams.get("page") ?? "1";
      if (!/^[1-9]\d*$/.test(page) || !Number.isSafeInteger(Number(page))) {
        throw new Error("Stopped: invalid page number.");
      }
      return { url, page: Number(page) };
    }

    let current = validateURL(start.href);
    if (current.page !== 1) {
      throw new Error("Start on page 1; partial shelf exports are not downloaded.");
    }
    console.info(`BookyStats: capturing only ${shelf}. ${notice}`);

    const records = [];
    const seenBooks = new Set();
    const visited = new Set();
    const paginationSettings = new Map(
      ["sort", "order", "per_page"].map((key) => [key, start.searchParams.get(key)]),
    );
    let total;
    let countAvailable;
    let pageDocument = document;

    function cell(row, name) {
      return row.querySelector(`td.field.${name} .value`)?.textContent.trim() ?? "";
    }

    function safeBookLink(anchor) {
      if (!anchor) throw new Error("Stopped: a book row has no title link.");
      const url = new URL(anchor.getAttribute("href"), start);
      const match = /^\/book\/show\/([1-9]\d*)(?:[.-][^/]*)?\/?$/.exec(url.pathname);
      if (url.origin !== start.origin || url.username || url.password || !match) {
        throw new Error("Stopped: a book row has an unsafe or unrecognized book URL.");
      }
      return { id: match[1], url: `${start.origin}/book/show/${match[1]}` };
    }

    while (true) {
      if (visited.has(current.page)) throw new Error("Stopped: pagination loop.");
      visited.add(current.page);
      if (/sign in|log in|captcha|access denied|just a moment|security check/i.test(pageDocument.title) ||
          pageDocument.querySelector(
            'input[type="password"], form[action*="/user/sign_in"], #challenge-form, ' +
            '#challenge-running, .g-recaptcha, iframe[src*="captcha"], iframe[src*="challenges.cloudflare.com"]',
          )) {
        throw new Error("Stopped: sign-in or a browser challenge requires your normal interaction.");
      }

      const table = pageDocument.querySelector("table#books");
      if (!table) throw new Error("Stopped: Goodreads books table is missing.");
      const rows = [...table.querySelectorAll("tbody tr")];
      const showing = pageDocument.querySelector("#booksShowing, .booksShowing");
      let range;
      if (showing) {
        const text = showing.textContent.trim();
        const match = /^([\d,]+)\s*[-–—]\s*([\d,]+)\s+of\s+([\d,]+)(?:\s+books?)?$/i.exec(text);
        const empty = /^(?:0\s+books?|no books|0\s*[-–—]\s*0\s+of\s+0(?:\s+books?)?)$/i.test(text);
        if (!match && !empty) throw new Error("Stopped: unrecognized visible shelf count.");
        range = match ? match.slice(1).map((value) => Number(value.replaceAll(",", ""))) : [0, 0, 0];
        if (range.some((value) => !Number.isSafeInteger(value)) ||
            (total !== undefined && range[2] !== total)) {
          throw new Error("Stopped: inconsistent shelf counts.");
        }
        total = range[2];
        if ((rows.length && range[0] !== records.length + 1) ||
            range[1] !== records.length + rows.length || range[1] > total ||
            (!rows.length && total !== 0)) {
          throw new Error("Stopped: row range does not match the visible shelf count.");
        }
      }
      if (countAvailable !== undefined && countAvailable !== Boolean(showing)) {
        throw new Error("Stopped: visible count disappeared or changed between pages.");
      }
      countAvailable = Boolean(showing);
      if (!rows.length && total !== 0) throw new Error("Stopped: an empty table cannot establish an empty shelf.");

      for (const row of rows) {
        const titleLinks = [...row.querySelectorAll('td.field.title .value a[href]')];
        if (!titleLinks.length) throw new Error("Stopped: malformed book row.");
        const book = safeBookLink(titleLinks[0]);
        if (titleLinks.some((anchor) => safeBookLink(anchor).id !== book.id)) {
          throw new Error("Stopped: ambiguous book row.");
        }
        const title = titleLinks[0].textContent.trim();
        const authorLinks = [...row.querySelectorAll('td.field.author .value a[href]')];
        if (!title || !authorLinks.length) throw new Error("Stopped: missing book title or author.");
        const authors = authorLinks.map((anchor) => {
          const url = new URL(anchor.getAttribute("href"), start);
          const name = anchor.textContent.trim();
          if (!name || url.origin !== start.origin || url.username || url.password ||
              !/^\/author\/show\/[1-9]\d*(?:[.-][^/]*)?\/?$/.test(url.pathname)) {
            throw new Error("Stopped: malformed author link.");
          }
          return name;
        });
        if (seenBooks.has(book.id)) throw new Error("Stopped: duplicate book ID across shelf rows.");
        seenBooks.add(book.id);
        // Only direct, unambiguous table values are exported. No inferred metadata.
        records.push([
          title, authors.join("; "), book.url, row.innerText || row.textContent,
          cell(row, "isbn"), cell(row, "isbn13"), "", "", "", "", "",
          cell(row, "avg_rating"), cell(row, "num_ratings"), "", "", "", "",
          cell(row, "format"), "",
        ]);
      }

      const nextLinks = [...pageDocument.querySelectorAll('a[rel~="next"], a.next_page[href]')];
      const candidates = nextLinks.map((anchor) => {
        const href = anchor.getAttribute("href");
        if (!href) throw new Error("Stopped: next-page link has no destination.");
        return validateURL(href);
      });
      if (!candidates.length) {
        if (total !== undefined && records.length !== total) {
          throw new Error("Stopped: final row count does not match the visible shelf count.");
        }
        break;
      }
      const next = candidates[0];
      if (candidates.some((candidate) => candidate.url.href !== next.url.href) ||
          next.page !== current.page + 1 || visited.has(next.page) ||
          (total !== undefined && records.length >= total)) {
        throw new Error("Stopped: inconsistent, skipped, or looping next-page links.");
      }
      // The first normal next link may make the server's default sort/order explicit.
      // Once established, retain those settings and the original page size.
      for (const key of ["sort", "order", "per_page"]) {
        const value = next.url.searchParams.get(key);
        if (current.page === 1 && key !== "per_page" && paginationSettings.get(key) === null) {
          paginationSettings.set(key, value);
        }
        if (value !== paginationSettings.get(key)) {
          throw new Error("Stopped: pagination changed the shelf ordering or page size.");
        }
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const response = await fetch(next.url.href, {
        credentials: "same-origin", mode: "same-origin", redirect: "error",
      });
      if (!response.ok || response.redirected || validateURL(response.url).url.href !== next.url.href) {
        throw new Error("Stopped: shelf request was rejected or changed destination; no retry attempted.");
      }
      pageDocument = new DOMParser().parseFromString(await response.text(), "text/html");
      current = next;
    }

    // CSV is program input: preserve original titles (including leading +, -, =, @).
    // Formula-prefix mutation would corrupt book metadata. Do not open it as a spreadsheet.
    const quote = (value) => `"${String(value).replaceAll('"', '""')}"`;
    const csv = [columns, ...records].map((row) => row.map(quote).join(",")).join("\r\n") + "\r\n";
    objectURL = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    downloadLink = document.createElement("a");
    downloadLink.href = objectURL;
    const stamp = new Date().toISOString().replaceAll(/[-:.]/g, "");
    downloadLink.download = `goodreads-${shelf === "read" ? "read" : "watchlist"}_${stamp}.csv`;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    console.info(
      `BookyStats: requested CSV download for ${records.length} ${shelf} books. ${notice} ` +
      "Original text is preserved; use as BookyStats input, not a spreadsheet. " +
      "Run separately on the other shelf. Browser download controls still apply.",
    );
    // Give the browser time to consume the Blob URL without bypassing download controls.
    setTimeout(() => URL.revokeObjectURL(objectURL), 60000);
  } catch (error) {
    if (objectURL) URL.revokeObjectURL(objectURL);
    console.error("BookyStats capture stopped; no completed CSV exported.", error.message);
  } finally {
    downloadLink?.remove();
  }
})();
