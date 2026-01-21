import React, { useMemo, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

const SUPPORT_EMAIL = "support@worldmarketreviewer.com"; // change later if you want

type Tier = "FREE" | "PRO_PREVIEW";

export default function ExploreTab() {
  // For now this is just UI (no payments). Later we can wire a real subscription.
  const [tier, setTier] = useState<Tier>("FREE");

  const tierLabel = useMemo(() => {
    return tier === "FREE" ? "Free (Testing)" : "Pro Preview";
  }, [tier]);

  async function openMailto() {
    const subject = encodeURIComponent("WorldMarketReviewer — Pro Waitlist");
    const body = encodeURIComponent(
      "Hi,\n\nPlease add me to the WorldMarketReviewer Pro waitlist.\n\nDevice: \nRegion: \nWhat features do you want most?: \n\nThanks!"
    );
    const url = `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`;
    try {
      const ok = await Linking.canOpenURL(url);
      if (!ok) return;
      await Linking.openURL(url);
    } catch {}
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Explore</Text>

      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.cardTitle}>Status</Text>
          <Text style={styles.badge}>{tierLabel}</Text>
        </View>

        <Text style={styles.text}>
          You’re currently running the testing build. This app is being validated over weeks of real market data.
          The goal is transparency + measurable edge — not “guaranteed wins.”
        </Text>

        <View style={styles.actions}>
          <Pressable
            onPress={() => setTier((t) => (t === "FREE" ? "PRO_PREVIEW" : "FREE"))}
            style={styles.buttonOutline}
          >
            <Text style={styles.buttonOutlineText}>
              Toggle {tier === "FREE" ? "Pro Preview" : "Free"}
            </Text>
          </Pressable>

          <Pressable onPress={openMailto} style={styles.button}>
            <Text style={styles.buttonText}>Join Pro Waitlist</Text>
          </Pressable>
        </View>

        <Text style={styles.hint}>
          This does not charge anything yet — it just helps you collect interest before launch.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>What this app does</Text>
        <Text style={styles.text}>
          WorldMarketReviewer loads historical daily prices, generates technical features, and uses walk-forward
          machine learning to estimate the probability a ticker will be higher after a fixed number of trading days.
        </Text>
        <Text style={styles.text}>
          The app emphasizes verification: you can check price moves, track accuracy over time, and review news that
          may explain volatility.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>How to use each tab</Text>
        <Text style={styles.text}>
          <Text style={styles.bold}>Home</Text> — run predictions for selected tickers{"\n\n"}
          <Text style={styles.bold}>Compare</Text> — visually verify recent price movement{"\n\n"}
          <Text style={styles.bold}>Watchlist</Text> — track up to 10 tickers together{"\n\n"}
          <Text style={styles.bold}>News</Text> — headlines for context (filter by language/country){"\n\n"}
          <Text style={styles.bold}>Accuracy</Text> — score matured predictions + report card{"\n\n"}
          <Text style={styles.bold}>Alerts</Text> — rules + manual checks + history
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Confidence explained (simple)</Text>
        <Text style={styles.text}>
          • <Text style={styles.bold}>LOW</Text> — near coin flip (close to 50/50){"\n"}
          • <Text style={styles.bold}>MEDIUM</Text> — model sees a modest edge{"\n"}
          • <Text style={styles.bold}>HIGH</Text> — model is far from 50/50 (stronger signal){"\n\n"}
          Even HIGH confidence can be wrong — markets change.
        </Text>
      </View>

      <View style={styles.warnCard}>
        <Text style={styles.cardTitle}>Important note</Text>
        <Text style={styles.warnText}>
          This app is for research and educational purposes only. Markets are uncertain and no model is always correct.
          Do not trade money you cannot afford to lose.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Pro (what people will pay for)</Text>

        <Text style={styles.text}>
          These are the features that feel premium and justify a subscription:
        </Text>

        <View style={styles.list}>
          <Text style={styles.listItem}>• More tickers + sector packs</Text>
          <Text style={styles.listItem}>• Smarter alerts (scheduled checks + thresholds + confidence bands)</Text>
          <Text style={styles.listItem}>• Longer accuracy history + per-ticker “trust score”</Text>
          <Text style={styles.listItem}>• Better signal filters (min confidence, min prob_up, volatility filters)</Text>
          <Text style={styles.listItem}>• Faster models + additional horizons (1d / 5d / 10d / 20d)</Text>
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>What’s next (recommended order)</Text>
        <View style={styles.list}>
          <Text style={styles.listItem}>1) Scheduled alerts (background checks)</Text>
          <Text style={styles.listItem}>2) Push notifications (Expo / later native)</Text>
          <Text style={styles.listItem}>3) Pro screen + locked features</Text>
          <Text style={styles.listItem}>4) Payments + account login</Text>
        </View>
        <Text style={styles.hint}>
          You’re doing it the right way: validate accuracy first, then monetize.
        </Text>
      </View>

      <Text style={styles.footer}>WorldMarketReviewer • Testing build</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: "800", marginBottom: 4 },

  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },

  card: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 14,
    gap: 10,
    backgroundColor: "white",
  },
  warnCard: {
    borderWidth: 1,
    borderColor: "#f5c77a",
    backgroundColor: "#fff4e3",
    borderRadius: 12,
    padding: 14,
    gap: 10,
  },

  cardTitle: { fontSize: 16, fontWeight: "900" },

  badge: {
    borderWidth: 1,
    borderColor: "#111",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    fontWeight: "900",
    fontSize: 12,
    color: "#111",
  },

  text: { fontSize: 14, lineHeight: 20, color: "#333" },
  warnText: { fontSize: 14, lineHeight: 20, color: "#7a4a00" },

  bold: { fontWeight: "900" },

  list: { gap: 6, marginTop: 4 },
  listItem: { fontSize: 13, lineHeight: 18, color: "#333" },

  actions: { flexDirection: "row", gap: 10, marginTop: 2 },
  button: {
    flex: 1,
    backgroundColor: "#111",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  buttonText: { color: "white", fontSize: 14, fontWeight: "800" },

  buttonOutline: {
    borderWidth: 1,
    borderColor: "#111",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    paddingHorizontal: 12,
  },
  buttonOutlineText: { fontWeight: "900", color: "#111", fontSize: 14 },

  hint: { fontSize: 12, color: "#666" },
  footer: { textAlign: "center", color: "#777", fontSize: 12, marginTop: 6 },
});
