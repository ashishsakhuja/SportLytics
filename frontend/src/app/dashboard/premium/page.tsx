import { Suspense } from "react";
import PremiumPageClient from "./PremiumPageClient";

export default function PremiumPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <PremiumPageClient />
    </Suspense>
  );
}