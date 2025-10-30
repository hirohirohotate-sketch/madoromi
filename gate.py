# -*- coding: utf-8 -*-
"""
wake-dock / gate.py
超軽量ゲート:
- HTTPを受けて対応するDockerコンテナをオンデマンド起動
- アイドルが続けばコンテナ自動停止
- routes.json（優先）または routes.yaml（pyyamlがあれば）からルートを読む

起動:
    python gate.py

必要環境:
    - Windows 10/11
    - Docker Desktop (Linuxコンテナモード)
    - Python 3.11+

任意の環境変数:
    HOST_PORT        ... ゲートがListenするポート (既定: 8080)
    BIND_HOST        ... バインドアドレス (既定: 127.0.0.1)
    STARTUP_TIMEOUT  ... 子のヘルスチェック待ち秒
    IDLE_SWEEP_SEC   ... アイドル監視間隔(秒)
    API_KEY          ... これをセットすると X-API-Key チェックが有効になる
"""
import os, sys, socket, threading, time, subprocess, shutil, http.client, json

try:
    import yaml  # optional
except Exception:
    yaml = None

HOST_PORT       = int(os.environ.get("HOST_PORT", "8080"))
BIND_HOST       = os.environ.get("BIND_HOST", "127.0.0.1")  # 基本ローカル専用
STARTUP_TIMEOUT = float(os.environ.get("STARTUP_TIMEOUT", "20.0"))
IDLE_SWEEP_SEC  = int(os.environ.get("IDLE_SWEEP_SEC", "1"))
API_KEY         = os.environ.get("API_KEY")  # X-API-Key ヘッダに要求(未設定なら無効)

CONFIG_JSON = "routes.json"
CONFIG_YAML = "routes.yaml"

routes = []  # [{"match":{"method":"POST","path":"/asr"}, "target":{...}}, ...]
states = {}  # group -> {"last_touch": float, "container": str, "port": int, "idle": int, ...}

def docker_path_ok():
    return shutil.which("docker") is not None

def _readall(sock):
    try:
        data = sock.recv(65536, socket.MSG_PEEK)
        if not data:
            time.sleep(0.01)
            data = sock.recv(65536, socket.MSG_PEEK)
        return data
    except Exception:
        return b""

def parse_request_line(peek: bytes):
    try:
        first = peek.split(b"\r\n", 1)[0].decode("latin-1", "ignore")
        parts = first.split(" ")
        if len(parts) >= 2:
            method = parts[0].upper()
            path = parts[1]
            return method, path
    except Exception:
        pass
    return None, None

def load_config():
    global routes
    if os.path.exists(CONFIG_JSON):
        with open(CONFIG_JSON, "r", encoding="utf-8") as f:
            routes = json.load(f)
        return "json"
    elif os.path.exists(CONFIG_YAML) and yaml is not None:
        with open(CONFIG_YAML, "r", encoding="utf-8") as f:
            routes = yaml.safe_load(f)
        return "yaml"
    else:
        routes = [
            {
                "match":{"method":"POST","path":"/asr"},
                "target":{
                    "group":"media-asr",
                    "image":"plugins-whisperer:latest",
                    "port":9090,
                    "health":"/__health",
                    "idle":300,
                    "volumes":["whisper_cache:/root/.cache/whisper"]
                }
            },
            {
                "match":{"method":"POST","path":"/subs/tidy"},
                "target":{
                    "group":"media-subtidy",
                    "image":"plugins-subtidy:latest",
                    "port":9090,
                    "health":"/__health",
                    "idle":180
                }
            },
            {
                "match":{"method":"POST","path":"/subs/burn"},
                "target":{
                    "group":"media-burn",
                    "image":"plugins-sub-burner:latest",
                    "port":9090,
                    "health":"/__health",
                    "idle":180
                }
            },
        ]
        return "built-in"

def find_route(method, path):
    for r in routes:
        m = (r.get("match") or {}).get("method","").upper()
        p = (r.get("match") or {}).get("path","")
        if m == method and p == path:
            return r
    return None

def container_name_for(group: str):
    return f"wake_{group}"

def container_running(name: str):
    try:
        out = subprocess.check_output(
            ["docker","ps","-q","-f", f"name=^{name}$"],
            creationflags=subprocess.CREATE_NO_WINDOW
        ).decode().strip()
        return len(out) > 0
    except Exception:
        return False

