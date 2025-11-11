import { useEffect, useState } from "react";
import TradeForm from "../components/TradeForm";
import { fetchCandles, fetchName, fetchSettings } from "../api/client";
import { useAppStore } from "../store/useAppStore";

export default function TradePage() {
  const { selection, setSelection } = useAppStore();
  const [symbol, setSymbol] = useState(selection?.symbol ?? "005930.KS");
  const [name, setName] = useState(selection?.name ?? "");
  const [lastPrice, setLastPrice] = useState(0);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [tradeConfig, setTradeConfig] = useState({
    quick_pct: [10, 25, 50, 100],
    tick: 50,
    default_price_type: "market" as const,
    confirm_phrase: "자동매매 금지 정책에 동의합니다",
  });

  useEffect(() => {
    fetchSettings().then((config) => {
      setTradeConfig(config.trade);
    });
  }, []);

  useEffect(() => {
    setSide("BUY");
    let active = true;
    const load = async () => {
      try {
        const [fetchedName, candles] = await Promise.all([
          fetchName(symbol),
          fetchCandles(symbol, 1),
        ]);
        if (!active) return;
        setName(fetchedName);
        setSelection({ symbol, name: fetchedName });
        const last = candles.at(-1)?.close ?? 0;
        setLastPrice(last);
      } catch (error) {
        console.error("trade symbol", error);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [symbol, setSelection]);

  return (
    <div style={{ display: "grid", gap: "16px", maxWidth: "640px" }}>
      <section style={{ display: "grid", gap: "12px" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          종목 코드
          <input
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.toUpperCase())}
            placeholder="005930.KS"
          />
        </label>
        <div>
          <strong>이름</strong>
          <div>{name}</div>
        </div>
      </section>
      <TradeForm
        symbol={symbol}
        name={name || symbol}
        side={side}
        onSideChange={setSide}
        lastPrice={lastPrice}
        quickPct={tradeConfig.quick_pct}
        tick={tradeConfig.tick}
        defaultPriceType={tradeConfig.default_price_type}
        confirmPhrase={tradeConfig.confirm_phrase}
      />
    </div>
  );
}
