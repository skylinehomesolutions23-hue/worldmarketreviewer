// mobile-expo/app/(tabs)/accuracy.tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";

const API_BASE = "https://worldmarketreviewer.onrender.com";

const STORAGE_KEYS = {
  savedTickersCandidates: [
    "wmr:savedTickers:v3",
    "wmr:savedTickers:v2",
    "wmr:savedTickers:v1",
    "savedTickers",
  ],
  lastAccuracyTicker: "wmr:lastAccuracyTicker:v3",
  lastAccuracyHorizon: "wmr:lastAccuracyHorizon:v3",
  lastAccuracyLimit: "wmr:lastAccuracyLimit:v3",
};

type ReportCard = {
  ticker: string;
  horizon_days: number;
  samples?: number;
  overall_hit_rate?: number | null;
  avg_realized_return?: number | null;
  high_confidence?: { label: string; lo: number; hi: number; count: number; hit_rate: number | null } | null;
  by_confidence?: Array<{ label: string; lo: number; hi: number; count: number; hit_rate: number | null }>;
  note?: string;
  [k: string]: any;
};

type ScoreRow = {
  id: number;
  ticker: string;
  generated_at: string;
  horizon_days: number;
  prob_up?: number | null;
  direction?: string | null;
  exp_return?: number | null;
  as_of_date?: string | null;
  as_of_close?: number | null;
  realized_return?: number | null;
  realized_direction?: string | null;
  scored_at?: string | null;
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

function fmtPct(x?: number | null, digits = 1) {
  if (x === null || x === undefined) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
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

export default function AccuracyTab() {
  const [savedTickers, setSavedTickers] = useState<string[]>([]);
  const [ticker, setTicker] = useState("SPY");
  const [horizon, setHorizon] = useState("5");
  const [limit, setLimit] = useState("200");

  const [scoring, setScoring] = useState(false);
  const [loading, setLoading] = useState(false);

  const [report, setReport] = useState<ReportCard | null>(null);
  const [rows, setRows] = useState<ScoreRow[]>([]);

  const parsed = useMemo(() => {
    const t = toUpperTicker(ticker) || "SPY";

    let h = parseInt(horizon, 10);
    if (!Number.isFinite(h)) h = 5;
    h = Math.max(1, Math.min(60, h));

    let lim = parseInt(limit, 10);
    if (!Number.isFinite(lim)) lim = 200;
    lim = Math.max(10, Math.min(2000, lim));

    return { t, h, lim };
  }, [ticker, horizon, limit]);

  useEffect(() => {
    loadSavedTickers().then(setSavedTickers).catch(() => setSavedTickers(["SPY", "QQQ", "TSLA"]));

    (async () => {
      try {
        const [t, h, lim] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEYS.lastAccuracyTicker),
          AsyncStorage.getItem(STORAGE_KEYS.lastAccuracyHorizon),
          AsyncStorage.getItem(STORAGE_KEYS.lastAccuracyLimit),
        ]);
        if (t) setTicker(toUpperTicker(t) || "SPY");
        if (h) setHorizon(String(h));
        if (lim) setLimit(String(lim));
      } catch {}
    })();
  }, []);

  async function savePrefs(t: string, h: number, lim: number) {
    try {
      await Promise.all([
        AsyncStorage.setItem(STORAGE_KEYS.lastAccuracyTicker, t),
        AsyncStorage.setItem(STORAGE_KEYS.lastAccuracyHorizon, String(h)),
        AsyncStorage.setItem(STORAGE_KEYS.lastAccuracyLimit, String(lim)),
      ]);
    } catch {}
  }

  async function fetchReportAndScoreboard() {
    const { t, h, lim } = parsed;
    setLoading(true);
    setReport(null);
    setRows([]);

    await savePrefs(t, h, lim);

    try {
      const [r1, r2] = await Promise.all([
        fetch(`${API_BASE}/api/report_card?ticker=${encodeURIComponent(t)}&horizon_days=${h}&limit=${lim}`),
        fetch(`${API_BASE}/api/scoreboard?ticker=${encodeURIComponent(t)}&horizon_days=${h}&limit=${lim}`),
      ]);

      const j1 = await r1.json();
      const j2 = await r2.json();

      setReport(j1);
      setRows(Array.isArray(j2?.rows) ? j2.rows : []);
    } catch (e: any) {
      Alert.alert("Accuracy error", e?.message || "Failed to load accuracy data");
    } finally {
      setLoading(false);
    }
  }

  async function runScoring() {
    setScoring(true);
    try {
      const res = await fetch(`${API_BASE}/api/score_predictions?limit=500&max_parallel=6&source_pref=auto`, {
        method: "POST",
      });
      const j = await res.json();

      const scored = j?.counts?.scored ?? 0;
      const notMatured = j?.counts?.not_matured ?? 0;

      Alert.alert(
        "Scoring complete",
        `Scored: ${scored}\nNot matured yet: ${notMatured}\n\nNow refresh to see updated accuracy.`
      );
    } catch (e: any) {
      Alert.alert("Scoring error", e?.message || "Failed to score predictions");
    } finally {
      setScoring(false);
    }
  }

  function pickTicker(t: string) {
    const up = toUpperTicker(t);
    if (!up) return;
    setTicker(up);
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Accuracy</Text>
      <Text style={styles.sub}>Scores past predictions after they “mature” (once enough trading days pass).</Text>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.card}>
          <Text style={styles.label}>Quick tickers</Text>
          <View style={styles.chips}>
            {(savedTickers.length ? savedTickers.slice(0, 12) : ["SPY", "QQQ", "TSLA"]).map((t) => (
              <Pressable key={t} onPress={() => pickTicker(t)} style={styles.chip}>
                <Text style={styles.chipText}>{t}</Text>
              </Pressable>
            ))}
          </View>

          <Text style={styles.label}>Ticker</Text>
          <TextInput
            value={ticker}
            onChangeText={(v) => setTicker(toUpperTicker(v))}
            placeholder="SPY"
            autoCapitalize="characters"
            autoCorrect={false}
            style={styles.input}
          />

          <View style={styles.row}>
            <View style={styles.rowItem}>
              <Text style={styles.label}>Horizon days</Text>
              <TextInput
                value={horizon}
                onChangeText={setHorizon}
                placeholder="5"
                keyboardType="number-pad"
                style={styles.input}
              />
            </View>

            <View style={styles.rowItem}>
              <Text style={styles.label}>Limit</Text>
              <TextInput
                value={limit}
                onChangeText={setLimit}
                placeholder="200"
                keyboardType="number-pad"
                style={styles.input}
              />
            </View>
          </View>

          <View style={styles.actions}>
            <Pressable style={styles.button} onPress={fetchReportAndScoreboard} disabled={loading}>
              <Text style={styles.buttonText}>{loading ? "Loading..." : "Refresh Accuracy"}</Text>
            </Pressable>

            <Pressable style={styles.buttonOutline} onPress={runScoring} disabled={scoring}>
              <Text style={styles.buttonOutlineText}>{scoring ? "Scoring..." : "Score Predictions"}</Text>
            </Pressable>
          </View>

          <Text style={styles.hint}>Tip: Run “Score Predictions” once per day. Then “Refresh Accuracy” to see updated results.</Text>
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Report Card</Text>
          {loading ? <ActivityIndicator /> : null}
        </View>

        {!report ? (
          <Text style={styles.muted}>Tap “Refresh Accuracy” to load stats.</Text>
        ) : report.note && !report.samples ? (
          <View style={styles.noteBox}>
            <Text style={styles.noteTitle}>Not enough scored samples yet</Text>
            <Text style={styles.noteText}>{report.note}</Text>
          </View>
        ) : (
          <View style={styles.card}>
            <Text style={styles.bigLine}>
              {report.ticker} • {report.horizon_days}d
            </Text>

            <View style={styles.kpis}>
              <View style={styles.kpi}>
                <Text style={styles.kpiLabel}>Samples</Text>
                <Text style={styles.kpiValue}>{report.samples ?? "—"}</Text>
              </View>

              <View style={styles.kpi}>
                <Text style={styles.kpiLabel}>Hit rate</Text>
                <Text style={styles.kpiValue}>{fmtPct(report.overall_hit_rate, 1)}</Text>
              </View>

              <View style={styles.kpi}>
                <Text style={styles.kpiLabel}>Avg realized</Text>
                <Text style={styles.kpiValue}>{fmtPct(report.avg_realized_return, 2)}</Text>
              </View>
            </View>

            {report.high_confidence ? (
              <View style={styles.subCard}>
                <Text style={styles.subCardTitle}>HIGH Confidence Bucket</Text>
                <Text style={styles.subCardText}>
                  count: {report.high_confidence.count} • hit rate: {fmtPct(report.high_confidence.hit_rate, 1)}
                </Text>
              </View>
            ) : null}

            {(report.by_confidence || []).length ? (
              <View style={styles.subCard}>
                <Text style={styles.subCardTitle}>By confidence</Text>
                {(report.by_confidence || []).map((b) => (
                  <Text key={b.label} style={styles.subCardText}>
                    {b.label}: count {b.count} • hit {fmtPct(b.hit_rate, 1)}
                  </Text>
                ))}
              </View>
            ) : null}

            <Text style={styles.hint}>“Hit rate” = how often UP/DOWN matched reality (after the horizon passed).</Text>
          </View>
        )}

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Recent Scored Predictions</Text>
        </View>

        {rows.length === 0 ? (
          <Text style={styles.muted}>No scored rows yet. Run “Score Predictions” after time passes.</Text>
        ) : (
          rows.slice(0, 50).map((r) => {
            const ok = (r.direction || "").toUpperCase() === (r.realized_direction || "").toUpperCase();
            return (
              <View key={r.id} style={styles.item}>
                <View style={styles.itemTop}>
                  <Text style={styles.itemTicker}>{r.ticker}</Text>
                  <Text style={[styles.badge, ok ? styles.badgeOk : styles.badgeBad]}>{ok ? "HIT" : "MISS"}</Text>
                </View>

                <Text style={styles.itemMeta}>
                  pred: {(r.direction || "—").toString()} • prob_up {fmtProb(r.prob_up)} • exp {fmtPct(r.exp_return, 1)}
                </Text>
                <Text style={styles.itemMeta}>
                  realized: {(r.realized_direction || "—").toString()} • return {fmtPct(r.realized_return, 2)}
                </Text>
                <Text style={styles.itemSmall}>
                  as_of {String(r.as_of_date || "—")} • close {fmtNum(r.as_of_close, 2)} • scored {String(r.scored_at || "—")}
                </Text>
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

  scroll: { paddingBottom: 40, gap: 12 },

  card: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 12,
    gap: 10,
    backgroundColor: "white",
  },

  label: { fontSize: 12, color: "#666", marginBottom: 6 },

  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    backgroundColor: "white",
  },

  row: { flexDirection: "row", gap: 10 },
  rowItem: { flex: 1 },

  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: "#ddd",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "white",
  },
  chipText: { fontWeight: "900", color: "#111", fontSize: 12 },

  actions: { flexDirection: "row", gap: 10, marginTop: 4 },
  button: {
    flex: 1,
    backgroundColor: "#111",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  buttonText: { color: "white", fontSize: 16, fontWeight: "700" },
  buttonOutline: {
    borderWidth: 1,
    borderColor: "#111",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    paddingHorizontal: 12,
  },
  buttonOutlineText: { fontWeight: "800", color: "#111" },

  hint: { fontSize: 12, color: "#666" },

  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 6,
  },
  sectionTitle: { fontSize: 18, fontWeight: "800" },

  muted: { color: "#666" },

  noteBox: {
    borderWidth: 1,
    borderColor: "#ffe2b8",
    backgroundColor: "#fff6e8",
    borderRadius: 12,
    padding: 12,
    gap: 6,
  },
  noteTitle: { fontWeight: "900", color: "#7a4a00" },
  noteText: { color: "#7a4a00" },

  bigLine: { fontSize: 16, fontWeight: "900" },

  kpis: { flexDirection: "row", gap: 10 },
  kpi: { flex: 1, borderWidth: 1, borderColor: "#eee", borderRadius: 10, padding: 10 },
  kpiLabel: { fontSize: 12, color: "#666" },
  kpiValue: { fontSize: 16, fontWeight: "900", marginTop: 2 },

  subCard: { borderWidth: 1, borderColor: "#eee", borderRadius: 10, padding: 10, gap: 4 },
  subCardTitle: { fontWeight: "900" },
  subCardText: { color: "#444", fontSize: 12 },

  item: {
    borderWidth: 1,
    borderColor: "#eee",
    borderRadius: 12,
    padding: 12,
    gap: 6,
    backgroundColor: "white",
  },
  itemTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  itemTicker: { fontSize: 16, fontWeight: "900" },

  badge: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    fontSize: 12,
    fontWeight: "900",
  },
  badgeOk: { backgroundColor: "#eaffea", color: "#0a6b0a", borderWidth: 1, borderColor: "#b8f0b8" },
  badgeBad: { backgroundColor: "#fff0f0", color: "#a40000", borderWidth: 1, borderColor: "#ffcccc" },

  itemMeta: { color: "#666", fontSize: 12 },
  itemSmall: { color: "#888", fontSize: 11 },
});
