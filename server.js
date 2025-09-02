import express from "express";
import fs from "fs";

const app = express();
app.use(express.json());              // đọc JSON body
app.use(express.static("public"));    // phục vụ file tĩnh ở /public

// API: lấy danh sách albums
app.get("/api/albums", (req, res) => {
  const file = "./data/albums.json";
  if (!fs.existsSync(file)) {
    return res.json({ site: { title: "Cosplay Gallery" }, albums: [] });
  }
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  res.json(data);
});

// API: thêm album mới
app.post("/api/albums", (req, res) => {
  const file = "./data/albums.json";
  let data = { site: { title: "Cosplay Gallery" }, albums: [] };
  if (fs.existsSync(file)) {
    data = JSON.parse(fs.readFileSync(file, "utf8"));
  }
  const album = req.body;
  if (!album.slug) return res.status(400).json({ error: "Missing slug" });

  // nếu slug đã tồn tại thì cập nhật, ngược lại thêm mới
  const idx = data.albums.findIndex(a => a.slug === album.slug);
  if (idx >= 0) {
    data.albums[idx] = album;
  } else {
    data.albums.unshift(album);
  }
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
  res.json({ ok: true, album });
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log("Server running on http://localhost:" + port));