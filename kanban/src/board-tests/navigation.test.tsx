// @vitest-environment jsdom
import { project } from "./fixtures";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import App from "../App";

it("synchronizes Herdr workspaces on focus while retaining local tasks on failure", async () => {
  let offline = false;
  const original = vi.mocked(invoke).getMockImplementation()!;
  vi.mocked(invoke).mockImplementation(async (command, args) => {
    if (command === "list_projects") return [project];
    if (command === "sync_projects") {
      if (offline) throw new Error("herdr.unavailable");
      return { projects: [{ ...project, name: "Synced name" }], workspaces: [], operations: [] };
    }
    if (command === "workspace_operations") return [];
    return original(command, args);
  });
  render(<App />);
  await screen.findByRole("button", { name: /^Synced name/ });
  offline = true;
  fireEvent(window, new Event("focus"));
  await screen.findByText(/同步失败/);
  expect(screen.getByText("修复拖放派发")).toBeTruthy();
});
