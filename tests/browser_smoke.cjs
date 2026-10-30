// Optional real-browser acceptance test. npm install playwright @sparticuz/chromium
// PLAYWRIGHT_MODULE and CHROMIUM_MODULE may point to already installed packages.
// No external account, credential, image, audio, or publishing service is used.
const fs = require("node:fs"),
  os = require("node:os"),
  path = require("node:path");
const { spawn, execFileSync } = require("node:child_process");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const chromiumPackage = require(
  process.env.CHROMIUM_MODULE || "@sparticuz/chromium",
);
const headless = chromiumPackage.default || chromiumPackage;
const data = fs.mkdtempSync(path.join(os.tmpdir(), "estudio-ui-"));
const python = process.env.PYTHON || "python3",
  port = Number(process.env.UI_TEST_PORT || 57322),
  url = "http://127.0.0.1:" + port;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
execFileSync(python, [
  "-c",
  `from PIL import Image; Image.new('RGB',(480,640),'#497c8b').save(${JSON.stringify(path.join(data, "image.png"))})`,
]);
const wav = Buffer.alloc(44 + 16000 * 8 * 2);
wav.write("RIFF");
wav.writeUInt32LE(wav.length - 8, 4);
wav.write("WAVEfmt ", 8);
wav.writeUInt32LE(16, 16);
wav.writeUInt16LE(1, 20);
wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(16000, 24);
wav.writeUInt32LE(32000, 28);
wav.writeUInt16LE(2, 32);
wav.writeUInt16LE(16, 34);
wav.write("data", 36);
wav.writeUInt32LE(wav.length - 44, 40);
for (let n = 0; n < 128000; n++)
  wav.writeInt16LE(
    Math.round(2000 * Math.sin((n / 16000) * 180 * Math.PI * 2)),
    44 + n * 2,
  );
fs.writeFileSync(path.join(data, "voice.wav"), wav);
const server = spawn(
  python,
  [
    "-u",
    "-m",
    "estudio",
    "--no-browser",
    "--port",
    String(port),
    "--data",
    path.join(data, "projects"),
  ],
  { stdio: ["ignore", "pipe", "pipe"] },
);
let logs = "";
server.stdout.on("data", (b) => (logs += b));
server.stderr.on("data", (b) => (logs += b));
(async () => {
  let browser;
  try {
    for (let i = 0; i < 100; i++) {
      try {
        if ((await fetch(url)).ok) break;
      } catch {}
      await sleep(100);
      if (i === 99) throw Error("Server startup failed: " + logs);
    }
    browser = await chromium.launch({
      executablePath: await headless.executablePath(),
      args: headless.args,
      headless: true,
    });
    const page = await browser.newPage({
        viewport: { width: 1440, height: 1050 },
      }),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(url);
    await page
      .getByRole("button", { name: "＋ Nuevo proyecto", exact: true })
      .click();
    await page
      .locator("#project-form [name=title]")
      .fill("Prueba visual del estudio");
    await page.locator("#project-form [name=duration]").fill("8");
    await page
      .locator("#project-form [name=script]")
      .fill(
        "El amanecer cubrió la costa de luz. Un pequeño barco apareció entre las olas.",
      );
    await page
      .getByRole("button", { name: "Crear proyecto", exact: true })
      .click();
    await page
      .getByRole("heading", { name: "Prueba visual del estudio", exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "Preparar guion y voz", exact: true })
      .click();
    await page.locator(".scene").first().waitFor({ timeout: 20000 });
    await page
      .getByRole("button", { name: "↑ Cargar narración", exact: true })
      .click();
    await page
      .locator("#upload-form [name=file]")
      .setInputFiles(path.join(data, "voice.wav"));
    await page.locator("#upload-form [name=rights]").selectOption("own");
    await page
      .getByRole("button", { name: "Cargar archivo", exact: true })
      .click();
    await page.locator("#modal").waitFor({ state: "hidden" });
    await page.locator(".scene button[data-scene]").first().click();
    await page
      .locator("#scene-form [name=prompt]")
      .fill(
        "A bright blue coastline, natural cinematic light, a small wooden boat.",
      );
    await page
      .getByRole("button", { name: "Guardar plano", exact: true })
      .click();
    await page.locator("#modal").waitFor({ state: "hidden" });
    await page.locator(".scene button[data-scene]").first().click();
    await page
      .getByRole("button", { name: "↑ Cargar imagen o clip", exact: true })
      .click();
    await page
      .locator("#upload-form [name=file]")
      .setInputFiles(path.join(data, "image.png"));
    await page.locator("#upload-form [name=rights]").selectOption("own");
    await page
      .getByRole("button", { name: "Cargar archivo", exact: true })
      .click();
    await page.locator("#modal").waitFor({ state: "hidden" });
    await page.getByRole("button", { name: "Revisión", exact: true }).click();
    await page.locator("#review-form [name=editorial]").check();
    await sleep(3800); // A background poll must never erase an unsaved checkbox.
    if (!(await page.locator("#review-form [name=editorial]").isChecked()))
      throw Error("Polling erased an unsaved review");
    for (const key of ["rights", "timing", "continuity"])
      await page.locator("#review-form [name=" + key + "]").check();
    await page
      .getByRole("button", { name: "Guardar revisión", exact: true })
      .click();
    await page
      .getByText("Proyecto preparado para exportar", { exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "Exportar video", exact: true })
      .click();
    await page
      .getByText("↓ Descargar MP4", { exact: true })
      .waitFor({ timeout: 60000 });
    await page.getByRole("button", { name: "Escenas", exact: true }).click();
    await page.evaluate(() => scrollTo(0, 0));
    if (process.env.UI_SCREENSHOT)
      await page.screenshot({
        path: process.env.UI_SCREENSHOT,
        fullPage: true,
      });
    await page
      .getByRole("button", { name: /Conexiones/, exact: false })
      .click();
    await page
      .getByRole("heading", {
        name: "Conecta una vez. Crea a tu ritmo.",
        exact: true,
      })
      .waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth + 2,
    );
    if (overflow) throw Error("Horizontal overflow at mobile size");
    if (errors.length) throw Error("JavaScript errors: " + errors.join("; "));
    console.log(
      JSON.stringify({
        ok: true,
        steps:
          "create → prepare → upload voice → edit scene → upload image → review → render → download → connections → mobile",
        data_directory: data,
        js_errors: errors,
      }),
    );
  } finally {
    if (browser) await browser.close();
    server.kill("SIGTERM");
  }
})().catch((e) => {
  console.error(e);
  console.error(logs);
  process.exitCode = 1;
});
