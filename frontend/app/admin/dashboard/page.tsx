"use client";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import { DashboardView } from "@/components/DashboardView";

export default function AdminDashboardPage() {
  return (
    <ProtectedRoute allowedRoles={["admin"]}>
      <DashboardView role="admin" />
    </ProtectedRoute>
  );
}
