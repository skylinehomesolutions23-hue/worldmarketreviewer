const BASE_URL = "https://worldmarketreviewer.onrender.com";

export async function startRun(tickers, maxParallel = 3) {
  const res = await fetch(`${BASE_URL}/api/run_phase2`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tickers, max_parallel: maxParallel }),
  });
  return res.json();
}

export async function getRunStatus(runId) {
  const res = await fetch(`${BASE_URL}/api/run_phase2/status?run_id=${encodeURIComponent(runId)}`);
  return res.json();
}

export async function getSummary(runId) {
  const url = runId
    ? `${BASE_URL}/api/summary?run_id=${encodeURIComponent(runId)}`
    : `${BASE_URL}/api/summary`;
  const res = await fetch(url);
  return res.json();
}
