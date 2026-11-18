"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { BLOOD_TYPES } from "@/lib/constants";
import type { DonorsByBloodType } from "@/types";

export function BloodTypeChart({ data }: { data: DonorsByBloodType }) {
  const chartData = BLOOD_TYPES.map((type) => ({ type, donors: data[type] ?? 0 }));

  return (
    <div className="h-72 w-full" aria-label="Donors per blood type bar chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="type" tick={{ fill: "#475569", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "#475569", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "#fff1f2" }}
            contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0" }}
            formatter={(value) => [`${value ?? 0} donors`, "Donors"]}
          />
          <Bar dataKey="donors" fill="#e11d48" radius={[6, 6, 0, 0]} maxBarSize={44} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
