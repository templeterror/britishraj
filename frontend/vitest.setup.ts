import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  try {
    window.sessionStorage.clear();
  } catch {
    // sessionStorage may be unavailable; tests that need it set it up themselves.
  }
});
