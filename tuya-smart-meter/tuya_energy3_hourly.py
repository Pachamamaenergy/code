# tuya_energy3_hourly.py
# ------------------------------------------------------------
# FUNKAR UTAN Tuya "statistics" subscription:
# - Hämtar shadow snapshot i loop (polling)
# - Sparar rådata + snapshot-CSV (som innan)
# - Appendar till logg-CSV (tidsserie)
# - Bygger timserie (energi per timme) lokalt från energicounters
#
# Output:
#  - tuya_device_raw.json
#  - tuya_shadow_raw.json
#  - tuya_shadow_values.csv
#  - tuya_log_long.csv              (NY: tidsserie i long format)
#  - tuya_hourly_energy.csv         (NY: energi per timme, A/B/total)
# ------------------------------------------------------------

from __future__ import annotations

import time
import json
import hmac
import hashlib
import csv
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
from urllib.parse import quote
from datetime import datetime, timezone

import requests
import pandas as pd


# =========================
# FYLL I DETTA
# =========================
ACCESS_ID = "Go to https://platform.tuya.com/"
ACCESS_SECRET = "Go to https://platform.tuya.com/"
DEVICE_ID = "Go to https://platform.tuya.com/"
REGION = "eu"   # eu / us / cn / in


# =========================
# LOGGNING (JUSTERA VID BEHOV)
# =========================
POLL_SECONDS = 60          # hämta snapshot varje minut (räcker för timvärden)
RUN_FOREVER = True         # True = kör tills du stoppar (Ctrl+C)
RUN_MINUTES = 30           # om RUN_FOREVER=False, hur länge köra

LOG_LONG_CSV = "tuya_log_long.csv"
HOURLY_CSV = "tuya_hourly_energy.csv"


# =========================
# SKALOR (matchar din device)
# =========================
SCALE_HINTS: Dict[str, float] = {
    "voltage_a": 10.0,
    "voltage_b": 10.0,
    "freq": 100.0,
    "current_a": 1000.0,
    "current_b": 1000.0,
    "power_a": 10.0,
    "power_b": 10.0,
    "total_power": 10.0,
    "power_factor": 100.0,
    "power_factor_a": 100.0,
    "power_factor_b": 100.0,

    # Energi (kWh) – dina faktiska codes med A/B
    "energy_forword_a": 10000.0,
    "energy_reverse_a": 10000.0,
    "energy_forword_b": 10000.0,
    "energy_reserse_b": 10000.0,
    "forward_energy_total": 10000.0,
    "reverse_energy_total": 10000.0,
}


# =========================
# TUYA API BASER
# =========================
BASE_URLS = {
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}


def _now_ms() -> str:
    return str(int(time.time() * 1000))


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256_hex(key: str, msg: str) -> str:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def _canonical_query(params: Optional[Dict[str, Any]]) -> str:
    if not params:
        return ""
    items = []
    for k in sorted(params.keys()):
        v = params[k]
        if v is None:
            continue
        items.append(f"{quote(str(k), safe='')}={quote(str(v), safe='')}")
    return "&".join(items)


@dataclass
class TuyaClient:
    access_id: str
    access_secret: str
    base_url: str
    token: Optional[str] = None

    def _sign(self, method: str, path: str, query=None, body=None) -> Dict[str, str]:
        t = _now_ms()
        method = method.upper()

        body_str = ""
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        body_hash = _sha256_hex(body_str.encode("utf-8"))

        query_str = _canonical_query(query)
        url_path = f"{path}?{query_str}" if query_str else path

        string_to_sign = "\n".join([method, body_hash, "", url_path])
        access_token = self.token or ""
        sign_str = self.access_id + access_token + t + string_to_sign
        sign = _hmac_sha256_hex(self.access_secret, sign_str)

        h = {
            "client_id": self.access_id,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256",
        }
        if self.token:
            h["access_token"] = self.token
        if method in ("POST", "PUT"):
            h["Content-Type"] = "application/json"
        return h

    def request(self, method: str, path: str, query=None, body=None, timeout: int = 20) -> Dict[str, Any]:
        headers = self._sign(method, path, query=query, body=body)
        r = requests.request(
            method=method.upper(),
            url=self.base_url + path,
            params=query,
            data=None if body is None else json.dumps(body, separators=(",", ":"), ensure_ascii=False),
            headers=headers,
            timeout=timeout,
        )
        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"Ogiltigt svar (inte JSON). HTTP {r.status_code}. Text:\n{r.text}")

        if r.status_code >= 400:
            raise RuntimeError(f"HTTP-fel {r.status_code}: {data}")

        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(f"Tuya API error: {data}")

        return data

    def get_token(self) -> None:
        res = self.request("GET", "/v1.0/token", query={"grant_type": 1})
        self.token = res["result"]["access_token"]


