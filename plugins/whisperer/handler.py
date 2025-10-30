from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from faster_whisper import WhisperModel
import tempfile, subprocess, os, uuid

app = FastAPI()

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
DEVICE     = os.getenv("WHISPER_DEVICE", "cpu")      # "cpu" / "cuda"
COMPUTE    = os.getenv("WHISPER_COMPUTE", "int8")    # "int8" / "float16" etc.

_model = None
def load_model():
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE)

@app.get("/__health")
def health():
    return JSONResponse({"ok": True})

@app.get("/__warm")
def warm():
    load_model()
    return JSONResponse({"warmed": True, "model": MODEL_NAME})

def _fmt_ts(t: float) -> str:
    if t is None:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def segments_to_srt(segments):
    out = []
    for i, seg in enumerate(segments, 1):
        out.append(f"{i}")
        out.append(f"{_fmt_ts(seg.start)} --> {_fmt_ts(seg.end)}")
        out.append(seg.text.strip())
        out.append("")
    return "\n".join(out)

@app.post("/asr")
async def asr(
    file: UploadFile,
    format: str = Form("json"),
    lang: str | None = Form(None),
    translate: bool = Form(False)
):
    load_model()

    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, f"in-{uuid.uuid4().hex}")
        with open(in_path, "wb") as f:
            f.write(await file.read())

        probe = (file.content_type or "").lower()
        if probe.startswith("video/"):
            wav_path = os.path.join(td, "audio.wav")
            subprocess.run(
                ["ffmpeg","-y","-i", in_path, "-ac","1","-ar","16000", wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            src = wav_path
        else:
            src = in_path

        task = "translate" if translate else "transcribe"
        segments, info = _model.transcribe(
            src,
            language=lang,
            task=task,
            vad_filter=True
        )
        segs = list(segments)

        if format == "srt":
            return PlainTextResponse(
                segments_to_srt(segs),
                media_type="text/plain; charset=utf-8"
            )
        else:
            data = [
                {"i": i+1,
                 "start": seg.start,
                 "end": seg.end,
                 "text": seg.text.strip()}
                for i, seg in enumerate(segs)
            ]
            return JSONResponse({
                "lang": info.language,
                "duration": info.duration,
                "segments": data
            })