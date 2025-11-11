import { useEffect, useState } from "react";
import { fetchCandles, fetchRecommendations, RecommendationCard } from "../api/client";
import { useAppStore } from "../store/useAppStore";

interface SparkData {
  symbol: string;
  points: number[];
}

export default function RecoCards({ top = 5 }: { top?: number }) {
  const [cards, setCards] = useState<RecommendationCard[]>([]);
  const [sparks, setSparks] = useState<Record<string, SparkData>>({});
  const { setSelection, setActiveTab } = useAppStore();

  useEffect(() => {
    let active = true;
    fetchRecommendations(top)
      .then((items) => {
        if (active) {
          setCards(items);
          items.forEach(async (item) => {
            try {
              const candles = await fetchCandles(item.symbol, 30);
              if (!active) return;
              setSparks((prev) => ({
                ...prev,
                [item.symbol]: {
                  symbol: item.symbol,
                  points: candles.map((c) => c.close),
                },
              }));
            } catch (error) {
              console.error("spark", error);
            }
          });
        }
      })
      .catch((error) => console.error("reco", error));
    return () => {
      active = false;
    };
  }, [top]);

  const goTrade = (symbol: string, name: string) => {
    setSelection({ symbol, name });
    setActiveTab("trade");
  };

  return (
    <div style={{ display: "grid", gap: "16px", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
      {cards.map((card) => {
        const spark = sparks[card.symbol];
        const min = spark ? Math.min(...spark.points) : 0;
        const max = spark ? Math.max(...spark.points) : 0;
        const path = spark
          ? spark.points
              .map((value, idx) => {
                const x = (idx / Math.max(spark.points.length - 1, 1)) * 180;
                const y = max === min ? 40 : 40 - ((value - min) / (max - min)) * 40;
                return `${idx === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
              })
              .join(" ")
          : "";
        return (
          <div
            key={card.symbol}
            style={{
              padding: "16px",
              borderRadius: "16px",
              background: "rgba(15,23,42,0.6)",
              boxShadow: "0 12px 24px rgba(15,23,42,0.4)",
              display: "grid",
              gap: "12px",
            }}
          >
            <header>
              <h3 style={{ margin: 0 }}>{card.name}</h3>
              <span style={{ opacity: 0.7 }}>{card.symbol}</span>
            </header>
            <div>
              <strong>Score</strong>
              <div style={{ fontSize: "1.6rem" }}>{card.score.toFixed(2)}</div>
            </div>
            {spark && (
              <svg width="180" height="48" viewBox="0 0 180 40">
                <path d={path} stroke="#38bdf8" fill="none" strokeWidth={2} />
              </svg>
            )}
            <ul style={{ margin: 0, paddingLeft: "18px" }}>
              {card.reasons.slice(0, 3).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <button type="button" onClick={() => goTrade(card.symbol, card.name)}>
              거래로 이동
            </button>
          </div>
        );
      })}
    </div>
  );
}
