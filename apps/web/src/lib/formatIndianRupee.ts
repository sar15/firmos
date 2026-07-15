export function formatIndianRupee(value: unknown): string {
  if (value === null || value === undefined) return "—";
  
  let paise = 0;
  if (typeof value === "number") {
    paise = value;
  } else if (typeof value === "object" && value !== null && "paise" in value) {
    paise = Number(value.paise);
  } else {
    paise = Number(value);
  }
  
  if (isNaN(paise)) return "—";

  const rupees = paise / 100;
  
  // Format to standard INR string with commas
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(rupees);
}
