#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, sys, time
from urllib.parse import urlparse
import requests

# ===================== CẤU HÌNH NHANH ======================
MAX_N = 200           # dò tới số bao nhiêu
STOP_AFTER = 1        # dừng sau bao nhiêu lần liên tiếp "không tồn tại"
TIMEOUT = 20
RETRIES = 2
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")

# Chuỗi báo 404 bằng HTML của site (cosplaytele dùng WordPress):
HTML_404_HINTS = [
    "Oops! That page can’t be found.",   # WP mặc định
    "404",                               # chung chung, hỗ trợ thêm
]

# Nếu bạn chỉ muốn nhận 1 định dạng (vd: webp) -> bỏ comment dòng dưới
# FORMAT_REGEX = re.compile(r"\.webp($|\?)", re.I)
FORMAT_REGEX = None

# Bộ lọc tên rác (thumbnail, -300x300, v.v.). Ở đây không dùng cho dò dãy, nhưng để sẵn.
JUNK_RE = re.compile(r"(thumb|thumbnail|icon|avatar|banner|amp|small|tiny|sprite|placeholder|loading|lazy|logo|watermark|utm_|-\d+x\d+)", re.I)

# ===========================================================

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def println(*a, **k):
    print(*a, **k, flush=True)

def safe_filename(name: str) -> str:
    try:
        name = re.sub(r"[^\w\-\.\s\p{L}\p{N}]+", " ", name, flags=re.U)
    except re.error:
        # với Python không có flag \p, fallback nhẹ
        name = re.sub(r"[^\w\-\.\s]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "images"

def detect_sequence(seed_url: str):
    """
    Bắt mẫu: ...<digits>...<ext>
    Ví dụ: Umeko-...-1_result.webp
    """
    path = seed_url.split("#", 1)[0].split("?", 1)[0]
    m = re.search(r"(.*?)(\d+)([^/]*?)\.(jpg|jpeg|png|webp|avif|gif)$", path, re.I)
    if not m:
        return None
    prefix, digits, tail, ext = m.groups()
    return {
        "prefix": prefix,
        "digits": digits,
        "tail": tail,
        "ext": ext,
        "pad": len(digits),
        "start": int(digits, 10)
    }

def build_seq_url(seq, n: int) -> str:
    num = str(n).zfill(seq["pad"])
    return f"{seq['prefix']}{num}{seq['tail']}.{seq['ext']}"

def looks_like_exist(url: str) -> bool:
    """
    Trả True nếu URL "có thật".
    - Ưu tiên HEAD; nếu lỗi -> GET.
    - Nếu status 200 nhưng nội dung là trang 404 w/ message -> coi như không tồn tại.
    - Trả False khi mã khác 200.
    """
    # Ưu tiên HEAD
    for attempt in range(RETRIES + 1):
        try:
            r = session.head(url, allow_redirects=True, timeout=TIMEOUT)
            code = r.status_code
            ct   = (r.headers.get("Content-Type") or "").lower()
            r.close()
            if code == 200:
                # Có server trả 200 + HTML 404, kiểm tra nhanh bằng GET nhẹ
                # Chỉ GET khi Content-Type không chứa "image"
                if "image" in ct:
                    return True
                return _double_check_by_get(url)
            else:
                return False
        except Exception:
            time.sleep(0.6)
    # Fallback GET
    return _double_check_by_get(url)

def _double_check_by_get(url: str) -> bool:
    try:
        r = session.get(url, allow_redirects=True, timeout=TIMEOUT)
        code = r.status_code
        text_snippet = ""
        if code == 200:
            # đọc tối đa 50KB để tìm chuỗi 404 HTML
            text_snippet = r.text[:50_000]
        r.close()
        if code != 200:
            return False
        if any(hint in text_snippet for hint in HTML_404_HINTS):
            return False
        return True
    except Exception:
        return False

def seq_key(u: str) -> int:
    m = re.search(r"(\d+)([^/]*?)\.(jpg|jpeg|png|webp|avif|gif)(\?|$)", u, re.I)
    return int(m.group(1)) if m else 10**9

def name_from_seed(seed_url: str) -> str:
    base = os.path.basename(seed_url.split("?", 1)[0])
    base = re.sub(r"\.[a-z0-9]+$", "", base, flags=re.I)
    base = re.sub(r"[_\-]+", " ", base)
    try:
        base = re.sub(r"[^\p{L}\p{N}\s]+", " ", base, flags=re.U)
    except re.error:
        base = re.sub(r"[^\w\s]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return safe_filename(base) or "images"

def process_seed(seed_url: str, max_n: int = MAX_N, stop_after: int = STOP_AFTER):
    if FORMAT_REGEX and not FORMAT_REGEX.search(seed_url):
        println(f"  [!] Bỏ qua (không khớp định dạng): {seed_url}")
        return None, []

    seq = detect_sequence(seed_url)
    if not seq:
        println(f"  [!] Không phát hiện số trong URL mẫu: {seed_url}")
        return None, []

    start = max(1, seq["start"])

    out, misses = [], 0
    for n in range(start, max_n + 1):
        url = build_seq_url(seq, n)
        if FORMAT_REGEX and not FORMAT_REGEX.search(url):
            continue
        if JUNK_RE.search(url):
            continue
        ok = looks_like_exist(url)
        println(f"    - {n}: {'OK' if ok else '404'}")
        if ok:
            out.append(url)
            misses = 0
        else:
            misses += 1
            if misses >= stop_after:
                println(f"    → Dừng do gặp {stop_after} lần 404 liên tiếp.")
                break

    out = sorted(set(out), key=seq_key)
    fname = f"{name_from_seed(seed_url)}.txt"
    with open(fname, "w", encoding="utf-8") as f:
        for u in out:
            f.write(u + "\n")
    return fname, out

def read_seeds_interactive():
    println("Dán các LINK MẪU (mỗi dòng 1 link).")
    println("Nhấn Enter trên dòng trống để bắt đầu.")
    println("Hoặc gõ @ALL để đọc từ ALL.txt\n")
    seeds = []
    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if not line:
            break
        if line == "@ALL":
            if not os.path.exists("ALL.txt"):
                println("[!] Không thấy ALL.txt")
                continue
            with open("ALL.txt", "r", encoding="utf-8") as f:
                for raw in f:
                    s = raw.strip()
                    if s and not s.startswith("#"):
                        seeds.append(s)
            break
        seeds.append(line)
    # lọc rỗng, trùng
    uniq = []
    seen = set()
    for s in seeds:
        if s not in seen:
            uniq.append(s); seen.add(s)
    return uniq

def main():
    println("=== Image Sequencer CLI (no server) ===")
    println(f"- Dò từ 1→{MAX_N}, dừng sau {STOP_AFTER} lần 404 liên tiếp.")
    if FORMAT_REGEX:
        println(f"- Chỉ nhận định dạng: {FORMAT_REGEX.pattern}")
    println("----------------------------------------")

    seeds = read_seeds_interactive()
    if not seeds:
        println("Không có link nào. Thoát.")
        return

    for idx, seed in enumerate(seeds, 1):
        println(f"\n[{idx}/{len(seeds)}] Seed: {seed}")
        fname, urls = process_seed(seed, max_n=MAX_N, stop_after=STOP_AFTER)
        if fname is None:
            println("  → Bỏ qua seed này (không hợp lệ).")
            continue
        println(f"  → Lưu {len(urls)} link vào: {fname}")

    println("\nXong ✅")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        println("\nHủy bởi người dùng.")