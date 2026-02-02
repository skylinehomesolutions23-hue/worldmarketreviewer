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

import TickerPicker from "@/components/TickerPicker";
import { CATALOG_TICKERS, STARTER_TICKERS } from "@/components/tickers";

const API_BASE = "https://worldmarketreviewer.onrender.com";

const STORAGE_KEYS = {
  savedTickers: "wmr:savedTickers:v3",

  // alerts tab prefs
  lastEmail: "wmr:alerts:lastEmail:v1",
  lastTickersText: "wmr:alerts:lastTickers:v1",
  alertsTickers: "wmr:alerts:tickers:v1",

  lastMinConfidence: "wmr:alerts:lastMinConfidence:v1",
  lastMinProbUp: "wmr:alerts:lastMinProbUp:v1",
  lastHorizon: "wmr:alerts:lastHorizon:v1",
};

type SubscribeRequest = {
  email: string;
  enabled?: boolean;
  tickers: string[]; // API accepts list or string in your backend; we send list
  min_confidence?: "LOW" | "MEDIUM" | "HIGH";
  min_prob_up?: number;
  horizon_days?: number;
  source_pref?: string;
  cooldown_minutes?: number;
};

type SubscriptionRow = {
  id?: string | number;
  email?: string;
  enabled?: boolean;
  tickers?: string | string[];
  tickers_list?: string[];
  min_confidence?: string;
  min_prob_up?: number;
  horizon_days?: number;
  source_pref?: string;
  cooldown_minutes?: number;
  last_sent_at?: string | null;
  created_at?: string;
  updated_at?: string;
  [k: string]: any;
};

type AlertEvent = {
  id?: string | number;
  email?: string;
  ticker?: string;
  event_type?: string;
  payload?: any;
  created_at?: string;
  [k: string]: any;
};

function toUpperTicker(s: string) {
  return (s || "")
    .toUpperCase()
    .replace(/[^A-Z0-9.\-]/g, "")
    .trim();
}

function uniq(arr: string[]) {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of arr || []) {
    const t = toUpperTicker(x);
    if (t && !seen.has(t)) {
      seen.add(t);
      out.push(t);
    }
  }
  return out;
}

function normalizeTickersText(input: string): string[] {
  const parts = (input || "")
    .replace(/\s+/g, ",")
    .split(",")
    .map((x) => toUpperTicker(x))
    .filter(Boolean);
  return uniq(parts);
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

async function readJsonArray(key: string): Promise<string[] | null> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) return null;
    const j = JSON.parse(raw);
    if (Array.isArray(j)) return uniq(j.map(String));
    return null;
  } catch {
    return null;
  }
}

