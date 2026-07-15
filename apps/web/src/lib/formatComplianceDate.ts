/**
 * Formats an ISO date string into a compliance-friendly date format
 * e.g., "2024-12-20" -> "20 Dec"
 */
export function formatComplianceDate(isoDateString: string | null): string {
  if (!isoDateString) return "—";
  
  const date = new Date(isoDateString);
  if (isNaN(date.getTime())) return isoDateString;

  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short"
  });
}
