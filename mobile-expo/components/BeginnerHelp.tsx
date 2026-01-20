// mobile-expo/components/BeginnerHelp.tsx
import React from "react";
import { StyleSheet, Text, View } from "react-native";

export default function BeginnerHelp({ horizonDays }: { horizonDays: number }) {
  return (
    <View style={styles.box}>
      <Text style={styles.title}>Beginner quick guide</Text>

      <Text style={styles.text}>
        • <Text style={styles.bold}>prob_up</Text> is the model’s estimated chance the price will be higher after{" "}
        <Text style={styles.bold}>{horizonDays}</Text> trading days.
      </Text>

      <Text style={styles.text}>
        • <Text style={styles.bold}>UP/DOWN</Text> is just whether prob_up is above or below 50%.
      </Text>

      <Text style={styles.text}>
        • <Text style={styles.bold}>Confidence</Text> = how far prob_up is from 50/50 (not a guarantee).
      </Text>

      <Text style={styles.text}>
        • Use <Text style={styles.bold}>Verify</Text> to compare recent price movement, and{" "}
        <Text style={styles.bold}>Report card</Text> to see scored accuracy over time.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    marginTop: 12,
    backgroundColor: "#0B1220",
    borderColor: "#223256",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
  },
  title: { color: "#FFFFFF", fontWeight: "900", marginBottom: 8 },
  text: { color: "#A7B0C0", lineHeight: 18, marginTop: 4 },
  bold: { color: "#E5E7EB", fontWeight: "900" },
});
