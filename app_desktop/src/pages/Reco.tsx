import RecoCards from "../components/RecoCards";
import { useAppStore } from "../store/useAppStore";

export default function RecoPage() {
  const { selection } = useAppStore();
  return (
    <div style={{ display: "grid", gap: "16px" }}>
      <p>추천 종목은 전략 점수와 미니 차트로 정렬됩니다. 원하는 종목을 누르면 거래 탭으로 이동합니다.</p>
      {selection && (
        <small>현재 선택: {selection.name} ({selection.symbol})</small>
      )}
      <RecoCards top={5} />
    </div>
  );
}
