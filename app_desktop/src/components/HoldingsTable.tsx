import { useEffect, useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { fetchHoldings, HoldingRow } from "../api/client";
import { useAppStore } from "../store/useAppStore";

interface HoldingsTableProps {
  refreshSec?: number;
  onRowsChange?: (rows: HoldingRow[]) => void;
}

export default function HoldingsTable({ refreshSec = 60, onRowsChange }: HoldingsTableProps) {
  const [rows, setRows] = useState<HoldingRow[]>([]);
  const [loading, setLoading] = useState(false);
  const { selection, setSelection } = useAppStore();

  const columns = useMemo<ColumnDef<HoldingRow>[]>(
    () => [
      {
        header: "종목",
        accessorFn: (row) => `${row.name} (${row.symbol})`,
      },
      {
        header: "수량",
        accessorKey: "qty",
      },
      {
        header: "평단",
        accessorKey: "avg_price",
        cell: (info) => info.getValue<number>().toFixed(2),
      },
      {
        header: "현재가",
        accessorKey: "last_price",
        cell: (info) => info.getValue<number>().toFixed(2),
      },
      {
        header: "손익%",
        accessorKey: "pnl_pct",
        cell: (info) => `${(info.getValue<number>() * 100).toFixed(2)}%`,
      },
      {
        header: "Exit",
        accessorKey: "exit_signal",
        cell: (info) => info.getValue<string | null>() ?? "-",
      },
    ],
    []
  );

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        setLoading(true);
        const data = await fetchHoldings();
        if (alive) {
          setRows(data.positions);
          onRowsChange?.(data.positions);
          if (data.positions.length && !selection) {
            const first = data.positions[0];
            setSelection({ symbol: first.symbol, name: first.name });
          }
        }
      } catch (error) {
        console.error("holdings fetch failed", error);
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    };
    load();
    const interval = setInterval(load, refreshSec * 1000);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [refreshSec, selection, setSelection]);

  return (
    <div className="table-container" style={{ overflowX: "auto" }}>
      {loading && <p>불러오는 중...</p>}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  style={{ textAlign: "left", padding: "8px", borderBottom: "1px solid rgba(148,163,184,0.2)" }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const isActive = selection?.symbol === row.original.symbol;
            return (
              <tr
                key={row.id}
                onClick={() => setSelection({ symbol: row.original.symbol, name: row.original.name })}
                style={{
                  cursor: "pointer",
                  backgroundColor: isActive ? "rgba(56, 189, 248, 0.2)" : "transparent",
                }}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} style={{ padding: "8px" }}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
