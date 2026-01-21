import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

export default function ExploreTab() {
  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Explore</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>What this app does</Text>
        <Text style={styles.text}>
          WorldMarketReviewer analyzes historical market data and uses
          walk-forward machine learning models to estimate the probability that
          a stock or ETF will be higher after a fixed number of trading days.
        </Text>
        <Text style={styles.text}>
          This is not a prediction of the future — it is a probability-based
          signal designed to help compare opportunities objectively.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>How predictions work</Text>
        <Text style={styles.text}>
          • Daily prices are converted into technical features{"\n"}
          • Models are trained using past data only{"\n"}
          • Each ticker gets a probability of going UP or DOWN{"\n"}
          • Confidence increases the farther the probability is from 50%
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Understanding confidence</Text>
        <Text style={styles.text}>
          LOW confidence means the model sees a near coin-flip outcome.{"\n\n"}
          MEDIUM confidence means a modest edge.{"\n\n"}
          HIGH confidence means the model historically performed better in
          similar conditions — but losses are still possible.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>How to use each tab</Text>
        <Text style={styles.text}>
          Home — Run predictions for selected tickers{"\n\n"}
          Compare — Verify recent price moves visually{"\n\n"}
          Watchlist — Track up to 10 tickers together{"\n\n"}
          News — See recent headlines that may affect price{"\n\n"}
          Accuracy — Measure how past predictions performed
        </Text>
      </View>

      <View style={styles.cardWarn}>
        <Text style={styles.cardTitle}>Important note</Text>
        <Text style={styles.warnText}>
          This app is for research and educational purposes only. Markets are
          uncertain and no model is always correct. Do not trade money you
          cannot afford to lose.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Coming soon (Pro)</Text>
        <Text style={styles.text}>
          • More tracked tickers{"\n"}
          • Price & confidence alerts{"\n"}
          • Faster and higher-frequency models{"\n"}
          • Longer accuracy history{"\n"}
          • Advanced filters and signals
        </Text>
      </View>

      <Text style={styles.footer}>
        You are currently using the public testing version.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    gap: 12,
    paddingBottom: 40,
  },
  title: {
    fontSize: 28,
    fontWeight: "800",
    marginBottom: 4,
  },
  card: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 14,
    gap: 8,
    backgroundColor: "white",
  },
  cardWarn: {
    borderWidth: 1,
    borderColor: "#f5c77a",
    backgroundColor: "#fff4e3",
    borderRadius: 12,
    padding: 14,
    gap: 8,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "900",
  },
  text: {
    fontSize: 14,
    lineHeight: 20,
    color: "#333",
  },
  warnText: {
    fontSize: 14,
    lineHeight: 20,
    color: "#7a4a00",
  },
  footer: {
    textAlign: "center",
    color: "#666",
    fontSize: 12,
    marginTop: 12,
  },
});
