import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  ActivityIndicator,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";

const API_BASE = "https://worldmarketreviewer.onrender.com";

const STORAGE_KEYS = {
  rules: "wmr:alerts:rules:v1",
  history: "wmr:alerts:history:v1",
  savedTickersCandidates: [
    "wmr:savedTickers:v3",
    "wmr:savedTickers:v2",
    "wmr:savedTickers:v1",
    "savedTickers",
  ],
};

type Rule = {
  id: string;
  name: string;
  minProbUp: number; // 0..1
  minConfidence: "LOW" | "MEDIUM" | "HIGH";
  tickers: string[]; // max 10
  enabled: boolean;
};

type Hit = {
  time: string;
  ruleId: string;
  ruleName: string;
  ticker: string;
  prob_up: number | null;
  confidence: string;
  source?: string;
  as_of_date?: string | null;
};

type Prediction = {
  ticker: string;
  prob_up?: number | null;
  confidence?: string;
  source?: string;
  as_of_date?: string | null;
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

function confRank(c: string) {
  const x = (c || "").toUpperCase().trim();
  if (x === "HIGH") return 3;
  if (x === "MEDIUM") return 2;
  if (x === "LOW") return 1;
  return 0;
}

function fmtProb(x?: number | null) {
  if (x === null || x === undefined) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(0)}%`;
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
        const cleaned = uniq(
          vals
            .replace(/\s+/g, ",")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        );
        if (cleaned.length) return cleaned;
      }
    } catch {}
  }
  return ["SPY", "QQQ", "TSLA", "NVDA", "AAPL"];
}

async function loadRules(): Promise<Rule[]> {
  const raw = await AsyncStorage.getItem(STORAGE_KEYS.rules);
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

async function saveRules(rules: Rule[]) {
  await AsyncStorage.setItem(STORAGE_KEYS.rules, JSON.stringify(rules));
}

async function loadHistory(): Promise<Hit[]> {
  const raw = await AsyncStorage.getItem(STORAGE_KEYS.history);
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

async function saveHistory(items: Hit[]) {
  await AsyncStorage.setItem(STORAGE_KEYS.history, JSON.stringify(items.slice(0, 200)));
}

export default function AlertsTab() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [history, setHistory] = useState<Hit[]>([]);
  const [loading, setLoading] = useState(false);

  // Create rule form
  const [name, setName] = useState("High edge");
  const [minProbUp, setMinProbUp] = useState("0.65");
  const [minConf, setMinConf] = useState<"LOW" | "MEDIUM" | "HIGH">("MEDIUM");
  const [tickersText, setTickersText] = useState("SPY,QQQ,TSLA,NVDA,AAPL");

  const parsed = useMemo(() => {
    let p = parseFloat(minProbUp);
    if (!Number.isFinite(p)) p = 0.65;
    p = Math.max(0, Math.min(1, p));
    const tickers = uniq(
      tickersText
        .replace(/\s+/g, ",")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    ).slice(0, 10);

    return { p, tickers };
  }, [minProbUp, tickersText]);

  useEffect(() => {
    (async () => {
      const [r, h, saved] = await Promise.all([loadRules(), loadHistory(), loadSavedTickers()]);
      setRules(r);
      setHistory(h);
      if (!tickersText.trim()) setTickersText(saved.join(","));
    })().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createRule() {
    const id = `${Date.now()}`;
    const rule: Rule = {
      id,
      name: name.trim() || "Alert Rule",
      minProbUp: parsed.p,
      minConfidence: minConf,
      tickers: parsed.tickers.length ? parsed.tickers : ["SPY", "QQQ", "TSLA"],
      enabled: true,
    };
    const next = [rule, ...rules];
    setRules(next);
    await saveRules(next);
    Alert.alert("Saved", "Rule created.");
  }

  async function toggleRule(id: string) {
    const next = rules.map((r) => (r.id === id ? { ...r, enabled: !r.enabled } : r));
    setRules(next);
    await saveRules(next);
  }

  async function deleteRule(id: string) {
    const next = rules.filter((r) => r.id !== id);
    setRules(next);
    await saveRules(next);
  }

  async function clearHistory() {
    setHistory([]);
    await saveHistory([]);
  }

  async function runCheckNow() {
    const active = rules.filter((r) => r.enabled);
    if (active.length === 0) {
      return Alert.alert("No enabled rules", "Create a rule or enable one first.");
    }

    // Union tickers across active rules
    const allTickers = uniq(active.flatMap((r) => r.tickers)).slice(0, 10);
    if (allTickers.length === 0) {
      return Alert.alert("No tickers", "Add tickers to at least one enabled rule.");
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tickers: allTickers,
          retrain: false,
          horizon_days: 5,
          base_weekly_move: 0.02,
          max_parallel: 4,
          source_pref: "auto",
        }),
      });

      const json = await res.json();
      const preds: Prediction[] = Array.isArray(json?.predictions) ? json.predictions : [];

      const hits: Hit[] = [];
      const now = new Date().toLocaleString();

      for (const rule of active) {
        const needProb = rule.minProbUp;
        const needConf = confRank(rule.minConfidence);

        for (const tk of rule.tickers) {
          const p = preds.find((x) => (x.ticker || "").toUpperCase() === tk.toUpperCase());
          const prob = p?.prob_up ?? null;
          const conf = (p?.confidence || "UNKNOWN").toUpperCase();

          const probOk = prob !== null && Number.isFinite(prob) && prob >= needProb;
          const confOk = confRank(conf) >= needConf;

          if (probOk && confOk) {
            hits.push({
              time: now,
              ruleId: rule.id,
              ruleName: rule.name,
              ticker: tk.toUpperTicker?.() ?? tk,
              prob_up: prob,
              confidence: conf,
              source: p?.source,
              as_of_date: p?.as_of_date ?? null,
            } as any);
          }
        }
      }

      if (hits.length) {
        const nextHist = [...hits, ...history].slice(0, 200);
        setHistory(nextHist);
        await saveHistory(nextHist);

        // For now: reliable device popup.
        // Later: true push/email (Step 2b).
        Alert.alert(
          `Alerts triggered (${hits.length})`,
          hits.slice(0, 6).map((h) => `${h.ticker} • ${fmtProb(h.prob_up)} • ${h.confidence}`).join("\n")
        );
      } else {
        Alert.alert("No alerts triggered", "Nothing matched your rules this run.");
      }
    } catch (e: any) {
      Alert.alert("Alert check failed", e?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Alerts</Text>
      <Text style={styles.sub}>Create rules and run checks during your testing phase.</Text>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Create a rule</Text>

          <Text style={styles.label}>Name</Text>
          <TextInput value={name} onChangeText={setName} style={styles.input} placeholder="High edge" />

          <Text style={styles.label}>Min prob_up (0–1)</Text>
          <TextInput
            value={minProbUp}
            onChangeText={setMinProbUp}
            style={styles.input}
            placeholder="0.65"
            keyboardType="decimal-pad"
          />

          <Text style={styles.label}>Min confidence</Text>
          <View style={styles.chips}>
            {(["LOW", "MEDIUM", "HIGH"] as const).map((c) => {
              const active = c === minConf;
              return (
                <Pressable
                  key={c}
                  onPress={() => setMinConf(c)}
                  style={[styles.chip, active && styles.chipActive]}
                >
                  <Text style={[styles.chipText, active && styles.chipTextActive]}>{c}</Text>
                </Pressable>
              );
            })}
          </View>

          <Text style={styles.label}>Tickers (max 10)</Text>
          <TextInput
            value={tickersText}
            onChangeText={setTickersText}
            style={styles.input}
            placeholder="SPY,QQQ,TSLA,NVDA"
            autoCapitalize="characters"
            autoCorrect={false}
          />

          <Pressable style={styles.button} onPress={createRule}>
            <Text style={styles.buttonText}>Save Rule</Text>
          </Pressable>
        </View>

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>Your rules</Text>
          <Pressable style={styles.outlineBtn} onPress={runCheckNow} disabled={loading}>
            <Text style={styles.outlineBtnText}>{loading ? "Checking..." : "Run Check Now"}</Text>
          </Pressable>
        </View>

        {loading ? <ActivityIndicator /> : null}

        {rules.length === 0 ? (
          <Text style={styles.muted}>No rules yet. Create one above.</Text>
        ) : (
          rules.map((r) => (
            <View key={r.id} style={styles.item}>
              <View style={styles.rowBetween}>
                <Text style={styles.itemTitle}>{r.name}</Text>
                <Pressable onPress={() => toggleRule(r.id)} style={[styles.badge, r.enabled ? styles.badgeOn : styles.badgeOff]}>
                  <Text style={styles.badgeText}>{r.enabled ? "ON" : "OFF"}</Text>
                </Pressable>
              </View>
              <Text style={styles.itemMeta}>
                prob_up ≥ {r.minProbUp.toFixed(2)} • conf ≥ {r.minConfidence} • tickers: {r.tickers.join(", ")}
              </Text>
              <Pressable onPress={() => deleteRule(r.id)} style={styles.deleteBtn}>
                <Text style={styles.deleteText}>Delete</Text>
              </Pressable>
            </View>
          ))
        )}

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>History</Text>
          <Pressable style={styles.outlineBtn} onPress={clearHistory}>
            <Text style={styles.outlineBtnText}>Clear</Text>
          </Pressable>
        </View>

        {history.length === 0 ? (
          <Text style={styles.muted}>No triggered alerts yet.</Text>
        ) : (
          history.slice(0, 40).map((h, idx) => (
            <View key={`${h.time}-${h.ruleId}-${idx}`} style={styles.historyItem}>
              <Text style={styles.historyTop}>
                {h.time} • {h.ruleName}
              </Text>
              <Text style={styles.historyLine}>
                {h.ticker} • {fmtProb(h.prob_up)} • {h.confidence}
                {h.as_of_date ? ` • as_of ${h.as_of_date}` : ""}
              </Text>
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

  button: {
    backgroundColor: "#111",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 2,
  },
  buttonText: { color: "white", fontSize: 16, fontWeight: "700" },

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
  itemTitle: { fontWeight: "900", fontSize: 16 },
  itemMeta: { color: "#666", fontSize: 12 },

  badge: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  badgeOn: { backgroundColor: "#111" },
  badgeOff: { backgroundColor: "#ddd" },
  badgeText: { color: "white", fontWeight: "900", fontSize: 12 },

  deleteBtn: { alignSelf: "flex-start", marginTop: 4 },
  deleteText: { color: "#a40000", fontWeight: "900" },

  historyItem: {
    borderWidth: 1,
    borderColor: "#eee",
    borderRadius: 12,
    padding: 12,
    backgroundColor: "white",
    gap: 4,
  },
  historyTop: { fontWeight: "900", color: "#111" },
  historyLine: { color: "#666", fontSize: 12 },
});
