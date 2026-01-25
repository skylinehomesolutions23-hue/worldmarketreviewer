// app/(tabs)/compare.tsx
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
  lastSourcePref: "wmr:lastSourcePref:v3",
};

type VerifyResponse = {
  ticker?: string;
  ok?: boolean;
  horizon_days?: number;
  source?: string;
  close_col?: string;

  last?: { close?: number; date?: string };
  realized?: {
    return_1d?: number | null;
    direction_1d?: string;
    return_horizon?: number | null;
    direction_horizon?: string;
    horizon_start_close?: number | null;
    horizon_start_date?: string | null;
  };

  series?: { n?: number; closes?: number[]; dates?: string[] };

  note?: string;
  [k: string]: any;
};

function normalizeTickers(input: string): string[] {
  return input
    .split(/[,\s]+/g)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
    .filter((t, idx, arr) => arr.indexOf(t) === idx);
}

function fmtPct(x: any, digits = 2): string {
  const n = typeof x === "number" ? x : Number(x);
  if (!Number.isFinite(n)) return "-";
  return `${(n * 100).toFixed(digits)}%`;
}

function fmtNum(x: any, digits = 2): string {
  const n = typeof x === "number" ? x : Number(x);
  if (!Number.isFinite(n)) return "-";
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

export default function CompareScreen() {
  const [savedTickers, setSavedTickers] = useState<string[]>(["SPY", "QQQ"]);
  const [ticker, setTicker] = useState<string>("SPY");
  const [horizonDays, setHorizonDays] = useState<number>(5);
  const [sourcePref, setSourcePref] = useState<"auto" | "stooq" | "yahoo">("auto");

  const [loading, setLoading] = useState<boolean>(false);
  const [data, setData] = useState<VerifyResponse | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        const [saved, lastInput, lastH, sp] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEYS.savedTickers),
          AsyncStorage.getItem(STORAGE_KEYS.lastTickersInput),
          AsyncStorage.getItem(STORAGE_KEYS.lastHorizon),
          AsyncStorage.getItem(STORAGE_KEYS.lastSourcePref),
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

        const s = (sp || "auto").toString().toLowerCase();
        if (s === "auto" || s === "stooq" || s === "yahoo") setSourcePref(s);
      } catch {
        // ignore
      }
    })();
  }, []);

  const quickTickers = useMemo(() => {
    const base = [...savedTickers];
    if (!base.includes("SPY")) base.unshift("SPY");
    if (!base.includes("QQQ")) base.unshift("QQQ");
    return base.slice(0, 18);
  }, [savedTickers]);

  async function persistPrefs(nextH: number, nextSource: "auto" | "stooq" | "yahoo") {
    try {
      await Promise.all([
        AsyncStorage.setItem(STORAGE_KEYS.lastHorizon, String(nextH)),
        AsyncStorage.setItem(STORAGE_KEYS.lastSourcePref, nextSource),
      ]);
    } catch {
      // ignore
    }
  }

  function cycleHorizon() {
    const next = horizonDays === 5 ? 10 : horizonDays === 10 ? 20 : 5;
    setHorizonDays(next);
    persistPrefs(next, sourcePref).catch(() => {});
    // optional: re-fetch immediately so the screen reflects the new horizon
    fetchVerify(ticker, next).catch(() => {});
  }

  function cycleSource() {
    const next: "auto" | "stooq" | "yahoo" =
      sourcePref === "auto" ? "stooq" : sourcePref === "stooq" ? "yahoo" : "auto";
    setSourcePref(next);
    persistPrefs(horizonDays, next).catch(() => {});
    // optional: re-fetch immediately so the screen reflects the new source
    fetchVerify(ticker, horizonDays, next).catch(() => {});
  }

  async function fetchVerify(tk?: string, h?: number, sp?: "auto" | "stooq" | "yahoo") {
    const t = (tk ?? ticker).trim().toUpperCase();
    const hd = h ?? horizonDays;
    const source = sp ?? sourcePref;
    if (!t) return;

    setLoading(true);
    setErr("");
    setData(null);

    try {
      const url = `${API_BASE}/api/verify?ticker=${encodeURIComponent(
        t
      )}&horizon_days=${encodeURIComponent(String(hd))}&n=90&lookback_days=240&source_pref=${encodeURIComponent(
        source
      )}`;

      const res = await fetch(url);
      const j = (await safeJson(res)) as VerifyResponse;

      if (!res.ok) {
        const msg = `HTTP ${res.status}: ${JSON.stringify(j).slice(0, 300)}`;
        setErr(msg);
        Alert.alert("Verify failed", msg);
        return;
      }

      setData(j);
      if (j?.ok === false && j?.note) {
        setErr(String(j.note));
      }
    } catch (e: any) {
      const msg = String(e?.message || e);
      setErr(msg);
      Alert.alert("Network error", msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // auto-load once on entry
    fetchVerify().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const lastClose = data?.last?.close;
  const lastDate = data?.last?.date ? String(data?.last?.date).slice(0, 10) : "";

  const r1d = data?.realized?.return_1d ?? null;
  const rH = data?.realized?.return_horizon ?? null;

  const dir1d = (data?.realized?.direction_1d || "").toUpperCase();
  const dirH = (data?.realized?.direction_horizon || "").toUpperCase();

  const hStartClose = data?.realized?.horizon_start_close ?? null;
  const hStartDate = data?.realized?.horizon_start_date
    ? String(data?.realized?.horizon_start_date).slice(0, 10)
    : "";

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Compare / Verify</Text>
        <Text style={styles.subtitle}>
          This shows what actually happened in the last {horizonDays} trading days.
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
            <Pressable onPress={cycleHorizon} style={styles.smallButton}>
              <Text style={styles.smallButtonText}>Horizon: {horizonDays}d</Text>
            </Pressable>

            <Pressable onPress={cycleSource} style={styles.smallButton}>
              <Text style={styles.smallButtonText}>Source: {sourcePref}</Text>
            </Pressable>

            <Pressable onPress={() => fetchVerify()} style={styles.button}>
              <Text style={styles.buttonText}>{loading ? "Loading..." : "Verify"}</Text>
            </Pressable>
          </View>

          <Text style={styles.hint}>
            Beginner tip: This is NOT the model’s prediction. This is the real past move over the last horizon.
            Use it to sanity-check prices and direction.
          </Text>

          <View style={styles.chipsWrap}>
            {quickTickers.map((t) => (
              <Pressable
                key={t}
                onPress={() => {
                  setTicker(t);
                  fetchVerify(t, horizonDays).catch(() => {});
                }}
                style={styles.chip}
              >
                <Text style={styles.chipText}>{t}</Text>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Result</Text>

          {loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator />
              <Text style={styles.loadingText}>Fetching verify data…</Text>
            </View>
          ) : err ? (
            <Text style={styles.errorText}>Error: {err}</Text>
          ) : !data ? (
            <Text style={styles.muted}>Tap “Verify”.</Text>
          ) : (
            <>
              <Text style={styles.meta}>
                ticker: <Text style={styles.mono}>{String(data.ticker || "").toUpperCase()}</Text>
              </Text>
              <Text style={styles.meta}>
                as_of: <Text style={styles.mono}>{lastDate || "-"}</Text>
                {typeof lastClose === "number" ? (
                  <>
                    {"  "}• close: <Text style={styles.mono}>{fmtNum(lastClose, 2)}</Text>
                  </>
                ) : null}
              </Text>

              <View style={styles.kpiRow}>
                <View style={styles.kpiBox}>
                  <Text style={styles.kpiLabel}>1D move</Text>
                  <Text style={styles.kpiValue}>{fmtPct(r1d, 2)}</Text>
                  <Text style={styles.kpiSub}>{dir1d || "-"}</Text>
                </View>

                <View style={styles.kpiBox}>
                  <Text style={styles.kpiLabel}>{horizonDays}D move</Text>
                  <Text style={styles.kpiValue}>{fmtPct(rH, 2)}</Text>
                  <Text style={styles.kpiSub}>{dirH || "-"}</Text>
                </View>

                <View style={styles.kpiBox}>
                  <Text style={styles.kpiLabel}>Start close</Text>
                  <Text style={styles.kpiValue}>{hStartClose == null ? "-" : fmtNum(hStartClose, 2)}</Text>
                  <Text style={styles.kpiSub}>{hStartDate || "-"}</Text>
                </View>
              </View>

              <View style={styles.infoRow}>
                <Text style={styles.infoText}>
                  Data source: <Text style={styles.mono}>{String(data.source || "-")}</Text>
                  {"  "}• Close col: <Text style={styles.mono}>{String(data.close_col || "-")}</Text>
                </Text>
              </View>

              {data.note ? <Text style={styles.hint}>{String(data.note)}</Text> : null}
            </>
          )}
        </View>

        <Text style={styles.footerNote}>
          Next step: we’ll optionally add a tiny sparkline chart right on this screen (still free).
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
  smallButtonText: { color: "#E5E7EB", fontWeight: "800" },

  hint: { color: "#A7B0C0", marginTop: 10, lineHeight: 18 },

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

  loadingRow: { marginTop: 10, flexDirection: "row", gap: 10, alignItems: "center" },
  loadingText: { color: "#A7B0C0" },

  muted: { color: "#A7B0C0" },
  errorText: { color: "#FF6B6B", marginTop: 8, fontWeight: "800" },

  meta: { color: "#A7B0C0", marginTop: 6 },
  mono: { color: "#FFFFFF", fontFamily: "monospace" },

  kpiRow: { flexDirection: "row", gap: 10, marginTop: 12, flexWrap: "wrap" },
  kpiBox: {
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    minWidth: 110,
    flexGrow: 1,
  },
  kpiLabel: { color: "#A7B0C0", fontWeight: "800" },
  kpiValue: { color: "#FFFFFF", fontWeight: "900", fontSize: 18, marginTop: 6 },
  kpiSub: { color: "#A7B0C0", marginTop: 6, fontWeight: "800" },

  infoRow: {
    marginTop: 12,
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  infoText: { color: "#A7B0C0", fontWeight: "700" },

  footerNote: { marginTop: 14, color: "#93A4C7", fontSize: 12, lineHeight: 16 },
});
