export function daysUntil(dateStr) {
  const d = new Date(dateStr);
  return Math.round((d - new Date()) / 86400000);
}

export function initials(name) {
  return name.slice(0, 2).toUpperCase();
}

export function currentMonthLabel(date = new Date()) {
  return date.toLocaleString("en-US", { month: "short" });
}
