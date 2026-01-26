// mobile-expo/app/(tabs)/alerts.tsx
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
  lastEmail: "wmr:alerts:lastEmail:v1",
  lastTickers: "wmr:alerts:lastTickers:v1",
  lastMinConfidence: "wmr:alerts:lastMinConfidence:v1",
  lastMinProbUp: "wmr:alerts:lastMinProbUp:v1",
  lastHorizon: "wmr:alerts:lastHorizon:v1",
  // NEW: local hint so we don't nag repeatedly
  warnedNoSubsEndpoint: "wmr:alerts:warnedNoSubsEndpoint:v1",
};

type SubscribeRequest = {
  email: string;
  tickers: string[];
  min_confidence?: "LOW" | "MEDIUM" | "HIGH";
  min_prob_up?: number;
  horizon_days?: number;
};

type SubscriptionRow = {
  id?: string | number;
  email?: string;
  tickers?: string[];
  min_confidence?: string;
  min_prob_up?: number;
  horizon_days?: number;
  created_at?: string;
  updated_at?: string;
  enabled?: boolean;
  [k: string]: any;
};

function toUpperTicker(s: string) {
  return (s || "")
    .toUpperCase()
    .replace(/[^A-Z0-9.\-]/g, "")
    .trim();
}

function normalizeTickers(input: string): string[] {
  const parts = (input || "")
    .replace(/\s+/g, ",")
    .split(",")
    .map((x) => toUpperTicker(x))
    .filter(Boolean);

  const seen = new Set<string>();
  const out: string[] = [];
  for (const t of parts) {
    if (!seen.has(t)) {
      seen.add(t);
      out.push(t);
    }
  }
  return out;
}

function clamp01(x: any): number | null {
  const n = typeof x === "number" ? x : Number(x);
  if (!Number.isFinite(n)) return null;
  return Math.max(0, Math.min(1, n));
}

