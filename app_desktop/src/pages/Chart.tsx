import { useEffect, useRef, useState } from "react";
import { createChart, ISeriesApi } from "lightweight-charts";
import { CandlePoint, fetchCandles, fetchName, fetchSettings } from "../api/client";
import { useAppStore } from "../store/useAppStore";

export default function ChartPage() {
  const { selection, setSelection } = useAppStore();
  const [symbol, setSymbol] = useState(selection?.symbol ?? "005930.KS");
  const [name, setName] = useState(selection?.name ?? "");
  const [candles, setCandles] = useState<CandlePoint[]>([]);
  const [periods, setPeriods] = useState([60, 120, 250]);
  const [period, setPeriod] = useState(120);
  const [showSMA20, setShowSMA20] = useState(true);
  const [showSMA60, setShowSMA60] = useState(true);
  const [showRSI, setShowRSI] = useState(false);
  const chartRef = useRef<HTMLDivElement | null>(null);
  const rsiRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchSettings().then((cfg) => {
      setPeriods(cfg.chart.periods);
      setPeriod(cfg.chart.periods[1] ?? 120);
    });
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([fetchName(symbol), fetchCandles(symbol, period)])
      .then(([resolvedName, series]) => {
        if (!active) return;
        setName(resolvedName);
        setSelection({ symbol, name: resolvedName });
        setCandles(series);
      })
      .catch((error) => console.error("chart", error));
    return () => {
      active = false;
    };
  }, [symbol, period, setSelection]);

  useEffect(() => {
    if (!chartRef.current || !candles.length) return;
    chartRef.current.innerHTML = "";
    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth || 800,
      height: 360,
      layout: { background: { color: "#0f172a" }, textColor: "#e2e8f0" },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const candleSeries = chart.addCandlestickSeries();
    const mainData = candles.map((point) => ({
      time: point.timestamp.substring(0, 10),
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
    }));
    candleSeries.setData(mainData);

    const smaSeries: ISeriesApi<"Line">[] = [];
    const computeSMA = (len: number) => {
      const result: { time: string; value: number }[] = [];
      for (let i = 0; i < candles.length; i += 1) {
        if (i + 1 < len) continue;
        const slice = candles.slice(i + 1 - len, i + 1);
        const avg = slice.reduce((sum, c) => sum + c.close, 0) / len;
        result.push({ time: candles[i].timestamp.substring(0, 10), value: avg });
      }
      return result;
    };

    if (showSMA20) {
      const series = chart.addLineSeries({ color: "#38bdf8", lineWidth: 2 });
      series.setData(computeSMA(20));
      smaSeries.push(series);
    }
    if (showSMA60) {
      const series = chart.addLineSeries({ color: "#f97316", lineWidth: 2 });
      series.setData(computeSMA(60));
      smaSeries.push(series);
    }

    const resize = () => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", resize);

    let rsiChart: ReturnType<typeof createChart> | null = null;
    if (rsiRef.current) {
      rsiRef.current.innerHTML = "";
    }
    if (showRSI && rsiRef.current) {
      rsiChart = createChart(rsiRef.current, {
        width: rsiRef.current.clientWidth || 800,
        height: 160,
        layout: { background: { color: "#111827" }, textColor: "#e2e8f0" },
        leftPriceScale: { visible: false },
        rightPriceScale: { visible: true },
        timeScale: { visible: false },
      });
      const rsiSeries = rsiChart.addLineSeries({ color: "#facc15" });
      const rsiValues: { time: string; value: number }[] = [];
      const periodRsi = 14;
      let gains = 0;
      let losses = 0;
      for (let i = 1; i < candles.length; i += 1) {
        const change = candles[i].close - candles[i - 1].close;
        if (i <= periodRsi) {
          if (change >= 0) gains += change;
          else losses -= change;
          continue;
        }
        if (change >= 0) {
          gains = (gains * (periodRsi - 1) + change) / periodRsi;
          losses = (losses * (periodRsi - 1)) / periodRsi;
        } else {
          gains = (gains * (periodRsi - 1)) / periodRsi;
          losses = (losses * (periodRsi - 1) - change) / periodRsi;
        }
        const rs = losses === 0 ? 100 : gains / losses;
        const rsi = 100 - 100 / (1 + rs);
        rsiValues.push({ time: candles[i].timestamp.substring(0, 10), value: rsi });
      }
      rsiSeries.setData(rsiValues);
    }

    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      smaSeries.forEach((series) => series.remove());
      if (rsiChart) rsiChart.remove();
    };
  }, [candles, showSMA20, showSMA60, showRSI]);

  return (
    <div style={{ display: "grid", gap: "16px" }}>
      <section style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
        <label>
          코드
          <input
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.toUpperCase())}
          />
        </label>
        <label>
          기간
          <select value={period} onChange={(event) => setPeriod(Number(event.target.value))}>
            {periods.map((p) => (
              <option key={p} value={p}>
                최근 {p}일
              </option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={showSMA20} onChange={(event) => setShowSMA20(event.target.checked)} /> SMA20
        </label>
        <label>
          <input type="checkbox" checked={showSMA60} onChange={(event) => setShowSMA60(event.target.checked)} /> SMA60
        </label>
        <label>
          <input type="checkbox" checked={showRSI} onChange={(event) => setShowRSI(event.target.checked)} /> RSI14
        </label>
      </section>
      <h2>
        {name} ({symbol})
      </h2>
      <div ref={chartRef} style={{ width: "100%", minHeight: "360px" }} />
      {showRSI && <div ref={rsiRef} style={{ width: "100%", minHeight: "160px" }} />}
    </div>
  );
}
