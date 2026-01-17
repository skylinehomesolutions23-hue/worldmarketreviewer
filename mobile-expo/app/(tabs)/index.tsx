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
  savedTickers: "wmr:savedTickers:v2",
  recentTickers: "wmr:recentTickers:v2",
  lastTickersInput: "wmr:lastTickersInput:v2",
  lastHorizon: "wmr:lastHorizon:v2",
  lastFilter: "wmr:lastFilter:v2",
  lastSort: "wmr:lastSort:v2",
  lastRetrain: "wmr:lastRetrain:v2",
};

const DEFAULT_TICKERS = [
  "AMZN","META","TSLA","NVDA","NFLX","AMD","INTC","JPM","BAC","GS",
    "MS","XOM","CVX","SPY","QQQ","DIA","ORCL","IBM","CRM","ADBE","WMT",
    "COST","HD","PFE","JNJ","UNH","BA","CAT","GE","XLK","XLF","XLE",
    "XLV","XLI","XLY","XLP","XLU"
];

type PredictionRow = {
  ticker: string;
  prob_up: number | null;
  exp_return: number | null;
  direction: "UP" | "DOWN" | string;
  horizon_days?: number;
  source?: string | null;
};

type SummaryResponse = {
  run_id?: string;
  generated_at?: string;
  tickers?: string[];
  horizon_days?: number;
  retrain?: boolean;
  predictions?: PredictionRow[];
  errors?: Record<string, string>;
  [key: string]: any;
};

function normalizeTickers(input: string): string[] {
  return input
    .split(/[,\s]+/g)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
    .filter((t, idx, arr) => arr.indexOf(t) === idx);
}

function fmtPct(x: number | null | undefined): string {
  if (typeof x !== "number") return "-";
  return (x * 100).toFixed(1) + "%";
}

function fmtNum(x: number | null | undefined): string {
  if (typeof x !== "number") return "-";
  return x.toFixed(4);
}

