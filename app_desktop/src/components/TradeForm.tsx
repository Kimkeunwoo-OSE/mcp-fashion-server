import { useState } from "react";
import { isPermissionGranted, requestPermission, sendNotification } from "@tauri-apps/api/notification";
import { postOrder, OrderResponse } from "../api/client";

interface TradeFormProps {
  symbol: string;
  name: string;
  side: "BUY" | "SELL";
  onSideChange?: (side: "BUY" | "SELL") => void;
  lastPrice: number;
  maxQty?: number;
  quickPct: number[];
  tick: number;
  defaultPriceType?: "market" | "limit";
  confirmPhrase: string;
  disabled?: boolean;
  onSubmitted?: (response: OrderResponse) => void;
}

export default function TradeForm({
  symbol,
  name,
  side,
  onSideChange,
  lastPrice,
  maxQty,
  quickPct,
  tick,
  defaultPriceType = "market",
  confirmPhrase,
  disabled,
  onSubmitted,
}: TradeFormProps) {
  const [mode, setMode] = useState<"qty" | "amount">("qty");
  const [qty, setQty] = useState<number>(maxQty && side === "SELL" ? maxQty : 1);
  const [amount, setAmount] = useState<number>(0);
  const [priceType, setPriceType] = useState<"market" | "limit">(defaultPriceType);
  const [limitPrice, setLimitPrice] = useState<number>(lastPrice || 0);
  const [approved, setApproved] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const effectiveQty = mode === "amount" && amount > 0
    ? Math.max(0, Math.floor(amount / Math.max(lastPrice, 1)))
    : qty;

  const handleQuick = (pct: number) => {
    if (side === "SELL" && maxQty) {
      const calc = Math.max(1, Math.floor((maxQty * pct) / 100));
      setQty(calc);
    } else if (side === "BUY" && lastPrice > 0) {
      const computed = Math.max(1, Math.floor(((amount || lastPrice) * pct) / 100 / lastPrice));
      setQty(computed);
    }
  };

  const submit = async () => {
    if (disabled) return;
    if (!approved) {
      setMessage("승인 체크가 필요합니다.");
      return;
    }
    if (effectiveQty < 1) {
      setMessage("수량을 확인하세요.");
      return;
    }
    if (side === "SELL" && maxQty && effectiveQty > maxQty) {
      setMessage("보유 수량을 초과합니다.");
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      const response = await postOrder({
        symbol,
        side,
        qty: effectiveQty,
        price_type: priceType,
        limit_price: priceType === "limit" ? limitPrice : undefined,
        approve: approved,
      });
      setMessage(response.ok ? "주문 전송 성공" : `주문 실패: ${response.message}`);
      if (response.ok) {
        const notify = async () => {
          const granted = await isPermissionGranted();
          if (!granted) {
            const permission = await requestPermission();
            if (permission !== "granted") {
              return;
            }
          }
          await sendNotification({
            title: "v5 Trader",
            body: `${side} ${name} (${symbol}) x${effectiveQty} ${priceType} - ${response.message}`
          });
        };
        void notify();
      }
      onSubmitted?.(response);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "주문 실패");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <div style={{ display: "flex", gap: "8px" }}>
        <button
          type="button"
          className={side === "BUY" ? "tab-link-active" : "tab-link"}
          onClick={() => onSideChange?.("BUY")}
          disabled={disabled || !onSideChange}
        >
          매수
        </button>
        <button
          type="button"
          className={side === "SELL" ? "tab-link-active" : "tab-link"}
          onClick={() => onSideChange?.("SELL")}
          disabled={disabled || !onSideChange}
        >
          매도
        </button>
      </div>

      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
        <button
          className={mode === "qty" ? "tab-link-active" : "tab-link"}
          type="button"
          onClick={() => setMode("qty")}
        >
          수량
        </button>
        <button
          className={mode === "amount" ? "tab-link-active" : "tab-link"}
          type="button"
          onClick={() => setMode("amount")}
        >
          금액
        </button>
      </div>

      {mode === "qty" ? (
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          매도/매수 수량
          <input
            type="number"
            min={1}
            max={maxQty ?? undefined}
            value={qty}
            onChange={(event) => setQty(Number(event.target.value))}
          />
        </label>
      ) : (
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          매도 금액(원)
          <input
            type="number"
            min={1000}
            step={1000}
            value={amount}
            onChange={(event) => setAmount(Number(event.target.value))}
          />
          <small>계산 수량: {effectiveQty}주 (현재가 {lastPrice.toLocaleString()}원)</small>
        </label>
      )}

      <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        가격 유형
        <select value={priceType} onChange={(event) => setPriceType(event.target.value as "market" | "limit")}> 
          <option value="market">시장가</option>
          <option value="limit">지정가</option>
        </select>
      </label>

      {priceType === "limit" && (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button type="button" onClick={() => setLimitPrice(Math.max(1, limitPrice - tick))}>-</button>
          <input
            type="number"
            value={limitPrice}
            step={tick}
            min={1}
            onChange={(event) => setLimitPrice(Number(event.target.value))}
          />
          <button type="button" onClick={() => setLimitPrice(limitPrice + tick)}>+</button>
        </div>
      )}

      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
        {quickPct.map((pct) => (
          <button key={pct} type="button" onClick={() => handleQuick(pct)}>
            {pct}%
          </button>
        ))}
      </div>

      <label style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <input
          type="checkbox"
          checked={approved}
          onChange={(event) => setApproved(event.target.checked)}
          disabled={disabled}
        />
        <span>{confirmPhrase}</span>
      </label>

      <button type="button" onClick={submit} disabled={disabled || submitting}>
        {submitting ? "전송 중..." : `${side === "BUY" ? "매수" : "매도"} 주문`}
      </button>

      {message && <p>{message}</p>}
      <small>
        {name} ({symbol}) • 현재가 {lastPrice.toLocaleString()}원
      </small>
    </div>
  );
}
