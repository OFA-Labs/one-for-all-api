// Test-only stand-in for the browse tool: runs the adapter's fixed expressions in
// a headless browser with a throwaway profile, against local fixture pages.
// One JSON request per stdin line, one JSON reply per stdout line.
const path = require("node:path");
const readline = require("node:readline");
const { chromium } = require(path.join(process.env.OFA_PLAYWRIGHT_DIR, "playwright"));

(async () => {
  const browser = await chromium.launch({ channel: process.env.OFA_BROWSER_CHANNEL || "msedge" });
  const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
  const reply = (body) => process.stdout.write(JSON.stringify(body) + "\n");
  reply({ ready: true });
  for await (const line of readline.createInterface({ input: process.stdin })) {
    const { name, args } = JSON.parse(line);
    try {
      let result;
      if (name === "navigate") {
        await page.goto(args.url, { waitUntil: "load", timeout: 5000 });
        result = { tab: 1 };
      } else if (name === "eval") {
        // The adapter's own constants arrive here, exactly as the browse tool would receive them.
        result = await page.evaluate(
          ([source, arg]) => (0, eval)(`(${source})`)(undefined, arg),
          [args.expression, args.arg ?? null],
        );
      } else {
        throw new Error(`unsupported ${name}`);
      }
      reply({ result: result ?? null });
    } catch (error) {
      reply({ error: String(error.message || error).slice(0, 500) });
    }
  }
  await browser.close();
})();
