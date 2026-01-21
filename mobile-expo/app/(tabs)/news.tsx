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
  lastNewsTicker: "wmr:lastNewsTicker:v2",
  lastNewsLimit: "wmr:lastNewsLimit:v2",
  lastNewsHoursBack: "wmr:lastNewsHoursBack:v2",
  newsLanguage: "wmr:newsLanguage:v2", // "ALL" or "English" etc
};

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

function normLang(s?: string) {
  const v = (s || "").trim();
  if (!v) return "";
  // Keep the original casing as returned (e.g., "English", "Chinese")
  // but normalize some common variants.
  const low = v.toLowerCase();
  if (low === "en") return "English";
  if (low === "zh" || low === "cn") return "Chinese";
  if (low === "hi") return "Hindi";
  if (low === "he") return "Hebrew";
  if (low === "es") return "Spanish";
  return v;
}

function looksEnglish(lang?: string) {
  const l = (lang || "").trim().toLowerCase();
  return l === "english" || l === "en" || l.startsWith("en ");
}

export default function NewsTab() {
  const [ticker, setTicker] = useState<string>("TSLA");
  const [limit, setLimit] = useState<string>("10");
  const [hoursBack, setHoursBack] = useState<string>("72");
  const [selectedLanguage, setSelectedLanguage] = useState<string>("ALL"); // "ALL" or e.g. "English"

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

  const availableLanguages = useMemo(() => {
    if (!resp || !resp.ok) return ["ALL"];
    const langs = new Set<string>();
    langs.add("ALL");

    for (const it of resp.items || []) {
      const l = normLang(it.language);
      if (l) langs.add(l);
      // If an item is English but label is weird/missing, still offer English when any English-looking appears
      if (looksEnglish(it.language)) langs.add("English");
    }

    return Array.from(langs).sort((a, b) => {
      if (a === "ALL") return -1;
      if (b === "ALL") return 1;
      return a.localeCompare(b);
    });
  }, [resp]);

  const filteredItems = useMemo(() => {
    if (!resp || !resp.ok) return [];
    const items = resp.items || [];

    if (selectedLanguage === "ALL") return items;

    // Special case: English filtering more forgiving
    if (selectedLanguage === "English") {
      return items.filter((it) => looksEnglish(it.language) || normLang(it.language) === "English");
    }

    return items.filter((it) => normLang(it.language) === selectedLanguage);
  }, [resp, selectedLanguage]);

  async function loadSaved() {
    try {
      const [t, lim, hb, lang] = await Promise.all([
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsTicker),
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsLimit),
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsHoursBack),
        AsyncStorage.getItem(STORAGE_KEYS.newsLanguage),
      ]);

      if (t) setTicker(toUpperTicker(t) || "TSLA");
      if (lim) setLimit(String(lim));
      if (hb) setHoursBack(String(hb));
      if (lang) setSelectedLanguage(lang);
    } catch {
      // ignore
    }
  }

  async function savePrefs(t: string, lim: number, hb: number, lang: string) {
    try {
      await Promise.all([
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsTicker, t),
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsLimit, String(lim)),
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsHoursBack, String(hb)),
        AsyncStorage.setItem(STORAGE_KEYS.newsLanguage, lang),
      ]);
    } catch {
      // ignore
    }
  }

  async function runFetch() {
    const { t, lim, hb } = parsed;

    setLoading(true);
    setResp(null);

    await savePrefs(t, lim, hb, selectedLanguage);

    const url = `${API_BASE}/api/news?ticker=${encodeURIComponent(
      t
    )}&limit=${encodeURIComponent(String(lim))}&hours_back=${encodeURIComponent(String(hb))}`;

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
      setTimeout(() => {
        runFetch();
      }, 50);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // If saved language no longer exists for this ticker/time window, fall back to ALL.
  useEffect(() => {
    if (!availableLanguages.includes(selectedLanguage)) {
      setSelectedLanguage("ALL");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableLanguages.join("|")]);

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

  async function setLang(lang: string) {
    setSelectedLanguage(lang);
    const { t, lim, hb } = parsed;
    await savePrefs(t, lim, hb, lang);
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
        <View style={styles.langWrap}>
          {availableLanguages.map((lang) => {
            const active = lang === selectedLanguage;
            return (
              <Pressable
                key={lang}
                onPress={() => setLang(lang)}
                style={[styles.langChip, active && styles.langChipActive]}
              >
                <Text style={[styles.langText, active && styles.langTextActive]}>
                  {lang === "ALL" ? "All" : lang}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Pressable style={styles.button} onPress={runFetch} disabled={loading}>
          <Text style={styles.buttonText}>{loading ? "Loading..." : "Fetch News"}</Text>
        </Pressable>

        <Text style={styles.hint}>
          This filters headlines on your phone. Backend is unchanged.
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
              No headlines found for {resp.ticker}
              {selectedLanguage !== "ALL" ? ` (${selectedLanguage})` : ""}.
            </Text>
          ) : (
            <>
              <Text style={styles.countLine}>
                Showing {filteredItems.length} of {resp.items.length}
                {selectedLanguage !== "ALL" ? ` • ${selectedLanguage}` : ""}
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
                    {it.language ? ` • ${normLang(it.language)}` : ""}
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

  langWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  langChip: {
    borderWidth: 1,
    borderColor: "#ddd",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "white",
  },
  langChipActive: {
    borderColor: "#111",
    backgroundColor: "#111",
  },
  langText: { fontWeight: "800", color: "#111", fontSize: 12 },
  langTextActive: { color: "white" },

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
