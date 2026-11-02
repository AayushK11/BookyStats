"use strict";

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const template = readFileSync(
  path.join(__dirname, "..", "..", "..", "src", "bookystats", "adapters", "exports", "goodreads_console.js"),
  "utf8",
);
const source = template.replace("__BOOKYSTATS_GOODREADS_ACCOUNT_JSON__", JSON.stringify("4242"));
const origin = "https://www.goodreads.com";
const firstURL = `${origin}/review/list/4242?shelf=read&view=table&page=1`;
const secondURL = `${origin}/review/list/4242?shelf=read&view=table&page=2`;
const headers = [
  "Title", "Author", "Goodreads_URL", "Row_Details", "ISBN", "ISBN13",
  "Description", "Publisher", "Publication_Date", "Pages", "Genres",
  "Average_Rating", "Ratings_Count", "Reviews_Count", "Cover_URL",
  "Series", "Series_Number", "Format", "Language",
];

function anchor(text, href) {
  return { textContent: text, getAttribute: (name) => name === "href" ? href : null };
}

function row({
  id = "11", title = "A book", author = "A writer", details = "raw row\nunknown field: original",
  titleLinks, authorLinks, values = {},
} = {}) {
  return {
    innerText: details,
    textContent: details,
    querySelector(selector) {
      const field = /^td\.field\.(\w+) \.value$/.exec(selector)?.[1];
      return Object.hasOwn(values, field) ? { textContent: values[field] } : null;
    },
    querySelectorAll(selector) {
      if (selector === "td.field.title .value a[href]") {
        return titleLinks ?? [anchor(title, `/book/show/${id}-title?tracking=discarded#fragment`)];
      }
      if (selector === "td.field.author .value a[href]") {
        return authorLinks ?? [anchor(author, "/author/show/99.Writer")];
      }
      throw new Error(`Unexpected row selector: ${selector}`);
    },
  };
}

// These tiny DOM-shaped stubs deliberately exercise the real resource, not a
// reimplementation of its algorithm. They are fixture evidence, not live DOM proof.
function page({ rows = [row()], next = [], count, missingTable = false, challenge = false, title = "My books" } = {}) {
  return {
    title,
    querySelector(selector) {
      if (selector === "table#books") {
        return missingTable ? null : {
          querySelectorAll: (value) => {
            assert.equal(value, "tbody tr");
            return rows;
          },
        };
      }
      if (selector === "#booksShowing, .booksShowing") {
        return count === undefined ? null : { textContent: count };
      }
      assert.match(selector, /input\[type="password"\]/);
      return challenge ? {} : null;
    },
    querySelectorAll(selector) {
      assert.equal(selector, 'a[rel~="next"], a.next_page[href]');
      return next.map((href) => anchor("next", href));
    },
  };
}

async function execute({ initial = page(), pages = [], url = firstURL, rejectFetch = false, status = 200, redirected = false, responseURL } = {}) {
  const requests = [];
  const downloads = [];
  const blobs = [];
  const errors = [];
  const messages = [];
  const delays = [];
  const revoked = [];
  let secretReads = 0;
  const denySecret = () => {
    secretReads += 1;
    throw new Error("Secret access forbidden");
  };
  const doc = Object.assign({}, initial, {
    body: { appendChild: () => {} },
    createElement(tag) {
      assert.equal(tag, "a");
      return {
        click() { downloads.push({ href: this.href, filename: this.download }); },
        remove() {},
      };
    },
  });
  Object.defineProperty(doc, "cookie", { get: denySecret });
  class BrowserURL extends URL {
    static createObjectURL(blob) {
      blobs.push(blob);
      return "blob:local-capture";
    }
    static revokeObjectURL(value) { revoked.push(value); }
  }
  const context = {
    document: doc,
    location: { href: url },
    URL: BrowserURL,
    Blob,
    Date: class extends Date {
      constructor(...args) { super(...(args.length ? args : ["2026-11-02T16:08:02.231Z"])); }
    },
    DOMParser: class {
      parseFromString(token, mime) {
        assert.equal(mime, "text/html");
        return pages[Number(token)];
      }
    },
    console: {
      info: (...args) => messages.push(args.join(" ")),
      error: (...args) => errors.push(args.join(" ")),
    },
    setTimeout(callback, delay) {
      delays.push(delay);
      callback();
    },
    async fetch(target, options) {
      requests.push({ target, options });
      if (rejectFetch) throw new Error("HTTP request rejected");
      return {
        ok: status >= 200 && status < 300,
        redirected,
        url: responseURL ?? target,
        text: async () => String(requests.length - 1),
      };
    },
  };
  for (const name of ["localStorage", "sessionStorage", "indexedDB"]) {
    Object.defineProperty(context, name, { get: denySecret });
  }
  await vm.runInNewContext(source, context);
  assert.equal(secretReads, 0);
  return { requests, downloads, blobs, errors, messages, delays, revoked };
}

