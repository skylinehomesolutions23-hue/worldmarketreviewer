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
  lastNewsTicker: "wmr:lastNewsTicker:v1",
  lastNewsLimit: "wmr:lastNewsLimit:v1",
  lastNewsHoursBack: "wmr:lastNewsHoursBack:v1",
  newsLangMode: "wmr:newsLangMode:v1", // "all" | "en"
};

type LangMode = "all" | "en";

type NewsItem = {
  title: string;
  url: string;
  domain?: string;
  seendate?: string;
  socialimage?: string;
  sourcecountry?: string;
  language?: string;
};

type NewsResponse =
  | {
      ok: true;
      provider: string;
      ticker: string;
      limit: number;
      hours_back: number;
      timespan?: string;
      items: NewsItem[];
      time_utc?: string;
    }
  | {
      ok: false;
      provider: string;
      ticker: string;
      error: string;
      note?: string;
      time_utc?: string;
      content_type?: string;
      url?: string;
      body_preview?: string;
    };

function toUpperTicker(s: string) {
  return (s || "").toUpperCase().replace(/[^A-Z0-9.\-]/g, "").trim();
}

function formatSeenDate(seendate?: string) {
  if (!seendate) return "";
  const s = String(seendate);
  if (s.length >= 15 && s.includes("T") && s.endsWith("Z")) {
    return s.replace("Z", " UTC");
  }
  return s;
}

function isEnglishItem(it: NewsItem): boolean {
  const lang = (it.language || "").trim().toLowerCase();
  // GDELT tends to return "English" exactly, but we accept a few variants.
  return lang === "english" || lang === "en" || lang.startsWith("en ");
}

