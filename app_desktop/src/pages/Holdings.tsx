import { useEffect, useState } from "react";
import DetailPanel from "../components/DetailPanel";
import HoldingsTable from "../components/HoldingsTable";
import { HoldingRow, fetchSettings } from "../api/client";
import { useAppStore } from "../store/useAppStore";

export default function HoldingsPage() {
  const { selection } = useAppStore();
  const [rows, setRows] = useState<HoldingRow[]>([]);
  const [tradeConfig, setTradeConfig] = useState({
    quick_pct: [10, 25, 50, 100],
    tick: 50,
    confirm_phrase: "자동매매 금지 정책에 동의합니다",
  });
  const [takeProfitPct, setTakeProfitPct] = useState(0.18);

  useEffect(() => {
    fetchSettings().then((cfg) => {
      setTradeConfig({
        quick_pct: cfg.trade.quick_pct,
        tick: cfg.trade.tick,
        confirm_phrase: cfg.trade.confirm_phrase,
      });
      setTakeProfitPct(cfg.risk.take_profit_pct);
    });
  }, []);

  const active = selection ? rows.find((row) => row.symbol === selection.symbol) : undefined;

  return (
    <div style={{ display: "grid", gap: "16px" }}>
      <HoldingsTable refreshSec={60} onRowsChange={setRows} />
      <DetailPanel
        holding={active}
        takeProfitPct={takeProfitPct}
        quickPct={tradeConfig.quick_pct}
        tick={tradeConfig.tick}
        confirmPhrase={tradeConfig.confirm_phrase}
      />
    </div>
  );
}
