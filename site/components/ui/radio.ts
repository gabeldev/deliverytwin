import type { KeyboardEvent } from "react";

/** WAI-ARIA radio group keys: arrows move and select, Home/End jump. Pair with tabIndex 0 on the checked radio, -1 on the rest. */
export function onRadioKeys(e: KeyboardEvent<HTMLElement>) {
  const next = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 } as Record<string, number>;
  if (!(e.key in next) && e.key !== "Home" && e.key !== "End") return;
  const radios = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]:not([disabled])'));
  const i = radios.indexOf(document.activeElement as HTMLButtonElement);
  if (i < 0 || !radios.length) return;
  e.preventDefault();
  const j = e.key === "Home" ? 0 : e.key === "End" ? radios.length - 1 : (i + next[e.key] + radios.length) % radios.length;
  radios[j].focus();
  radios[j].click();
}
