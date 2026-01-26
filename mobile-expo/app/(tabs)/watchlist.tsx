// mobile-expo/app/(tabs)/watchlist.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";

const API_BASE = "https://worldmarketreviewer.onrender.com";

const STORAGE_KEYS = {
  savedTickersCandidates: [
    "wmr:savedTickers:v3",
    "wmr:savedTickers:v2",
    "wmr:savedTickers:v1",
    "savedTickers",
  ],
};

type Prediction = {
  ticker: string;
  source?: string;
  prob_up?: number | null;
  exp_return?: number | null;
  direction?: string;
  horizon_days?: number;
  as_of_date?: string | null;
  as_of_close?: number | null;
  confidence?: string;
  confidence_score?: number | null;
};

type VerifyResponse = {
  ticker?: string;
  ok?: boolean;
  series?: { n?: number; closes?: number[]; dates?: string[] };
  note?: string;
  [k: string]: any;
};

function toUpperTicker(s: string) {
  return (s || "").toUpperCase().replace(/[^A-Z0-9.\-]/g, "").trim();
}

function uniq(arr: string[]) {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of arr) {
    const t = toUpperTicker(x);
    if (t && !seen.has(t)) {
      seen.add(t);
      out.push(t);
    }
  }
  return out;
}

async function loadSavedTickers(): Promise<string[]> {
  for (const key of STORAGE_KEYS.savedTickersCandidates) {
    try {
      const raw = await AsyncStorage.getItem(key);
      if (!raw) continue;

      let vals: any = null;
      try {
        vals = JSON.parse(raw);
      } catch {
        vals = raw;
      }

      if (Array.isArray(vals)) {
        const cleaned = uniq(vals.map(String));
        if (cleaned.length) return cleaned;
      }

      if (typeof vals === "string") {
        const parts = vals
          .replace(/\s+/g, ",")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
        const cleaned = uniq(parts);
        if (cleaned.length) return cleaned;
      }
    } catch {
      // ignore
    }
  }

  return ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MSFT", "AMZN"];
}

