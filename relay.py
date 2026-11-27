#!/usr/bin/env python3
"""CustoMapsCoD relay: asks the game servers (UDP "getstatus", like the game) and sends the answers to the site.
The site's hosting (one.com) cannot ask them itself. Run by GitHub Actions (.github/workflows/relay.yml).

Settings (GitHub > Settings > Secrets and variables > Actions):
  SITE_URL   e.g. https://www.customapscod.com
  RELAY_KEY  the same code as in includes/relay_config.php on the site
"""
import base64, json, os, socket, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

SITE = os.environ.get("SITE_URL", "").rstrip("/")
KEY = os.environ.get("RELAY_KEY", "")
ROUNDS = int(os.environ.get("ROUNDS", "4"))    # rounds in one run (one run every 5 minutes)
PAUSE = int(os.environ.get("PAUSE", "60"))     # seconds between two rounds
TIMEOUT = 1.5                                  # seconds to wait for a server
AGENT = "CustoMapsCoD-relay/1.0 (+GitHub Actions)"


def call(method, data=None):
    req = urllib.request.Request(SITE + "/relay.php", method=method, data=data,
                                 headers={"X-Relay-Key": KEY, "User-Agent": AGENT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def ask(server):
    host, port, proto = server["host"], int(server["port"]), server["proto"]
    question = b"\xff\xff\xff\xff\x02getstatus\n" if proto == "mohaa" else b"\xff\xff\xff\xffgetstatus\n"
    raw, ping = b"", 0
    try:
        addr = socket.getaddrinfo(host, port, type=socket.SOCK_DGRAM)[0]
        with socket.socket(addr[0], socket.SOCK_DGRAM) as s:
            s.settimeout(TIMEOUT)
            t0 = time.monotonic()
            s.sendto(question, addr[4])
            raw, _ = s.recvfrom(65535)
            ping = round((time.monotonic() - t0) * 1000)
    except OSError:
        pass  # no answer = offline
    return {"host": host, "port": port, "proto": proto, "raw": base64.b64encode(raw).decode("ascii"), "ping": ping}


def one_round():
    servers = call("GET")["servers"]
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(ask, servers))
    answer = call("POST", json.dumps({"results": results}).encode("utf-8"))
    print(time.strftime("%H:%M:%S"), f"{len(servers)} servers asked, {answer.get('online')} online, saved: {answer.get('ok')}", flush=True)


if __name__ == "__main__":
    if not SITE or not KEY:
        sys.exit("SITE_URL and RELAY_KEY must be set (GitHub > Settings > Secrets and variables > Actions).")
    failures = 0
    for i in range(ROUNDS):
        try:
            one_round()
        except Exception as ex:  # the site may be busy for a moment: next round
            failures += 1
            print(time.strftime("%H:%M:%S"), "ERROR:", ex, flush=True)
        if i < ROUNDS - 1:
            time.sleep(PAUSE)
    sys.exit(1 if failures == ROUNDS else 0)
