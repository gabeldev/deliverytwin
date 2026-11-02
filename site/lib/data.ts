import { readFile } from "node:fs/promises";
import path from "node:path";
import type { Research, Scenario, ScenarioIndex, Truth } from "./types";

const DATA = path.join(process.cwd(), "public", "data");

export async function loadIndex(): Promise<ScenarioIndex> {
  return JSON.parse(await readFile(path.join(DATA, "scenarios", "index.json"), "utf8"));
}

export async function loadScenario(id: string): Promise<Scenario> {
  if (!/^l\d-\d+$/.test(id)) throw new Error("bad scenario id");
  return JSON.parse(await readFile(path.join(DATA, "scenarios", `${id}.json`), "utf8"));
}

export async function loadTruth(id: string): Promise<Truth> {
  if (!/^l\d-\d+$/.test(id)) throw new Error("bad scenario id");
  return JSON.parse(await readFile(path.join(DATA, "scenarios", `${id}.truth.json`), "utf8"));
}

export async function loadResearch(): Promise<Research> {
  return JSON.parse(await readFile(path.join(DATA, "research.json"), "utf8"));
}

export const FLAGSHIP = "l2-2";
export const WHATIF = "l0-2";
export const REPO = "https://github.com/gabeldev/deliverytwin";
export const HF = "https://huggingface.co/gabeldev/deliverytwin-investigator-qwen3-1.7b-lora";
export const blob = (p: string) => `${REPO}/blob/main/${p}`;
