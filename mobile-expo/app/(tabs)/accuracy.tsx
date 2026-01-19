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
  savedTickers: "wmr:savedTickers:v3",
  lastTickersInput: "wmr:lastTickersInput:v3",
  lastHorizon: "wmr:lastHorizon:v3",
  // NEW: local cooldown for "Score now"
  lastScoreTapUtc: "wmr:lastScoreTapUtc:v1",
};

type MetricsResponse = {
  ticker?: string;
  horizon_days?: number;
  count?: number;
  hit_rate?: number;
  avg_realized_return?: number | null;

  // old API shape (if you ever switch back)
  calibration?: { lo: number; hi: number; count: number; up_rate: number | null }[];

  // new API shape (your current api.py)
  by_confidence?: { label: string; lo: number; hi: number; count: number; hit_rate: number | null }[];

  note?: string;
  [k: string]: any;
};

type ScoreResponse = {
  ok?: boolean;
  requested?: number;
  fetched?: number;
  counts?: Record<string, number>;
  note?: string;
  sample?: any[];
  [k: string]: any;
};

function normalizeTickers(input: string): string[] {
  return input
    .split(/[,\s]+/g)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
    .filter((t, idx, arr) => arr.indexOf(t) === idx);
}

function fmtPct(x: any, digits = 1): string {
  const n = typeof x === "number" ? x : Number(x);
  if (!Number.isFinite(n)) return "-";
  return `${(n * 100).toFixed(digits)}%`;
}

async function safeJson(res: Response) {
  const txt = await res.text();
  try {
    return JSON.parse(txt);
  } catch {
    return { raw: txt };
  }
}

function nowUtcMs(): number {
  return Date.now();
}