function parseCSV(csv) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < csv.length; index += 1) {
    const character = csv[index];
    if (character === '"') {
      if (quoted && csv[index + 1] === '"') { cell += '"'; index += 1; }
      else quoted = !quoted;
    } else if (character === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if (character === "\r" && csv[index + 1] === "\n" && !quoted) {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      index += 1;
    } else cell += character;
  }
  assert.equal(quoted, false);
  assert.equal(cell, "");
  return rows;
}

async function stopped(options) {
  const result = await execute(options);
  assert.equal(result.downloads.length, 0);
  assert.equal(result.blobs.length, 0);
  assert.equal(result.errors.length, 1);
  assert.match(result.errors[0], /capture stopped/);
  return result;
}

test("resource has one account substitution point and no external dependencies", () => {
  assert.equal(template.split("__BOOKYSTATS_GOODREADS_ACCOUNT_JSON__").length, 2);
  assert.doesNotMatch(template, /\b(?:import|require|eval)\s*[( ]/);
});

test("captures exactly one shelf sequentially, escaping CSV and preserving raw text and unknowns", async () => {
  const title = '=A "quoted", title\nwith another line';
  const details = 'title =A "quoted", title\r\nnotes: unchanged\n未知';
  const result = await execute({
    initial: page({
      rows: [row({ title, details, values: { isbn: " 0140328726 ", avg_rating: "4.03", num_ratings: "38,310", format: "Hardcover" } })],
      next: [secondURL],
      count: "1–1 of 2",
    }),
    pages: [page({ rows: [row({ id: "12", title: "+Normal title", author: "Sáenz, María" })], count: "2–2 of 2" })],
  });
  assert.equal(result.errors.length, 0);
  assert.equal(result.requests.length, 1);
  assert.equal(result.requests[0].target, secondURL);
  assert.deepEqual({ ...result.requests[0].options }, {
    credentials: "same-origin", mode: "same-origin", redirect: "error",
  });
  assert.deepEqual(result.delays, [1000, 60000]);
  assert.equal(result.downloads.length, 1);
  assert.equal(result.downloads[0].filename, "goodreads-read_20261102T160802231Z.csv");
  assert.deepEqual(result.revoked, ["blob:local-capture"]);
  const csv = await result.blobs[0].text();
  const records = parseCSV(csv);
  assert.deepEqual(records[0], headers);
  assert.equal(records.length, 3);
  assert.equal(records[1].length, 19);
  assert.equal(records[1][0], title);
  assert.equal(records[1][2], `${origin}/book/show/11`);
  assert.equal(records[1][3], details);
  assert.equal(records[1][4], "0140328726");
  assert.equal(records[1][11], "4.03");
  assert.equal(records[1][12], "38,310");
  for (const column of [5, 6, 7, 8, 9, 10, 13, 14, 15, 16, 18]) assert.equal(records[1][column], "");
  assert.equal(records[2][0], "+Normal title");
  assert.equal(records[2][1], "Sáenz, María");
  assert.ok(result.messages.some((message) => message.includes("not verified complete account")));
  assert.ok(result.messages.some((message) => message.includes("not a spreadsheet")));
});

test("to-read captures use watchlist filename and never request another shelf", async () => {
  const result = await execute({ url: firstURL.replace("shelf=read", "shelf=to-read") });
  assert.equal(result.errors.length, 0);
  assert.equal(result.requests.length, 0);
  assert.equal(result.downloads[0].filename, "goodreads-watchlist_20261102T160802231Z.csv");
});

test("accepts exact-account public slugs and normal generated-URL pagination defaults", async () => {
  const url = `${origin}/review/list/4242-reader-name?shelf=read&view=table&per_page=100`;
  const next = `${origin}/review/list/4242-reader-name?shelf=read&view=table&per_page=100&page=2&sort=date_read&order=d&utf8=%E2%9C%93`;
  const third = next.replace("page=2", "page=3").replace("/4242-reader-name?", "/4242?");
  const result = await execute({
    url,
    initial: page({ count: "1–1 of 3", next: [next] }),
    pages: [
      page({ rows: [row({ id: "12" })], count: "2–2 of 3", next: [third] }),
      page({ rows: [row({ id: "13" })], count: "3–3 of 3" }),
    ],
  });
  assert.equal(result.errors.length, 0);
  assert.deepEqual(result.requests.map(({ target }) => target), [next, third]);
  assert.deepEqual(result.delays, [1000, 1000, 60000]);
  assert.equal(parseCSV(await result.blobs[0].text()).length, 4);
});

test("accepts sort/order/utf8 already present on a to-read starting URL", async () => {
  const url = `${origin}/review/list/4242-reader?shelf=to-read&view=table&per_page=100&sort=position&order=a&utf8=%E2%9C%93`;
  const next = `${url}&page=2`;
  const result = await execute({
    url, initial: page({ next: [next] }), pages: [page({ rows: [row({ id: "12" })] })],
  });
  assert.equal(result.errors.length, 0);
  assert.equal(result.downloads.length, 1);
  assert.equal(result.requests[0].target, next);
});

for (const innerText of [undefined, ""]) {
  test(`retains unrendered next-page textContent when innerText is ${JSON.stringify(innerText)}`, async () => {
    const details = 'unrendered row\nISBN: 0123456789\n"unknown", preserved';
    const unrendered = row({ id: "12", details });
    unrendered.innerText = innerText;
    const result = await execute({
      initial: page({ next: [secondURL] }),
      pages: [page({ rows: [unrendered] })],
    });
    assert.equal(result.errors.length, 0);
    assert.equal(parseCSV(await result.blobs[0].text())[2][3], details);
  });
}

test("a visibly confirmed empty shelf exports only the header", async () => {
  const result = await execute({ initial: page({ rows: [], count: "0 books" }) });
  assert.equal(result.errors.length, 0);
  assert.deepEqual(parseCSV(await result.blobs[0].text()), [headers]);
});

for (const [name, next] of [
  ["cross-account", secondURL.replace("4242", "9999")],
  ["numeric-prefix account", secondURL.replace("4242", "42424-reader")],
  ["cross-shelf", secondURL.replace("shelf=read", "shelf=to-read")],
  ["cross-host", secondURL.replace("www.goodreads.com", "evil.example")],
  ["HTTP", secondURL.replace("https:", "http:")],
  ["page loop", firstURL],
  ["page skip", secondURL.replace("page=2", "page=3")],
  ["non-table view", secondURL.replace("view=table", "view=grid")],
  ["ambiguous query", `${secondURL}&shelf=read`],
  ["unknown filter", `${secondURL}&search=query`],
  ["credential token", `${secondURL}&token=forbidden`],
  ["credential access_token", `${secondURL}&access_token=forbidden`],
  ["credential cookie", `${secondURL}&cookie=forbidden`],
  ["invalid utf8", `${secondURL}&utf8=forbidden`],
  ["duplicate utf8", `${secondURL}&utf8=%E2%9C%93&utf8=%E2%9C%93`],
  ["changed page size", `${secondURL}&per_page=100`],
]) {
  test(`rejects ${name} pagination before any request or download`, async () => {
    const result = await stopped({ initial: page({ next: [next] }) });
    assert.equal(result.requests.length, 0);
  });
}

for (const [name, options] of [
  ["duplicate book", { pages: [page()] }],
  ["missing table", { pages: [page({ missingTable: true })] }],
  ["malformed row", { pages: [page({ rows: [row({ titleLinks: [] })] })] }],
  ["missing author", { pages: [page({ rows: [row({ id: "12", authorLinks: [] })] })] }],
  ["challenge", { pages: [page({ challenge: true })] }],
  ["sign-in title", { pages: [page({ title: "Sign in | Goodreads" })] }],
  ["HTTP rejection", { status: 429 }],
  ["network rejection", { rejectFetch: true }],
  ["redirect", { redirected: true }],
  ["response account mismatch", { responseURL: secondURL.replace("4242", "9999") }],
]) {
  test(`never exports partial rows after ${name}`, async () => {
    const result = await stopped({ initial: page({ next: [secondURL] }), ...options });
    assert.equal(result.requests.length, 1);
    assert.deepEqual(result.delays, [1000]);
  });
}

for (const [name, initial, pages] of [
  ["truncated final page", page({ count: "1–1 of 2" }), []],
  ["changed totals", page({ count: "1–1 of 2", next: [secondURL] }), [page({ rows: [row({ id: "12" })], count: "2–2 of 3" })]],
  ["wrong range", page({ count: "2–2 of 2" }), []],
  ["lost count", page({ count: "1–1 of 2", next: [secondURL] }), [page({ rows: [row({ id: "12" })] })]],
  ["unrecognized count", page({ count: "many books" }), []],
  ["empty unknown table", page({ rows: [] }), []],
  ["next after total reached", page({ count: "1–1 of 1", next: [secondURL] }), []],
]) {
  test(`rejects ${name} rather than downloading a misleading CSV`, () => stopped({ initial, pages }));
}

for (const [name, url] of [
  ["wrong initial account", firstURL.replace("4242", "9999")],
  ["different numeric account with slug", firstURL.replace("4242", "42424-reader")],
  ["malformed account slug", firstURL.replace("4242", "4242-reader/other")],
  ["initial page 2", secondURL],
  ["unsupported shelf", firstURL.replace("shelf=read", "shelf=owned")],
  ["unrelated origin", firstURL.replace("www.goodreads.com", "example.com")],
  ["HTTP origin", firstURL.replace("https:", "http:")],
]) {
  test(`rejects ${name} before fetching`, async () => {
    assert.equal((await stopped({ url })).requests.length, 0);
  });
}

test("does not allow established ordering to change after the first pagination link", async () => {
  const next = `${secondURL}&sort=date_read&order=d`;
  const third = `${secondURL.replace("page=2", "page=3")}&sort=title&order=d`;
  const result = await stopped({
    initial: page({ next: [next] }),
    pages: [page({ rows: [row({ id: "12" })], next: [third] })],
  });
  assert.equal(result.requests.length, 1);
});

test("does not allow explicit initial sorting to be replaced", async () => {
  const result = await stopped({
    url: `${firstURL}&sort=title&order=a`,
    initial: page({ next: [`${secondURL}&sort=date_read&order=d`] }),
  });
  assert.equal(result.requests.length, 0);
});

test("does not export ambiguous or cross-origin row anchors", async () => {
  await stopped({ initial: page({ rows: [row({ titleLinks: [anchor("Book", "https://evil.example/book/show/11")] })] }) });
  await stopped({ initial: page({ rows: [row({ titleLinks: [
    anchor("One", "/book/show/11"), anchor("Other", "/book/show/12"),
  ] })] }) });
});