def scale_value(code: str, raw_value: Any) -> Tuple[Any, str]:
    if not isinstance(raw_value, (int, float)):
        return raw_value, ""
    if code in SCALE_HINTS:
        div = SCALE_HINTS[code]
        scaled = raw_value / div
        if "voltage" in code:
            return scaled, "V"
        if code == "freq":
            return scaled, "Hz"
        if code.startswith("current"):
            return scaled, "A"
        if "power" in code:
            return scaled, "W"
        if "energy" in code:
            return scaled, "kWh"
        return scaled, ""
    return raw_value, ""


def save_json(filename: str, obj: Any) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_snapshot_files(client: TuyaClient) -> List[Dict[str, Any]]:
    # device + shadow snapshot (som innan)
    dev = client.request("GET", f"/v1.0/devices/{DEVICE_ID}")
    shadow = client.request("GET", f"/v2.0/cloud/thing/{DEVICE_ID}/shadow/properties")

    save_json("tuya_device_raw.json", dev)
    save_json("tuya_shadow_raw.json", shadow)

    props = shadow.get("result", {}).get("properties", [])
    rows = []
    for p in props:
        code = p.get("code", "")
        raw = p.get("value")
        scaled, unit = scale_value(code, raw)
        rows.append({
            "code": code,
            "dp_id": p.get("dp_id"),
            "type": p.get("type"),
            "time": p.get("time"),
            "raw_value": raw,
            "scaled_value": scaled,
            "unit_hint": unit,
        })

    # snapshot-CSV (oförändrat namn)
    with open("tuya_shadow_values.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["code"])
        w.writeheader()
        w.writerows(rows)

    return rows


def append_long_log(rows: List[Dict[str, Any]], sample_time_utc: datetime) -> None:
    # Long/tidy logg: en rad per code per mätningstidpunkt
    file_exists = False
    try:
        with open(LOG_LONG_CSV, "r", encoding="utf-8"):
            file_exists = True
    except FileNotFoundError:
        file_exists = False

    fieldnames = ["sample_time_utc", "code", "scaled_value", "unit_hint", "raw_value"]
    with open(LOG_LONG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            w.writeheader()
        for r in rows:
            w.writerow({
                "sample_time_utc": sample_time_utc.isoformat(),
                "code": r.get("code"),
                "scaled_value": r.get("scaled_value"),
                "unit_hint": r.get("unit_hint"),
                "raw_value": r.get("raw_value"),
            })


def build_hourly_energy_from_log() -> None:
    """
    Bygger energi per timme genom att:
    - läsa LOG_LONG_CSV
    - plocka ut energicounters (kWh)
    - ta differens per timme (last - first) för varje code
    """
    try:
        df = pd.read_csv(LOG_LONG_CSV)
    except FileNotFoundError:
        print("⚠️ Ingen loggfil än (tuya_log_long.csv). Kör scriptet en stund först.")
        return

    if df.empty:
        print("⚠️ Loggfilen är tom.")
        return

    df["sample_time_utc"] = pd.to_datetime(df["sample_time_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["sample_time_utc"])

    energy_codes = [
        "energy_forword_a",
        "energy_reverse_a",
        "energy_forword_b",
        "energy_reserse_b",
        "forward_energy_total",
        "reverse_energy_total",
    ]
    e = df[df["code"].isin(energy_codes)].copy()
    if e.empty:
        print("⚠️ Hittade inga energikoder i loggen ännu.")
        return

    # timbucket
    # FIX: använd 'h' (litet) istället för 'H' pga pandas-versioner
    e["hour"] = e["sample_time_utc"].dt.floor("h")

    e["scaled_value"] = pd.to_numeric(e["scaled_value"], errors="coerce")
    e = e.dropna(subset=["scaled_value"])

    # Energi per timme = (sista counter - första counter) i respektive timme
    g = e.sort_values("sample_time_utc").groupby(["code", "hour"])["scaled_value"]
    hourly = (g.last() - g.first()).reset_index()
    hourly = hourly.rename(columns={"scaled_value": "kWh_in_hour"})

    hourly.to_csv(HOURLY_CSV, index=False, encoding="utf-8")
    print(f"✅ Skrev {HOURLY_CSV} ({len(hourly)} rader)")


def main() -> None:
    if REGION not in BASE_URLS:
        raise ValueError(f"REGION måste vara en av {list(BASE_URLS.keys())}. Du har: {REGION}")

    base_url = BASE_URLS[REGION]
    client = TuyaClient(ACCESS_ID, ACCESS_SECRET, base_url)

    print("✅ Hämtar token...")
    client.get_token()

    # kör-loop
    start_time = time.time()
    try:
        while True:
            sample_time_utc = datetime.now(timezone.utc)

            rows = write_snapshot_files(client)   # behåller gamla filer
            append_long_log(rows, sample_time_utc)

            print(f"✅ Snapshot + logg: {sample_time_utc.isoformat()}  (rows={len(rows)})")

            # uppdatera timfil varje varv (billigt)
            build_hourly_energy_from_log()

            if not RUN_FOREVER:
                if (time.time() - start_time) >= RUN_MINUTES * 60:
                    print("✅ Klar (tidsgräns nådd).")
                    break

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        print("\n🛑 Stoppad med Ctrl+C. (Logg + timfil finns sparad.)")


if __name__ == "__main__":
    main()
