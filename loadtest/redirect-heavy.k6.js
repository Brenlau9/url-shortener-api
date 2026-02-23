import http from "k6/http";
import { check, sleep } from "k6";

/**
 * Redirect-heavy test for URL Shortener
 *
 * - setup(): creates N short links once (requires API key)
 * - default(): repeatedly hits GET /{code} without following redirects
 *
 * Run (in docker):
 *   API_KEY="sk_dev_..." docker compose run --rm k6-redirect
 */

export const options = {
  scenarios: {
    redirects: {
      // Most useful for “how many rps can I sustain?”
      executor: "constant-arrival-rate",
      rate: __ENV.RATE ? parseInt(__ENV.RATE, 10) : 500, // requests per second
      timeUnit: "1s",
      duration: __ENV.DURATION || "2m",
      preAllocatedVUs: __ENV.VUS ? parseInt(__ENV.VUS, 10) : 100,
      maxVUs: __ENV.MAX_VUS ? parseInt(__ENV.MAX_VUS, 10) : 500,
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],         // <1% errors
    http_req_duration: ["p(95)<250"],       // p95 < 250ms (tune to your target)
  },
};

const BASE_URL = __ENV.BASE_URL || "http://api:8000";
const API_KEY = __ENV.API_KEY;

const CREATE_HEADERS = {
  "Content-Type": "application/json",
  "X-API-Key": API_KEY,
};

export function setup() {
  if (!API_KEY) throw new Error("Missing API_KEY env var");

  const numLinks = __ENV.NUM_LINKS ? parseInt(__ENV.NUM_LINKS, 10) : 200;
  const codes = [];

  // Create links once so the redirect test doesn't spend most of its time creating.
  for (let i = 0; i < numLinks; i++) {
    const payload = JSON.stringify({ url: `https://example.com/?seed=${i}` });
    const res = http.post(`${BASE_URL}/api/v1/links`, payload, { headers: CREATE_HEADERS });

    check(res, {
      "setup create succeeded (201/200)": (r) => r.status === 201 || r.status === 200,
    });

    const body = res.json();
    // Your API returns { code: "...", ... }
    if (body && body.code) codes.push(body.code);
  }

  if (codes.length === 0) throw new Error("No codes created in setup()");
  return { codes };
}

export default function (data) {
  const codes = data.codes;
  const code = codes[Math.floor(Math.random() * codes.length)];

  // Key: do NOT follow redirects.
  // If your endpoint returns 307/302 + Location, following it would hammer example.com instead of your API.
  const res = http.get(`${BASE_URL}/${code}`, {
    redirects: 0,
  });

  check(res, {
    // Expect a redirect, but allow rate limiting responses if you have it on GET.
    "redirect returned 3xx or 429": (r) => (r.status >= 300 && r.status < 400) || r.status === 429,
  });

  // tiny sleep to reduce tight-loop CPU overhead (optional; constant-arrival-rate drives the pace anyway)
  sleep(0.001);
}