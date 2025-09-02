import express from "express";
import fs from "fs";
import path from "path";

const app = express();
app.use(express.json());
app.use(express.static("public"));

const DATA_FILE = process.env.DATA_FILE || "./data/albums.json";

function ensureFile(filePath) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(
      filePath,
      JSON.stringify({ site: { title: "Cosplay Gallery" }, albums: [] }, null, 2)
    );
  }
}
ensureFile(DATA_FILE);

function readData() {
  return JSON.parse(fs.readFileSync(DATA_FILE, "utf8"));
}
function writeData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

// ---- API ----
// List all
app.get("/api/albums", (req, res) => {
  try { res.json(readData()); } catch { res.status(500).json({ error: "Read error" }); }
});

// Get one
app.get("/api/albums/:slug", (req, res) => {
  try {
    const data = readData();
    const a = data.albums.find(x => x.slug === req.params.slug);
    if (!a) return res.status(404).json({ error: "Not found" });
    res.json(a);
  } catch { res.status(500).json({ error: "Read error" }); }
});

// Create / Upsert
app.post("/api/albums", (req, res) => {
  try {
    const album = req.body;
    if (!album?.slug) return res.status(400).json({ error: "Missing slug" });
    const data = readData();
    const idx = data.albums.findIndex(a => a.slug === album.slug);
    if (idx >= 0) data.albums[idx] = album;
    else data.albums.unshift(album);
    writeData(data);
    res.json({ ok: true, album });
  } catch (e) { res.status(500).json({ error: "Write error" }); }
});

// Update only (PUT)
app.put("/api/albums/:slug", (req, res) => {
  try {
    const album = req.body;
    const slug = req.params.slug;
    const data = readData();
    const idx = data.albums.findIndex(a => a.slug === slug);
    if (idx < 0) return res.status(404).json({ error: "Not found" });
    data.albums[idx] = { ...data.albums[idx], ...album, slug };
    writeData(data);
    res.json({ ok: true, album: data.albums[idx] });
  } catch { res.status(500).json({ error: "Write error" }); }
});

// Delete
app.delete("/api/albums/:slug", (req, res) => {
  try {
    const slug = req.params.slug;
    const data = readData();
    const before = data.albums.length;
    data.albums = data.albums.filter(a => a.slug !== slug);
    if (data.albums.length === before) return res.status(404).json({ error: "Not found" });
    writeData(data);
    res.json({ ok: true });
  } catch { res.status(500).json({ error: "Write error" }); }
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log("Server running on :" + port));