export default function AccuracyScreen() {
  const [savedTickers, setSavedTickers] = useState<string[]>(["SPY", "QQQ"]);
  const [ticker, setTicker] = useState<string>("SPY");
  const [horizonDays, setHorizonDays] = useState<number>(5);

  const [loadingMetrics, setLoadingMetrics] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [metricsErr, setMetricsErr] = useState<string>("");

  const [loadingScore, setLoadingScore] = useState<boolean>(false);
  const [scoreResp, setScoreResp] = useState<ScoreResponse | null>(null);

  const [cooldownLeftSec, setCooldownLeftSec] = useState<number>(0);

  useEffect(() => {
    (async () => {
      try {
        const [saved, lastInput, lastH] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEYS.savedTickers),
          AsyncStorage.getItem(STORAGE_KEYS.lastTickersInput),
          AsyncStorage.getItem(STORAGE_KEYS.lastHorizon),
        ]);

        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length) {
            setSavedTickers(parsed.map(String).map((x) => x.toUpperCase()));
          }
        }

        const fromInput = lastInput ? normalizeTickers(String(lastInput)) : [];
        if (fromInput.length) setTicker(fromInput[0]);

        if (lastH) {
          const n = Number(lastH);
          if (Number.isFinite(n) && n > 0) setHorizonDays(n);
        }
      } catch {
        // ignore
      }
    })();
  }, []);

  const quickTickers = useMemo(() => {
    const base = [...savedTickers];
    if (!base.includes("SPY")) base.unshift("SPY");
    return base.slice(0, 15);
  }, [savedTickers]);

  async function fetchMetrics(tk?: string, h?: number) {
    const t = (tk ?? ticker).trim().toUpperCase();
    const hd = h ?? horizonDays;

    if (!t) return;

    setLoadingMetrics(true);
    setMetrics(null);
    setMetricsErr("");

    try {
      const url = `${API_BASE}/api/metrics?ticker=${encodeURIComponent(
        t
      )}&horizon_days=${encodeURIComponent(String(hd))}&limit=500`;

      const res = await fetch(url);
      const data = (await safeJson(res)) as MetricsResponse;

      if (!res.ok) {
        setMetricsErr(`HTTP ${res.status}: ${JSON.stringify(data).slice(0, 300)}`);
        return;
      }

      setMetrics(data);
    } catch (e: any) {
      setMetricsErr(String(e?.message || e));
    } finally {
      setLoadingMetrics(false);
    }
  }

  // Cooldown: 30 minutes
  const SCORE_COOLDOWN_MS = 30 * 60 * 1000;

  async function checkCooldown(): Promise<boolean> {
    try {
      const last = await AsyncStorage.getItem(STORAGE_KEYS.lastScoreTapUtc);
      const lastMs = last ? Number(last) : 0;
      const now = nowUtcMs();
      const diff = now - (Number.isFinite(lastMs) ? lastMs : 0);
      if (diff < SCORE_COOLDOWN_MS) {
        const left = Math.ceil((SCORE_COOLDOWN_MS - diff) / 1000);
        setCooldownLeftSec(left);
        Alert.alert(
          "Please wait",
          `To avoid hammering the free backend, you can score again in ~${Math.ceil(left / 60)} min.`
        );
        return false;
      }
      return true;
    } catch {
      return true;
    }
  }

  async function stampCooldown() {
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.lastScoreTapUtc, String(nowUtcMs()));
      setCooldownLeftSec(0);
    } catch {}
  }

  async function scoreNow() {
    const ok = await checkCooldown();
    if (!ok) return;

    setLoadingScore(true);
    setScoreResp(null);

    try {
      await stampCooldown();

      const res = await fetch(`${API_BASE}/api/score_predictions?limit=500&max_parallel=4`, {
        method: "POST",
      });
      const data = (await safeJson(res)) as ScoreResponse;

      setScoreResp(data);

      if (!res.ok) {
        Alert.alert("Score failed", `HTTP ${res.status}`);
      } else {
        await fetchMetrics();
      }
    } catch (e: any) {
      Alert.alert("Score failed", String(e?.message || e));
    } finally {
      setLoadingScore(false);
    }
  }

  useEffect(() => {
    // auto-load metrics on first enter
    fetchMetrics().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Accuracy Report Card</Text>
        <Text style={styles.subtitle}>
          Scores past predictions after the horizon passes. More samples = more reliable.
        </Text>

        <View style={styles.card}>
          <Text style={styles.label}>Ticker</Text>
          <TextInput
            value={ticker}
            onChangeText={(t) => setTicker(t.toUpperCase())}
            placeholder="SPY"
            placeholderTextColor="#6b7280"
            autoCapitalize="characters"
            autoCorrect={false}
            style={styles.input}
          />

          <View style={styles.row}>
            <Pressable
              onPress={() => {
                const next = horizonDays === 5 ? 10 : horizonDays === 10 ? 20 : 5;
                setHorizonDays(next);
              }}
              style={styles.smallButton}
            >
              <Text style={styles.smallButtonText}>Horizon: {horizonDays}d</Text>
            </Pressable>

            <Pressable onPress={() => fetchMetrics()} style={styles.button}>
              <Text style={styles.buttonText}>{loadingMetrics ? "Loading..." : "Load metrics"}</Text>
            </Pressable>

            <Pressable onPress={scoreNow} style={[styles.smallButton, styles.scoreButton]}>
              <Text style={styles.smallButtonText}>{loadingScore ? "Scoring..." : "Score now"}</Text>
            </Pressable>
          </View>

          <Text style={styles.hint}>
            Beginner note: “Hit rate” = how often UP/DOWN was correct after{" "}
            <Text style={styles.bold}>{horizonDays} trading days</Text>.
          </Text>

          {cooldownLeftSec > 0 ? (
            <Text style={styles.mutedSmall}>
              Score cooldown: ~{Math.ceil(cooldownLeftSec / 60)} min remaining
            </Text>
          ) : null}

          <View style={styles.chipsWrap}>
            {quickTickers.map((t) => (
              <Pressable
                key={t}
                onPress={() => {
                  setTicker(t);
                  fetchMetrics(t, horizonDays);
                }}
                style={styles.chip}
              >
                <Text style={styles.chipText}>{t}</Text>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Metrics</Text>

          {loadingMetrics ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator />
              <Text style={styles.loadingText}>Fetching…</Text>
            </View>
          ) : metricsErr ? (
            <Text style={styles.errorText}>Error: {metricsErr}</Text>
          ) : !metrics ? (
            <Text style={styles.muted}>Tap “Load metrics”.</Text>
          ) : metrics.note && !metrics.hit_rate ? (
            <Text style={styles.muted}>{metrics.note}</Text>
          ) : (
            <>
              <View style={styles.kpiRow}>
                <View style={styles.kpiBox}>
                  <Text style={styles.kpiLabel}>Hit rate</Text>
                  <Text style={styles.kpiValue}>{fmtPct(metrics.hit_rate, 1)}</Text>
                </View>
                <View style={styles.kpiBox}>
                  <Text style={styles.kpiLabel}>Avg realized</Text>
                  <Text style={styles.kpiValue}>
                    {metrics.avg_realized_return == null ? "-" : fmtPct(metrics.avg_realized_return, 2)}
                  </Text>
                </View>
                <View style={styles.kpiBox}>
                  <Text style={styles.kpiLabel}>Samples</Text>
                  <Text style={styles.kpiValue}>{String(metrics.count ?? "-")}</Text>
                </View>
              </View>

              <Text style={styles.sectionSubtitle}>By confidence</Text>

              {Array.isArray(metrics.by_confidence) && metrics.by_confidence.length ? (
                metrics.by_confidence.map((b, idx) => (
                  <View key={idx} style={styles.calRow}>
                    <Text style={styles.calLeft}>{b.label}</Text>
                    <Text style={styles.calMid}>n={b.count}</Text>
                    <Text style={styles.calRight}>{b.hit_rate == null ? "-" : fmtPct(b.hit_rate, 0)}</Text>
                  </View>
                ))
              ) : Array.isArray(metrics.calibration) && metrics.calibration.length ? (
                metrics.calibration.map((b, idx) => (
                  <View key={idx} style={styles.calRow}>
                    <Text style={styles.calLeft}>
                      {fmtPct(b.lo, 0)}–{fmtPct(Math.min(1, b.hi), 0)}
                    </Text>
                    <Text style={styles.calMid}>n={b.count}</Text>
                    <Text style={styles.calRight}>{b.up_rate == null ? "-" : fmtPct(b.up_rate, 0)}</Text>
                  </View>
                ))
              ) : (
                <Text style={styles.muted}>No buckets yet.</Text>
              )}

              {metrics.note ? <Text style={styles.hint}>{metrics.note}</Text> : null}
            </>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Last score run</Text>
          {!scoreResp ? (
            <Text style={styles.muted}>Tap “Score now” to update scored outcomes.</Text>
          ) : (
            <>
              <Text style={styles.meta}>ok: {String(scoreResp.ok)}</Text>
              <Text style={styles.meta}>fetched: {String(scoreResp.fetched ?? "-")}</Text>
              <Text style={styles.meta}>
                counts: <Text style={styles.monoSmall}>{JSON.stringify(scoreResp.counts || {}, null, 0)}</Text>
              </Text>
              {scoreResp.note ? <Text style={styles.hint}>{scoreResp.note}</Text> : null}
            </>
          )}
        </View>

        <Text style={styles.footerNote}>
          Reminder: Even strong models won’t be 100%. You’re building transparency + measurable edge.
        </Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#0B1220" },
  container: { padding: 16, paddingBottom: 40 },
  title: { color: "#FFFFFF", fontSize: 22, fontWeight: "900" },
  subtitle: { color: "#A7B0C0", marginTop: 6, marginBottom: 12, lineHeight: 18 },
  bold: { color: "#E5E7EB", fontWeight: "900" },

  card: {
    backgroundColor: "#111A2E",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 16,
    padding: 14,
    marginTop: 12,
  },

  label: { color: "#E5E7EB", fontWeight: "800", marginBottom: 6 },
  input: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: "#FFFFFF",
    fontSize: 16,
  },

  row: { flexDirection: "row", gap: 10, marginTop: 12, alignItems: "center", flexWrap: "wrap" },

  button: { backgroundColor: "#2E6BFF", paddingHorizontal: 16, paddingVertical: 12, borderRadius: 12 },
  buttonText: { color: "#FFFFFF", fontWeight: "900" },

  smallButton: {
    backgroundColor: "#1B2A4A",
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#223256",
  },
  scoreButton: { borderColor: "#2E6BFF" },
  smallButtonText: { color: "#E5E7EB", fontWeight: "800" },

  hint: { color: "#A7B0C0", marginTop: 10, lineHeight: 18 },
  mutedSmall: { color: "#A7B0C0", fontSize: 12, marginTop: 8 },
  chipsWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  chip: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
  },
  chipText: { color: "#E5E7EB", fontWeight: "900" },

  sectionTitle: { color: "#FFFFFF", fontWeight: "900", fontSize: 16, marginBottom: 6 },
  sectionSubtitle: { color: "#E5E7EB", marginTop: 12, marginBottom: 6, fontWeight: "900" },

  loadingRow: { marginTop: 10, flexDirection: "row", gap: 10, alignItems: "center" },
  loadingText: { color: "#A7B0C0" },

  muted: { color: "#A7B0C0" },
  errorText: { color: "#FF6B6B", marginTop: 8, fontWeight: "800" },

  kpiRow: { flexDirection: "row", gap: 10, marginTop: 10, flexWrap: "wrap" },
  kpiBox: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    minWidth: 110,
  },
  kpiLabel: { color: "#A7B0C0", fontWeight: "800" },
  kpiValue: { color: "#FFFFFF", fontWeight: "900", fontSize: 18, marginTop: 4 },

  calRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 8,
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  calLeft: { color: "#E5E7EB", fontWeight: "900", width: 110 },
  calMid: { color: "#A7B0C0", fontWeight: "800", marginLeft: 8 },
  calRight: { color: "#FFFFFF", fontWeight: "900", marginLeft: "auto" },

  meta: { color: "#A7B0C0", marginTop: 6 },
  monoSmall: { color: "#E5E7EB", fontFamily: "monospace", fontSize: 12 },

  footerNote: { marginTop: 14, color: "#93A4C7", fontSize: 12, lineHeight: 16 },
});