def start_container(group: str, target: dict):
    name = container_name_for(group)
    try:
        subprocess.run(["docker","rm","-f", name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass
    vols = []
    for v in target.get("volumes", []):
        vols += ["-v", v]
    args = ["docker","run","--rm","--name", name,"-p", f"127.0.0.1:{target['port']}:{target['port']}"] + vols + [target["image"]]
    subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)

def stop_container(name: str):
    try:
        subprocess.run(["docker","stop","-t","5", name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=6,creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        try:
            subprocess.run(["docker","rm","-f", name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

def wait_healthy(port: int, health: str):
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
            conn.request("GET", health)
            r = conn.getresponse()
            r.read()
            conn.close()
            if 200 <= r.status < 300:
                return True
        except Exception:
            pass
        time.sleep(0.05)
    return False

lock = threading.Lock()

def reaper():
    while True:
        time.sleep(IDLE_SWEEP_SEC)
        now = time.time()
        with lock:
            for g, st in list(states.items()):
                name = container_name_for(g)
                idle = st.get("idle", 180)
                last = st.get("last_touch", now)
                if container_running(name) and (now - last) > idle:
                    stop_container(name)

def send_http_response(sock, status_text, body_text=""):
    try:
        body = body_text.encode("utf-8")
        header = (f"HTTP/1.1 {status_text}\r\nContent-Length: {len(body)}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n").encode("latin-1", "ignore")
        sock.sendall(header + body)
    except Exception:
        pass

def proxy_stream(client_sock, port):
    try:
        upstream = socket.create_connection(("127.0.0.1", port), timeout=5.0)
    except Exception:
        send_http_response(client_sock, "502 Bad Gateway")
        client_sock.close()
        return
    def pump(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass
    t1 = threading.Thread(target=pump, args=(client_sock, upstream), daemon=True)
    t2 = threading.Thread(target=pump, args=(upstream, client_sock), daemon=True)
    t1.start(); t2.start(); t1.join(); t2.join()
    client_sock.close(); upstream.close()

def handle_admin(client_sock, method, path):
    if path.startswith("/__health"):
        send_http_response(client_sock, "200 OK", '{"ok":true}')
        return True
    if path.startswith("/admin/status"):
        with lock:
            data = {g:{"port":st.get("port"),"idle":st.get("idle"),"last_touch":st.get("last_touch"),"image":st.get("image"),"running":container_running(container_name_for(g))} for g, st in states.items()}
        send_http_response(client_sock,"200 OK",json.dumps({"routes": routes, "states": data}))
        return True
    if path.startswith("/admin/reload-routes"):
        mode = load_config()
        send_http_response(client_sock,"200 OK",json.dumps({"reloaded": mode}))
        return True
    return False

def handle_client(client_sock):
    if API_KEY:
        peek = _readall(client_sock)
        if b"\r\n\r\n" in peek:
            head = peek.split(b"\r\n\r\n",1)[0].decode("latin-1","ignore")
            if "X-API-Key:" not in head or (f"X-API-Key: {API_KEY}" not in head and f"X-API-Key:{API_KEY}" not in head):
                send_http_response(client_sock,"401 Unauthorized","missing or invalid X-API-Key")
                client_sock.close(); return
    peek = _readall(client_sock)
    method, path = parse_request_line(peek)
    if not method or not path:
        send_http_response(client_sock, "400 Bad Request", "cannot parse request line"); return
    if path.startswith("/__health") or path.startswith("/admin/"):
        if handle_admin(client_sock, method, path): return
    r = find_route(method, path)
    if not r:
        send_http_response(client_sock, "404 Not Found", "no route"); return
    target = r.get("target", {})
    group  = target.get("group") or (method + "_" + path.strip("/").replace("/","_"))
    port   = int(target.get("port", 9090))
    idle   = int(target.get("idle", 180))
    health = target.get("health", "/__health")
    image  = target.get("image", "")
    name = container_name_for(group)
    need_start = not container_running(name)
    with lock:
        st = states.setdefault(group,{"last_touch": time.time(),"container": name,"port": port,"idle": idle,"image": image,"health": health})
        st.update({"port": port, "idle": idle, "image": image, "health": health}); st["last_touch"] = time.time()
    if need_start:
        if not image:
            send_http_response(client_sock, "500 Internal Server Error", "image not set"); return
        start_container(group, target)
        ok = wait_healthy(port, health)
        if not ok:
            send_http_response(client_sock, "503 Service Unavailable", "backend not healthy"); return
    proxy_stream(client_sock, port)

def main():
    if not docker_path_ok():
        print("docker が見つかりません。Docker Desktop を起動して PATH が通っているか確認してください。",file=sys.stderr)
        sys.exit(1)
    mode = load_config(); print(f"[gate] config source: {mode}, routes loaded: {len(routes)}")
    threading.Thread(target=reaper, daemon=True).start()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((BIND_HOST, HOST_PORT)); s.listen(128)
    host_label = "localhost" if BIND_HOST in ("0.0.0.0","127.0.0.1") else BIND_HOST
    print(f"[gate] listening on http://{host_label}:{HOST_PORT}")
    try:
        while True:
            c, _ = s.accept(); threading.Thread(target=handle_client, args=(c,), daemon=True).start()
    finally:
        s.close()

if __name__ == "__main__":
    main()