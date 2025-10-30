from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse
import tempfile, subprocess, os, uuid

app = FastAPI()

@app.get("/__health")
def health():
    return {"ok": True}

@app.post("/subs/burn")
async def burn(
    video: UploadFile,
    srt: UploadFile,
    font_size: int = Form(28)
):
    with tempfile.TemporaryDirectory() as td:
        vpath = os.path.join(td, f"v-{uuid.uuid4().hex}.mp4")
        spath = os.path.join(td, f"s-{uuid.uuid4().hex}.srt")
        out   = os.path.join(td, "with_subs.mp4")

        with open(vpath,"wb") as f:
            f.write(await video.read())
        with open(spath,"wb") as f:
            f.write(await srt.read())

        cmd = [
            "ffmpeg","-y",
            "-i", vpath,
            "-vf", f"subtitles={spath}:force_style='Fontsize={font_size}'",
            "-c:a","copy",
            out
        ]
        subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)

        return FileResponse(out,media_type="video/mp4",filename="with_subs.mp4")