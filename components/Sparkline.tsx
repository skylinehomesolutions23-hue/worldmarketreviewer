import React, { useMemo } from "react";
import { View } from "react-native";
import Svg, { Path } from "react-native-svg";

type SparklineProps = {
  values: number[];
  width?: number;
  height?: number;
  stroke?: string;
  strokeWidth?: number;
};

function isFiniteNumber(x: any): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

export default function Sparkline({
  values,
  width = 120,
  height = 36,
  stroke = "#22c55e",
  strokeWidth = 2,
}: SparklineProps) {
  const d = useMemo(() => {
    const cleaned = (values ?? []).filter(isFiniteNumber);
    if (cleaned.length < 2) return "";

    let min = cleaned[0];
    let max = cleaned[0];
    for (const v of cleaned) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
    const range = max - min || 1;

    const stepX = width / (cleaned.length - 1);

    let path = "";
    for (let i = 0; i < cleaned.length; i++) {
      const x = i * stepX;
      const y = height - ((cleaned[i] - min) / range) * height;
      path += (i === 0 ? "M " : " L ") + `${x.toFixed(2)} ${y.toFixed(2)}`;
    }
    return path;
  }, [values, width, height]);

  if (!d) return <View style={{ width, height }} />;

  return (
    <View style={{ width, height }}>
      <Svg width={width} height={height}>
        <Path d={d} fill="none" stroke={stroke} strokeWidth={strokeWidth} />
      </Svg>
    </View>
  );
}
