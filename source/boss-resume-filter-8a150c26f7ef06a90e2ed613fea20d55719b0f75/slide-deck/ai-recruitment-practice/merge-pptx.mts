// Minimal PPTX/PDF merger for the ai-recruitment-practice slide deck.
// Uses pptxgenjs (already installed in baoyu-slide-deck skill dir).
// No Bun-specific APIs (import.meta.dir) — runs under plain tsx/node.
import { existsSync, readdirSync, readFileSync } from "fs";
import { join, basename, extname } from "path";
import PptxGenJSImport from "pptxgenjs";
// pptxgenjs is CommonJS; under ESM the default export may be nested.
const PptxGenJS = (PptxGenJSImport as any).default ?? PptxGenJSImport;

const DECK_DIR = "c:/Users/yaououzhong/Work/boss-resume-filter/slide-deck/ai-recruitment-practice";
const PROMPTS_DIR = join(DECK_DIR, "prompts");
const OUT_PPTX = join(DECK_DIR, "ai-recruitment-practice.pptx");

interface SlideInfo {
  filename: string;
  path: string;
  index: number;
  promptPath?: string;
}

function findSlideImages(dir: string): SlideInfo[] {
  const files = readdirSync(dir);
  const slidePattern = /^(\d+)-slide-.*\.(png|jpg|jpeg)$/i;
  return files
    .filter((f) => slidePattern.test(f))
    .map((f) => {
      const match = f.match(slidePattern)!;
      const baseName = f.replace(/\.(png|jpg|jpeg)$/i, "");
      const promptPath = join(PROMPTS_DIR, `${baseName}.md`);
      return {
        filename: f,
        path: join(dir, f),
        index: parseInt(match[1], 10),
        promptPath: existsSync(promptPath) ? promptPath : undefined,
      };
    })
    .sort((a, b) => a.index - b.index);
}

async function main() {
  const slides = findSlideImages(DECK_DIR);
  if (slides.length === 0) {
    console.error("No slide images found.");
    process.exit(1);
  }

  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_16x9";
  pptx.author = "baoyu-slide-deck";
  pptx.subject = "AI 驱动的人力资源池智能招聘实践";

  let notesCount = 0;
  for (const slide of slides) {
    const s = pptx.addSlide();
    const imageData = readFileSync(slide.path);
    const base64 = imageData.toString("base64");
    const ext = extname(slide.filename).toLowerCase().replace(".", "");
    const mimeType = ext === "png" ? "image/png" : "image/jpeg";

    s.addImage({
      data: `data:${mimeType};base64,${base64}`,
      x: 0,
      y: 0,
      w: "100%",
      h: "100%",
      sizing: { type: "cover", w: "100%", h: "100%" },
    });

    if (slide.promptPath) {
      const slidePrompt = readFileSync(slide.promptPath, "utf-8");
      s.addNotes(slidePrompt);
      notesCount++;
    }
    console.log(`Added: ${slide.filename}${slide.promptPath ? " (with notes)" : ""}`);
  }

  await pptx.writeFile({ fileName: OUT_PPTX });
  console.log(`\nCreated: ${OUT_PPTX}`);
  console.log(`Total slides: ${slides.length}, with notes: ${notesCount}`);
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});