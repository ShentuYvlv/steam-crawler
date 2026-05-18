const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  Document,
  Footer,
  Header,
  Packer,
  PageNumber,
  PageOrientation,
  Paragraph,
  TextRun,
  PageBreak,
} = require("docx");

const repoRoot = path.resolve(__dirname, "..");
const defaultOutput = path.join(__dirname, "线上社区运营管理系统-源代码.docx");
const codeRoots = ["backend/app", "backend/alembic", "src"];
const extraFiles = ["main.py", "run.py"];
const linesPerPage = 50;
const frontPages = 30;
const backPages = 30;
const linesPerSegment = linesPerPage * frontPages;

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith("--")) {
      continue;
    }
    const value = argv[i + 1];
    args[key.slice(2)] = value;
    i += 1;
  }
  return args;
}

function collectFiles() {
  const files = [];
  for (const relativeRoot of codeRoots) {
    const absoluteRoot = path.join(repoRoot, relativeRoot);
    walkFiles(absoluteRoot, files);
  }
  for (const relativeFile of extraFiles) {
    const absoluteFile = path.join(repoRoot, relativeFile);
    if (fs.existsSync(absoluteFile) && fs.statSync(absoluteFile).isFile()) {
      files.push(absoluteFile);
    }
  }
  return files
    .filter((file) => file.endsWith(".py"))
    .sort((a, b) => a.localeCompare(b, "en"));
}

function walkFiles(dir, files) {
  if (!fs.existsSync(dir)) {
    return;
  }
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const absolutePath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkFiles(absolutePath, files);
      continue;
    }
    if (entry.isFile()) {
      files.push(absolutePath);
    }
  }
}

function readFileLines(filePath) {
  const content = fs.readFileSync(filePath, "utf8");
  return content.split(/\r?\n/);
}

function collectLeadingLines(files, limit) {
  const rows = [];
  for (const filePath of files) {
    const relativePath = path.relative(repoRoot, filePath).replaceAll(path.sep, "/");
    const lines = readFileLines(filePath);
    for (let index = 0; index < lines.length; index += 1) {
      rows.push({
        filePath: relativePath,
        lineNumber: index + 1,
        text: lines[index],
      });
      if (rows.length >= limit) {
        return rows;
      }
    }
  }
  return rows;
}

function collectTrailingLines(files, limit) {
  const rows = [];
  for (let fileIndex = files.length - 1; fileIndex >= 0; fileIndex -= 1) {
    const filePath = files[fileIndex];
    const relativePath = path.relative(repoRoot, filePath).replaceAll(path.sep, "/");
    const lines = readFileLines(filePath);
    for (let lineIndex = lines.length - 1; lineIndex >= 0; lineIndex -= 1) {
      rows.push({
        filePath: relativePath,
        lineNumber: lineIndex + 1,
        text: lines[lineIndex],
      });
      if (rows.length >= limit) {
        return rows.reverse();
      }
    }
  }
  return rows.reverse();
}

function buildParagraph(row) {
  const text = row.text.length > 0 ? row.text : " ";
  return new Paragraph({
    spacing: { before: 0, after: 0, line: 180 },
    children: [
      new TextRun({
        text,
        font: "Courier New",
        size: 18,
      }),
    ],
  });
}

function addPageBreak(children) {
  children.push(
    new Paragraph({
      spacing: { before: 0, after: 0 },
      children: [new PageBreak()],
    }),
  );
}

async function main() {
  const args = parseArgs(process.argv);
  const softwareTitle = args.title || "线上社区运营管理系统";
  const softwareVersion = args.version || "V1.0";
  const outputPath = path.resolve(args.output || defaultOutput);
  const files = collectFiles();

  const frontRows = collectLeadingLines(files, linesPerSegment);
  const backRows = collectTrailingLines(files, linesPerSegment);
  const selectedRows = [...frontRows, ...backRows];
  const children = [];

  for (let index = 0; index < selectedRows.length; index += 1) {
    children.push(buildParagraph(selectedRows[index]));
    if ((index + 1) % linesPerPage === 0 && index !== selectedRows.length - 1) {
      addPageBreak(children);
    }
  }

  const doc = new Document({
    styles: {
      default: {
        document: {
          run: {
            font: "Courier New",
            size: 18,
          },
        },
      },
    },
    sections: [
      {
        properties: {
          page: {
            margin: {
              top: 288,
              right: 288,
              bottom: 288,
              left: 288,
              header: 120,
              footer: 120,
            },
            size: {
              width: 16838,
              height: 11906,
              orientation: PageOrientation.LANDSCAPE,
            },
            pageNumbers: {
              start: 1,
            },
          },
        },
        headers: {
          default: new Header({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 0, after: 0 },
                children: [
                  new TextRun({
                    text: `${softwareTitle} ${softwareVersion}`,
                    font: "SimSun",
                    size: 18,
                    bold: true,
                  }),
                ],
              }),
            ],
          }),
        },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 0, after: 0 },
                children: [
                  new TextRun({ text: "第 ", font: "SimSun", size: 16 }),
                  new TextRun({ children: [PageNumber.CURRENT], font: "SimSun", size: 16 }),
                  new TextRun({ text: " 页 / 共 ", font: "SimSun", size: 16 }),
                  new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "SimSun", size: 16 }),
                  new TextRun({ text: " 页", font: "SimSun", size: 16 }),
                ],
              }),
            ],
          }),
        },
        children,
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);

  process.stdout.write(
    `${JSON.stringify({
      outputPath,
      totalFiles: files.length,
      frontRows: frontRows.length,
      backRows: backRows.length,
      totalRows: selectedRows.length,
    }, null, 2)}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
