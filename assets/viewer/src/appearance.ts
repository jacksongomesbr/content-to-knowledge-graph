export type Appearance = "system" | "light" | "dark";
export const appearanceStorageKey = "knowledge-graph:appearance";

function readAppearance(): Appearance {
  try {
    const saved = localStorage.getItem(appearanceStorageKey);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

export function initializeAppearance(onChange: () => void): void {
  const system = matchMedia("(prefers-color-scheme: dark)");
  const select = document.querySelector<HTMLSelectElement>("#appearance")!;
  let preference = readAppearance();
  const apply = () => {
    const dark =
      preference === "dark" || (preference === "system" && system.matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    select.value = preference;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", dark ? "#141d18" : "#f5f4ef");
    onChange();
  };
  select.addEventListener("change", () => {
    preference = select.value as Appearance;
    try {
      if (preference === "system")
        localStorage.removeItem(appearanceStorageKey);
      else localStorage.setItem(appearanceStorageKey, preference);
    } catch {
      /* The selection still works when storage is unavailable. */
    }
    apply();
  });
  system.addEventListener("change", () => {
    if (preference === "system") apply();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === appearanceStorageKey || event.key === null) {
      preference = readAppearance();
      apply();
    }
  });
  apply();
}
