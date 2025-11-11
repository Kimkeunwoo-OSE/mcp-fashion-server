import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:5173",
  timeout: 10000,
});

export interface HoldingRow {
  symbol: string;
  name: string;
  qty: number;
  avg_price: number;
  last_price: number;
  pnl_pct: number;
  exit_signal?: string | null;
}

export interface HoldingsResponse {
  positions: HoldingRow[];
  cash: number;
}

export interface RecommendationCard {
  symbol: string;
  name: string;
  score: number;
  reasons: string[];
}

export interface RecommendationsResponse {
  items: RecommendationCard[];
}

export interface CandlePoint {
  symbol: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OrderRequest {
  symbol: string;
  side: "BUY" | "SELL";
  qty: number;
  price_type: "market" | "limit";
  limit_price?: number;
  approve: boolean;
}

export interface OrderResponse {
  ok: boolean;
  order_id?: string | null;
  message: string;
}

export interface SettingsResponse {
  watch: { top_n: number; refresh_sec: number; };
  trade: { quick_pct: number[]; tick: number; default_price_type: "market" | "limit"; confirm_phrase: string; };
  chart: { periods: number[]; indicators: string[]; };
  risk: { take_profit_pct: number; stop_loss_pct: number; trailing_pct: number; };
}

export const fetchSettings = async () => {
  const { data } = await api.get<SettingsResponse>("/api/settings");
  return data;
};

export const fetchHoldings = async () => {
  const { data } = await api.get<HoldingsResponse>("/api/holdings");
  return data;
};

export const fetchRecommendations = async (top = 5) => {
  const { data } = await api.get<RecommendationsResponse>("/api/reco", {
    params: { top },
  });
  return data.items;
};

export const fetchCandles = async (symbol: string, limit = 120) => {
  const { data } = await api.get<{ candles: CandlePoint[] }>("/api/candles", {
    params: { symbol, limit },
  });
  return data.candles;
};

export const fetchName = async (symbol: string) => {
  const { data } = await api.get<{ symbol: string; name: string }>("/api/name", {
    params: { symbol },
  });
  return data.name;
};

export const postOrder = async (body: OrderRequest) => {
  const { data } = await api.post<OrderResponse>("/api/order", body);
  return data;
};

export default api;
