import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { webcrypto } from "node:crypto";
vi.stubGlobal("crypto", webcrypto);
afterEach(() => {
  cleanup();
});
