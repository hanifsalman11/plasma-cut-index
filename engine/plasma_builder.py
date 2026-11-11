import os
import json
import re
import time
import math
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://hanifsalman11.github.io/plasma-cut-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6").strip()
CUSTOM_PLASMA = os.environ.get("CUSTOM_PLASMA", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_plasmas.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

_CACHED_MODELS = None

# Format: (Machine / Cut Scenario, Output Amps, Metal Thickness In, Cut Speed IPM, Pierce Delay Sec, Kerf Width In, Input Breaker 240V Amps)
SEED_PLASMAS = [
    ("Hypertherm Powermax 45 XP (45A CNC & Handheld) Cut Settings", 45, 0.250, 72, 0.40, 0.062, 30),
    ("Hypertherm Powermax 30 XP & 30 AIR (30A Dual-Voltage)", 30, 0.188, 55, 0.35, 0.054, 20),
    ("Hypertherm Powermax 65 SYNC (65A CNC Table) Cut Settings", 65, 0.500, 48, 0.65, 0.075, 50),
    ("Hypertherm Powermax 85 SYNC (85A Heavy CNC) Cut Settings", 85, 0.750, 38, 0.85, 0.088, 60),
    ("PrimeWeld CUT60 (60A Non-HF Pilot Arc CNC) Cut Settings", 60, 0.375, 58, 0.50, 0.068, 50),
    ("PrimeWeld CUT50DP (50A Dual-Voltage Pilot Arc) Settings", 50, 0.250, 75, 0.40, 0.062, 40),
    ("Langmuir CrossFire & CrossFire Pro CNC Plasma Table (45A–60A)", 45, 0.250, 70, 0.45, 0.062, 40),
    ("Langmuir CrossFire XR 4x8 CNC Plasma Table (65A–85A)", 65, 0.500, 46, 0.65, 0.074, 50),
    ("ArcDroid Robotic CNC Plasma Arm (45A–60A Non-HF) Settings", 45, 0.188, 105, 0.30, 0.058, 40),
    ("YesWelder CUT-55DS Pro & CUT-65DS Non-HF Pilot Arc Settings", 65, 0.500, 44, 0.65, 0.074, 50),
    ("BestArc BTC500DP & BTC650DP (50A/65A CNC Port) Cut Settings", 50, 0.250, 72, 0.40, 0.062, 40),
    ("Miller Spectrum 625 X-TREME (40A) & 875 Auto-Line (60A)", 60, 0.375, 56, 0.50, 0.068, 50),
    ("Hobart AirForce 40i (40A 240V) & 27i Plasma Cutter Settings", 40, 0.250, 62, 0.45, 0.060, 30),
    ("Lincoln Electric Tomahawk 625 (40A) & 1000 (60A) Settings", 60, 0.375, 56, 0.50, 0.068, 50),
    ("Everlast PowerPlasma 50S / 60S / 80S CNC Pilot Arc Settings", 60, 0.375, 58, 0.50, 0.068, 50),
    ("Lotos LTP5500D & LTP7500D CNC Non-HF Pilot Arc Settings", 55, 0.375, 50, 0.55, 0.066, 40),
    ("16-Gauge (0.060\") Sheet Metal CNC Plasma IPM & FineCut Kerf", 30, 0.060, 210, 0.10, 0.045, 30),
    ("14-Gauge (0.075\") Mild Steel CNC Plasma IPM & Pierce Delay", 40, 0.075, 185, 0.15, 0.052, 30),
    ("10-Gauge (0.135\" / 1/8\") Mild Steel CNC Plasma Cut Settings", 45, 0.135, 135, 0.25, 0.058, 40),
    ("3/16-Inch (0.188\") Mild Steel Plate CNC Plasma Cut Settings", 45, 0.188, 100, 0.30, 0.060, 40),
    ("1/4-Inch (0.250\") Mild Steel Plate CNC Plasma Cut Settings", 45, 0.250, 72, 0.40, 0.062, 40),
    ("3/8-Inch (0.375\") Structural Steel CNC Plasma Cut Settings", 60, 0.375, 58, 0.50, 0.068, 50),
    ("1/2-Inch (0.500\") Heavy Steel Plate CNC Plasma Cut Settings", 65, 0.500, 46, 0.65, 0.075, 50),
    ("5/8-Inch (0.625\") Steel Plate Max CNC Pierce & Edge Start", 85, 0.625, 42, 0.80, 0.084, 60),
    ("3/4-Inch (0.750\") Heavy Plate Plasma Severance & Breaker", 85, 0.750, 34, 1.00, 0.088, 60),
    ("1/4-Inch 304 Stainless Steel CNC Plasma Speed & Nitrogen/Air", 45, 0.250, 62, 0.45, 0.064, 40),
    ("1/4-Inch 6061 Aluminum Plate CNC Plasma Speed & THC Volts", 45, 0.250, 88, 0.35, 0.065, 40),
    ("4-Stage Desiccant Air Dryer CFM & 0.01-Micron Filter Sizing", 60, 0.375, 58, 0.50, 0.068, 50),
    ("NEC Article 630 Plasma Cutter Duty-Cycle Breaker & Wire AWG", 60, 0.375, 58, 0.50, 0.068, 50),
    ("CNC Plasma Water Table Volume & Anti-Rust Nitrite/Green Ratio", 60, 0.250, 72, 0.40, 0.062, 50)
]


def load_json(filepath, default):
    """Self-healing JSON loader: otomatis pulih jika file korup atau kosong."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, type(default)) else default
        except Exception as e:
            print(f"[SELF-HEAL] Recovering {filepath} due to read notice: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=45.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def get_active_gemini_model(api_key):
    """
    LAPIS 1: Mesin Pemindai Versi Model Free Tier Otomatis berbasis Regex tanpa angka versi manual.
    Otomatis mendeteksi model Gemini Flash STABIL generasi tertinggi lintas tahun.
    """
    global _CACHED_MODELS
    if _CACHED_MODELS is not None:
        return _CACHED_MODELS

    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        req = urllib.request.Request(list_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            scored_models = []

            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])

                if "generateContent" not in methods or "flash" not in name.lower():
                    continue

                if any(bad in name.lower() for bad in [
                    "preview", "exp", "thinking", "image", "tts", "audio", "vision", "8b"
                ]):
                    continue

                ver_match = re.search(r"gemini-(\d+(?:\.\d+)?)-flash", name.lower())
                if ver_match:
                    ver_num = float(ver_match.group(1))
                    if name.lower() == f"gemini-{ver_match.group(1)}-flash":
                        tier_score = 2
                    elif name.lower() == f"gemini-{ver_match.group(1)}-flash-lite":
                        tier_score = 1
                    else:
                        tier_score = 0
                    scored_models.append((ver_num, tier_score, name))
                elif name.lower() == "gemini-flash-latest":
                    scored_models.append((0.1, 0, name))

            if scored_models:
                scored_models.sort(key=lambda x: (x[0], x[1]), reverse=True)
                _CACHED_MODELS = [item[2] for item in scored_models[:2]]
                print(f"[GEMINI] Future-proof active models locked: {_CACHED_MODELS}")
                return _CACHED_MODELS
    except Exception as e:
        print(f"[WARN] Dynamic model discovery notice: {e}")

    _CACHED_MODELS = ["gemini-flash-latest"]
    return _CACHED_MODELS


def discover_google_plasma_queries(published_slugs):
    """
    LAPIS 4: 3-Tier Infinite Keyword Supply:
    Tier A: Seed List -> Tier B: Google Suggest US -> Tier C: Combinatorial Metal Thickness × Alloy × Amps Permutator.
    """
    discovered = []
    seeds = [
        "plasma cutter cut chart ",
        "hypertherm 45xp settings for ",
        "primeweld cut60 settings for ",
        "cnc plasma cut speed for "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for pref in seeds:
                        if "for " in pref or "chart " in pref:
                            cleaned = cleaned.replace(pref, "")
                    cleaned = re.sub(
                        r"\b(calculator|size|sizing|chart|manual|review|reddit|for)\b",
                        "",
                        cleaned
                    ).strip()
                    if 5 <= len(cleaned) <= 42:
                        amp_m = re.search(r"\b(30|40|45|50|55|60|65|80|85)\b", cleaned)
                        amp_v = int(amp_m.group(1)) if amp_m else 45
                        discovered.append((cleaned.title(), amp_v, 0.250, 72, 0.40, 0.062, 40))
        except Exception as e:
            print(f"[WARN] Google Suggest notice: {e}")

    # Tier C Fallback: Combinatorial Permutator (Anti-Habis Lintas Tahun)
    metal_gauges = [
        ("18-Gauge (0.048\")", 0.048, 225, 0.08, 0.044),
        ("16-Gauge (0.060\")", 0.060, 200, 0.10, 0.046),
        ("14-Gauge (0.075\")", 0.075, 175, 0.15, 0.050),
        ("12-Gauge (0.105\")", 0.105, 150, 0.20, 0.055),
        ("10-Gauge (0.135\")", 0.135, 125, 0.25, 0.058),
        ("3/16-Inch (0.188\")", 0.188, 95, 0.30, 0.060),
        ("1/4-Inch (0.250\")", 0.250, 72, 0.40, 0.062),
        ("5/16-Inch (0.312\")", 0.312, 62, 0.45, 0.065),
        ("3/8-Inch (0.375\")", 0.375, 54, 0.50, 0.068),
        ("1/2-Inch (0.500\")", 0.500, 42, 0.65, 0.075)
    ]
    alloys = [
        ("A36 Mild Steel", 1.00),
        ("304 Stainless Steel", 0.85),
        ("5052 / 6061 Aluminum", 1.22)
    ]
    amp_classes = [45, 60, 65]
    for g_label, thk_in, base_ipm, p_del, k_in in metal_gauges:
        for al_name, spd_mult in alloys:
            for a_val in amp_classes:
                if thk_in >= 0.500 and a_val < 60:
                    continue
                combo_title = f"{g_label} {al_name} on {a_val}A CNC Plasma"
                test_slug = slugify(f"{combo_title}-ipm-kerf-pierce-calculator")
                if test_slug not in published_slugs:
                    adj_ipm = int(round(base_ipm * spd_mult * (a_val / 45.0)))
                    brk_v = 30 if a_val <= 45 else 50
                    discovered.append((combo_title, a_val, thk_in, adj_ipm, p_del, k_in, brk_v))
                    if len(discovered) >= 25:
                        return discovered
    return discovered


def build_deterministic_plasma_data(pls_tuple):
    """
    LAPIS 3: Mesin Fisika Busur Plasma CNC (IPM, Pierce Delay, Kerf, THC Volts) & NEC 630 (100% Bebas Gagal).
    """
    model_name, cut_amps, thick_in, speed_ipm, pierce_sec, kerf_in, breaker_amps = pls_tuple

    # 1. Parameter Tinggi Torch CNC (Pierce Height, Cut Height, & THC Target Arc Voltage):
    # Standar CNC Torch Height Control (THC): Cut Height = 0.060" (1.5mm); Pierce Height = 2.5x Cut Height = 0.150" (3.8mm)
    cut_height_in = 0.060
    pierce_height_in = 0.150
    thc_arc_volts = int(round(112.0 + (thick_in * 48.0)))

    # 2. Kebutuhan Udara Tekan Kering (Clean Dry Air SCFM @ PSI):
    air_psi = 65 if cut_amps <= 45 else 75
    air_scfm = 4.5 if cut_amps <= 35 else (6.0 if cut_amps <= 50 else 6.7)

    # 3. Kelistrikan Input 240V Single-Phase (NEC Article 630 Electric Welders & Plasma Cutters):
    # Input Power (kW) = (Cut_Amps * Arc_Volts) / (1000 * 0.85 Inverter Efficiency)
    input_kw = round((cut_amps * thc_arc_volts) / (1000.0 * 0.85), 1)
    input_max_amps_240v = round((input_kw * 1000.0) / 240.0, 1)
    # NEC 630.11 Duty Cycle Multiplier (50% Duty Cycle = 0.71x untuk penghantar, tetapi breaker sampai 200% I_1max):
    wire_awg = "10/2 AWG Copper (NEMA 6-50)" if breaker_amps <= 35 else ("8/2 or 6/2 AWG Copper (NEMA 6-50)" if breaker_amps <= 50 else "6/2 AWG Copper (60A Circuit)")

    return {
        "plasma_name": model_name,
        "wire_spec": wire_awg,
        "seo_title": f"{model_name} Cut Speed (IPM), Kerf, Pierce & Breaker Calculator (2026)",
        "meta_description": f"Calculate exact CNC plasma cut speed ({speed_ipm} IPM @ {cut_amps}A), pierce delay ({pierce_sec}s), kerf width ({kerf_in}\"), THC voltage ({thc_arc_volts}V), {air_scfm} SCFM air dryer, and 240V {breaker_amps}A breaker for {model_name}.",
        "specs": {
            "torch_output_amps": cut_amps,
            "material_thickness_in": thick_in,
            "cnc_cut_speed_ipm": speed_ipm,
            "pierce_delay_sec": pierce_sec,
            "pierce_height_in": pierce_height_in,
            "cut_height_in": cut_height_in,
            "kerf_width_in": kerf_in,
            "thc_target_arc_volts": thc_arc_volts,
            "air_pressure_psi": air_psi,
            "air_flow_scfm": air_scfm,
            "input_power_kw": input_kw,
            "input_max_amps_240v": input_max_amps_240v,
            "recommended_breaker_amps": breaker_amps,
            "recommended_wire_awg": wire_awg
        },
        "cnc_verdict": f"Cutting {thick_in:g}-inch metal at {cut_amps} Amps ({model_name}) requires a CNC feed rate of {speed_ipm} IPM (Inches Per Minute), a {pierce_sec}-second pierce delay at {pierce_height_in}\" pierce height before dropping to a {cut_height_in}\" cut height, a CAM kerf width offset of {kerf_in}\", and a Torch Height Control (THC) target of ~{thc_arc_volts}V DC. Supply the torch with {air_scfm} SCFM of moisture-free air at {air_psi} PSI through a 4-stage desiccant dryer. Drawing {input_max_amps_240v}A peak ({input_kw} kW) on 240V single-phase power, NEC Article 630 specifies a {breaker_amps}-Amp 2-pole circuit breaker wired with {wire_awg}.",
        "hardware_bundle": [
            {
                "badge": f"{cut_amps}A CNC Pilot-Arc Plasma",
                "title": f"{cut_amps}A–60A Non-HF Pilot Arc CNC-Ready Inverter Plasma Cutter (120V/240V Dual-Voltage w/ CNC Port)",
                "price_range": "$349 - $1,899",
                "amazon_query": f"Pilot Arc CNC Plasma Cutter {cut_amps}A 60A Non HF 240V PrimeWeld Hypertherm",
                "pls_note": f"Non-High-Frequency (Non-HF) blowback pilot arc starts cleanly without scrambling USB CNC controller electronics."
            },
            {
                "badge": f"{air_scfm} SCFM 4-Stage Air Dryer",
                "title": "4-Stage Compressed Air Drying System (Water Trap + 0.01µm Coalescing Filter + Desiccant Bead Dryer)",
                "price_range": "$119 - $269",
                "amazon_query": "4 Stage 3 Stage Desiccant Air Dryer System Plasma Cutter 0.01 Micron",
                "pls_note": f"Strips 99.99% of oil mist and water vapor at {air_psi} PSI—tripling electrode and nozzle consumable life."
            },
            {
                "badge": f"240V {breaker_amps}A NEMA 6-50 Kit",
                "title": f"Heavy-Duty 240V 50-Amp NEMA 6-50 Extension Cord (25ft–50ft {wire_awg.split()[0]} AWG) + Breaker & Outlet Box",
                "price_range": "$69 - $169",
                "amazon_query": "240V 50 Amp NEMA 6-50 Extension Cord Welder Plasma Cutter 6 AWG 8 AWG",
                "pls_note": f"Handles {input_max_amps_240v}A primary inverter draw with zero voltage sag so the plasma arc never sputters on thick plate."
            },
            {
                "badge": "CNC Consumables & Table Fluid",
                "title": "CNC Shielded / FineCut Torch Consumables Kit (Electrodes + Nozzles) + Plasma Green Water Table Additive",
                "price_range": "$64 - $219",
                "amazon_query": "Plasma Cutter Consumables Kit Electrodes Nozzles CNC Water Table Additive",
                "pls_note": f"Maintains a razor-sharp {kerf_in}\" kerf width and prevents CNC water-table slats from rusting or foaming."
            }
        ],
        "fabricator_checklist": [
            f"Never use a High-Frequency (HF) Start plasma cutter on a CNC table: HF start arcs radiate thousands of volts of EMI noise that freeze USB ports and fry stepper drivers—always use a Non-HF Blowback Pilot Arc cutter ({model_name}).",
            f"Eliminate Low-Speed vs. High-Speed Dross (Slag): if you get thick, bubbly roll-over dross on the bottom edge that peels off easily with pliers, your speed is too SLOW (<{int(speed_ipm * 0.8)} IPM). If you get hard, thin bead dross welded to the bottom that requires heavy grinding, your speed is too FAST (>{int(speed_ipm * 1.15)} IPM) or your torch height is above {cut_height_in}\".",
            f"Set Pierce Height to 2.5x Cut Height ({pierce_height_in}\" Pierce Height vs. {cut_height_in}\" Cut Height): piercing at {cut_height_in}\" blows molten metal straight up into the nozzle orifice, ruining a $12 copper tip on the very first pierce.",
            "Install a Desiccant Silica-Gel Bead Air Dryer directly on the back of the plasma table: compressed air must meet ISO 8573-1 Class 1.2.1 dryness, because moisture in the plasma jet oxidizes the hafnium electrode pit in seconds."
        ],
        "faqs": [
            {
                "q": f"What cut speed (IPM), pierce delay, and kerf width should I use for {model_name}?",
                "a": f"For {thick_in:g}-inch metal at {cut_amps} Amps, program your CAM post-processor (Fusion 360 / SheetCam) to {speed_ipm} IPM cut speed, {pierce_sec} seconds pierce delay, {pierce_height_in}\" pierce height, {cut_height_in}\" cut height, {kerf_in}\" kerf width, and ~{thc_arc_volts}V THC arc voltage."
            },
            {
                "q": f"What size 240V breaker and wire gauge do I need for a {cut_amps}A plasma cutter?",
                "a": f"At {cut_amps}A cutting output and ~{thc_arc_volts}V arc voltage (85% inverter efficiency), the machine draws ~{input_kw} kW ({input_max_amps_240v}A at 240V). Under NEC Article 630 duty-cycle rules, wire a dedicated {breaker_amps}-Amp 2-pole circuit breaker with {wire_awg} to a NEMA 6-50R receptacle."
            },
            {
                "q": f"How much air CFM and PSI does {model_name} require?",
                "a": f"A {cut_amps}A plasma torch requires {air_scfm} SCFM of continuous clean, dry air regulated to {air_psi} PSI while flowing. Pair your compressor with a 0.01-micron coalescing filter and a color-changing silica desiccant dryer."
            }
        ]
    }


def generate_plasma_data(pls_tuple):
    """
    LAPIS 2: Memanggil model Gemini stabil dengan proteksi Cooldown HTTP 429 & Fallback Otomatis.
    """
    if not GEMINI_API_KEY:
        return build_deterministic_plasma_data(pls_tuple)

    model_name, cut_amps, thick_in, speed_ipm, pierce_sec, kerf_in, breaker_amps = pls_tuple
    det_fallback = build_deterministic_plasma_data(pls_tuple)
    sp = det_fallback["specs"]

    prompt = f"""
You are a Certified AWS (American Welding Society) CNC Plasma Fabrication Engineer & NEC Article 630 Specialist. Create an accurate 2026 CNC & handheld plasma cutter cut speed (IPM), pierce delay, kerf width, THC arc voltage, desiccant air dryer CFM, and 240V breaker/wire guide for: "{model_name}".
Baseline specs: Torch Output={cut_amps}A, Thickness={thick_in}", Cut Speed={speed_ipm} IPM, Pierce Delay={pierce_sec}s (Pierce Height={sp['pierce_height_in']}", Cut Height={sp['cut_height_in']}"), Kerf Width={kerf_in}", THC Voltage={sp['thc_target_arc_volts']}V, Air={sp['air_flow_scfm']} SCFM @ {sp['air_pressure_psi']} PSI, Electrical={sp['input_power_kw']} kW ({sp['input_max_amps_240v']}A @ 240V -> {breaker_amps}A Breaker, {sp['recommended_wire_awg']}).
Return ONLY a valid JSON object matching this exact schema:
{{
  "plasma_name": "{model_name}",
  "wire_spec": "{sp['recommended_wire_awg']}",
  "seo_title": "{model_name} Cut Speed (IPM), Kerf, Pierce & Breaker Calculator (2026)",
  "meta_description": "Calculate exact CNC plasma cut speed (IPM), pierce delay, kerf width, THC arc voltage, air CFM, and 240V breaker size for {model_name}.",
  "specs": {{
    "torch_output_amps": {cut_amps},
    "material_thickness_in": {thick_in},
    "cnc_cut_speed_ipm": {speed_ipm},
    "pierce_delay_sec": {pierce_sec},
    "pierce_height_in": {sp['pierce_height_in']},
    "cut_height_in": {sp['cut_height_in']},
    "kerf_width_in": {kerf_in},
    "thc_target_arc_volts": {sp['thc_target_arc_volts']},
    "air_pressure_psi": {sp['air_pressure_psi']},
    "air_flow_scfm": {sp['air_flow_scfm']},
    "input_power_kw": {sp['input_power_kw']},
    "input_max_amps_240v": {sp['input_max_amps_240v']},
    "recommended_breaker_amps": {breaker_amps},
    "recommended_wire_awg": "{sp['recommended_wire_awg']}"
  }},
  "cnc_verdict": "3-sentence technical summary stating IPM cut speed, pierce delay/height, kerf width, THC volts, SCFM @ PSI air requirement, and 240V NEC 630 breaker/wire specs.",
  "hardware_bundle": [
    {{
      "badge": "{cut_amps}A CNC Pilot-Arc Plasma",
      "title": "{cut_amps}A–60A Non-HF Pilot Arc CNC-Ready Inverter Plasma Cutter (120V/240V)",
      "price_range": "$349 - $1,899",
      "amazon_query": "Pilot Arc CNC Plasma Cutter {cut_amps}A 60A Non HF 240V PrimeWeld",
      "pls_note": "1-sentence non-HF blowback arc and CNC port note"
    }},
    {{
      "badge": "{sp['air_flow_scfm']} SCFM 4-Stage Air Dryer",
      "title": "4-Stage Compressed Air Drying System (0.01µm Coalescing + Desiccant Bead Dryer)",
      "price_range": "$119 - $269",
      "amazon_query": "4 Stage Desiccant Air Dryer System Plasma Cutter 0.01 Micron",
      "pls_note": "1-sentence moisture removal and hafnium electrode protection note"
    }},
    {{
      "badge": "240V {breaker_amps}A NEMA 6-50 Kit",
      "title": "Heavy-Duty 240V 50A NEMA 6-50 Extension Cord + Breaker & Receptacle Box",
      "price_range": "$69 - $169",
      "amazon_query": "240V 50 Amp NEMA 6-50 Extension Cord Welder Plasma Cutter",
      "pls_note": "1-sentence voltage drop prevention and NEC 630 compliance note"
    }},
    {{
      "badge": "Consumables & Water Additive",
      "title": "CNC Shielded Torch Consumables Kit + Plasma Green Water Table Anti-Rust Fluid",
      "price_range": "$64 - $219",
      "amazon_query": "Plasma Cutter Consumables Kit Electrodes Nozzles CNC Water Table Additive",
      "pls_note": "1-sentence kerf precision and slat corrosion protection note"
    }}
  ],
  "fabricator_checklist": [
    "Step 1 regarding Non-HF blowback pilot arc vs HF EMI interference on CNC tables",
    "Step 2 regarding diagnosing low-speed dross vs high-speed dross at {speed_ipm} IPM",
    "Step 3 regarding 0.150-inch pierce height vs 0.060-inch cut height",
    "Step 4 regarding ISO 8573-1 desiccant air drying to prevent nozzle blowouts"
  ],
  "faqs": [
    {{"q": "What IPM speed, pierce delay, and kerf width should I use for {model_name}?", "a": "Exact IPM, pierce delay in seconds, pierce/cut height, and kerf width in inches."}},
    {{"q": "What size 240V breaker and wire gauge do I need for {model_name}?", "a": "Exact primary amps, kW, NEC 630 breaker, and copper AWG."}},
    {{"q": "How do I stop beveling and dross on my CNC plasma cuts?", "a": "Direct troubleshooting of swirl ring orientation, air dryness, cut height, and IPM speed."}}
  ]
}}
"""

    for model_id in get_active_gemini_model(GEMINI_API_KEY):
        for attempt in range(2):
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json"
                    }
                }
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=40) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                    parsed = json.loads(raw_text)
                    if "specs" in parsed and "hardware_bundle" in parsed:
                        time.sleep(6)
                        return parsed
            except urllib.error.HTTPError as he:
                if he.code == 429:
                    print(f"[RATE-LIMIT] HTTP 429 on {model_id} (attempt {attempt + 1}). Cooling down 20s...")
                    time.sleep(20)
                else:
                    print(f"[WARN] HTTP {he.code} on {model_id} for '{model_name}': {he}")
                    break
            except Exception as e:
                print(f"[WARN] Gemini ({model_id}) notice for '{model_name}': {e}")
                break

    return det_fallback


def build_plasma_html_page(data, slug, mon_cfg):
    pls_name = data.get("plasma_name", "CNC Plasma Cutter Setup")
    sp = data.get("specs", {})
    c_amps = int(safe_float(sp.get("torch_output_amps", 45), 45))
    thk_in = round(safe_float(sp.get("material_thickness_in", 0.250), 0.250), 3)
    ipm = int(safe_float(sp.get("cnc_cut_speed_ipm", 72), 72))
    p_sec = round(safe_float(sp.get("pierce_delay_sec", 0.40), 0.40), 2)
    kerf_in = round(safe_float(sp.get("kerf_width_in", 0.062), 0.062), 3)
    thc_v = int(safe_float(sp.get("thc_target_arc_volts", 124), 124))
    scfm = round(safe_float(sp.get("air_flow_scfm", 6.0), 6.0), 1)
    psi = int(safe_float(sp.get("air_pressure_psi", 65), 65))
    brk_a = int(safe_float(sp.get("recommended_breaker_amps", 40), 40))
    wire_s = sp.get("recommended_wire_awg", "8/2 AWG Copper (NEMA 6-50)")

    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "Pilot+Arc+Plasma+Cutter+60A+CNC+Desiccant+Air+Dryer"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{pls_name} IPM Speed, Kerf & Pierce Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    bundle_html = ""
    for item in data.get("hardware_bundle", []):
        amz_url = build_amazon_url(item.get("amazon_query", item.get("title", "CNC Pilot Arc Plasma Cutter")), mon_cfg)
        bundle_html += f"""
        <div class="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex flex-col justify-between hover:border-cyan-500/60 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-2.5 py-0.5 rounded">{item.get('badge', 'Plasma Gear')}</span>
              <span class="text-sm font-bold text-emerald-400">{item.get('price_range', '$69+')}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-2">{item.get('title', '')}</h3>
            <p class="text-xs text-zinc-400 mt-2 leading-relaxed">⚡ {item.get('pls_note', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-cyan-500 hover:bg-cyan-400 text-zinc-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price on Amazon →
          </a>
        </div>"""

    # Build Mild Steel Thickness vs IPM Cut Speed, Pierce Delay, Kerf Width & THC Volts Reference Matrix Table
    pls_tiers = [
        ("16 GA (0.060\" / 1.5mm)", "30A – 45A", "195 – 225 IPM", "0.10 sec", "0.048\" Kerf | 115V THC"),
        ("10 GA (0.135\" / 1/8\")", "45A Output", "125 – 140 IPM", "0.25 sec", "0.058\" Kerf | 118V THC"),
        ("3/16\" Plate (0.188\")", "45A – 50A", "95 – 105 IPM", "0.30 sec", "0.060\" Kerf | 121V THC"),
        ("1/4\" Plate (0.250\")", "45A – 60A", "70 – 85 IPM", "0.40 sec", "0.062\" Kerf | 124V THC"),
        ("3/8\" Plate (0.375\")", "60A – 65A", "54 – 64 IPM", "0.50 sec", "0.068\" Kerf | 130V THC"),
        ("1/2\" Plate (0.500\")", "65A – 85A", "42 – 52 IPM", "0.65 sec", "0.075\" Kerf | 136V THC")
    ]
    matrix_rows_html = ""
    for m_lbl, a_lbl, s_lbl, p_lbl, k_lbl in pls_tiers:
        matrix_rows_html += f"""
        <tr class="border-b border-zinc-800 hover:bg-zinc-800/40">
          <td class="py-3 px-4 font-bold text-white">{m_lbl}</td>
          <td class="py-3 px-4 text-zinc-300">{a_lbl}</td>
          <td class="py-3 px-4 font-bold text-cyan-400">{s_lbl}</td>
          <td class="py-3 px-4 text-emerald-400 font-semibold">{p_lbl}</td>
          <td class="py-3 px-4 text-xs text-zinc-300">{k_lbl}</td>
        </tr>"""

    checklist_html = ""
    for idx, step_text in enumerate(data.get("fabricator_checklist", []), start=1):
        checklist_html += f"""
        <label class="flex items-start gap-3.5 bg-zinc-900 border border-zinc-800 rounded-xl p-4 cursor-pointer hover:border-zinc-700 transition">
          <input type="checkbox" class="mt-1 w-5 h-5 accent-cyan-500 rounded cursor-pointer pls-check">
          <span class="text-sm text-zinc-200 leading-relaxed"><strong>CNC Plasma Step {idx}:</strong> {step_text}</span>
        </label>"""

    faqs_html = "".join([
        f"<div class='bg-zinc-900 border border-zinc-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-zinc-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"
    amz_domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    amz_tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', pls_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', pls_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-zinc-950 text-zinc-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-cyan-500 text-zinc-950 px-2 py-0.5 rounded font-black">PLASMA</span>CutIndex
      </a>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-cyan-500 hover:bg-cyan-400 text-zinc-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Plasma Cutters & Air Dryers →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-cyan-500 text-zinc-950 px-3 py-1 rounded-full">{ipm} IPM @ {c_amps}A ({thk_in:g}" Metal)</span>
        <span class="text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full">Pierce: {p_sec}s | Kerf: {kerf_in}" | THC: {thc_v}V</span>
        <span class="text-xs font-semibold bg-zinc-800 text-zinc-300 px-3 py-1 rounded-full">Air: {scfm} SCFM @ {psi} PSI | 240V {brk_a}A</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', pls_name)}</h1>
      <div class="mt-4 bg-zinc-900 border-l-4 border-cyan-500 p-4 rounded-r-xl text-sm text-zinc-200 leading-relaxed">
        <strong>AWS CNC Plasma & NEC 630 Verdict:</strong> {data.get('cnc_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE CNC PLASMA CUT SPEED (IPM), PIERCE DELAY, KERF & BREAKER CALCULATOR -->
    <section class="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {pls_name} IPM Speed, Kerf & Breaker Calculator</h2>
      <p class="text-xs text-zinc-400 mb-6">Select your metal thickness, metal alloy type, and plasma torch amperage to compute exact SheetCam / Fusion 360 cut speed (IPM), pierce delay (sec), kerf width offset, THC target voltage, and 240V breaker size.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div>
            <label for="thickSelect" class="block text-xs font-medium text-zinc-400 mb-1">Material Gauge / Plate Thickness</label>
            <select id="thickSelect" class="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm font-bold text-white focus:outline-none focus:border-cyan-500">
              <option value="0.060|205|0.10|0.048" {"selected" if thk_in <= 0.065 else ""}>16 GA (0.060" / 1.5mm Sheet)</option>
              <option value="0.075|180|0.15|0.052" {"selected" if 0.065 < thk_in <= 0.090 else ""}>14 GA (0.075" / 1.9mm Sheet)</option>
              <option value="0.105|150|0.20|0.055" {"selected" if 0.090 < thk_in <= 0.120 else ""}>12 GA (0.105" / 2.7mm Sheet)</option>
              <option value="0.135|130|0.25|0.058" {"selected" if 0.120 < thk_in <= 0.160 else ""}>10 GA (0.135" / 1/8" Plate)</option>
              <option value="0.188|98|0.30|0.060" {"selected" if 0.160 < thk_in <= 0.210 else ""}>3/16" Plate (0.188" / 4.8mm)</option>
              <option value="0.250|72|0.40|0.062" {"selected" if 0.210 < thk_in <= 0.300 else ""}>1/4" Plate (0.250" / 6.4mm)</option>
              <option value="0.375|48|0.55|0.068" {"selected" if 0.300 < thk_in <= 0.420 else ""}>3/8" Plate (0.375" / 9.5mm)</option>
              <option value="0.500|35|0.70|0.075" {"selected" if 0.420 < thk_in <= 0.560 else ""}>1/2" Plate (0.500" / 12.7mm)</option>
              <option value="0.750|22|1.00|0.088" {"selected" if thk_in > 0.560 else ""}>3/4" Heavy Plate (0.750" / 19mm)</option>
            </select>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="alloySelect" class="block text-xs font-medium text-zinc-400 mb-1">Metal Alloy Type</label>
              <select id="alloySelect" class="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                <option value="1.00" selected>Mild / Carbon Steel (1.0x IPM)</option>
                <option value="0.85">304 / 316 Stainless Steel (0.85x IPM)</option>
                <option value="1.22">5052 / 6061 Aluminum (1.22x IPM)</option>
              </select>
            </div>
            <div>
              <label for="ampSlider" class="block text-xs font-medium text-zinc-400 mb-1">Plasma Torch Output: <span id="ampVal" class="text-cyan-400 font-bold">{c_amps}A</span></label>
              <input id="ampSlider" type="range" min="25" max="85" step="5" value="{c_amps}" class="w-full accent-cyan-500 cursor-pointer mt-1.5">
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-zinc-950 border border-cyan-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-cyan-400 font-bold">CNC Feed & Pierce</span>
            <div class="text-2xl sm:text-3xl font-black text-white mt-1"><span id="ipmOut">{ipm}</span> <span class="text-xs font-normal text-zinc-400">IPM</span></div>
            <p id="pierceKerfOut" class="text-xs text-cyan-400 font-semibold mt-1">Pierce: {p_sec}s | Kerf: {kerf_in}"</p>
          </div>

          <div class="bg-zinc-950 border border-emerald-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-emerald-400 font-bold">THC Volts & 240V Circuit</span>
            <div id="thcOut" class="text-xl sm:text-2xl font-black text-emerald-400 mt-1">{thc_v}V THC (0.06" Ht)</div>
            <p id="brkAirOut" class="text-xs text-zinc-300 font-semibold mt-1">{brk_a}A Breaker | {scfm} SCFM@{psi}PSI</p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-cyan-950/40 border border-cyan-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div id="plsAdviceBanner" class="text-sm text-cyan-100 font-medium"></div>
        <a id="dynamicPlsBtn" href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-cyan-500 hover:bg-cyan-400 text-zinc-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Shop Matched Plasma Cutter & Dryer on Amazon →
        </a>
      </div>
    </section>

    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Complete {pls_name} Cutter, Air Dryer & Cord Bundle</h2>
        <span class="text-xs text-zinc-400">ISO 8573-1 Dry Air & NEC Article 630 Rated</span>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{bundle_html}</div>
    </section>

    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">CNC Plasma Cut Chart: Metal Thickness, IPM Speed, Pierce Delay & Kerf Width</h2>
      <div class="overflow-x-auto bg-zinc-900 border border-zinc-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-zinc-800 bg-zinc-950/60 text-zinc-400 uppercase text-xs">
              <th class="py-3.5 px-4">Mild Steel Thickness</th>
              <th class="py-3.5 px-4">Torch Amps</th>
              <th class="py-3.5 px-4 text-cyan-400">Cut Speed (IPM)</th>
              <th class="py-3.5 px-4 text-emerald-400">Pierce Delay</th>
              <th class="py-3.5 px-4">Kerf Width & THC Volts</th>
            </tr>
          </thead>
          <tbody>{matrix_rows_html}</tbody>
        </table>
      </div>
    </section>

    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">CNC Plasma Non-HF Pilot Arc, Desiccant Dryer & Dross-Free Checklist</h2>
        <span id="plsBadge" class="text-xs font-bold bg-zinc-800 text-cyan-400 px-3 py-1 rounded-full">0 / 4 Completed</span>
      </div>
      <div class="space-y-3">{checklist_html}</div>
    </section>

    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({pls_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-zinc-800 py-8 text-center text-xs text-zinc-500 px-4">
    <p>© {datetime.now(timezone.utc).year} PlasmaCutIndex. Independent CNC Plasma Cut Speed, Kerf & NEC 630 Electrical Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const amzDomain = "{amz_domain}";
    const amzTag = "{amz_tag}";

    const thickSelect = document.getElementById('thickSelect');
    const alloySelect = document.getElementById('alloySelect');
    const ampSlider = document.getElementById('ampSlider');
    const ampVal = document.getElementById('ampVal');
    const ipmOut = document.getElementById('ipmOut');
    const pierceKerfOut = document.getElementById('pierceKerfOut');
    const thcOut = document.getElementById('thcOut');
    const brkAirOut = document.getElementById('brkAirOut');
    const plsAdviceBanner = document.getElementById('plsAdviceBanner');
    const dynamicPlsBtn = document.getElementById('dynamicPlsBtn');

    function recalculatePlasma() {{
      const thkParts = thickSelect.value.split('|');
      const thkIn = parseFloat(thkParts[0]);
      const baseIpm45 = parseInt(thkParts[1], 10);
      const basePierce = parseFloat(thkParts[2]);
      const baseKerf = parseFloat(thkParts[3]);
      const alloyMult = parseFloat(alloySelect.value);
      const amps = parseInt(ampSlider.value, 10);

      ampVal.textContent = `${{amps}}A`;

      const calcIpm = Math.max(12, Math.round(baseIpm45 * alloyMult * (amps / 45.0)));
      const calcPierce = Math.max(0.08, (basePierce * (45.0 / amps))).toFixed(2);
      const calcKerf = (baseKerf + ((amps - 45) * 0.0004)).toFixed(3);
      const thcVolts = Math.round(112.0 + (thkIn * 48.0));

      const scfm = amps <= 35 ? "4.5" : (amps <= 50 ? "6.0" : "6.7");
      const psi = amps <= 45 ? 65 : 75;
      const brkSpec = amps <= 35 ? "30A (10 AWG)" : (amps <= 60 ? "50A (8/6 AWG)" : "60A (6 AWG)");

      ipmOut.textContent = calcIpm;
      pierceKerfOut.textContent = `Pierce: ${{calcPierce}}s | Kerf: ${{calcKerf}}"`;
      thcOut.textContent = `${{thcVolts}}V THC (0.06" Ht)`;
      brkAirOut.textContent = `${{brkSpec}} | ${{scfm}} SCFM@${{psi}}PSI`;

      plsAdviceBanner.innerHTML = `⚡ <strong>SheetCam / Fusion 360 Spec:</strong> Set feed rate to <strong>${{calcIpm}} IPM</strong>, pierce delay to <strong>${{calcPierce}}s</strong> (0.15" pierce height / 0.06" cut height), and kerf width to <strong>${{calcKerf}}"</strong>. Pair your <strong>${{amps}}A Non-HF Pilot Arc Plasma Cutter</strong> with a <strong>4-Stage Desiccant Air Dryer (${{scfm}} SCFM @ ${{psi}} PSI)</strong> on a <strong>240V ${{brkSpec}} circuit</strong>.`;
      dynamicPlsBtn.href = `https://${{amzDomain}}/s?k=Pilot+Arc+CNC+Plasma+Cutter+${{amps}}A+Desiccant+Air+Dryer+System&tag=${{amzTag}}`;
    }}

    thickSelect.addEventListener('change', recalculatePlasma);
    alloySelect.addEventListener('change', recalculatePlasma);
    ampSlider.addEventListener('input', recalculatePlasma);
    recalculatePlasma();

    const checks = document.querySelectorAll('.pls-check');
    const badge = document.getElementById('plsBadge');
    checks.forEach(ch => {{
      ch.addEventListener('change', () => {{
        const done = Array.from(checks).filter(c => c.checked).length;
        badge.textContent = `${{done}} / ${{checks.length}} Completed`;
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "Pilot+Arc+Plasma+Cutter+60A+CNC+Desiccant+Air+Dryer"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-zinc-900 border border-zinc-800 hover:border-cyan-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-cyan-500 text-zinc-950 px-2.5 py-0.5 rounded">{item.get('ipm', 72)} IPM @ {item.get('amps', 45)}A</span>
            <span class="text-xs text-zinc-400">Pierce: {item.get('pierce', 0.40)}s | {item.get('kerf', 0.062)}" Kerf</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-cyan-400 transition">{item['plasma_name']}</h2>
          <p class="text-xs text-zinc-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-cyan-400">Calculate IPM, Kerf & Pierce Delay →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PlasmaCutIndex — CNC Plasma Cut Speed (IPM), Kerf Width, Pierce Delay & Breaker Calculator (2026)</title>
  <meta name="description" content="Calculate exact CNC and handheld plasma cutter feed rate (IPM), SheetCam and Fusion 360 kerf width offset, pierce delay, THC arc voltage, desiccant air dryer CFM, and 240V breaker size for Hypertherm, PrimeWeld, Langmuir CrossFire, and YesWelder setups.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="PlasmaCutIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen flex flex-col">
  <header class="border-b border-zinc-800 bg-zinc-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-cyan-500 text-zinc-950 px-2 py-0.5 rounded font-black">PLASMA</span>CutIndex
      </div>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-cyan-500 hover:bg-cyan-400 text-zinc-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Plasma Cutters & Air Dryers →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">CNC Plasma Cut Speed (IPM), Kerf Width & Pierce Delay Database</h1>
      <p class="text-zinc-400 mt-3 text-base sm:text-lg">Select your plasma cutter model, CNC table, or metal thickness below to calculate G-code IPM feed rates, pierce delay seconds, kerf width compensation, desiccant air dryer CFM, and 240V breaker sizing.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search plasma cutter or thickness (e.g. Hypertherm 45 XP, PrimeWeld CUT60, Langmuir CrossFire, 1/4 Steel, 3/8 Plate...)" class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-cyan-500">
      </div>
    </div>

    <div id="plsGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-zinc-800 py-8 text-center text-xs text-zinc-500">
    <p>© {datetime.now(timezone.utc).year} PlasmaCutIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('plsGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>PlasmaCutIndex CNC Plasma Cut Speed & CAM Settings Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive CNC Plasma Cut Speed (IPM), Kerf Width, Pierce Delay & 240V Breaker Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    """Multi-Endpoint Search Engine Pinger (IndexNow Global + Bing + Google WebSub)."""
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    for idx_endpoint in ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow"]:
        try:
            req = urllib.request.Request(
                idx_endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"[INDEXNOW] Pushed {len(new_urls)} URLs to {idx_endpoint} (HTTP {resp.status})")
                break
        except Exception as e:
            print(f"[WARN] IndexNow ({idx_endpoint}) notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published if "slug" in item}

    candidates = []
    if CUSTOM_PLASMA:
        candidates.append((CUSTOM_PLASMA.strip(), 45, 0.250, 72, 0.40, 0.062, 40))
    candidates.extend(SEED_PLASMAS)
    candidates.extend(discover_google_plasma_queries(published_slugs))

    new_urls = []
    count = 0

    for pls_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        p_name = pls_tuple[0]
        slug = slugify(f"{p_name}-ipm-kerf-pierce-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Generating CNC plasma cut speed & kerf calculator for: {p_name}...")
        try:
            data = generate_plasma_data(pls_tuple)
            build_plasma_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "plasma_name": data.get("plasma_name", p_name),
                "slug": slug,
                "title": data.get("seo_title", f"{p_name} Plasma Cut Calculator"),
                "description": data.get("meta_description", ""),
                "amps": int(safe_float(sp.get("torch_output_amps", pls_tuple[1]), pls_tuple[1])),
                "ipm": int(safe_float(sp.get("cnc_cut_speed_ipm", pls_tuple[3]), pls_tuple[3])),
                "pierce": round(safe_float(sp.get("pierce_delay_sec", pls_tuple[4]), pls_tuple[4]), 2),
                "kerf": round(safe_float(sp.get("kerf_width_in", pls_tuple[5]), pls_tuple[5]), 3),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            if count < PAGES_PER_RUN:
                time.sleep(15)
        except Exception as e:
            print(f"[ERROR] Failed building {p_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new CNC plasma cut speed & kerf calculator pages.")


if __name__ == "__main__":
    main()