export default function HomeScreen() {
  const [tickersInput, setTickersInput] = useState<string>("SPY, QQQ, IWM");
  const [savedTickers, setSavedTickers] = useState<string[]>(DEFAULT_TICKERS);
  const [recentTickers, setRecentTickers] = useState<string[]>([]);
  const [retrainEveryRun, setRetrainEveryRun] = useState<boolean>(true);

  const [horizonDays, setHorizonDays] = useState<number>(5);
  const [filterDir, setFilterDir] = useState<"ALL" | "UP" | "DOWN">("ALL");
  const [sortBy, setSortBy] = useState<"PROB" | "EXPRET" | "AZ">("PROB");

  const [loading, setLoading] = useState<boolean>(false);
  const [resp, setResp] = useState<SummaryResponse | null>(null);
  const [showDebug, setShowDebug] = useState<boolean>(false);

  const tickers = useMemo(() => normalizeTickers(tickersInput), [tickersInput]);

  useEffect(() => {
    (async () => {
      try {
        const [
          saved,
          recent,
          last,
          h,
          f,
          s,
          r,
        ] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEYS.savedTickers),
          AsyncStorage.getItem(STORAGE_KEYS.recentTickers),
          AsyncStorage.getItem(STORAGE_KEYS.lastTickersInput),
          AsyncStorage.getItem(STORAGE_KEYS.lastHorizon),
          AsyncStorage.getItem(STORAGE_KEYS.lastFilter),
          AsyncStorage.getItem(STORAGE_KEYS.lastSort),
          AsyncStorage.getItem(STORAGE_KEYS.lastRetrain),
        ]);

        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length) setSavedTickers(parsed);
        }
        if (recent) {
          const parsed = JSON.parse(recent);
          if (Array.isArray(parsed)) setRecentTickers(parsed);
        }
        if (last && typeof last === "string" && last.trim().length > 0) {
          setTickersInput(last);
        }
        if (h) setHorizonDays(Math.max(1, parseInt(h, 10) || 5));
        if (f === "UP" || f === "DOWN" || f === "ALL") setFilterDir(f);
        if (s === "PROB" || s === "EXPRET" || s === "AZ") setSortBy(s);
        if (r === "0" || r === "1") setRetrainEveryRun(r === "1");
      } catch (e: any) {
        // ignore
      }
    })();
  }, []);

  async function persist(key: string, val: string) {
    try {
      await AsyncStorage.setItem(key, val);
    } catch {
      // ignore
    }
  }

  async function addToRecent(list: string[]) {
    const key = list.join(",");
    const next = [key, ...recentTickers.filter((x) => x !== key)].slice(0, 10);
    setRecentTickers(next);
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.recentTickers, JSON.stringify(next));
    } catch {
      // ignore
    }
  }

  async function addSavedTicker(ticker: string) {
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    if (savedTickers.includes(t)) return;
    const next = [t, ...savedTickers].slice(0, 30);
    setSavedTickers(next);
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.savedTickers, JSON.stringify(next));
    } catch {
      // ignore
    }
  }

  async function removeSavedTicker(ticker: string) {
    const next = savedTickers.filter((x) => x !== ticker);
    setSavedTickers(next);
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.savedTickers, JSON.stringify(next));
    } catch {
      // ignore
    }
  }

  async function callSummaryAPI(list: string[]) {
    const payload = {
      tickers: list,
      retrain: retrainEveryRun,
      horizon_days: horizonDays,
      base_weekly_move: 0.02,
      max_parallel: 3,
    };

    const res = await fetch(`${API_BASE}/api/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const txt = await res.text();
    try {
      return JSON.parse(txt);
    } catch {
      return { error: `Bad JSON: ${txt}` };
    }
  }

  async function runPrediction() {
    const list = tickers.length ? tickers : DEFAULT_TICKERS;

    setLoading(true);
    setResp(null);

    try {
      await persist(STORAGE_KEYS.lastTickersInput, tickersInput);
      await persist(STORAGE_KEYS.lastHorizon, String(horizonDays));
      await persist(STORAGE_KEYS.lastFilter, filterDir);
      await persist(STORAGE_KEYS.lastSort, sortBy);
      await persist(STORAGE_KEYS.lastRetrain, retrainEveryRun ? "1" : "0");

      await addToRecent(list);

      const data: SummaryResponse = await callSummaryAPI(list);

      setResp(data);

      if (data?.errors && Object.keys(data.errors).length > 0) {
        // show a short error summary
        const firstKey = Object.keys(data.errors)[0];
        Alert.alert("Some tickers failed", `${firstKey}: ${String(data.errors[firstKey])}`);
      }
      if (data?.error) {
        Alert.alert("API error", String(data.error));
      }
    } catch (e: any) {
      Alert.alert("Network error", String(e?.message || e));
      setResp({ error: String(e?.message || e) });
    } finally {
      setLoading(false);
    }
  }

  function applyTickerSet(csv: string) {
    setTickersInput(csv);
    persist(STORAGE_KEYS.lastTickersInput, csv);
  }

  const rawPreds = resp?.predictions || [];

  const filteredSortedPreds = useMemo(() => {
    let preds = [...rawPreds];

    if (filterDir !== "ALL") {
      preds = preds.filter((p) => String(p.direction).toUpperCase() === filterDir);
    }

    if (sortBy === "AZ") {
      preds.sort((a, b) => String(a.ticker).localeCompare(String(b.ticker)));
    } else if (sortBy === "EXPRET") {
      preds.sort((a, b) => (b.exp_return ?? -999) - (a.exp_return ?? -999));
    } else {
      preds.sort((a, b) => (b.prob_up ?? -999) - (a.prob_up ?? -999));
    }

    return preds;
  }, [rawPreds, filterDir, sortBy]);

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>WorldMarketReviewer</Text>
        <Text style={styles.subtitle}>Mobile Predictions (sorted + filterable)</Text>

        <View style={styles.card}>
          <Text style={styles.label}>Tickers (comma or space separated)</Text>
          <TextInput
            value={tickersInput}
            onChangeText={(t) => {
              setTickersInput(t);
              persist(STORAGE_KEYS.lastTickersInput, t);
            }}
            placeholder="SPY, QQQ, IWM"
            placeholderTextColor="#6b7280"
            autoCapitalize="characters"
            autoCorrect={false}
            style={styles.input}
          />

          <View style={styles.row}>
            <Pressable
              onPress={() => setRetrainEveryRun((v) => !v)}
              style={[styles.toggle, retrainEveryRun ? styles.toggleOn : styles.toggleOff]}
            >
              <Text style={styles.toggleText}>Retrain: {retrainEveryRun ? "ON" : "OFF"}</Text>
            </Pressable>

            <View style={styles.pillsRow}>
              {[1, 5, 10, 20].map((h) => (
                <Pressable
                  key={h}
                  onPress={() => {
                    setHorizonDays(h);
                    persist(STORAGE_KEYS.lastHorizon, String(h));
                  }}
                  style={[styles.pill, horizonDays === h ? styles.pillOn : styles.pillOff]}
                >
                  <Text style={styles.pillText}>{h}d</Text>
                </Pressable>
              ))}
            </View>

            <Pressable onPress={runPrediction} style={styles.button}>
              <Text style={styles.buttonText}>{loading ? "Running..." : "Run"}</Text>
            </Pressable>
          </View>

          {loading && (
            <View style={styles.loadingRow}>
              <ActivityIndicator />
              <Text style={styles.loadingText}>Fetching predictions…</Text>
            </View>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Saved tickers</Text>
          <Text style={styles.hint}>Tap inserts. Long-press removes. “Save ticker” saves the first ticker you typed.</Text>

          <View style={styles.chipsWrap}>
            {savedTickers.map((t) => (
              <Pressable
                key={t}
                onPress={() => applyTickerSet(t)}
                onLongPress={() => removeSavedTicker(t)}
                style={styles.chip}
              >
                <Text style={styles.chipText}>{t}</Text>
              </Pressable>
            ))}
          </View>

          <View style={styles.row}>
            <Pressable
              onPress={() => {
                const list = normalizeTickers(tickersInput);
                if (list.length === 0) return;
                addSavedTicker(list[0]);
              }}
              style={styles.smallButton}
            >
              <Text style={styles.smallButtonText}>Save ticker (first)</Text>
            </Pressable>

            <Pressable onPress={() => applyTickerSet(DEFAULT_TICKERS.join(", "))} style={styles.smallButton}>
              <Text style={styles.smallButtonText}>Defaults</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Results</Text>

          <View style={styles.row}>
            <View style={styles.pillsRow}>
              {(["ALL", "UP", "DOWN"] as const).map((v) => (
                <Pressable
                  key={v}
                  onPress={() => {
                    setFilterDir(v);
                    persist(STORAGE_KEYS.lastFilter, v);
                  }}
                  style={[styles.pill, filterDir === v ? styles.pillOn : styles.pillOff]}
                >
                  <Text style={styles.pillText}>{v}</Text>
                </Pressable>
              ))}
            </View>

            <View style={styles.pillsRow}>
              {[
                { k: "PROB" as const, label: "Prob↓" },
                { k: "EXPRET" as const, label: "Exp↓" },
                { k: "AZ" as const, label: "A→Z" },
              ].map((x) => (
                <Pressable
                  key={x.k}
                  onPress={() => {
                    setSortBy(x.k);
                    persist(STORAGE_KEYS.lastSort, x.k);
                  }}
                  style={[styles.pill, sortBy === x.k ? styles.pillOn : styles.pillOff]}
                >
                  <Text style={styles.pillText}>{x.label}</Text>
                </Pressable>
              ))}
            </View>
          </View>

          {!resp ? (
            <Text style={styles.muted}>Run to see output.</Text>
          ) : (
            <>
              <Text style={styles.meta}>
                run_id: <Text style={styles.mono}>{String(resp.run_id || "")}</Text>
              </Text>
              <Text style={styles.meta}>
                generated_at: <Text style={styles.mono}>{String(resp.generated_at || "")}</Text>
              </Text>

              {resp?.errors && Object.keys(resp.errors).length > 0 ? (
                <Text style={styles.errorText}>
                  Errors: {Object.keys(resp.errors).length} (tap Debug to view)
                </Text>
              ) : null}

              {filteredSortedPreds.length === 0 ? (
                <Text style={styles.muted}>No predictions returned.</Text>
              ) : (
                <View style={{ marginTop: 10 }}>
                  {filteredSortedPreds.map((p) => (
                    <View key={p.ticker} style={styles.resultRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.resultTitle}>
                          {p.ticker}{" "}
                          <Text style={p.direction === "UP" ? styles.up : styles.down}>
                            {String(p.direction)}
                          </Text>
                        </Text>
                        <Text style={styles.resultSub}>
                          prob: {fmtPct(p.prob_up)} • exp: {fmtNum(p.exp_return)} • src:{" "}
                          {p.source || "-"} • {p.horizon_days ?? horizonDays}d
                        </Text>
                      </View>
                      <Text style={styles.bigPct}>{fmtPct(p.prob_up)}</Text>
                    </View>
                  ))}
                </View>
              )}

              <Pressable onPress={() => setShowDebug((v) => !v)} style={styles.debugToggle}>
                <Text style={styles.debugToggleText}>{showDebug ? "Hide Debug" : "Show Debug"}</Text>
              </Pressable>

              {showDebug ? (
                <View style={styles.jsonBox}>
                  <Text style={styles.monoSmall}>{JSON.stringify(resp, null, 2)}</Text>
                </View>
              ) : null}
            </>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Recent runs</Text>
          <Text style={styles.hint}>Tap to reuse the exact same ticker set.</Text>

          {recentTickers.length === 0 ? (
            <Text style={styles.muted}>No recent runs yet.</Text>
          ) : (
            <View style={styles.recentList}>
              {recentTickers.map((csv) => (
                <Pressable key={csv} onPress={() => applyTickerSet(csv)} style={styles.recentItem}>
                  <Text style={styles.recentText}>{csv}</Text>
                </Pressable>
              ))}
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#0B1220" },
  container: { padding: 16, paddingBottom: 40 },
  title: { color: "#FFFFFF", fontSize: 24, fontWeight: "800" },
  subtitle: { color: "#A7B0C0", marginTop: 4, marginBottom: 12 },

  card: {
    backgroundColor: "#111A2E",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 16,
    padding: 14,
    marginTop: 12,
  },

  label: { color: "#E5E7EB", fontWeight: "700", marginBottom: 6 },
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
  buttonText: { color: "#FFFFFF", fontWeight: "800" },

  smallButton: {
    backgroundColor: "#1B2A4A",
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#223256",
  },
  smallButtonText: { color: "#E5E7EB", fontWeight: "700" },

  toggle: { paddingHorizontal: 12, paddingVertical: 10, borderRadius: 12, borderWidth: 1 },
  toggleOn: { backgroundColor: "#16324F", borderColor: "#2E6BFF" },
  toggleOff: { backgroundColor: "#1B2A4A", borderColor: "#223256" },
  toggleText: { color: "#E5E7EB", fontWeight: "700" },

  pillsRow: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  pill: { paddingHorizontal: 10, paddingVertical: 8, borderRadius: 999, borderWidth: 1 },
  pillOn: { backgroundColor: "#16324F", borderColor: "#2E6BFF" },
  pillOff: { backgroundColor: "#0B1220", borderColor: "#223256" },
  pillText: { color: "#E5E7EB", fontWeight: "800", fontSize: 12 },

  loadingRow: { marginTop: 10, flexDirection: "row", gap: 10, alignItems: "center" },
  loadingText: { color: "#A7B0C0" },

  sectionTitle: { color: "#FFFFFF", fontWeight: "800", fontSize: 16, marginBottom: 6 },
  hint: { color: "#A7B0C0", marginBottom: 10, lineHeight: 18 },

  chipsWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { backgroundColor: "#0B1220", borderColor: "#223256", borderWidth: 1, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 999 },
  chipText: { color: "#E5E7EB", fontWeight: "800" },

  muted: { color: "#A7B0C0" },
  meta: { color: "#A7B0C0", marginBottom: 4 },
  mono: { color: "#FFFFFF", fontFamily: "monospace" },

  resultRow: {
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: "#223256",
  },
  resultTitle: { color: "#FFFFFF", fontWeight: "900", fontSize: 16 },
  resultSub: { color: "#A7B0C0", marginTop: 3, fontSize: 12 },
  bigPct: { color: "#FFFFFF", fontWeight: "900" },
  up: { color: "#7CFFB2" },
  down: { color: "#FF8A8A" },

  errorText: { color: "#FF6B6B", marginTop: 8, fontWeight: "700" },

  debugToggle: {
    marginTop: 12,
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
    alignSelf: "flex-start",
  },
  debugToggleText: { color: "#E5E7EB", fontWeight: "800" },

  jsonBox: { marginTop: 10, backgroundColor: "#0B1220", borderColor: "#223256", borderWidth: 1, borderRadius: 12, padding: 12 },
  monoSmall: { color: "#E5E7EB", fontFamily: "monospace", fontSize: 12, lineHeight: 16 },

  recentList: { gap: 8 },
  recentItem: { backgroundColor: "#0B1220", borderColor: "#223256", borderWidth: 1, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10 },
  recentText: { color: "#E5E7EB", fontWeight: "700" },
});
