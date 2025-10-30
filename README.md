# madoromi — ローカルAPIを“ゼロ常駐”で動かす

**madoromi** は、Windows で “**呼ばれたら起動／アイドルなら停止**” を実現する  
**超軽量ゲート + Docker 子コンテナ** の仕組みです。  
普段は **ゲートだけ常駐（CPUほぼ0%）**、アクセス時にだけ対象APIのコンテナを立ち上げ、  
**一定時間アクセスが無ければ自動停止**します。

---

## 🧩 構成一覧

```
madoromi/
├─ gate.py
├─ routes.json
├─ README.md
├─ LICENSE
├─ plugins/
│  ├─ whisperer/
│  ├─ subtidy/
│  └─ sub-burner/
├─ scripts/
│  ├─ Do-ASR.bat
│  ├─ asr-cli.ps1
│  ├─ Do-Burn.bat
│  └─ subs-burn-cli.ps1
└─ service/
   └─ MyGateService.xml
```

---

## 🚀 クイックスタート

```powershell
docker build -t plugins-whisperer:latest .\plugins\whisperer
docker build -t plugins-subtidy:latest .\plugins\subtidy
docker build -t plugins-sub-burner:latest .\plugins\sub-burner
python .\gate.py
```

---

## 🧠 主なエンドポイント

| メソッド | パス | 内容 |
|-----------|------|------|
| POST | `/asr` | 音声/動画 → 文字起こし（SRT/JSON） |
| POST | `/subs/tidy` | SRT整形 |
| POST | `/subs/burn` | SRTを動画に焼き込み（ハードサブ） |

---

## ⚙️ routes.json の例

```json
[
  {
    "match": {"method": "POST", "path": "/asr"},
    "target": {
      "group": "media-asr",
      "image": "plugins-whisperer:latest",
      "port": 9090,
      "health": "/__health",
      "idle": 300,
      "volumes": ["whisper_cache:/root/.cache/whisper"]
    }
  }
]
```

---

## 🖱 ドラッグ&ドロップ実行（curl不要）

| 用途 | ファイル | 使い方 |
|------|-----------|--------|
| 文字起こし | `scripts\Do-ASR.bat` | 音声/動画をドラッグ&ドロップ |
| 字幕焼き込み | `scripts\Do-Burn.bat` | 動画とSRTをドラッグ&ドロップ |

---

## 🔐 セキュリティ

- 既定で `127.0.0.1` バインド
- 環境変数 `API_KEY` で `X-API-Key` を要求可能

---

## 🧩 管理エンドポイント

| パス | 内容 |
|------|------|
| `GET /__health` | ゲート自体のヘルスチェック |
| `GET /admin/status` | ルート・各コンテナの状態 |
| `POST /admin/reload-routes` | ルーティング設定再読込 |

---

## 🧰 Windowsサービス化（任意）

`service/MyGateService.xml` と [WinSW](https://github.com/winsw/winsw) を使うと、  
`python gate.py` をWindowsサービスとして登録できます。

---

## 📜 ライセンス

MIT License  
著作権表記と免責を残せば、商用・改変・再配布すべて自由です。

---

**wake-dock** は「ローカルで静かに待ち、必要な瞬間だけ働く」軽量APIプラットフォームです。