export default function AlertsTab() {
  const [email, setEmail] = useState("");

  // manual text input (still supported)
  const [tickersText, setTickersText] = useState("SPY,QQQ");

  // picker-driven tickers (what we actually use)
  const [editing, setEditing] = useState(false);
  const [alertsTickers, setAlertsTickers] = useState<string[]>(STARTER_TICKERS);

  const [minConfidence, setMinConfidence] = useState<"LOW" | "MEDIUM" | "HIGH">("HIGH");
  const [minProbUp, setMinProbUp] = useState("0.65");
  const [horizonDays, setHorizonDays] = useState("5");

  const [loading, setLoading] = useState(false);

  // live subscription + events
  const [subLoading, setSubLoading] = useState(false);
  const [subscription, setSubscription] = useState<SubscriptionRow | null>(null);

  const [eventsLoading, setEventsLoading] = useState(false);
  const [events, setEvents] = useState<AlertEvent[]>([]);

  // derive numbers safely
  const parsed = useMemo(() => {
    // prefer picker tickers; if empty, fall back to text
    const tickers = (alertsTickers?.length ? alertsTickers : normalizeTickersText(tickersText)).slice(0, 25);

    let p = Number(minProbUp);
    if (!Number.isFinite(p)) p = 0.65;
    p = Math.max(0, Math.min(1, p));

    let h = parseInt(horizonDays, 10);
    if (!Number.isFinite(h)) h = 5;
    h = Math.max(1, Math.min(60, h));

    return { tickers, min_prob_up: p, horizon_days: h };
  }, [alertsTickers, tickersText, minProbUp, horizonDays]);

  // initial load
  useEffect(() => {
    (async () => {
      try {
        const [
          savedTickersRaw,
          savedEmail,
          lastTickersText,
          savedAlertsTickers,
          lastConf,
          lastProb,
          lastH,
        ] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEYS.savedTickers),
          AsyncStorage.getItem(STORAGE_KEYS.lastEmail),
          AsyncStorage.getItem(STORAGE_KEYS.lastTickersText),
          readJsonArray(STORAGE_KEYS.alertsTickers),
          AsyncStorage.getItem(STORAGE_KEYS.lastMinConfidence),
          AsyncStorage.getItem(STORAGE_KEYS.lastMinProbUp),
          AsyncStorage.getItem(STORAGE_KEYS.lastHorizon),
        ]);

        if (savedEmail) setEmail(String(savedEmail));

        if (lastTickersText) setTickersText(String(lastTickersText));

        // picker tickers: alertsTickers > saved watchlist tickers > starter
        if (savedAlertsTickers && savedAlertsTickers.length) {
          setAlertsTickers(savedAlertsTickers.slice(0, 40));
        } else if (savedTickersRaw) {
          try {
            const arr = JSON.parse(savedTickersRaw);
            if (Array.isArray(arr) && arr.length) {
              setAlertsTickers(uniq(arr.map(String)).slice(0, 40));
              // also set text for visibility
              setTickersText(uniq(arr.map(String)).slice(0, 10).join(","));
            }
          } catch {
            // ignore
          }
        } else {
          setAlertsTickers(STARTER_TICKERS);
        }

        const c = String(lastConf || "").toUpperCase();
        if (c === "LOW" || c === "MEDIUM" || c === "HIGH") setMinConfidence(c as any);

        if (lastProb) setMinProbUp(String(lastProb));
        if (lastH) setHorizonDays(String(lastH));
      } catch {
        // ignore
      } finally {
        // if we already have an email saved, load subscription + events
        const em = (await AsyncStorage.getItem(STORAGE_KEYS.lastEmail)) || "";
        if (em && isEmailLike(em)) {
          await refreshSubscription(em).catch(() => {});
          await refreshEvents(em).catch(() => {});
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // persist picker tickers whenever they change
  useEffect(() => {
    (async () => {
      try {
        await AsyncStorage.setItem(STORAGE_KEYS.alertsTickers, JSON.stringify(alertsTickers));
      } catch {
        // ignore
      }
    })();
  }, [alertsTickers]);

  async function persistPrefs() {
    try {
      await Promise.all([
        AsyncStorage.setItem(STORAGE_KEYS.lastEmail, email.trim()),
        AsyncStorage.setItem(STORAGE_KEYS.lastTickersText, tickersText),
        AsyncStorage.setItem(STORAGE_KEYS.lastMinConfidence, minConfidence),
        AsyncStorage.setItem(STORAGE_KEYS.lastMinProbUp, String(parsed.min_prob_up)),
        AsyncStorage.setItem(STORAGE_KEYS.lastHorizon, String(parsed.horizon_days)),
      ]);
    } catch {
      // ignore
    }
  }

  async function refreshSubscription(emOverride?: string) {
    const em = (emOverride ?? email).trim().toLowerCase();
    if (!isEmailLike(em)) return;

    setSubLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/alerts/subscription?email=${encodeURIComponent(em)}`,
        { method: "GET" }
      );
      const j = await safeJson(res);

      if (!res.ok || !j?.ok) {
        setSubscription(null);
        return;
      }
      setSubscription(j.subscription || null);
    } catch {
      setSubscription(null);
    } finally {
      setSubLoading(false);
    }
  }

  async function refreshEvents(emOverride?: string) {
    const em = (emOverride ?? email).trim().toLowerCase();
    if (!isEmailLike(em)) return;

    setEventsLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/alerts/events?email=${encodeURIComponent(em)}&limit=50`,
        { method: "GET" }
      );
      const j = await safeJson(res);

      if (!res.ok || !j?.ok) {
        setEvents([]);
        return;
      }
      const rows = Array.isArray(j.events) ? j.events : [];
      setEvents(rows);
    } catch {
      setEvents([]);
    } finally {
      setEventsLoading(false);
    }
  }

  async function subscribe() {
    const em = email.trim();
    if (!isEmailLike(em)) return Alert.alert("Enter a valid email", "Example: you@email.com");

    if (parsed.tickers.length === 0) {
      return Alert.alert("Add at least 1 ticker", "Pick tickers or type: SPY, QQQ, NVDA");
    }

    setLoading(true);
    try {
      await persistPrefs();

      // keep text roughly in sync with picker (nice for visibility)
      const shortText = parsed.tickers.slice(0, 10).join(",");
      setTickersText(shortText);

      const body: SubscribeRequest = {
        email: em,
        enabled: true,
        tickers: parsed.tickers.slice(0, 10), // backend enforces up to 10
        min_confidence: minConfidence,
        min_prob_up: parsed.min_prob_up,
        horizon_days: parsed.horizon_days,
        source_pref: "auto",
        cooldown_minutes: 360,
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
        `Email: ${em}\nTickers: ${body.tickers.join(", ")}\nMin conf: ${minConfidence}\nMin prob_up: ${fmtPct01(
          parsed.min_prob_up,
          0
        )}\nHorizon: ${parsed.horizon_days}d`
      );

      // now show real backend subscription + events
      await refreshSubscription(em);
      await refreshEvents(em);
    } catch (e: any) {
      Alert.alert("Network error", String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  const topChips = useMemo(() => parsed.tickers.slice(0, 10), [parsed.tickers]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Alerts</Text>
      <Text style={styles.sub}>
        Pick tickers + thresholds, then subscribe. This uses your Render backend alerts system.
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

          <View style={styles.rowBetween}>
            <Text style={styles.label}>Tickers</Text>
            <Pressable style={styles.outlineBtnSmall} onPress={() => setEditing((v) => !v)}>
              <Text style={styles.outlineBtnTextSmall}>{editing ? "Done" : "Edit tickers"}</Text>
            </Pressable>
          </View>

          {editing ? (
            <View style={{ marginTop: 8 }}>
              <TickerPicker
                title="Alert tickers"
                catalog={CATALOG_TICKERS}
                selected={alertsTickers}
                onChangeSelected={(next) => setAlertsTickers(uniq(next))}
                maxSelected={40}
              />
              <Text style={styles.hint}>
                Note: backend subscription stores up to 10 tickers. We’ll send your first 10.
              </Text>
            </View>
          ) : null}

          {/* Chips preview (what will be sent) */}
          <View style={styles.chips}>
            {topChips.length ? (
              topChips.map((t) => (
                <View key={t} style={styles.chip}>
                  <Text style={styles.chipText}>{t}</Text>
                </View>
              ))
            ) : (
              <Text style={styles.muted}>No tickers selected yet.</Text>
            )}
          </View>

          {/* Keep manual input as fallback (optional) */}
          <Text style={styles.label}>Manual tickers (optional)</Text>
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
                  style={[styles.chipBtn, on && styles.chipActive]}
                >
                  <Text style={[styles.chipBtnText, on && styles.chipTextActive]}>{c}</Text>
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
            Calls <Text style={styles.mono}>POST /api/alerts/subscribe</Text> then refreshes subscription + events.
          </Text>
        </View>

        {/* Subscription */}
        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>Your Subscription</Text>
          <Pressable
            style={styles.outlineBtn}
            onPress={() => refreshSubscription().catch(() => {})}
            disabled={subLoading}
          >
            <Text style={styles.outlineBtnText}>{subLoading ? "Loading..." : "Refresh"}</Text>
          </Pressable>
        </View>

        {subLoading ? <ActivityIndicator /> : null}

        {!subscription ? (
          <Text style={styles.muted}>
            No subscription loaded. Enter your email and tap Refresh, or Subscribe.
          </Text>
        ) : (
          <View style={styles.item}>
            <Text style={styles.itemTitle}>{String(subscription.email || "—")}</Text>
            <Text style={styles.itemMeta}>
              enabled: {String(subscription.enabled ?? true)} • cooldown: {subscription.cooldown_minutes ?? "—"} min
            </Text>
            <Text style={styles.itemMeta}>
              min_conf: {String(subscription.min_confidence || "—")} • min_prob_up:{" "}
              {subscription.min_prob_up == null ? "—" : fmtPct01(subscription.min_prob_up, 0)} • horizon:{" "}
              {subscription.horizon_days ?? "—"}d
            </Text>
            <Text style={styles.itemMeta}>
              tickers:{" "}
              {Array.isArray(subscription.tickers_list)
                ? subscription.tickers_list.join(", ")
                : Array.isArray(subscription.tickers)
                ? subscription.tickers.join(", ")
                : String(subscription.tickers || "—")}
            </Text>
            {subscription.last_sent_at ? (
              <Text style={styles.itemSmall}>last_sent_at: {String(subscription.last_sent_at)}</Text>
            ) : null}
          </View>
        )}

        {/* Events */}
        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>Recent Alert Events</Text>
          <Pressable
            style={styles.outlineBtn}
            onPress={() => refreshEvents().catch(() => {})}
            disabled={eventsLoading}
          >
            <Text style={styles.outlineBtnText}>{eventsLoading ? "Loading..." : "Refresh"}</Text>
          </Pressable>
        </View>

        {eventsLoading ? <ActivityIndicator /> : null}

        {events.length === 0 ? (
          <Text style={styles.muted}>No events yet. Once alerts trigger, they’ll show up here.</Text>
        ) : (
          events.slice(0, 50).map((ev, idx) => (
            <View key={String(ev.id ?? idx)} style={styles.item}>
              <View style={styles.rowBetween}>
                <Text style={styles.itemTitle}>{String(ev.ticker || "—")}</Text>
                <Text style={styles.itemSmall}>{String(ev.created_at || "")}</Text>
              </View>
              <Text style={styles.itemMeta}>type: {String(ev.event_type || "—")}</Text>
              {ev.payload ? (
                <Text style={styles.itemSmall} numberOfLines={6}>
                  payload: {JSON.stringify(ev.payload)}
                </Text>
              ) : null}
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
  chipText: { fontWeight: "900", color: "#111", fontSize: 12 },

  chipBtn: {
    borderWidth: 1,
    borderColor: "#ddd",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "white",
  },
  chipActive: { borderColor: "#111", backgroundColor: "#111" },
  chipBtnText: { fontWeight: "900", color: "#111", fontSize: 12 },
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

  outlineBtnSmall: {
    borderWidth: 1,
    borderColor: "#111",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  outlineBtnTextSmall: { fontWeight: "900", color: "#111", fontSize: 12 },

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
