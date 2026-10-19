// Minimal PDF merger for the ai-recruitment-practice slide deck.
// Uses pdf-lib (installed locally). No Bun-specific APIs.
import { readdirSync, readFileSync } from "fs";
import { join } from "path";
import { PDFDocument } from "pdf-lib";

const DECK_DIR = "c:/Users/yaououzhong/Work/boss-resume-filter/slide-deck/ai-recruitment-practice";
const OUT_PDF = join(DECK_DIR, "ai-recruitment-practice.pdf");

async function main() {
  const files = readdirSync(DECK_DIR);
  const slidePattern = /^(\d+)-slide-.*\.(png|jpg|jpeg)$/i;
  const slides = files
    .filter((f) => slidePattern.test(f))
    .map((f) => ({ filename: f, path: join(DECK_DIR, f), index: parseInt(f.match(slidePattern)![1], 10) }))
    .sort((a, b) => a.index - b.index);

  if (slides.length === 0) {
    console.error("No slide images found.");
    process.exit(1);
  }

  const pdfDoc = await PDFDocument.create();
  for (const slide of slides) {
    const bytes = readFileSync(slide.path);
    const ext = slide.filename.toLowerCase().endsWith(".png") ? "png" : "jpg";
    const img = ext === "png" ? await pdfDoc.embedPng(bytes) : await pdfDoc.embedJpg(bytes);
    // 16:9 page at landscape Letter-ish size (10in x 5.625in)
    const page = pdfDoc.addPage([720, 405]); // 10in x 5.625in at 72dpi
    page.drawImage(img, { x: 0, y: 0, width: 720, height: 405 });
    console.log(`Added: ${slide.filename}`);
  }

  const out = await pdfDoc.save();
  const { writeFileSync } = await import("fs");
  writeFileSync(OUT_PDF, out);
  console.log(`\nCreated: ${OUT_PPTX_INFO()}`);
  console.log(`Total slides: ${slides.length}`);
}

function OUT_PPTX_INFO(): string {
  return OUT_PDF;
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});