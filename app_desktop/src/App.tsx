import { useEffect } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import TradePage from "./pages/Trade";
import ChartPage from "./pages/Chart";
import RecoPage from "./pages/Reco";
import HoldingsPage from "./pages/Holdings";
import { useAppStore } from "./store/useAppStore";

const tabs = [
  { path: "/", label: "거래", key: "trade" },
  { path: "/chart", label: "차트", key: "chart" },
  { path: "/reco", label: "추천", key: "reco" },
  { path: "/holdings", label: "보유/알림", key: "holdings" },
];

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const { activeTab, setActiveTab } = useAppStore();

  useEffect(() => {
    const current = tabs.find((tab) => tab.path === location.pathname) ?? tabs[0];
    setActiveTab(current.key);
  }, [location.pathname, setActiveTab]);

  useEffect(() => {
    const match = tabs.find((tab) => tab.key === activeTab);
    if (match && match.path !== location.pathname) {
      navigate(match.path);
    }
  }, [activeTab, navigate, location.pathname]);

  return (
    <div className="app-shell" style={{ padding: "12px 24px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ fontSize: "1.5rem", margin: 0 }}>v5 Trader Desktop</h1>
        <nav style={{ display: "flex", gap: "12px" }}>
          {tabs.map((tab) => (
            <NavLink
              key={tab.key}
              to={tab.path}
              className={({ isActive }) =>
                `tab-link${isActive ? " tab-link-active" : ""}`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main style={{ marginTop: "16px" }}>
        <Routes>
          <Route path="/" element={<TradePage />} />
          <Route path="/chart" element={<ChartPage />} />
          <Route path="/reco" element={<RecoPage />} />
          <Route path="/holdings" element={<HoldingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
