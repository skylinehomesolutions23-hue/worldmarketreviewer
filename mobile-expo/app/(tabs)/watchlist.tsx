import React, { useEffect, useMemo, useState } from "react";
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

export default function WatchlistTab() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");

  const [loading, setLoading] = useState(false);
  const [preds, setPreds] = useState<Prediction[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const top10 = useMemo(() => (tickers.length ? tickers.slice(0, 10) : []), [tickers]);

  useEffect(() => {
    loadSavedTickers()
      .then((t) => {
        setTickers(t);
        setSelected(t[0] || "SPY");
      })
      .catch(() => {
        setTickers(["SPY", "QQQ", "TSLA"]);
        setSelected("SPY");
      });
  }, []);

  async function runPredictions() {
    const list = top10.length ? top10 : ["SPY", "QQQ", "TSLA"];
    setLoading(true);
    setPreds([]);

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
      setPreds(got);

      const now = new Date();
      setLastUpdated(now.toLocaleString());
    } catch (e: any) {
      Alert.alert("Watchlist error", e?.message || "Failed to fetch predictions");
    } finally {
      setLoading(false);
    }
  }

  function openNews(t: string) {
    const tk = toUpperTicker(t);
    router.push({ pathname: "/news", params: { ticker: tk } });
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Watchlist</Text>
      <Text style={styles.sub}>
        Tracks your saved tickers (max 10). Tap a ticker to open News.
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>Tracked tickers</Text>

        <View style={styles.chips}>
          {(top10.length ? top10 : ["SPY", "QQQ", "TSLA"]).map((t) => {
            const active = toUpperTicker(t) === toUpperTicker(selected);
            return (
              <Pressable
                key={t}
                onPress={() => {
                  setSelected(t);
                  openNews(t);
                }}
                style={[styles.chip, active && styles.chipActive]}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{t}</Text>
              </Pressable>
            );
          })}
        </View>

        <Pressable style={styles.button} onPress={runPredictions} disabled={loading}>
          <Text style={styles.buttonText}>
            {loading ? "Running..." : "Run predictions for top 10"}
          </Text>
        </Pressable>

        {lastUpdated ? (
          <Text style={styles.hint}>Last updated: {lastUpdated}</Text>
        ) : (
          <Text style={styles.hint}>Tip: run this daily to test real accuracy over weeks.</Text>
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
          preds.map((p) => (
            <View key={p.ticker} style={styles.item}>
              <View style={styles.itemRow}>
                <Text style={styles.itemTicker}>{p.ticker}</Text>
                <Text style={styles.itemDir}>{(p.direction || "—").toString()}</Text>
              </View>

              <Text style={styles.itemMeta}>
                prob_up: {fmtProb(p.prob_up)} • confidence: {(p.confidence || "—").toString()} • exp:
                {` ${fmtPct(p.exp_return)}`}
              </Text>

              <Text style={styles.itemMeta}>
                as_of: {(p.as_of_date || "—").toString()} • source: {(p.source || "—").toString()}
              </Text>

              <View style={styles.actions}>
                <Pressable style={styles.smallBtn} onPress={() => openNews(p.ticker)}>
                  <Text style={styles.smallBtnText}>Open News</Text>
                </Pressable>
              </View>
            </View>
          ))
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
  chipActive: { borderColor: "#111", backgroundColor: "#111" },
  chipText: { fontWeight: "800", color: "#111", fontSize: 12 },
  chipTextActive: { color: "white" },

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

  actions: { flexDirection: "row", gap: 8, marginTop: 4 },
  smallBtn: {
    borderWidth: 1,
    borderColor: "#111",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
  },
  smallBtnText: { fontWeight: "900", color: "#111", fontSize: 12 },
});
