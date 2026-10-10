import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PersonaPicker from "@/features/heirloom/components/PersonaPicker";
import { getSession } from "@/features/heirloom/session";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const post = vi.hoisted(() => vi.fn());
vi.mock("@/features/heirloom/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/heirloom/api/client")>();
  return { ...actual, default: { post }, createRelayClient: () => ({ post }) };
});

const META = { revision: 0, consent_revision: 0, mode: "demo" as const, degraded: [] };
const session = (role: string, name: string) => ({
  data: { token: `tok-${role}`, family_id: "fam-1", person: { id: `p-${role}`, display_name: name, role } },
  meta: META,
  errors: [],
});

beforeEach(() => {
  post.mockReset();
  push.mockReset();
});

describe("PersonaPicker", () => {
  it("shows the three personas and the synthetic-data banner", () => {
    render(<PersonaPicker />);
    expect(screen.getByText("Sarah Lin")).toBeInTheDocument();
    expect(screen.getByText("Lead advisor")).toBeInTheDocument();
    expect(screen.getByText("Robert Morgan")).toBeInTheDocument();
    expect(screen.getByText("Client")).toBeInTheDocument();
    expect(screen.getByText("James Morgan")).toBeInTheDocument();
    expect(screen.getByText("Adult family member")).toBeInTheDocument();
    expect(screen.getByText("Synthetic Morgan family · demo mode · no real client data")).toBeInTheDocument();
  });

  it("choosing a persona creates a session, stores it and routes to its screen", async () => {
    post.mockResolvedValue(session("advisor", "Sarah Lin"));
    render(<PersonaPicker />);

    await userEvent.click(screen.getByRole("button", { name: /Sarah Lin/ }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/relay/advisor"));
    expect(post).toHaveBeenCalledWith("/demo/sessions", { persona: "sarah" });
    expect(getSession()).toEqual({
      token: "tok-advisor",
      familyId: "fam-1",
      person: { id: "p-advisor", displayName: "Sarah Lin", role: "advisor" },
    });
  });

  it.each([
    ["Robert Morgan", "robert", "parent", "/relay/parent"],
    ["James Morgan", "james", "adult_heir", "/relay/heir"],
  ])("routes %s to %s", async (name, persona, role, route) => {
    post.mockResolvedValue(session(role, name));
    render(<PersonaPicker />);
    await userEvent.click(screen.getByRole("button", { name: new RegExp(name) }));
    await waitFor(() => expect(push).toHaveBeenCalledWith(route));
    expect(post).toHaveBeenCalledWith("/demo/sessions", { persona });
  });

  it("shows a recoverable error when the backend is unreachable", async () => {
    const { RelayApiError } = await import("@/features/heirloom/api/client");
    post.mockRejectedValueOnce(new RelayApiError(0, "network_error", "Failed to fetch"));
    render(<PersonaPicker />);

    await userEvent.click(screen.getByRole("button", { name: /Sarah Lin/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach Heirloom Relay");
    expect(push).not.toHaveBeenCalled();

    post.mockResolvedValueOnce(session("advisor", "Sarah Lin"));
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/relay/advisor"));
  });

  it("Reset demo posts /demo/reset and confirms", async () => {
    post.mockResolvedValueOnce(session("advisor", "Sarah Lin")); // bootstrap token for the reset call
    post.mockResolvedValueOnce({ data: { status: "reset" }, meta: META, errors: [] });
    render(<PersonaPicker />);

    await userEvent.click(screen.getByRole("button", { name: "Reset demo" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/demo/reset"));
    expect(await screen.findByText("Demo data reset.")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
