"use client";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import { DashboardView } from "@/components/DashboardView";

export default function HospitalDashboardPage() {
  return (
    <ProtectedRoute allowedRoles={["hospital"]}>
      <DashboardView role="hospital" />
    </ProtectedRoute>
  );
}
