import SportDashboard from "./sport-dashboard";

export default async function SportDashboardPage({
  params,
}: {
  params: Promise<{ sport: string }>;
}) {
  const { sport } = await params;
  return <SportDashboard sport={sport} />;
}