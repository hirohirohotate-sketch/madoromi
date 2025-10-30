from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.get("/__health")
def health():
    return {"ok": True}

def parse_srt(text: str):
    blocks, cur = [], {"i": None, "t": None, "lines": []}
    for line in text.splitlines():
        if line.strip().isdigit() and not cur["lines"]:
            cur = {"i": int(line.strip()), "t": None, "lines": []}
        elif "-->" in line:
            cur["t"] = line.strip()
        elif line.strip() == "":
            if cur["t"] is not None:
                blocks.append(cur)
                cur = {"i": None, "t": None, "lines": []}
        else:
            cur["lines"].append(line.rstrip())
    if cur["t"] is not None:
        blocks.append(cur)
    return blocks

def wrap_text(s: str, width: int = 34):
    out, line = [], ""
    for ch in s:
        line += ch
        if len(line) >= width and ch not in "、。！？":
            out.append(line)
            line = ""
    if line:
        out.append(line)
    return out

def tidy_srt(text: str, width=34, max_lines=2):
    blocks = parse_srt(text)
    tidied = []
    idx = 1
    for b in blocks:
        joined = "".join(b["lines"]).strip()
        if not joined:
            continue
        lines = wrap_text(joined, width)
        chunk = []
        for ln in lines:
            chunk.append(ln)
            if len(chunk) == max_lines:
                tidied.append({"i": idx, "t": b["t"], "lines": chunk})
                idx += 1
                chunk = []
        if chunk:
            tidied.append({"i": idx, "t": b["t"], "lines": chunk})
            idx += 1
    out = []
    for b in tidied:
        out += [str(b["i"]), b["t"], *b["lines"], ""]
    return "\n".join(out)

@app.post("/subs/tidy")
async def tidy(
    file: UploadFile,
    max_chars_per_line: int = Form(34),
    max_lines_per_block: int = Form(2),
):
    srt = (await file.read()).decode("utf-8", errors="ignore")
    out = tidy_srt(
        srt,
        width=max_chars_per_line,
        max_lines=max_lines_per_block
    )
    return PlainTextResponse(out, media_type="text/plain; charset=utf-8")