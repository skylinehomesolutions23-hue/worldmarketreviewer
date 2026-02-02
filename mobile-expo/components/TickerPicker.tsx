// mobile-expo/components/TickerPicker.tsx
import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";

type Props = {
  title?: string;
  catalog: string[];
  selected: string[];
  onChangeSelected: (next: string[]) => void;
  maxSelected?: number;
};

function norm(t: string) {
  return (t || "").trim().toUpperCase();
}

function uniqUpper(list: string[]) {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const t0 of list || []) {
    const t = norm(t0);
    if (!t || seen.has(t)) continue;
    seen.add(t);
    out.push(t);
  }
  return out;
}

export default function TickerPicker({
  title = "Choose tickers",
  catalog,
  selected,
  onChangeSelected,
  maxSelected = 40,
}: Props) {
  const [q, setQ] = useState("");

  const selectedNorm = useMemo(() => uniqUpper(selected), [selected]);
  const selectedSet = useMemo(() => new Set(selectedNorm), [selectedNorm]);

  const allCatalog = useMemo(() => uniqUpper(catalog), [catalog]);

  const filtered = useMemo(() => {
    const query = norm(q);
    const base = query ? allCatalog.filter((t) => t.includes(query)) : allCatalog;

    // Put selected items first (nice UX)
    const selectedFirst: string[] = [];
    const rest: string[] = [];
    for (const t of base) {
      if (selectedSet.has(t)) selectedFirst.push(t);
      else rest.push(t);
    }

    return [...selectedFirst, ...rest];
  }, [q, allCatalog, selectedSet]);

  function toggle(ticker: string) {
    const t = norm(ticker);
    if (!t) return;

    const next = new Set(selectedSet);

    if (next.has(t)) next.delete(t);
    else {
      if (next.size >= maxSelected) return;
      next.add(t);
    }

    // stable sort
    const nextArr = Array.from(next).sort();
    onChangeSelected(nextArr);
  }

  return (
    <View style={{ padding: 12, gap: 10 }}>
      <Text style={{ fontSize: 18, fontWeight: "700" }}>{title}</Text>

      <TextInput
        value={q}
        onChangeText={setQ}
        placeholder="Search tickers (ex: SPY, NVDA, QQQ)"
        autoCapitalize="characters"
        autoCorrect={false}
        style={{
          borderWidth: 1,
          borderColor: "#ddd",
          borderRadius: 10,
          paddingHorizontal: 12,
          paddingVertical: 10,
        }}
      />

      <Text style={{ color: "#666" }}>
        Selected: {selectedNorm.length}/{maxSelected} (tap ✅ to remove)
      </Text>

      <ScrollView style={{ maxHeight: 420, borderWidth: 1, borderColor: "#eee", borderRadius: 12 }}>
        {filtered.map((t) => {
          const isOn = selectedSet.has(t);
          return (
            <Pressable
              key={t}
              onPress={() => toggle(t)}
              style={{
                paddingHorizontal: 12,
                paddingVertical: 12,
                borderBottomWidth: 1,
                borderBottomColor: "#f0f0f0",
                flexDirection: "row",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <Text style={{ fontSize: 16, fontWeight: "600" }}>{t}</Text>
              <Text style={{ fontSize: 16 }}>{isOn ? "✅" : "⬜"}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
