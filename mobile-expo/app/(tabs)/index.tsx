// mobile-expo/app/(tabs)/index.tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
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
  recentRuns: "wmr:recentRuns:v3",
  lastTickersInput: "wmr:lastTickersInput:v3",
  lastHorizon: "wmr:lastHorizon:v3",
  lastFilter: "wmr:lastFilter:v3",
  lastSort: "wmr:lastSort:v3",
  lastRetrain: "wmr:lastRetrain:v3",
  showDebug: "wmr:showDebug:v3",
  highOnly: "wmr:highOnly:v1",
  lastSourcePref: "wmr:lastSourcePref:v1",
};

const DEFAULT_TICKERS = [
  "AMZN",
  "META",
  "TSLA",
  "NVDA",
  "NFLX",
  "AMD",
  "INTC",
  "JPM",
  "BAC",
  "GS",
  "MS",
  "XOM",
  "CVX",
  "SPY",
  "QQQ",
];

type DirectionFilter = "ALL" | "UP" | "DOWN";
type SortMode = "PROB_DESC" | "EXP_DESC" | "TICKER_ASC";
type SourcePref = "auto" | "cache" | "yfinance";

type PredRow = {
  id?: number;
  ticker?: string;
  prob_up?: number | null;
  exp_return?: number | null;
  direction?: "UP" | "DOWN" | string;
  horizon_days?: number;
  source?: string;
  rows?: number;

  as_of_date?: string | null;
  as_of_close?: number | null;
  realized_return?: number | null;
  realized_direction?: string | null;
  scored_at?: string | null;

  confidence?: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN" | string;
  confidence_score?: number | null;

  [k: string]: any;
};

type SummaryResponse = {
  run_id?: string;
  generated_at?: string;
  tickers?: string[];
  predictions?: PredRow[];
  errors?: Record<string, string>;
  error?: string;
  note?: string | null;
  [k: string]: any;
};

function normalizeTickers(input: string): string[] {
  return input
    .split(/[,\s]+/g)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
    .filter((t, idx, arr) => arr.indexOf(t) === idx);
}

function fmtPct(x: any): string {
  const n = typeof x === "number" ? x : Number(x);
  if (!Number.isFinite(n)) return "-";
  return `${(n * 100).toFixed(1)}%`;
}

function fmtNum(x: any, digits = 4): string {
  const n = typeof x === "number" ? x : Number(x);
  if (!Number.isFinite(n)) return "-";
  return n.toFixed(digits);
}

function nowISO(): string {
  return new Date().toISOString();
}

async function safeJson(res: Response) {
  const txt = await res.text();
  try {
    return JSON.parse(txt);
  } catch {
    return { raw: txt };
  }
}

function makeLocalRunId(): string {
  const rnd = Math.random().toString(16).slice(2, 8).toUpperCase();
  const ts = Date.now().toString(16).toUpperCase();
  return `LOCAL-${ts}-${rnd}`;
}

function clamp01(n: any): number | null {
  const x = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(x)) return null;
  return Math.max(0, Math.min(1, x));
}

function confRank(label: any): number {
  const s = String(label || "").toUpperCase();
  if (s === "HIGH") return 3;
  if (s === "MEDIUM") return 2;
  if (s === "LOW") return 1;
  return 0;
}

function confLabelFromProb(probUp: number | null): "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN" {
  if (probUp === null) return "UNKNOWN";
  const p = Math.abs(probUp - 0.5);
  if (p >= 0.2) return "HIGH";
  if (p >= 0.1) return "MEDIUM";
  if (p >= 0.0) return "LOW";
  return "UNKNOWN";
}

async function openUrl(url: string) {
  try {
    const ok = await Linking.canOpenURL(url);
    if (!ok) return Alert.alert("Cannot open link", url);
    await Linking.openURL(url);
  } catch {
    Alert.alert("Cannot open link", url);
  }
}