export default function NewsTab() {
  const [ticker, setTicker] = useState<string>("TSLA");
  const [limit, setLimit] = useState<string>("10");
  const [hoursBack, setHoursBack] = useState<string>("72");
  const [langMode, setLangMode] = useState<LangMode>("all");

  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<NewsResponse | null>(null);

  const parsed = useMemo(() => {
    const t = toUpperTicker(ticker) || "TSLA";

    let lim = parseInt(limit, 10);
    if (!Number.isFinite(lim)) lim = 10;
    lim = Math.max(1, Math.min(50, lim));

    let hb = parseInt(hoursBack, 10);
    if (!Number.isFinite(hb)) hb = 72;
    hb = Math.max(6, Math.min(24 * 30, hb));

    return { t, lim, hb };
  }, [ticker, limit, hoursBack]);

  const filteredItems = useMemo(() => {
    if (!resp || !resp.ok) return [];
    if (langMode === "en") return (resp.items || []).filter(isEnglishItem);
    return resp.items || [];
  }, [resp, langMode]);

  async function loadSaved() {
    try {
      const [t, lim, hb, lm] = await Promise.all([
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsTicker),
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsLimit),
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsHoursBack),
        AsyncStorage.getItem(STORAGE_KEYS.newsLangMode),
      ]);

      if (t) setTicker(toUpperTicker(t) || "TSLA");
      if (lim) setLimit(String(lim));
      if (hb) setHoursBack(String(hb));

      if (lm === "all" || lm === "en") setLangMode(lm);
    } catch {
      // ignore
    }
  }

  async function savePrefs(t: string, lim: number, hb: number, lm: LangMode) {
    try {
      await Promise.all([
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsTicker, t),
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsLimit, String(lim)),
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsHoursBack, String(hb)),
        AsyncStorage.setItem(STORAGE_KEYS.newsLangMode, lm),
      ]);
    } catch {
      // ignore
    }
  }

  async function runFetch(nextLangMode?: LangMode) {
    const { t, lim, hb } = parsed;
    const lm = nextLangMode ?? langMode;

    setLoading(true);
    setResp(null);

    await savePrefs(t, lim, hb, lm);

    const url = `${API_BASE}/api/news?ticker=${encodeURIComponent(
      t
    )}&limit=${encodeURIComponent(String(lim))}&hours_back=${encodeURIComponent(
      String(hb)
    )}`;

    try {
      const res = await fetch(url, { method: "GET" });
      const text = await res.text();

      let json: any = null;
      try {
        json = JSON.parse(text);
      } catch {
        throw new Error(
          `Non-JSON response from server (HTTP ${res.status}). First 120 chars: ${text
            .slice(0, 120)
            .replace(/\s+/g, " ")}`
        );
      }

      setResp(json as NewsResponse);
    } catch (e: any) {
      setResp({
        ok: false,
        provider: "gdelt",
        ticker: parsed.t,
        error: e?.message || "Request failed",
        note: "Mobile fetch failed.",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSaved().finally(() => {
      // auto-fetch after loading saved prefs
      setTimeout(() => {
        runFetch();
      }, 50);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function openUrl(url?: string) {
    if (!url) return;
    try {
      const ok = await Linking.canOpenURL(url);
      if (!ok) {
        Alert.alert("Can't open link", url);
        return;
      }
      await Linking.openURL(url);
    } catch {
      Alert.alert("Can't open link", url);
    }
  }

  function setLang(lm: LangMode) {
    setLangMode(lm);
    // persist immediately (no need to refetch; filter is client-side)
    const { t, lim, hb } = parsed;
    savePrefs(t, lim, hb, lm);
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>News</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Ticker</Text>
        <TextInput
          value={ticker}
          onChangeText={(v) => setTicker(toUpperTicker(v))}
          placeholder="TSLA"
          autoCapitalize="characters"
          autoCorrect={false}
          style={styles.input}
        />

        <View style={styles.row}>
          <View style={styles.rowItem}>
            <Text style={styles.label}>Limit</Text>
            <TextInput
              value={limit}
              onChangeText={setLimit}
              placeholder="10"
              keyboardType="number-pad"
              style={styles.input}
            />
          </View>

          <View style={styles.rowItem}>
            <Text style={styles.label}>Hours back</Text>
            <TextInput
              value={hoursBack}
              onChangeText={setHoursBack}
              placeholder="72"
              keyboardType="number-pad"
              style={styles.input}
            />
          </View>
        </View>

        <Text style={styles.label}>Language</Text>
        <View style={styles.toggleRow}>
          <Pressable
            onPress={() => setLang("all")}
            style={[styles.toggleBtn, langMode === "all" && styles.toggleBtnActive]}
          >
            <Text style={[styles.toggleText, langMode === "all" && styles.toggleTextActive]}>
              All
            </Text>
          </Pressable>

          <Pressable
            onPress={() => setLang("en")}
            style={[styles.toggleBtn, langMode === "en" && styles.toggleBtnActive]}
          >
            <Text style={[styles.toggleText, langMode === "en" && styles.toggleTextActive]}>
              English only
            </Text>
          </Pressable>
        </View>

        <Pressable style={styles.button} onPress={() => runFetch()} disabled={loading}>
          <Text style={styles.buttonText}>{loading ? "Loading..." : "Fetch News"}</Text>
        </Pressable>

        <Text style={styles.hint}>
          Uses your backend (/api/news). Language filtering is applied on your phone (fast).
        </Text>
      </View>

      <View style={styles.resultsHeader}>
        <Text style={styles.resultsTitle}>Results</Text>
        {loading ? <ActivityIndicator /> : null}
      </View>

      <ScrollView contentContainerStyle={styles.results}>
        {!resp ? (
          <Text style={styles.muted}>No data yet.</Text>
        ) : resp.ok ? (
          filteredItems.length === 0 ? (
            <Text style={styles.muted}>
              No {langMode === "en" ? "English" : ""} articles found for {resp.ticker}.
            </Text>
          ) : (
            <>
              <Text style={styles.countLine}>
                Showing {filteredItems.length} of {resp.items.length} items
                {langMode === "en" ? " (English only)" : ""}
              </Text>

              {filteredItems.map((it, idx) => (
                <Pressable
                  key={`${it.url}-${idx}`}
                  style={styles.item}
                  onPress={() => openUrl(it.url)}
                >
                  <Text style={styles.itemTitle} numberOfLines={3}>
                    {it.title}
                  </Text>
                  <Text style={styles.itemMeta}>
                    {(it.domain || "unknown").toString()}
                    {it.seendate ? ` • ${formatSeenDate(it.seendate)}` : ""}
                    {it.language ? ` • ${it.language}` : ""}
                  </Text>
                  <Text style={styles.itemUrl} numberOfLines={1}>
                    {it.url}
                  </Text>
                </Pressable>
              ))}
            </>
          )
        ) : (
          <View style={styles.errorBox}>
            <Text style={styles.errorTitle}>Error: {resp.error || "Unknown error"}</Text>
            {resp.note ? <Text style={styles.errorText}>{resp.note}</Text> : null}
            {resp.content_type ? (
              <Text style={styles.errorText}>content-type: {resp.content_type}</Text>
            ) : null}
            {resp.url ? <Text style={styles.errorText}>url: {resp.url}</Text> : null}
            {resp.body_preview ? (
              <Text style={styles.errorText} numberOfLines={6}>
                {resp.body_preview}
              </Text>
            ) : null}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  title: { fontSize: 28, fontWeight: "800" },

  card: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 12,
    gap: 10,
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

  toggleRow: { flexDirection: "row", gap: 10 },
  toggleBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: "white",
  },
  toggleBtnActive: {
    borderColor: "#111",
    backgroundColor: "#111",
  },
  toggleText: { fontWeight: "800", color: "#111" },
  toggleTextActive: { color: "white" },

  button: {
    marginTop: 4,
    backgroundColor: "#111",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  buttonText: { color: "white", fontSize: 16, fontWeight: "700" },

  hint: { fontSize: 12, color: "#666", marginTop: 2 },

  resultsHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  resultsTitle: { fontSize: 18, fontWeight: "800" },

  results: { paddingBottom: 40, gap: 10 },

  countLine: { color: "#666", fontSize: 12 },

  item: {
    borderWidth: 1,
    borderColor: "#eee",
    borderRadius: 12,
    padding: 12,
    gap: 6,
    backgroundColor: "white",
  },
  itemTitle: { fontSize: 16, fontWeight: "800" },
  itemMeta: { fontSize: 12, color: "#666" },
  itemUrl: { fontSize: 12, color: "#444" },

  muted: { color: "#666" },

  errorBox: {
    borderWidth: 1,
    borderColor: "#ffcccc",
    backgroundColor: "#fff5f5",
    borderRadius: 12,
    padding: 12,
    gap: 8,
  },
  errorTitle: { fontWeight: "800", color: "#a40000" },
  errorText: { color: "#7a1d1d", fontSize: 12 },
});
