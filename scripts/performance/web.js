import http from "k6/http";
import exec from "k6/execution";
import { Counter, Rate, Trend } from "k6/metrics";

const base = (__ENV.BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const mix = __ENV.MIX || "lexical";
const mode = __ENV.MODE || "step";
const rate = Number(__ENV.RATE || 1);
const queries = JSON.parse(
  __ENV.QUERIES || '["Italia","Roma","elezioni","terremoto"]',
);
const folders = JSON.parse(__ENV.FOLDERS || "[]");
const expected = __ENV.ORACLE ? JSON.parse(open(__ENV.ORACLE)) : null;
const share = Number(__ENV.SEMANTIC_PERCENT || 25);
if (
  !["lexical", "mixed", "archive", "filter", "live", "annotation"].includes(
    mix,
  ) ||
  !["step", "spike", "soak", "baseline"].includes(mode) ||
  !Number.isInteger(rate) ||
  rate < 1 ||
  !queries.length ||
  share < 0 ||
  share > 100
)
  throw Error("Invalid workload configuration");
if (mix === "archive" && !folders.length)
  throw Error("FOLDERS must contain archive leaf paths");
const accounts = mix === "annotation" ? JSON.parse(open(__ENV.ACCOUNTS)) : [];
const vus = Number(__ENV.VUS || Math.max(10, rate * 8));
const accountCount = mode === "baseline" ? 1 : vus * (mode === "spike" ? 3 : 1);
if (
  mix === "annotation" &&
  (__ENV.DISPOSABLE !== "1" || accounts.length < accountCount)
)
  throw Error(
    "Annotation needs a disposable replica and one test account per VU",
  );
const steps =
  mode === "spike"
    ? [
        [0.5, "5m"],
        [1.5, "2m"],
        [0.5, "5m"],
      ]
    : [
        [
          mode === "soak" ? 0.7 : 1,
          __ENV.DURATION || (mode === "soak" ? "2h" : "5m"),
        ],
      ];
const scenarios = {};
let offset = 0;
for (const [i, [factor, duration]] of steps.entries()) {
  const seconds = /^(\d+)(s|m|h)$/.exec(duration);
  if (!seconds) throw Error("Use integer s, m or h for DURATION");
  scenarios["phase_" + i] =
    mode === "baseline"
      ? { executor: "constant-vus", vus: 1, duration }
      : {
          executor: "constant-arrival-rate",
          rate: Math.max(1, Math.round(rate * factor)),
          timeUnit: "1s",
          preAllocatedVUs: vus,
          duration,
          startTime: offset + "s",
        };
  offset += Number(seconds[1]) * { s: 1, m: 60, h: 3600 }[seconds[2]];
}
export const options = {
  scenarios,
  discardResponseBodies: false,
  noCookiesReset: true,
  systemTags: [
    "name",
    "status",
    "scenario",
    "method",
    "expected_response",
    "error_code",
  ],
  thresholds: {
    journey_failed: ["rate<=" + (__ENV.ERROR_BUDGET || "0")],
    ...(__ENV.P95_MS ? { journey_ms: ["p(95)<=" + __ENV.P95_MS] } : {}),
    ...(mode === "baseline" ? {} : { dropped_iterations: ["count==0"] }),
  },
};
const failed = new Rate("journey_failed");
const useful = new Counter("useful_journeys");
const started = new Counter("journeys_started");
const latency = new Trend("journey_ms", true);
function get(path, name) {
  if (!path.startsWith("/") || path.startsWith("//"))
    throw Error("Unexpected path");
  const r = http.get(base + path, { tags: { name }, redirects: 0 });
  if (r.status !== 200) throw Error(name + ":" + r.status);
  return r;
}
function article(path, id) {
  const html = get(path, "article").html();
  if (
    html.find(".save-button").attr("data-id") !== id ||
    !html.find(".article-body").text().trim()
  )
    throw Error("Wrong article");
}
function search(q, profile, page, filter) {
  const data = get(
    "/api/search?q=" +
      encodeURIComponent(q) +
      "&profile=" +
      profile +
      "&page=" +
      page +
      (filter ? "&year_from=2005&year_to=2021" : ""),
    "search_" + profile,
  ).json();
  if (
    data.query !== q ||
    data.profile !== profile ||
    data.page !== page ||
    !data.hits.length ||
    (filter &&
      data.hits.some(
        (h) =>
          !h.publication_date ||
          +h.publication_date.slice(0, 4) < 2005 ||
          +h.publication_date.slice(0, 4) > 2021,
      ))
  )
    throw Error("Invalid search results");
  if (expected) {
    const key = JSON.stringify([q, profile, page, filter]);
    if (
      JSON.stringify(data.hits.map((h) => h.document_id)) !==
      JSON.stringify(expected[key])
    )
      throw Error("Frozen ranking mismatch");
  }
  return data.hits;
}
let session;
function annotation() {
  const account = accounts[exec.vu.idInTest - 1];
  const prefix = "/api/annotation/";
  const headers = { "Content-Type": "application/json", Origin: base };
  if (!session) {
    const login = http.post(base + prefix + "login", JSON.stringify(account), {
      headers,
      tags: { name: "login" },
    });
    if (login.status !== 200) throw Error("login");
    session = login.json();
  }
  headers["X-CSRF-Token"] = session.csrf;
  if (session.coordinator) get(prefix + "dashboard", "dashboard").json();
  const task = get(prefix + "tasks", "tasks").json()[0];
  const key = {
    packet_id: task.packet_id,
    query_id: task.topic.query_id,
    document_id: task.document.document_id,
  };
  const version = task.own_judgment ? task.own_judgment.version : 0;
  const quote = Array.from(task.document.body).slice(0, 32).join("");
  const body = Object.assign({}, key, {
    expected_version: version,
    status: "judged",
    grade: 1,
    rationale: "Verifica di persistenza sul database di benchmark",
    evidence: [
      { field: "body", quote, start: 0, end: Array.from(quote).length },
    ],
    request_id:
      "perf-" +
      Date.now() +
      "-" +
      exec.vu.idInTest +
      "-" +
      exec.scenario.iterationInTest,
  });
  const saved = http.post(base + prefix + "judgments", JSON.stringify(body), {
    headers,
    tags: { name: "save" },
  });
  if (saved.status !== 200) throw Error("save:" + saved.status);
  const params = Object.keys(key)
    .map((k) => k + "=" + encodeURIComponent(key[k]))
    .join("&");
  const latest = get(prefix + "history?" + params, "history").json()[0];
  if (
    latest.version !== version + 1 ||
    latest.grade !== 1 ||
    latest.evidence[0].quote !== quote
  )
    throw Error("Persistence");
}
export default function () {
  const i = exec.scenario.iterationInTest;
  const q = queries[i % queries.length];
  const profile = mix === "mixed" && (i * 37) % 100 < share ? "semantic" : "E1";
  const tags = { mix, profile, phase: exec.scenario.name };
  const begin = Date.now();
  started.add(1, tags);
  let ok = false;
  try {
    if (mix === "annotation") annotation();
    else if (mix === "live") {
      const data = get(
        "/api/search/live?q=" + encodeURIComponent(q),
        "live",
      ).json();
      if (!Array.isArray(data.hits) || !data.hits.length)
        throw Error("Live results");
      if (data.next_cursor) {
        const next = get(
          "/api/search/live?q=" +
            encodeURIComponent(q) +
            "&cursor=" +
            encodeURIComponent(data.next_cursor),
          "live_page",
        ).json();
        if (
          !next.hits.length ||
          next.hits.some((h) =>
            data.hits.some((a) => a.document_id === h.document_id),
          )
        )
          throw Error("Invalid live continuation");
      }
    } else if (mix === "archive") {
      if (!get("/archivio", "archive").html().find("main.archive").size())
        throw Error("Unexpected archive page");
      const link = get(folders[i % folders.length], "folder")
        .html()
        .find(".result-list a")
        .first()
        .attr("href");
      article(link, decodeURIComponent(link.split("?")[0].split("/").pop()));
    } else {
      if (!get("/", "home").html().find("#q").size())
        throw Error("Unexpected home page");
      const hits = search(q, profile, 1, mix === "filter");
      if (mix === "filter") {
        const next = search(q, profile, 2, true);
        if (next.some((h) => hits.some((a) => a.document_id === h.document_id)))
          throw Error("Duplicate page");
      }
      article(
        "/articles/" + encodeURIComponent(hits[0].document_id),
        hits[0].document_id,
      );
    }
    ok = true;
  } catch (error) {
    if (__ITER === 0) console.error(String(error));
  } finally {
    failed.add(!ok, tags);
    useful.add(ok ? 1 : 0, tags);
    latency.add(Date.now() - begin, tags);
  }
}