export default function HomeScreen() {
  const [tickersInput, setTickersInput] = useState<string>(DEFAULT_TICKERS.join(", "));
  const [savedTickers, setSavedTickers] = useState<string[]>(DEFAULT_TICKERS);
  const [recentRuns, setRecentRuns] = useState<string[]>([]);
  const [horizonDays, setHorizonDays] = useState<number>(5);
  const [retrainEveryRun, setRetrainEveryRun] = useState<boolean>(true);

  const [filter, setFilter] = useState<DirectionFilter>("ALL");
  const [sortMode, setSortMode] = useState<SortMode>("PROB_DESC");
  const [showDebug, setShowDebug] = useState<boolean>(false);
  const [highOnly, setHighOnly] = useState<boolean>(false);

  // ✅ NEW (B): source selector
  const [sourcePref, setSourcePref] = useState<SourcePref>("auto");

  const [loading, setLoading] = useState<boolean>(false);
  const [resp, setResp] = useState<SummaryResponse | null>(null);
  const [debugLine, setDebugLine] = useState<string>("");

  const tickers = useMemo(() => normalizeTickers(tickersInput), [tickersInput]);

  useEffect(() => {
    (async () => {
      try {
        const [
          saved,
          recent,
          lastInput,
          lastH,
          lastFilter,
          lastSort,
          lastRetrain,
          lastShowDebug,
          lastHighOnly,
          lastSourcePref,
        ] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEYS.savedTickers),
          AsyncStorage.getItem(STORAGE_KEYS.recentRuns),
          AsyncStorage.getItem(STORAGE_KEYS.lastTickersInput),
          AsyncStorage.getItem(STORAGE_KEYS.lastHorizon),
          AsyncStorage.getItem(STORAGE_KEYS.lastFilter),
          AsyncStorage.getItem(STORAGE_KEYS.lastSort),
          AsyncStorage.getItem(STORAGE_KEYS.lastRetrain),
          AsyncStorage.getItem(STORAGE_KEYS.showDebug),
          AsyncStorage.getItem(STORAGE_KEYS.highOnly),
          AsyncStorage.getItem(STORAGE_KEYS.lastSourcePref),
        ]);

        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length) setSavedTickers(parsed);
        }
        if (recent) {
          const parsed = JSON.parse(recent);
          if (Array.isArray(parsed)) setRecentRuns(parsed);
        }
        if (lastInput && typeof lastInput === "string" && lastInput.trim()) {
          setTickersInput(lastInput);
        }
        if (lastH) {
          const n = Number(lastH);
          if (Number.isFinite(n) && n > 0) setHorizonDays(n);
        }
        if (lastFilter && ["ALL", "UP", "DOWN"].includes(lastFilter)) {
          setFilter(lastFilter as DirectionFilter);
        }
        if (lastSort && ["PROB_DESC", "EXP_DESC", "TICKER_ASC"].includes(lastSort)) {
          setSortMode(lastSort as SortMode);
        }
        if (lastRetrain && (lastRetrain === "1" || lastRetrain === "0")) {
          setRetrainEveryRun(lastRetrain === "1");
        }
        if (lastShowDebug && (lastShowDebug === "1" || lastShowDebug === "0")) {
          setShowDebug(lastShowDebug === "1");
        }
        if (lastHighOnly && (lastHighOnly === "1" || lastHighOnly === "0")) {
          setHighOnly(lastHighOnly === "1");
        }

        // ✅ load source pref
        if (lastSourcePref && ["auto", "cache", "yfinance"].includes(lastSourcePref)) {
          setSourcePref(lastSourcePref as SourcePref);
        }
      } catch (e: any) {
        setDebugLine(`Init storage error: ${String(e?.message || e)}`);
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

  async function persistLastInput(val: string) {
    await persist(STORAGE_KEYS.lastTickersInput, val);
  }

  async function persistPrefs(
    next?: Partial<{
      horizonDays: number;
      filter: DirectionFilter;
      sortMode: SortMode;
      retrainEveryRun: boolean;
      showDebug: boolean;
      highOnly: boolean;
      sourcePref: SourcePref;
    }>
  ) {
    const h = next?.horizonDays ?? horizonDays;
    const f = next?.filter ?? filter;
    const s = next?.sortMode ?? sortMode;
    const r = next?.retrainEveryRun ?? retrainEveryRun;
    const d = next?.showDebug ?? showDebug;
    const ho = next?.highOnly ?? highOnly;
    const sp = next?.sourcePref ?? sourcePref;

    await Promise.all([
      persist(STORAGE_KEYS.lastHorizon, String(h)),
      persist(STORAGE_KEYS.lastFilter, f),
      persist(STORAGE_KEYS.lastSort, s),
      persist(STORAGE_KEYS.lastRetrain, r ? "1" : "0"),
      persist(STORAGE_KEYS.showDebug, d ? "1" : "0"),
      persist(STORAGE_KEYS.highOnly, ho ? "1" : "0"),
      persist(STORAGE_KEYS.lastSourcePref, sp),
    ]);
  }

  async function addToRecentRun(list: string[], h: number, retrain: boolean) {
    const key = `${list.join(",")}|h=${h}|r=${retrain ? 1 : 0}`;
    const next = [key, ...recentRuns.filter((x) => x !== key)].slice(0, 10);
    setRecentRuns(next);
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.recentRuns, JSON.stringify(next));
    } catch {}
  }

  async function addSavedTicker(ticker: string) {
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    if (savedTickers.includes(t)) return;
    const next = [t, ...savedTickers].slice(0, 40);
    setSavedTickers(next);
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.savedTickers, JSON.stringify(next));
    } catch {}
  }

  async function removeSavedTicker(ticker: string) {
    const next = savedTickers.filter((x) => x !== ticker);
    setSavedTickers(next);
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.savedTickers, JSON.stringify(next));
    } catch {}
  }

  async function callSummaryAPI(list: string[]) {
    const min_confidence = highOnly ? "HIGH" : undefined;

    // Prefer POST (live predictions)
    try {
      const res = await fetch(`${API_BASE}/api/summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tickers: list,
          retrain: retrainEveryRun,
          horizon_days: horizonDays,
          max_parallel: 1,
          min_confidence,
          // ✅ NEW (B)
          source_pref: sourcePref,
        }),
      });
      if (res.ok) return (await safeJson(res)) as SummaryResponse;
    } catch {
      // ignore
    }

    // GET fallback (stored predictions)
    const retrain = retrainEveryRun ? 1 : 0;
    const qs =
      `tickers=${encodeURIComponent(list.join(","))}` +
      `&retrain=${retrain}` +
      `&horizon_days=${encodeURIComponent(String(horizonDays))}` +
      `&source_pref=${encodeURIComponent(sourcePref)}`;

    const res = await fetch(`${API_BASE}/api/summary?${qs}`);
    return (await safeJson(res)) as SummaryResponse;
  }

    async function runPrediction() {
    const list = tickers.length ? tickers : DEFAULT_TICKERS;
    setLoading(true);
    setResp(null);

    const localRunId = makeLocalRunId();
    const localGeneratedAt = nowISO();

    setDebugLine(
      `Debug: tickers=${list.join(",")} horizon=${horizonDays} retrain=${retrainEveryRun ? "1" : "0"} highOnly=${
        highOnly ? "1" : "0"
      } source_pref=${sourcePref} local_run_id=${localRunId}`
    );

    try {
      await persistLastInput(tickersInput);
      await persistPrefs();
      await addToRecentRun(list, horizonDays, retrainEveryRun);

      const data: SummaryResponse = await callSummaryAPI(list);

      if (!data.run_id) data.run_id = localRunId;
      if (!data.generated_at) data.generated_at = localGeneratedAt;

      setResp(data);
      if (data?.error) Alert.alert("API error", String(data.error));
    } catch (e: any) {
      setResp({
        run_id: localRunId,
        generated_at: localGeneratedAt,
        error: String(e?.message || e),
      });
      Alert.alert("Network error", String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  function applyTickerCSV(csv: string) {
    setTickersInput(csv);
    persistLastInput(csv);
  }

  function applyRecentKey(key: string) {
    // format: CSV|h=5|r=1
    const [csv, hPart, rPart] = key.split("|");
    const h = Number((hPart || "").replace("h=", ""));
    const r = (rPart || "").replace("r=", "") === "1";
    if (csv) applyTickerCSV(csv);
    if (Number.isFinite(h) && h > 0) setHorizonDays(h);
    setRetrainEveryRun(r);
    persistPrefs({
      horizonDays: Number.isFinite(h) && h > 0 ? h : horizonDays,
      retrainEveryRun: r,
    });
  }

  const predictions: PredRow[] = useMemo(() => {
    const raw = resp?.predictions;
    if (!Array.isArray(raw)) return [];
    return raw
      .map((p) => {
        const prob = clamp01(p.prob_up);
        const computedLabel = confLabelFromProb(prob);
        return {
          ...p,
          ticker: (p.ticker || "").toString().toUpperCase(),
          prob_up: prob,
          exp_return: typeof p.exp_return === "number" ? p.exp_return : Number(p.exp_return),
          confidence: (p.confidence ? String(p.confidence).toUpperCase() : computedLabel) as any,
          // ✅ keep confidence_score aligned with backend (0..1)
          confidence_score: p.confidence_score ?? (prob === null ? null : Math.abs(prob - 0.5) * 2),
        };
      })
      .filter((p) => p.ticker);
  }, [resp]);

  const filteredSorted = useMemo(() => {
    let arr = [...predictions];

    if (highOnly) {
      arr = arr.filter((p) => confRank(p.confidence) >= 3);
    }

    if (filter !== "ALL") {
      arr = arr.filter((p) => (p.direction || "").toString().toUpperCase() === filter);
    }

    if (sortMode === "TICKER_ASC") {
      arr.sort((a, b) => String(a.ticker).localeCompare(String(b.ticker)));
    } else if (sortMode === "EXP_DESC") {
      arr.sort((a, b) => (Number(b.exp_return) || -999) - (Number(a.exp_return) || -999));
    } else {
      // PROB_DESC: tie-breaker by confidence label
      arr.sort((a, b) => {
        const pb = Number(b.prob_up);
        const pa = Number(a.prob_up);
        if (pb !== pa) return (pb || -999) - (pa || -999);
        return confRank(b.confidence) - confRank(a.confidence);
      });
    }

    return arr;
  }, [predictions, filter, sortMode, highOnly]);

  const topUp = useMemo(() => {
    return [...predictions]
      .filter((p) => (p.direction || "").toString().toUpperCase() === "UP")
      .sort((a, b) => (Number(b.prob_up) || -999) - (Number(a.prob_up) || -999))
      .slice(0, 5);
  }, [predictions]);

  const topDown = useMemo(() => {
    return [...predictions]
      .filter((p) => (p.direction || "").toString().toUpperCase() === "DOWN")
      .sort((a, b) => (Number(a.prob_up) || 999) - (Number(b.prob_up) || 999))
      .slice(0, 5);
  }, [predictions]);

  const errorKeys = useMemo(() => {
    const e = resp?.errors;
    if (!e || typeof e !== "object") return [];
    return Object.keys(e).sort();
  }, [resp]);

  function cycleSourcePref(cur: SourcePref): SourcePref {
    // auto -> cache -> yfinance -> auto
    if (cur === "auto") return "cache";
    if (cur === "cache") return "yfinance";
    return "auto";
  }

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>WorldMarketReviewer</Text>
        <Text style={styles.subtitle}>Mobile Predictions (Render backend)</Text>

        <View style={styles.card}>
          <Text style={styles.label}>Tickers (comma or space separated)</Text>
          <TextInput
            value={tickersInput}
            onChangeText={(t) => {
              setTickersInput(t);
              persistLastInput(t);
            }}
            placeholder="SPY, QQQ, NVDA"
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
                persist(STORAGE_KEYS.lastHorizon, String(next));
              }}
              style={styles.smallButton}
            >
              <Text style={styles.smallButtonText}>Horizon: {horizonDays}d</Text>
            </Pressable>

            <Pressable
              onPress={() => {
                setRetrainEveryRun((v) => {
                  const nv = !v;
                  persist(STORAGE_KEYS.lastRetrain, nv ? "1" : "0");
                  return nv;
                });
              }}
              style={[styles.smallButton, retrainEveryRun ? styles.smallButtonOn : null]}
            >
              <Text style={styles.smallButtonText}>Retrain: {retrainEveryRun ? "ON" : "OFF"}</Text>
            </Pressable>

            <Pressable
              onPress={() => {
                setHighOnly((v) => {
                  const nv = !v;
                  persist(STORAGE_KEYS.highOnly, nv ? "1" : "0");
                  return nv;
                });
              }}
              style={[styles.smallButton, highOnly ? styles.smallButtonOn : null]}
            >
              <Text style={styles.smallButtonText}>High only: {highOnly ? "ON" : "OFF"}</Text>
            </Pressable>

            {/* ✅ NEW (B): Source selector */}
            <Pressable
              onPress={() => {
                setSourcePref((v) => {
                  const nv = cycleSourcePref(v);
                  persist(STORAGE_KEYS.lastSourcePref, nv);
                  return nv;
                });
              }}
              style={styles.smallButton}
            >
              <Text style={styles.smallButtonText}>
                Source: {sourcePref === "auto" ? "Auto" : sourcePref === "cache" ? "Cache" : "Live"}
              </Text>
            </Pressable>

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

          <View style={styles.row}>
            <Pressable onPress={() => openUrl(`${API_BASE}/api/explain`)} style={styles.linkButton}>
              <Text style={styles.linkButtonText}>What am I looking at?</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Saved tickers</Text>
          <Text style={styles.hint}>Tap to replace input. Long-press removes.</Text>

          <View style={styles.chipsWrap}>
            {savedTickers.map((t) => (
              <Pressable
                key={t}
                onPress={() => applyTickerCSV(t)}
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
              <Text style={styles.smallButtonText}>Save first ticker</Text>
            </Pressable>

            <Pressable onPress={() => applyTickerCSV(DEFAULT_TICKERS.join(", "))} style={styles.smallButton}>
              <Text style={styles.smallButtonText}>Defaults</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Recent runs</Text>
          <Text style={styles.hint}>Tap to reuse the exact same set (repeatability).</Text>

          {recentRuns.length === 0 ? (
            <Text style={styles.muted}>No recent runs yet.</Text>
          ) : (
            <View style={styles.recentList}>
              {recentRuns.map((key) => (
                <Pressable key={key} onPress={() => applyRecentKey(key)} style={styles.recentItem}>
                  <Text style={styles.recentText}>{key.replace("|", "  ")}</Text>
                </Pressable>
              ))}
            </View>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Results</Text>

          {!resp ? (
            <Text style={styles.muted}>Run to see output.</Text>
          ) : (
            <>
              <Text style={styles.meta}>
                generated_at: <Text style={styles.mono}>{String(resp.generated_at || "")}</Text>
              </Text>
              <Text style={styles.meta}>
                run_id: <Text style={styles.mono}>{String(resp.run_id || "")}</Text>
              </Text>

              {resp?.error ? <Text style={styles.errorText}>Error: {String(resp.error)}</Text> : null}

              {errorKeys.length > 0 ? (
                <View style={styles.errorBox}>
                  <Text style={styles.errorTitle}>Ticker errors</Text>
                  {errorKeys.map((k) => (
                    <Text key={k} style={styles.errorItem}>
                      • {k}: {String(resp?.errors?.[k] || "")}
                    </Text>
                  ))}
                </View>
              ) : null}

              {predictions.length === 0 ? (
                <Text style={styles.muted}>No predictions returned.</Text>
              ) : (
                <>
                  <View style={styles.row}>
                    <Pressable
                      onPress={() => {
                        const next: DirectionFilter = filter === "ALL" ? "UP" : filter === "UP" ? "DOWN" : "ALL";
                        setFilter(next);
                        persist(STORAGE_KEYS.lastFilter, next);
                      }}
                      style={styles.smallButton}
                    >
                      <Text style={styles.smallButtonText}>Filter: {filter}</Text>
                    </Pressable>

                    <Pressable
                      onPress={() => {
                        const next: SortMode =
                          sortMode === "PROB_DESC"
                            ? "EXP_DESC"
                            : sortMode === "EXP_DESC"
                            ? "TICKER_ASC"
                            : "PROB_DESC";
                        setSortMode(next);
                        persist(STORAGE_KEYS.lastSort, next);
                      }}
                      style={styles.smallButton}
                    >
                      <Text style={styles.smallButtonText}>
                        Sort: {sortMode === "PROB_DESC" ? "Prob ↓" : sortMode === "EXP_DESC" ? "Exp ↓" : "Ticker A–Z"}
                      </Text>
                    </Pressable>

                    <Pressable
                      onPress={() => {
                        setShowDebug((v) => {
                          const nv = !v;
                          persist(STORAGE_KEYS.showDebug, nv ? "1" : "0");
                          return nv;
                        });
                      }}
                      style={styles.smallButton}
                    >
                      <Text style={styles.smallButtonText}>{showDebug ? "Hide Debug" : "Show Debug"}</Text>
                    </Pressable>
                  </View>

                  <View style={styles.splitRow}>
                    <View style={styles.splitCol}>
                      <Text style={styles.splitTitle}>Top UP</Text>
                      {topUp.length === 0 ? (
                        <Text style={styles.muted}>None.</Text>
                      ) : (
                        topUp.map((p) => (
                          <ResultCard key={`up-${p.ticker}`} p={p} sourcePref={sourcePref} />
                        ))
                      )}
                    </View>

                    <View style={styles.splitCol}>
                      <Text style={styles.splitTitle}>Top DOWN</Text>
                      {topDown.length === 0 ? (
                        <Text style={styles.muted}>None.</Text>
                      ) : (
                        topDown.map((p) => (
                          <ResultCard key={`down-${p.ticker}`} p={p} sourcePref={sourcePref} />
                        ))
                      )}
                    </View>
                  </View>

                  <Text style={styles.sectionSubtitle}>All results</Text>
                  {filteredSorted.map((p) => (
                    <ResultCard key={`all-${p.ticker}`} p={p} sourcePref={sourcePref} />
                  ))}

                  {showDebug ? (
                    <View style={styles.jsonBox}>
                      <Text style={styles.monoSmall}>{JSON.stringify(resp, null, 2)}</Text>
                    </View>
                  ) : null}
                </>
              )}
            </>
          )}
        </View>

        <Text style={styles.debug}>{debugLine}</Text>
      </ScrollView>
    </View>
  );
}

function ResultCard({ p, sourcePref }: { p: PredRow; sourcePref: SourcePref }) {
  const dir = (p.direction || "").toString().toUpperCase();
  const prob = typeof p.prob_up === "number" ? p.prob_up : Number(p.prob_up);
  const exp = typeof p.exp_return === "number" ? p.exp_return : Number(p.exp_return);
  const conf = String(p.confidence || confLabelFromProb(clamp01(prob))).toUpperCase();
  const ticker = String(p.ticker || "").toUpperCase();

  const confStyle =
    conf === "HIGH" ? styles.badgeConfHigh : conf === "MEDIUM" ? styles.badgeConfMed : styles.badgeConfLow;

  const horizon = String(p.horizon_days ?? 5);

  return (
    <View style={styles.resultCard}>
      <View style={styles.resultRow}>
        <Text style={styles.resultTicker}>{ticker}</Text>

        <View style={[styles.badge, dir === "UP" ? styles.badgeUp : styles.badgeDown]}>
          <Text style={styles.badgeText}>{dir || "?"}</Text>
        </View>

        <View style={[styles.badge, confStyle]}>
          <Text style={styles.badgeText}>{conf}</Text>
        </View>

        <Text style={styles.resultProb}>{fmtPct(prob)}</Text>
      </View>

      <Text style={styles.resultMeta}>
        exp: {fmtNum(exp, 4)} • horizon: {horizon}d
        {p.source ? ` • src: ${p.source}` : ""}
      </Text>

      <View style={styles.row}>
        <Pressable
          onPress={() =>
            openUrl(
              `${API_BASE}/api/verify?ticker=${encodeURIComponent(ticker)}&horizon_days=${encodeURIComponent(
                horizon
              )}&source_pref=${encodeURIComponent(sourcePref)}`
            )
          }
          style={styles.linkPill}
        >
          <Text style={styles.linkPillText}>Verify</Text>
        </Pressable>

        <Pressable
          onPress={() =>
            openUrl(
              `${API_BASE}/api/report_card?ticker=${encodeURIComponent(ticker)}&horizon_days=${encodeURIComponent(
                horizon
              )}&source_pref=${encodeURIComponent(sourcePref)}`
            )
          }
          style={styles.linkPill}
        >
          <Text style={styles.linkPillText}>Report card</Text>
        </Pressable>
      </View>

      {p.as_of_date ? (
        <Text style={styles.mutedSmall}>
          as_of: {String(p.as_of_date).slice(0, 10)}
          {p.scored_at ? `  •  scored` : `  •  not scored yet`}
          {p.realized_return != null ? `  •  realized: ${fmtPct(p.realized_return)}` : ""}
        </Text>
      ) : null}
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
  smallButtonOn: { borderColor: "#2E6BFF" },
  smallButtonText: { color: "#E5E7EB", fontWeight: "700" },

  linkButton: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  linkButtonText: { color: "#E5E7EB", fontWeight: "800" },

  linkPill: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  linkPillText: { color: "#E5E7EB", fontWeight: "800" },

  loadingRow: { marginTop: 10, flexDirection: "row", gap: 10, alignItems: "center" },
  loadingText: { color: "#A7B0C0" },

  sectionTitle: { color: "#FFFFFF", fontWeight: "800", fontSize: 16, marginBottom: 6 },
  sectionSubtitle: { color: "#E5E7EB", marginTop: 12, marginBottom: 6, fontWeight: "800" },
  hint: { color: "#A7B0C0", marginBottom: 10, lineHeight: 18 },

  chipsWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
  },
  chipText: { color: "#E5E7EB", fontWeight: "800" },

  recentList: { gap: 8 },
  recentItem: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  recentText: { color: "#E5E7EB", fontWeight: "700" },

  muted: { color: "#A7B0C0" },
  mutedSmall: { color: "#A7B0C0", fontSize: 12, marginTop: 8 },
  meta: { color: "#A7B0C0", marginBottom: 4 },
  mono: { color: "#FFFFFF", fontFamily: "monospace" },
  monoSmall: { color: "#E5E7EB", fontFamily: "monospace", fontSize: 12, lineHeight: 16 },

  errorText: { color: "#FF6B6B", marginTop: 8, fontWeight: "700" },
  errorBox: {
    marginTop: 10,
    backgroundColor: "#1A0F18",
    borderColor: "#4B2030",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
  },
  errorTitle: { color: "#FFD1D1", fontWeight: "800", marginBottom: 6 },
  errorItem: { color: "#FFD1D1", marginTop: 2 },

  splitRow: { flexDirection: "row", gap: 10, marginTop: 10, flexWrap: "wrap" },
  splitCol: { flexGrow: 1, flexBasis: 260 },
  splitTitle: { color: "#FFFFFF", fontWeight: "900", marginBottom: 6 },

  resultCard: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    marginTop: 8,
  },
  resultRow: { flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap" },
  resultTicker: { color: "#FFFFFF", fontWeight: "900", fontSize: 16 },
  resultProb: { color: "#E5E7EB", fontWeight: "800", marginLeft: "auto" },
  resultMeta: { color: "#A7B0C0", marginTop: 6 },

  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, borderWidth: 1 },
  badgeUp: { backgroundColor: "#0F2A22", borderColor: "#1ED9A6" },
  badgeDown: { backgroundColor: "#2A1416", borderColor: "#FF6B6B" },

  badgeConfHigh: { backgroundColor: "#102A4A", borderColor: "#2E6BFF" },
  badgeConfMed: { backgroundColor: "#2A2510", borderColor: "#FFD166" },
  badgeConfLow: { backgroundColor: "#1B2A4A", borderColor: "#223256" },

  badgeText: { color: "#FFFFFF", fontWeight: "900" },

  jsonBox: {
    marginTop: 10,
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
  },

  debug: { marginTop: 14, color: "#93A4C7", fontSize: 12 },
});
