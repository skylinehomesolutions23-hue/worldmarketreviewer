import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useLocalSearchParams } from "expo-router";

const API_BASE = "https://worldmarketreviewer.onrender.com";

const STORAGE_KEYS = {
  savedTickersCandidates: [
    "wmr:savedTickers:v3",
    "wmr:savedTickers:v2",
    "wmr:savedTickers:v1",
    "savedTickers",
  ],
  savedTickersDefaultWrite: "wmr:savedTickers:v3",

  lastNewsTicker: "wmr:lastNewsTicker:v3",
  lastNewsLimit: "wmr:lastNewsLimit:v3",
  lastNewsHoursBack: "wmr:lastNewsHoursBack:v3",
  newsLanguage: "wmr:newsLanguage:v3",
  newsCountry: "wmr:newsCountry:v3",
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

function formatSeenDate(seendate?: string) {
  if (!seendate) return "";
  const s = String(seendate);
  if (s.length >= 15 && s.includes("T") && s.endsWith("Z")) return s.replace("Z", " UTC");
  return s;
}

function normLang(s?: string) {
  const v = (s || "").trim();
  if (!v) return "";
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

function normCountry(s?: string) {
  return (s || "").trim();
}

async function findSavedTickersKey(): Promise<string> {
  for (const key of STORAGE_KEYS.savedTickersCandidates) {
    try {
      const raw = await AsyncStorage.getItem(key);
      if (raw && raw.trim().length > 0) return key;
    } catch {}
  }
  return STORAGE_KEYS.savedTickersDefaultWrite;
}

async function loadSavedTickers(): Promise<{ key: string; tickers: string[] }> {
  const key = await findSavedTickersKey();

  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) {
      return { key, tickers: ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MSFT", "AMZN"] };
    }

    let vals: any = null;
    try {
      vals = JSON.parse(raw);
    } catch {
      vals = raw;
    }

    if (Array.isArray(vals)) {
      const cleaned = uniq(vals.map(String));
      return {
        key,
        tickers: cleaned.length
          ? cleaned
          : ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MSFT", "AMZN"],
      };
    }

    if (typeof vals === "string") {
      const cleaned = uniq(
        vals
          .replace(/\s+/g, ",")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      );
      return {
        key,
        tickers: cleaned.length
          ? cleaned
          : ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MSFT", "AMZN"],
      };
    }
  } catch {}

  return { key, tickers: ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MSFT", "AMZN"] };
}

async function saveTickersToKey(key: string, tickers: string[]) {
  await AsyncStorage.setItem(key, JSON.stringify(uniq(tickers)));
}

export default function NewsTab() {
  const params = useLocalSearchParams();
  const routeTicker = typeof params.ticker === "string" ? params.ticker : "";

  const [ticker, setTicker] = useState<string>("TSLA");
  const [limit, setLimit] = useState<string>("10");
  const [hoursBack, setHoursBack] = useState<string>("72");

  const [selectedLanguage, setSelectedLanguage] = useState<string>("ALL");
  const [selectedCountry, setSelectedCountry] = useState<string>("ALL");

  const [savedTickers, setSavedTickers] = useState<string[]>([]);
  const [savedTickersKey, setSavedTickersKey] = useState<string>(
    STORAGE_KEYS.savedTickersDefaultWrite
  );
  const [editTickers, setEditTickers] = useState(false);

  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [resp, setResp] = useState<NewsResponse | null>(null);

  const lastFetchId = useRef(0);

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
    const langs = new Set<string>(["ALL"]);
    for (const it of resp.items || []) {
      const l = normLang(it.language);
      if (l) langs.add(l);
      if (looksEnglish(it.language)) langs.add("English");
    }
    return Array.from(langs).sort((a, b) => {
      if (a === "ALL") return -1;
      if (b === "ALL") return 1;
      return a.localeCompare(b);
    });
  }, [resp]);

  const availableCountries = useMemo(() => {
    if (!resp || !resp.ok) return ["ALL"];
    const cs = new Set<string>(["ALL"]);
    for (const it of resp.items || []) {
      const c = normCountry(it.sourcecountry);
      if (c) cs.add(c);
    }
    return Array.from(cs).sort((a, b) => {
      if (a === "ALL") return -1;
      if (b === "ALL") return 1;
      return a.localeCompare(b);
    });
  }, [resp]);

  const filteredItems = useMemo(() => {
    if (!resp || !resp.ok) return [];
    let items = resp.items || [];

    if (selectedCountry !== "ALL") {
      items = items.filter((it) => normCountry(it.sourcecountry) === selectedCountry);
    }

    if (selectedLanguage === "ALL") return items;
    if (selectedLanguage === "English") {
      return items.filter((it) => looksEnglish(it.language) || normLang(it.language) === "English");
    }
    return items.filter((it) => normLang(it.language) === selectedLanguage);
  }, [resp, selectedLanguage, selectedCountry]);

  async function loadPrefs() {
    try {
      const [t, lim, hb, lang, country] = await Promise.all([
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsTicker),
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsLimit),
        AsyncStorage.getItem(STORAGE_KEYS.lastNewsHoursBack),
        AsyncStorage.getItem(STORAGE_KEYS.newsLanguage),
        AsyncStorage.getItem(STORAGE_KEYS.newsCountry),
      ]);

      if (t) setTicker(toUpperTicker(t) || "TSLA");
      if (lim) setLimit(String(lim));
      if (hb) setHoursBack(String(hb));
      if (lang) setSelectedLanguage(lang);
      if (country) setSelectedCountry(country);
    } catch {}
  }

  async function savePrefs(t: string, lim: number, hb: number, lang: string, country: string) {
    try {
      await Promise.all([
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsTicker, t),
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsLimit, String(lim)),
        AsyncStorage.setItem(STORAGE_KEYS.lastNewsHoursBack, String(hb)),
        AsyncStorage.setItem(STORAGE_KEYS.newsLanguage, lang),
        AsyncStorage.setItem(STORAGE_KEYS.newsCountry, country),
      ]);
    } catch {}
  }

  async function runFetch(forcedTicker?: string, asRefresh?: boolean) {
    const fetchId = ++lastFetchId.current;

    const { lim, hb } = parsed;
    const t = toUpperTicker(forcedTicker ?? parsed.t) || "TSLA";

    if (asRefresh) setRefreshing(true);
    else setLoading(true);

    setResp(null);
    await savePrefs(t, lim, hb, selectedLanguage, selectedCountry);

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
          `Non-JSON response (HTTP ${res.status}). First 120 chars: ${text
            .slice(0, 120)
            .replace(/\s+/g, " ")}`
        );
      }

      if (fetchId !== lastFetchId.current) return;
      setResp(json as NewsResponse);
    } catch (e: any) {
      if (fetchId !== lastFetchId.current) return;
      setResp({
        ok: false,
        provider: "gdelt",
        ticker: t,
        error: e?.message || "Request failed",
        note: "Mobile fetch failed.",
      });
    } finally {
      if (fetchId === lastFetchId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }

  useEffect(() => {
    loadSavedTickers()
      .then(({ key, tickers }) => {
        setSavedTickersKey(key);
        setSavedTickers(tickers);
      })
      .catch(() => {
        setSavedTickersKey(STORAGE_KEYS.savedTickersDefaultWrite);
        setSavedTickers(["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MSFT", "AMZN"]);
      });

    loadPrefs().finally(() => {
      const tk = toUpperTicker(routeTicker);
      if (tk) setTicker(tk);

      setTimeout(() => {
        runFetch(tk || undefined);
      }, 50);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const tk = toUpperTicker(routeTicker);
    if (tk && tk !== parsed.t) {
      setTicker(tk);
      runFetch(tk);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeTicker]);

  useEffect(() => {
    if (!availableLanguages.includes(selectedLanguage)) setSelectedLanguage("ALL");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableLanguages.join("|")]);

  useEffect(() => {
    if (!availableCountries.includes(selectedCountry)) setSelectedCountry("ALL");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableCountries.join("|")]);

  async function openUrl(url?: string) {
    if (!url) return;
    try {
      const ok = await Linking.canOpenURL(url);
      if (!ok) return Alert.alert("Can't open link", url);
      await Linking.openURL(url);
    } catch {
      Alert.alert("Can't open link", url);
    }
  }

  async function setLang(lang: string) {
    setSelectedLanguage(lang);
    const { t, lim, hb } = parsed;
    await savePrefs(t, lim, hb, lang, selectedCountry);
  }

  async function setCountry(country: string) {
    setSelectedCountry(country);
    const { t, lim, hb } = parsed;
    await savePrefs(t, lim, hb, selectedLanguage, country);
  }

  async function tapTickerChip(t: string) {
    const up = toUpperTicker(t);
    if (!up) return;
    setTicker(up);
    await runFetch(up);
  }

  async function addCurrentTickerToSaved() {
    const t = parsed.t;
    const next = uniq([t, ...(savedTickers || [])]);
    try {
      await saveTickersToKey(savedTickersKey, next);
      setSavedTickers(next);
      Alert.alert("Saved", `${t} added to your tickers.`);
    } catch {
      Alert.alert("Error", "Couldn't save tickers.");
    }
  }

  async function removeSavedTicker(t: string) {
    const up = toUpperTicker(t);
    const next = (savedTickers || []).filter((x) => toUpperTicker(x) !== up);
    try {
      await saveTickersToKey(savedTickersKey, next);
      if (next.length) setSavedTickers(next);
    } catch {
      Alert.alert("Error", "Couldn't update tickers.");
    }
  }

  const isSaved = useMemo(() => {
    const t = parsed.t;
    return (savedTickers || []).some((x) => toUpperTicker(x) === t);
  }, [parsed.t, savedTickers]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>News</Text>

      <ScrollView
        contentContainerStyle={styles.results}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => runFetch(undefined, true)} />
        }
      >
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.label}>Quick tickers</Text>

            <View style={styles.rowRight}>
              <Pressable
                onPress={() => setEditTickers((v) => !v)}
                style={[styles.smallBtn, editTickers && styles.smallBtnActive]}
              >
                <Text style={[styles.smallBtnText, editTickers && styles.smallBtnTextActive]}>
                  {editTickers ? "Done" : "Edit"}
                </Text>
              </Pressable>

              <Pressable
                onPress={addCurrentTickerToSaved}
                style={[styles.smallBtn, isSaved && styles.smallBtnDisabled]}
                disabled={isSaved}
              >
                <Text style={[styles.smallBtnText, isSaved && styles.smallBtnTextDisabled]}>
                  {isSaved ? "Saved" : "+ Save"}
                </Text>
              </Pressable>
            </View>
          </View>

          <View style={styles.tickerWrap}>
            {(savedTickers.length ? savedTickers : ["SPY", "QQQ", "TSLA", "NVDA"]).map((t) => (
              <View key={t} style={styles.tickerChipRow}>
                <Pressable onPress={() => tapTickerChip(t)} style={styles.tickerChip}>
                  <Text style={styles.tickerText}>{t}</Text>
                </Pressable>

                {editTickers ? (
                  <Pressable onPress={() => removeSavedTicker(t)} style={styles.removeChip}>
                    <Text style={styles.removeChipText}>✕</Text>
                  </Pressable>
                ) : null}
              </View>
            ))}
          </View>

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
          <View style={styles.chipWrap}>
            {availableLanguages.map((lang) => {
              const active = lang === selectedLanguage;
              return (
                <Pressable
                  key={lang}
                  onPress={() => setLang(lang)}
                  style={[styles.chip, active && styles.chipActive]}
                >
                  <Text style={[styles.chipText, active && styles.chipTextActive]}>
                    {lang === "ALL" ? "All" : lang}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          <Text style={styles.label}>Country</Text>
          <View style={styles.chipWrap}>
            {availableCountries.map((c) => {
              const active = c === selectedCountry;
              return (
                <Pressable
                  key={c}
                  onPress={() => setCountry(c)}
                  style={[styles.chip, active && styles.chipActive]}
                >
                  <Text style={[styles.chipText, active && styles.chipTextActive]}>
                    {c === "ALL" ? "All" : c}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          <Pressable style={styles.button} onPress={() => runFetch()} disabled={loading}>
            <Text style={styles.buttonText}>{loading ? "Loading..." : "Fetch News"}</Text>
          </Pressable>

          <Text style={styles.hint}>Pull down to refresh. Tap a watchlist ticker to jump here.</Text>
        </View>

        <View style={styles.resultsHeader}>
          <Text style={styles.resultsTitle}>Results</Text>
          {loading ? <ActivityIndicator /> : null}
        </View>

        {!resp ? (
          <Text style={styles.muted}>No data yet.</Text>
        ) : resp.ok ? (
          filteredItems.length === 0 ? (
            <Text style={styles.muted}>
              No headlines found for {resp.ticker}
              {selectedLanguage !== "ALL" ? ` • ${selectedLanguage}` : ""}
              {selectedCountry !== "ALL" ? ` • ${selectedCountry}` : ""}
            </Text>
          ) : (
            <>
              <Text style={styles.countLine}>
                Showing {filteredItems.length} of {resp.items.length}
                {selectedLanguage !== "ALL" ? ` • ${selectedLanguage}` : ""}
                {selectedCountry !== "ALL" ? ` • ${selectedCountry}` : ""}
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
                    {it.sourcecountry ? ` • ${normCountry(it.sourcecountry)}` : ""}
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
  container: { flex: 1, padding: 16, gap: 10 },
  title: { fontSize: 28, fontWeight: "800" },

  card: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 12,
    gap: 10,
    backgroundColor: "white",
  },

  rowBetween: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
  },
  rowRight: { flexDirection: "row", alignItems: "center", gap: 8 },

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

  smallBtn: {
    borderWidth: 1,
    borderColor: "#ddd",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "white",
  },
  smallBtnActive: { borderColor: "#111", backgroundColor: "#111" },
  smallBtnDisabled: { opacity: 0.5 },
  smallBtnText: { fontWeight: "800", color: "#111", fontSize: 12 },
  smallBtnTextActive: { color: "white" },
  smallBtnTextDisabled: { color: "#111" },

  tickerWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  tickerChipRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  tickerChip: {
    borderWidth: 1,
    borderColor: "#ddd",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "white",
  },
  tickerText: { fontWeight: "800", color: "#111", fontSize: 12 },
  removeChip: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#111",
  },
  removeChipText: { color: "white", fontWeight: "900", fontSize: 12 },

  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: "#ddd",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "white",
  },
  chipActive: { borderColor: "#111", backgroundColor: "#111" },
  chipText: { fontWeight: "800", color: "#111", fontSize: 12 },
  chipTextActive: { color: "white" },

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
    marginTop: 10,
    marginBottom: 6,
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