function fmtPct01(x: any, digits = 0) {
  const n = clamp01(x);
  if (n == null) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

function isEmailLike(s: string) {
  const x = (s || "").trim();
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(x);
}

async function safeJson(res: Response) {
  const txt = await res.text();
  try {
    return JSON.parse(txt);
  } catch {
    return { raw: txt };
  }
}

export default function AlertsTab() {
  const [email, setEmail] = useState("");
  const [tickersText, setTickersText] = useState("SPY,QQQ");
  const [minConfidence, setMinConfidence] = useState<"LOW" | "MEDIUM" | "HIGH">("HIGH");
  const [minProbUp, setMinProbUp] = useState("0.65");
  const [horizonDays, setHorizonDays] = useState("5");

  const [loading, setLoading] = useState(false);
  const [subsLoading, setSubsLoading] = useState(false);
  const [subs, setSubs] = useState<SubscriptionRow[]>([]);

  const parsed = useMemo(() => {
    const tickers = normalizeTickers(tickersText).slice(0, 25);

    let p = Number(minProbUp);
    if (!Number.isFinite(p)) p = 0.65;
    p = Math.max(0, Math.min(1, p));

    let h = parseInt(horizonDays, 10);
    if (!Number.isFinite(h)) h = 5;
    h = Math.max(1, Math.min(60, h));

    return { tickers, min_prob_up: p, horizon_days: h };
  }, [tickersText, minProbUp, horizonDays]);

  useEffect(() => {
    (async () => {
      try {
        const [savedTickers, lastEmail, lastTickers, lastConf, lastProb, lastH] =
          await Promise.all([
            AsyncStorage.getItem(STORAGE_KEYS.savedTickers),
            AsyncStorage.getItem(STORAGE_KEYS.lastEmail),
            AsyncStorage.getItem(STORAGE_KEYS.lastTickers),
            AsyncStorage.getItem(STORAGE_KEYS.lastMinConfidence),
            AsyncStorage.getItem(STORAGE_KEYS.lastMinProbUp),
            AsyncStorage.getItem(STORAGE_KEYS.lastHorizon),
          ]);

        if (lastEmail) setEmail(String(lastEmail));
        if (lastTickers) setTickersText(String(lastTickers));

        if (!lastTickers && savedTickers) {
          try {
            const arr = JSON.parse(savedTickers);
            if (Array.isArray(arr) && arr.length) {
              setTickersText(arr.map(String).slice(0, 10).join(","));
            }
          } catch {
            // ignore
          }
        }

        const c = String(lastConf || "").toUpperCase();
        if (c === "LOW" || c === "MEDIUM" || c === "HIGH") setMinConfidence(c as any);

        if (lastProb) setMinProbUp(String(lastProb));
        if (lastH) setHorizonDays(String(lastH));
      } catch {
        // ignore
      } finally {
        // Do not auto-fetch subscriptions from backend because endpoint isn't deployed.
        refreshSubscriptions().catch(() => {});
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function persistPrefs() {
    try {
      await Promise.all([
        AsyncStorage.setItem(STORAGE_KEYS.lastEmail, email.trim()),
        AsyncStorage.setItem(STORAGE_KEYS.lastTickers, tickersText),
        AsyncStorage.setItem(STORAGE_KEYS.lastMinConfidence, minConfidence),
        AsyncStorage.setItem(STORAGE_KEYS.lastMinProbUp, String(parsed.min_prob_up)),
        AsyncStorage.setItem(STORAGE_KEYS.lastHorizon, String(parsed.horizon_days)),
      ]);
    } catch {
      // ignore
    }
  }

  // ✅ SAFE: backend list endpoint not deployed yet, so do NOT fetch it.
  async function refreshSubscriptions() {
    setSubsLoading(true);
    try {
      setSubs([]);

      // One-time helpful hint (optional)
      const warned = await AsyncStorage.getItem(STORAGE_KEYS.warnedNoSubsEndpoint);
      if (!warned) {
        await AsyncStorage.setItem(STORAGE_KEYS.warnedNoSubsEndpoint, "1");
        // Keep it quiet by default. Uncomment if you want a one-time popup.
        // Alert.alert(
        //   "Subscriptions list",
        //   "Your backend doesn't have GET /api/alerts/subscriptions yet, so the app can't show the subscription list."
        // );
      }
    } finally {
      setSubsLoading(false);
    }
  }

  async function subscribe() {
    const em = email.trim();
    if (!isEmailLike(em)) return Alert.alert("Enter a valid email", "Example: you@email.com");

    if (parsed.tickers.length === 0) {
      return Alert.alert("Add at least 1 ticker", "Example: SPY, QQQ, NVDA");
    }

    setLoading(true);
    try {
      await persistPrefs();

      const body: SubscribeRequest = {
        email: em,
        tickers: parsed.tickers,
        min_confidence: minConfidence,
        min_prob_up: parsed.min_prob_up,
        horizon_days: parsed.horizon_days,
      };

      const res = await fetch(`${API_BASE}/api/alerts/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const j = await safeJson(res);

      if (!res.ok) {
        const msg = `HTTP ${res.status}: ${JSON.stringify(j).slice(0, 600)}`;
        Alert.alert("Subscribe failed", msg);
        return;
      }

      Alert.alert(
        "Subscribed",
        `Email: ${em}\nTickers: ${parsed.tickers.join(", ")}\nMin conf: ${minConfidence}\nMin prob_up: ${fmtPct01(
          parsed.min_prob_up,
          0
        )}\nHorizon: ${parsed.horizon_days}d`
      );

      // Keep UI stable (no backend list endpoint)
      await refreshSubscriptions();
    } catch (e: any) {
      Alert.alert("Network error", String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Alerts</Text>
      <Text style={styles.sub}>
        Subscribe to email alerts from the backend. (Subscription list UI is disabled until the backend list endpoint
        exists.)
      </Text>

      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Create / Update Subscription</Text>

          <Text style={styles.label}>Email</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            style={styles.input}
            placeholder="you@email.com"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
          />

          <Text style={styles.label}>Tickers (comma or space separated)</Text>
          <TextInput
            value={tickersText}
            onChangeText={setTickersText}
            style={styles.input}
            placeholder="SPY, QQQ, NVDA"
            autoCapitalize="characters"
            autoCorrect={false}
          />

          <Text style={styles.label}>Min confidence</Text>
          <View style={styles.chips}>
            {(["LOW", "MEDIUM", "HIGH"] as const).map((c) => {
              const on = c === minConfidence;
              return (
                <Pressable
                  key={c}
                  onPress={() => setMinConfidence(c)}
                  style={[styles.chip, on && styles.chipActive]}
                >
                  <Text style={[styles.chipText, on && styles.chipTextActive]}>{c}</Text>
                </Pressable>
              );
            })}
          </View>

          <View style={styles.row}>
            <View style={styles.rowItem}>
              <Text style={styles.label}>Min prob_up (0–1)</Text>
              <TextInput
                value={minProbUp}
                onChangeText={setMinProbUp}
                style={styles.input}
                placeholder="0.65"
                keyboardType="decimal-pad"
              />
            </View>

            <View style={styles.rowItem}>
              <Text style={styles.label}>Horizon days</Text>
              <TextInput
                value={horizonDays}
                onChangeText={setHorizonDays}
                style={styles.input}
                placeholder="5"
                keyboardType="number-pad"
              />
            </View>
          </View>

          <Pressable style={styles.button} onPress={subscribe} disabled={loading}>
            <Text style={styles.buttonText}>{loading ? "Submitting..." : "Subscribe"}</Text>
          </Pressable>

          <Text style={styles.hint}>
            This calls <Text style={styles.mono}>POST /api/alerts/subscribe</Text>.
          </Text>
        </View>

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>Subscriptions</Text>
          <Pressable style={styles.outlineBtn} onPress={refreshSubscriptions} disabled={subsLoading}>
            <Text style={styles.outlineBtnText}>{subsLoading ? "Loading..." : "Refresh"}</Text>
          </Pressable>
        </View>

        {subsLoading ? <ActivityIndicator /> : null}

        {subs.length === 0 ? (
          <Text style={styles.muted}>
            Subscription list isn’t available yet (backend is missing GET /api/alerts/subscriptions).
          </Text>
        ) : (
          subs.slice(0, 50).map((s, idx) => (
            <View key={String(s.id ?? idx)} style={styles.item}>
              <Text style={styles.itemTitle}>{String(s.email || "—")}</Text>
              <Text style={styles.itemMeta}>
                tickers: {Array.isArray(s.tickers) ? s.tickers.join(", ") : "—"}
              </Text>
              <Text style={styles.itemMeta}>
                min_conf: {String(s.min_confidence || "—")} • min_prob_up:{" "}
                {s.min_prob_up == null ? "—" : fmtPct01(s.min_prob_up, 0)} • horizon: {s.horizon_days ?? "—"}d
              </Text>
              {s.created_at ? <Text style={styles.itemSmall}>created_at: {String(s.created_at)}</Text> : null}
              {s.updated_at ? <Text style={styles.itemSmall}>updated_at: {String(s.updated_at)}</Text> : null}
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
  sub: { color: "#666" },

  scroll: { paddingBottom: 40, gap: 12 },

  card: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 12,
    gap: 10,
    backgroundColor: "white",
  },
  cardTitle: { fontWeight: "900", fontSize: 16 },

  label: { fontSize: 12, color: "#666" },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    backgroundColor: "white",
  },

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
  chipText: { fontWeight: "900", color: "#111", fontSize: 12 },
  chipTextActive: { color: "white" },

  row: { flexDirection: "row", gap: 10 },
  rowItem: { flex: 1 },

  button: {
    backgroundColor: "#111",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 2,
  },
  buttonText: { color: "white", fontSize: 16, fontWeight: "700" },

  hint: { fontSize: 12, color: "#666" },
  mono: { fontFamily: "monospace" },

  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sectionTitle: { fontSize: 18, fontWeight: "900" },

  outlineBtn: {
    borderWidth: 1,
    borderColor: "#111",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  outlineBtnText: { fontWeight: "900", color: "#111" },

  muted: { color: "#666" },

  item: {
    borderWidth: 1,
    borderColor: "#eee",
    borderRadius: 12,
    padding: 12,
    gap: 6,
    backgroundColor: "white",
  },
  itemTitle: { fontWeight: "900", fontSize: 14 },
  itemMeta: { color: "#666", fontSize: 12 },
  itemSmall: { color: "#888", fontSize: 11 },
});
