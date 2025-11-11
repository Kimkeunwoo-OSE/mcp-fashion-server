import { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";
import { CandlePoint, fetchCandles } from "../api/client";
import TradeForm from "./TradeForm";

interface DetailPanelProps {
  holding?: {
    symbol: string;
    name: string;
    qty: number;
    avg_price: number;
    last_price: number;
    exit_signal?: string | null;
  };
  takeProfitPct: number;
  quickPct: number[];
  tick: number;
  confirmPhrase: string;
}

export default function DetailPanel({
  holding,
  takeProfitPct,
  quickPct,
  tick,
  confirmPhrase,
}: DetailPanelProps) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [candles, setCandles] = useState<CandlePoint[]>([]);

  useEffect(() => {
    if (!holding) {
      setCandles([]);
      return;
    }
    let active = true;
    fetchCandles(holding.symbol, 120)
      .then((series) => {
        if (active) setCandles(series);
      })
      .catch((error) => console.error("candles", error));
    return () => {
      active = false;
    };
  }, [holding?.symbol]);

  useEffect(() => {
    if (!chartRef.current || !candles.length) {
      return;
    }
    chartRef.current.innerHTML = "";
    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth || 600,
      height: 320,
      layout: { background: { color: "#0f172a" }, textColor: "#e2e8f0" },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const candlestick = chart.addCandlestickSeries();
    const volume = chart.addHistogramSeries({
      priceScaleId: "",
      color: "rgba(14, 165, 233, 0.4)",
      priceFormat: { type: "volume" },
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    const data = candles.map((point) => ({
      time: point.timestamp.substring(0, 10),
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
    }));
    const volData = candles.map((point) => ({
      time: point.timestamp.substring(0, 10),
      value: point.volume,
      color: point.close >= point.open ? "rgba(34,197,94,0.6)" : "rgba(248,113,113,0.6)",
    }));
    candlestick.setData(data);
    volume.setData(volData);
    const handleResize = () => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [candles]);

  if (!holding) {
    return <p>보유 종목을 선택하면 상세 정보가 표시됩니다.</p>;
  }

  const recommended = holding.avg_price * (1 + takeProfitPct);

  return (
    <div style={{ marginTop: "24px", display: "grid", gap: "24px" }}>
      <section style={{ display: "grid", gap: "16px" }}>
        <h2 style={{ margin: 0 }}>
          {holding.name} ({holding.symbol})
        </h2>
        <div style={{ display: "grid", gap: "12px", gridTemplateColumns: "1fr 1fr" }}>
          <div>
            <div ref={chartRef} style={{ width: "100%", height: "320px" }} />
            <div style={{ display: "flex", gap: "16px", marginTop: "12px" }}>
              <div>
                <strong>평단</strong>
                <div>{holding.avg_price.toLocaleString()}원</div>
              </div>
              <div>
                <strong>현재가</strong>
                <div>{holding.last_price.toLocaleString()}원</div>
              </div>
              <div>
                <strong>권고 매도가</strong>
                <div>{recommended.toFixed(2)}원</div>
              </div>
              {holding.exit_signal && (
                <div>
                  <strong>Exit</strong>
                  <div>{holding.exit_signal}</div>
                </div>
              )}
            </div>
          </div>
          <div style={{ padding: "16px", borderRadius: "12px", background: "rgba(15,23,42,0.6)" }}>
            <TradeForm
              symbol={holding.symbol}
              name={holding.name}
              side="SELL"
              lastPrice={holding.last_price}
              maxQty={holding.qty}
              quickPct={quickPct}
              tick={tick}
              confirmPhrase={confirmPhrase}
              disabled={holding.qty <= 0}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
