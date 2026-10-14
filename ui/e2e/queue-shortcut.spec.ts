import { expect, test, type Page } from "@playwright/test";
import { createConversationViaAPI } from "./helpers";

// Mod+Shift+Enter (⌘⇧↵ on mac, Ctrl+Shift+Enter elsewhere) queues the composed
// message to run after the current turn instead of interrupting it, and falls
// back to an ordinary send when the agent is idle. Playwright reports a Linux
// platform, so the mod is Ctrl.

async function openConversation(
  page: Page,
  request: Parameters<typeof createConversationViaAPI>[0],
) {
  const slug = await createConversationViaAPI(request, "echo: queue shortcut seed");
  await page.goto(`/c/${slug}`);
  await page.waitForLoadState("domcontentloaded");
  const messageInput = page.getByTestId("message-input");
  await expect(messageInput).toBeVisible({ timeout: 30000 });
  return messageInput;
}

async function sendAndWaitForWorking(page: Page, text: string) {
  const messageInput = page.getByTestId("message-input");
  await messageInput.fill(text);
  await page.getByTestId("send-button").click();
  await expect(page.getByTestId("agent-thinking")).toBeVisible({ timeout: 30000 });
}

test.describe("queue-shortcut", () => {
  test.use({ viewport: { width: 1280, height: 800 }, isMobile: false, hasTouch: false });

  test("Ctrl+Shift+Enter queues the composed message", async ({ page, request }) => {
    const messageInput = await openConversation(page, request);
    await sendAndWaitForWorking(page, "delay: 60");

    await messageInput.fill("queued via shortcut");
    await messageInput.press("Control+Shift+Enter");

    await expect(messageInput).toHaveValue("");
    await expect(page.getByTestId("queued-badge")).toHaveCount(1, { timeout: 10000 });
    await expect(page.locator("text=queued via shortcut")).toHaveCount(1);
  });

  test("holding Ctrl+Shift previews queueing on the send button", async ({ page, request }) => {
    const messageInput = await openConversation(page, request);
    await sendAndWaitForWorking(page, "delay: 60");
    await messageInput.fill("hold to preview");

    const sendButton = page.getByTestId("send-button");
    await page.keyboard.down("Control");
    await expect(sendButton).toHaveAttribute("aria-label", "Compact and send");
    await page.keyboard.down("Shift");
    await expect(sendButton).toHaveAttribute("aria-label", "Queue after agent finishes");
    await page.keyboard.up("Shift");
    await expect(sendButton).toHaveAttribute("aria-label", "Compact and send");
    await page.keyboard.up("Control");
    await expect(sendButton).toHaveAttribute("aria-label", "Send message");
  });

  test("Shift+Enter still inserts a newline while the agent works", async ({ page, request }) => {
    const messageInput = await openConversation(page, request);
    await sendAndWaitForWorking(page, "delay: 60");

    await messageInput.fill("first line");
    await messageInput.press("Shift+Enter");
    await messageInput.pressSequentially("second line");

    await expect(messageInput).toHaveValue("first line\nsecond line");
    await expect(page.getByTestId("queued-badge")).toHaveCount(0);
  });

  test("Ctrl+Shift+Enter sends when the agent is idle", async ({ page, request }) => {
    const messageInput = await openConversation(page, request);

    await messageInput.fill("sent via shortcut");
    await messageInput.press("Control+Shift+Enter");

    await expect(messageInput).toHaveValue("");
    await expect(page.locator("text=sent via shortcut")).toHaveCount(1);
    await expect(page.getByTestId("queued-badge")).toHaveCount(0);
  });
});