function fmtPct(x?: number | null) {
  if (x === null || x === undefined) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function fmtProb(x?: number | null) {
  if (x === null || x === undefined) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(0)}%`;
}

function fmtNum(x?: number | null, digits = 2) {
  if (x === null || x === undefined) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

async function safeJson(res: Response) {
  const txt = await res.text();
  try {
    return JSON.parse(txt);
  } catch {
    return { raw: txt };
  }
}

/**
 * Mini sparkline (no SVG). Same style as Compare.
 */
function Sparkline({
  closes,
  height = 36,
  maxBars = 50,
}: {
  closes: number[];
  height?: number;
  maxBars?: number;
}) {
  const series = useMemo(() => {
    const raw = Array.isArray(closes) ? closes.filter((x) => Number.isFinite(Number(x))) : [];
    if (raw.length < 2) return null;

    const take = raw.length > maxBars ? raw.slice(raw.length - maxBars) : raw.slice();
    let mn = Infinity;
    let mx = -Infinity;
    for (const v of take) {
      if (v < mn) mn = v;
      if (v > mx) mx = v;
    }
    if (!Number.isFinite(mn) || !Number.isFinite(mx)) return null;

    const range = mx - mn;
    const safeRange = range === 0 ? 1 : range;

    const first = take[0];
    const last = take[take.length - 1];
    const up = last >= first;

    const bars = take.map((v) => {
      const t = (v - mn) / safeRange; // 0..1
      const h = Math.max(2, Math.round(t * (height - 2)));
      return h;
    });

    return { bars, up };
  }, [closes, height, maxBars]);

  if (!series) return null;

  const barColor = series.up ? "#37D67A" : "#FF6B6B";

  return (
    <View style={[styles.sparkWrap, { height }]}>
      <View style={styles.sparkBarsRow}>
        {series.bars.map((h, idx) => (
          <View
            key={idx}
            style={[
              styles.sparkBar,
              {
                height: h,
                backgroundColor: barColor,
                opacity: idx === series.bars.length - 1 ? 1 : 0.85,
              },
            ]}
          />
        ))}
      </View>
    </View>
  );
}

export default function WatchlistTab() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const [preds, setPreds] = useState<Prediction[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  // sparkline cache (in-memory)
  const [sparkByTicker, setSparkByTicker] = useState<Record<string, number[]>>({});
  const sparkReqId = useRef(0);

  const top10 = useMemo(() => (tickers.length ? tickers.slice(0, 10) : []), [tickers]);

  useEffect(() => {
    loadSavedTickers()
      .then((t) => setTickers(t))
      .catch(() => setTickers(["SPY", "QQQ", "TSLA"]));
  }, []);

  function openNews(t: string) {
    const tk = toUpperTicker(t);
    router.push({ pathname: "/(tabs)/news", params: { ticker: tk } });
  }

  async function fetchVerifySeries(ticker: string) {
    const tk = toUpperTicker(ticker);
    if (!tk) return null;

    const url = `${API_BASE}/api/verify?ticker=${encodeURIComponent(
      tk
    )}&horizon_days=5&n=60&lookback_days=240&source_pref=auto`;

    const res = await fetch(url);
    const j = (await safeJson(res)) as VerifyResponse;

    if (!res.ok) return null;
    const closes = Array.isArray(j?.series?.closes) ? (j.series!.closes as number[]) : [];
    return closes.length >= 2 ? closes : null;
  }

  async function hydrateSparklinesFor(predictions: Prediction[]) {
    const myId = ++sparkReqId.current;

    // only do up to 10 (top10)
    const list = uniq(predictions.map((p) => p.ticker)).slice(0, 10);

    // avoid re-fetching if we already have it
    const need = list.filter((t) => !sparkByTicker[toUpperTicker(t)]);

    if (need.length === 0) return;

    // limit concurrency (2 at a time) so we don’t hammer API/mobile
    const concurrency = 2;
    let idx = 0;

    const runOne = async () => {
      while (idx < need.length) {
        const i = idx++;
        const tk = toUpperTicker(need[i]);

        try {
          const closes = await fetchVerifySeries(tk);
          if (myId !== sparkReqId.current) return; // canceled by newer run

          if (closes) {
            setSparkByTicker((prev) => ({ ...prev, [tk]: closes }));
          }
        } catch {
          // ignore per ticker
        }
      }
    };

    await Promise.all(Array.from({ length: concurrency }, () => runOne()));
  }

  async function runPredictions() {
    const list = top10.length ? top10 : ["SPY", "QQQ", "TSLA"];
    setLoading(true);
    setPreds([]);
    // keep existing spark cache (so it feels instant on subsequent runs)

    try {
      const res = await fetch(`${API_BASE}/api/summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tickers: list,
          retrain: false,
          horizon_days: 5,
          base_weekly_move: 0.02,
          max_parallel: 4,
          source_pref: "auto",
        }),
      });

      const json = await res.json();
      const got: Prediction[] = Array.isArray(json?.predictions) ? json.predictions : [];

      // Sort: highest confidence first, then highest prob_up
      got.sort((a, b) => {
        const ar = (a.confidence_score ?? 0) - (b.confidence_score ?? 0);
        if (ar !== 0) return -ar;
        return (b.prob_up ?? 0) - (a.prob_up ?? 0);
      });

      setPreds(got);
      setLastUpdated(new Date().toLocaleString());

      // sparkline series for each ticker (non-blocking, but awaited here)
      hydrateSparklinesFor(got).catch(() => {});
    } catch (e: any) {
      Alert.alert("Watchlist error", e?.message || "Failed to fetch predictions");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Watchlist</Text>
      <Text style={styles.sub}>Tracks your saved tickers (max 10). Includes mini sparklines.</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Tracked</Text>

        <View style={styles.chips}>
          {(top10.length ? top10 : ["SPY", "QQQ", "TSLA"]).map((t) => (
            <Pressable key={t} onPress={() => openNews(t)} style={styles.chip}>
              <Text style={styles.chipText}>{t}</Text>
            </Pressable>
          ))}
        </View>

        <Pressable style={styles.button} onPress={runPredictions} disabled={loading}>
          <Text style={styles.buttonText}>{loading ? "Running..." : "Run predictions for top 10"}</Text>
        </Pressable>

        {lastUpdated ? (
          <Text style={styles.hint}>Last updated: {lastUpdated}</Text>
        ) : (
          <Text style={styles.hint}>Run this daily to build a real accuracy track record.</Text>
        )}
      </View>

      <View style={styles.resultsHeader}>
        <Text style={styles.resultsTitle}>Predictions</Text>
        {loading ? <ActivityIndicator /> : null}
      </View>

      <ScrollView contentContainerStyle={styles.results}>
        {preds.length === 0 ? (
          <Text style={styles.muted}>No predictions yet. Tap “Run predictions for top 10”.</Text>
        ) : (
          preds.map((p) => {
            const tk = toUpperTicker(p.ticker);
            const closes = sparkByTicker[tk] || null;

            return (
              <View key={p.ticker} style={styles.item}>
                <View style={styles.itemRow}>
                  <Text style={styles.itemTicker}>{p.ticker}</Text>
                  <Text style={styles.itemDir}>{(p.direction || "—").toString()}</Text>
                </View>

                <Text style={styles.itemMeta}>
                  prob_up: {fmtProb(p.prob_up)} • confidence: {(p.confidence || "—").toString()} • exp:{" "}
                  {fmtPct(p.exp_return)}
                </Text>

                <Text style={styles.itemMeta}>
                  as_of: {(p.as_of_date || "—").toString()} • close: {fmtNum(p.as_of_close, 2)} • source:{" "}
                  {(p.source || "—").toString()}
                </Text>

                {/* Sparkline */}
                {closes ? (
                  <View style={{ marginTop: 8 }}>
                    <Sparkline closes={closes} />
                  </View>
                ) : (
                  <Text style={styles.sparkMuted}>Loading sparkline…</Text>
                )}

                <View style={styles.actions}>
                  <Pressable style={styles.smallBtn} onPress={() => openNews(p.ticker)}>
                    <Text style={styles.smallBtnText}>Open News</Text>
                  </Pressable>
                </View>
              </View>
            );
          })
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 10 },
  title: { fontSize: 28, fontWeight: "800" },
  sub: { color: "#666", marginBottom: 4 },

  card: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 12,
    gap: 10,
    backgroundColor: "white",
  },

  label: { fontSize: 12, color: "#666", marginBottom: 6 },

  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: "#ddd",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "white",
  },
  chipText: { fontWeight: "800", color: "#111", fontSize: 12 },

  button: {
    backgroundColor: "#111",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 2,
  },
  buttonText: { color: "white", fontSize: 16, fontWeight: "700" },

  hint: { fontSize: 12, color: "#666" },

  resultsHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 4,
  },
  resultsTitle: { fontSize: 18, fontWeight: "800" },
  results: { paddingBottom: 40, gap: 10 },

  muted: { color: "#666" },

  item: {
    borderWidth: 1,
    borderColor: "#eee",
    borderRadius: 12,
    padding: 12,
    gap: 6,
    backgroundColor: "white",
  },
  itemRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  itemTicker: { fontSize: 16, fontWeight: "900" },
  itemDir: { fontSize: 12, fontWeight: "900", color: "#111" },
  itemMeta: { fontSize: 12, color: "#666" },

  actions: { flexDirection: "row", gap: 8, marginTop: 8 },
  smallBtn: {
    borderWidth: 1,
    borderColor: "#111",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
  },
  smallBtnText: { fontWeight: "900", color: "#111", fontSize: 12 },

  // Sparkline styles
  sparkWrap: {
    borderWidth: 1,
    borderColor: "#eee",
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    backgroundColor: "white",
  },
  sparkBarsRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 2,
  },
  sparkBar: {
    width: 3,
    borderRadius: 2,
  },
  sparkMuted: { fontSize: 12, color: "#888", marginTop: 6 },
});
