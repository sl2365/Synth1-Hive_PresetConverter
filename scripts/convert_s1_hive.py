import sys
import time
from pathlib import Path
from collections import OrderedDict
import math
import re


if getattr(sys, "frozen", False):
    SCRIPT_DIR = Path(sys.executable).resolve().parent
else:
    SCRIPT_DIR = Path(__file__).resolve().parent

BASE_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() == "scripts" else SCRIPT_DIR

INIT_FILE = BASE_DIR / "ConverterINIT.h2p"
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

ENV_TIME_REDUCTION_PERCENT_LOW = 10.0
ENV_TIME_REDUCTION_PERCENT_HIGH = 20.0
ENV_TIME_HIGH_THRESHOLD = 80

# -------------------------------------------------
# Hive parsing / writing
# -------------------------------------------------

def strip_blob(text: str) -> str:
    idx = text.find("\n$$$$")
    if idx != -1:
        return text[:idx]
    idx = text.find("$$$$")
    if idx != -1:
        return text[:idx]
    return text


def extract_blob(text: str):
    idx = text.find("\n$$$$")
    if idx != -1:
        return text[idx + 1:]  # keep blob starting from $$$$
    idx = text.find("$$$$")
    if idx != -1:
        return text[idx:]
    return ""


def parse_h2p(path: Path):
    full_text = path.read_text(encoding="utf-8", errors="ignore")
    blob_text = extract_blob(full_text)
    text = strip_blob(full_text)

    data = OrderedDict()
    order = []
    header_lines = []
    current_section = None
    seen_first_section = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")

        if line.startswith("#cm="):
            seen_first_section = True
            current_section = line[4:].strip()
            if current_section not in data:
                data[current_section] = OrderedDict()
                order.append(current_section)
            continue

        if not seen_first_section:
            stripped = line.strip()
            if stripped:
                header_lines.append(line)
            continue

        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            continue

        if stripped.startswith("//"):
            continue

        if stripped.startswith("/*") or stripped.startswith("*/"):
            continue

        if "=" in stripped:
            if current_section is None:
                current_section = "__global__"
                if current_section not in data:
                    data[current_section] = OrderedDict()
                    order.append(current_section)

            key, value = stripped.split("=", 1)
            data[current_section][key.strip()] = value.strip()

    return data, order, header_lines, blob_text


def write_h2p(path: Path, data, order, header_lines, blob_text="", meta_lines=None):
    lines = []

    cleaned_header_lines = strip_existing_meta_from_header(header_lines)

    if meta_lines:
        lines.extend(meta_lines)

    if cleaned_header_lines:
        if lines:
            lines.append("")
        lines.extend(cleaned_header_lines)
    else:
        if not lines:
            lines.append("#AM=Hive")
            lines.append("#Vers=200")
            lines.append("#Endian=little")

    for section in order:
        if section == "__global__":
            for key, value in data[section].items():
                lines.append(f"{key}={value}")
            continue

        lines.append(f"#cm={section}")
        for key, value in data[section].items():
            lines.append(f"{key}={value}")

    text = "\n".join(lines) + "\n"

    if blob_text:
        if not text.endswith("\n"):
            text += "\n"
        text += blob_text
        if not text.endswith("\n"):
            text += "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def set_hive(data, section, key, value):
    if section not in data:
        data[section] = OrderedDict()
    data[section][key] = format_hive_value(value)


def format_hive_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def init_lfo_matrix_sources(hive_data):
    # These must always exist for every converted preset
    set_hive(hive_data, "MM1", "Active", 0)
    set_hive(hive_data, "MM1", "Source", 29)  # LFO1
    set_hive(hive_data, "MM1", "Dest1", "none:assigned")
    set_hive(hive_data, "MM1", "Depth1", 0.0)
    set_hive(hive_data, "MM1", "Dest2", "none:assigned")
    set_hive(hive_data, "MM1", "Depth2", 0.0)

    set_hive(hive_data, "MM2", "Active", 0)
    set_hive(hive_data, "MM2", "Source", 30)  # LFO2
    set_hive(hive_data, "MM2", "Dest1", "none:assigned")
    set_hive(hive_data, "MM2", "Depth1", 0.0)
    set_hive(hive_data, "MM2", "Dest2", "none:assigned")
    set_hive(hive_data, "MM2", "Depth2", 0.0)


# -------------------------------------------------
# Synth1 parsing
# -------------------------------------------------

def parse_synth1_preset(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    result = {
        "name": "",
        "color": None,
        "ver": None,
        "params": {}
    }

    for line in lines:
        if "," in line and line[0].isdigit():
            left, right = line.split(",", 1)
            try:
                pid = int(left.strip())
                val = int(right.strip())
                result["params"][pid] = val
            except ValueError:
                pass
        elif line.startswith("color="):
            result["color"] = line.split("=", 1)[1].strip()
        elif line.startswith("ver="):
            try:
                result["ver"] = int(line.split("=", 1)[1].strip())
            except ValueError:
                result["ver"] = line.split("=", 1)[1].strip()
        else:
            if not result["name"]:
                result["name"] = line

    return result


# -------------------------------------------------
# Naming helpers
# -------------------------------------------------

def roman_to_int(token: str):
    values = {
        "I": 1,
        "V": 5,
        "X": 10,
        "L": 50,
        "C": 100,
        "D": 500,
        "M": 1000,
    }

    token = token.upper().strip()
    if not token:
        return None

    total = 0
    prev = 0
    for ch in reversed(token):
        if ch not in values:
            return None
        val = values[ch]
        if val < prev:
            total -= val
        else:
            total += val
            prev = val

    return total


def replace_safe_roman_numerals(name: str) -> str:
    # Convert standalone roman numeral words conservatively.
    # Intentionally skip lone "I" because it is too ambiguous.

    roman_map = {
        "II": 2,
        "III": 3,
        "IV": 4,
        "V": 5,
        "VI": 6,
        "VII": 7,
        "VIII": 8,
        "IX": 9,
        "X": 10,
        "XI": 11,
        "XII": 12,
        "XIII": 13,
        "XIV": 14,
        "XV": 15,
        "XVI": 16,
        "XVII": 17,
        "XVIII": 18,
        "XIX": 19,
        "XX": 20,
    }

    parts = re.split(r"(\W+)", name)

    for i, part in enumerate(parts):
        token = part.strip()
        if token in roman_map:
            parts[i] = str(roman_map[token])

    return "".join(parts)

def sanitize_patch_name(name: str) -> str:
    if not name:
        return "Unnamed"

    name = name.replace("Synth1", "").strip()
    name = re.sub(r"\s+", " ", name).strip()
    name = replace_safe_roman_numerals(name)

    words = name.split(" ")
    out_words = []
    small_words = {"a", "an", "and", "the", "of", "to", "in", "on", "for", "at", "by"}

    for i, w in enumerate(words):
        if not w:
            continue
        if i == 0:
            out_words.append(w[:1].upper() + w[1:])
        else:
            if w.lower() in small_words:
                out_words.append(w.lower())
            else:
                out_words.append(w[:1].upper() + w[1:])

    name = " ".join(out_words)
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name.strip() or "Unnamed"


def clean_meta_text(value: str) -> str:
    if value is None:
        return ""

    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("'", "")

    cleaned_lines = []
    for line in value.splitlines():
        stripped = line.strip()

        # If line is made only of repeated separator chars, shorten it
        if stripped and len(set(stripped)) == 1 and stripped[0] in "-_=*~#.":
            stripped = stripped[0] * min(len(stripped), 30)

        cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines).strip()


def get_bank_name_from_folder(folder: Path) -> str:
    return clean_meta_text(folder.name)


def get_readme_description(folder: Path) -> str:
    readme_path = folder / "readme.txt"
    if not readme_path.exists():
        return ""

    text = readme_path.read_text(encoding="utf-8", errors="ignore")
    return clean_meta_text(text)


def build_meta_header(bank_name: str, description: str) -> list[str]:
    lines = [
        "/*@Meta",
        "",
        "Bank:",
        f"'{bank_name}'",
        "",
        "Author:",
        "'sl23 (Synth1 Conversion)'",
        "",
        "Description:",
        f"'{description}'",
        "",
        "*/",
    ]
    return lines


def strip_existing_meta_from_header(header_lines):
    if not header_lines:
        return []

    out = []
    in_meta = False

    for line in header_lines:
        stripped = line.strip()

        if stripped.startswith("/*@Meta"):
            in_meta = True
            continue

        if in_meta:
            if stripped == "*/":
                in_meta = False
            continue

        out.append(line)

    return out


# -------------------------------------------------
# Utility / scaling helpers
# -------------------------------------------------

def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def scale_linear(v, in_min, in_max, out_min, out_max):
    if in_max == in_min:
        return out_min
    ratio = (v - in_min) / (in_max - in_min)
    return out_min + ratio * (out_max - out_min)


def scale_0_127_to_100(v):
    return scale_linear(v, 0, 127, 0.0, 100.0)


def scale_0_127_to_50(v):
    return scale_linear(v, 0, 127, 0.0, 50.0)


def scale_0_127_to_150_cutoff(v):
    # Based on your measured Hive report:
    # Min = 30, Mid approx 90, Max = 150
    return scale_linear(v, 0, 127, 30.0, 150.0)


def scale_0_127_center_63_to_bipolar_100(v):
    return ((v - 63.0) / 64.0) * 100.0


def scale_0_127_center_64_to_bipolar_100(v):
    if v >= 64:
        return ((v - 64.0) / 63.0) * 100.0
    return ((v - 64.0) / 64.0) * 100.0


def scale_0_127_to_pan(v):
    # Synth1 0..127 where 64=center
    return scale_0_127_center_64_to_bipolar_100(v)


def scale_fx_level_half_wet(v):
    # Synth1 FX level acts more like level than full wet/dry.
    # Restrict to 0..50 in Hive.
    return scale_0_127_to_50(v)


def s1_mix_to_hive_volumes(v):
    # Synth1: 0 osc1 only, 63 center, 127 osc2 only
    osc2 = v / 127.0
    osc1 = 1.0 - osc2
    return osc1 * 100.0, osc2 * 100.0


def s1_pitch_to_hive_octave_semi(v):
    # Synth1 osc2 pitch centered at 64, approx -60..+60 semitones
    semis = v - 64
    octave = int(math.floor(semis / 12.0))
    semi = semis - (octave * 12)

    while semi > 11:
        semi -= 12
        octave += 1
    while semi < -11:
        semi += 12
        octave -= 1

    octave = clamp(octave, -4, 4)
    semi = clamp(semi, -12, 12)
    return octave, semi


def adjust_env_time_value(v):
    if v <= ENV_TIME_HIGH_THRESHOLD:
        percent = ENV_TIME_REDUCTION_PERCENT_LOW
    else:
        extra = (v - ENV_TIME_HIGH_THRESHOLD) / (127 - ENV_TIME_HIGH_THRESHOLD)
        percent = ENV_TIME_REDUCTION_PERCENT_LOW + (
            (ENV_TIME_REDUCTION_PERCENT_HIGH - ENV_TIME_REDUCTION_PERCENT_LOW) * extra
        )

    factor = 1.0 - (percent / 100.0)
    return clamp(v * factor, 0, 127)


# -------------------------------------------------
# Mappings confirmed from your reports
# -------------------------------------------------

def map_s1_wave_to_hive(v):
    # Synth1 osc1: 0=Sine,1=Saw,2=Square,3=Tri
    # Hive:        Sine=0,Saw=1,Pulse=3,Tri=2
    return {
        0: 0,
        1: 1,
        2: 3,
        3: 2,
    }.get(v, 1)


def map_s1_osc2_wave_to_hive(v):
    # Synth1 osc2: 1=Saw,2=Square,3=Tri,4=Random(S&H)
    return {
        1: 1,
        2: 3,
        3: 2,
        4: 6,   # best current match: RandomStep&Hold
    }.get(v, 1)


def map_s1_subwave_to_hive(v):
    # Synth1 sub: 0=Sine,1=Tri,2=Saw,3=Square
    # Hive:       Sine=1,Tri=3,Saw=2,Pulse=4
    return {
        0: 1,
        1: 3,
        2: 2,
        3: 4,
    }.get(v, 1)


def map_s1_filter_type_to_hive(v):
    # Synth1: 0=LPF12, 1=LPF24, 2=HPF12, 3=BPF12, 4=LPF DiodeLadder
    # Hive:   LP12=2, LP24=1, HP12=4, BP12=3
    return {
        0: 2,
        1: 1,
        2: 4,
        3: 3,
        4: 1,   # best approx for diode ladder
    }.get(v, 1)


def map_s1_voice_mode_to_hive(v):
    # Synth1: 0=Poly,1=Mono,2=Legato
    return {
        0: 0,
        1: 1,
        2: 2,
    }.get(v, 0)


def map_s1_unison_phase_to_hive_trigger(v):
    # Approximation:
    # low  -> Reset
    # mid  -> Flow
    # high -> Random
    if v <= 42:
        return 2  # Reset
    elif v <= 84:
        return 0  # Flow
    else:
        return 1  # Random


def map_s1_arp_type_to_hive_dir(v):
    # Synth1: 1=Up&Down, 2=Up, 3=Down, 4=Random
    # Hive:   Up=1, Down=2, Up+Down1=3, Random=5
    return {
        1: 3,
        2: 1,
        3: 2,
        4: 5,
    }.get(v, 1)


def map_s1_arp_range_to_hive(v):
    # Synth1: 0=1Oct,1=2Oct,2=3Oct,3=4Oct
    # Hive:   1,2,3,4
    return {
        0: 1,
        1: 2,
        2: 3,
        3: 4,
    }.get(v, 1)


def map_s1_arp_beat_to_hive(v):
    # Returns: (CLK.Base, CLK.Mult)
    # Hive CLK.Base:
    #   0=1/32, 1=1/16, 2=1/8, 3=1/4
    #
    # Hive CLK.Mult:
    #   50..200
    #   triplets: ~75
    #   dotted: ~150
    #
    # Some slow Synth1 values are only approximate because Hive base range is limited.
    table = {
        0:  (3, 200.0),  # 1        approx
        1:  (3, 200.0),  # 2+4+8    approx
        2:  (3, 200.0),  # 2+4      approx
        3:  (3, 200.0),  # 2
        4:  (3, 175.0),  # 4+8+16   approx
        5:  (3, 150.0),  # 4+8
        6:  (3, 50.0),   # 1/3      approx
        7:  (3, 100.0),  # 4
        8:  (2, 175.0),  # 8+16+32  approx
        9:  (2, 150.0),  # 8+16
        10: (3, 50.0),   # 2/3      approx
        11: (2, 100.0),  # 8
        12: (1, 150.0),  # 16+32
        13: (3, 75.0),   # 4/3
        14: (1, 100.0),  # 16
        15: (2, 75.0),   # 8/3
        16: (0, 100.0),  # 32
        17: (1, 75.0),   # 16/3
        18: (0, 75.0),   # 32/3
    }
    return table.get(v, (2, 100.0))



def map_s1_delay_type_to_hive(v):
    # Synth1: 0=Stereo,1=Cross,2=PingPong
    # Hive:   Stereo=0, PingPong=1, CrossFeedback=2
    return {
        0: 0,
        1: 2,
        2: 1,
    }.get(v, 0)


def map_s1_lfo1_wave_to_hive(v):
    # Synth1 LFO1:
    # 0=Saw,1=Tri,2=Square,3=Random(S&H),4=Random smooth,5=Sine
    # Hive:
    # SawDown=3,Tri=1,Square=4,RandomStep&Hold=6,RandomSmoothed=7,Sine=0
    return {
        0: 3,
        1: 1,
        2: 4,
        3: 6,
        4: 7,
        5: 0,
    }.get(v, 1)


def map_s1_lfo2_wave_to_hive(v):
    # Synth1 LFO2:
    # 0=Saw, 1=Tri, 2=Square, 3=Random(S&H), 4=Random smooth, 5=Sine
    # Hive:
    # SawDown=3, Tri=1, Square=4, RandomStep&Hold=6, RandomSmoothed=7, Sine=0
    return {
        0: 3,  # Saw
        1: 1,  # Tri
        2: 4,  # Square
        3: 6,  # Random Step&Hold
        4: 7,  # Random Smoothed
        5: 0,  # Sine
    }.get(v, 1)


def scale_s1_lfo_amount_to_hive_depth(v):
    # Synth1 LFO amount is effectively unipolar in your mapping notes
    return scale_0_127_to_100(v)


def map_s1_lfo_dest_to_hive_dests(v, hive_data=None):
    """
    Returns:
        (dest1, dest2, invert_second)

    invert_second is used for crossfade-like behavior where the second destination
    should move opposite to the first.
    """
    table = {
        1: ("Osc2:Tune", None, False),                 # Osc2 Pitch
        2: ("Osc1:Tune", "Osc2:Tune", False),         # Osc1+2 Pitch
        3: ("Filter1:Cutoff", None, False),           # Filter Cutoff
        4: ("Osc1:Volume", "Osc2:Volume", False),     # Amp Level
        6: ("Osc1:Phase", "Osc2:Phase", False),       # FM approximation
        7: ("Osc1:Pan", "Osc2:Pan", False),           # Pan
    }

    # Synth1 Pulse Width affects both oscillators
    if v == 5:
        osc1_wave = str(hive_data.get("Osc1", {}).get("Wave", ""))
        osc2_wave = str(hive_data.get("Osc2", {}).get("Wave", ""))

        osc1_is_pulse = (osc1_wave == "3")
        osc2_is_pulse = (osc2_wave == "3")

        if osc1_is_pulse and osc2_is_pulse:
            return ("Osc1:PWidth", "Osc2:PWidth", False)
        elif osc1_is_pulse:
            return ("Osc1:PWidth", None, False)
        elif osc2_is_pulse:
            return ("Osc2:PWidth", None, False)
        else:
            return (None, None, False)

    return table.get(v, (None, None, False))


def apply_s1_lfo_matrix(hive_data, mm_section, source_value, active_value, dest_value, amount_value):
    """
    Generic mapper for Synth1 LFO1/LFO2 -> Hive MM1/MM2
    """
    set_hive(hive_data, mm_section, "Active", 1 if active_value else 0)
    set_hive(hive_data, mm_section, "Source", source_value)

    dest1, dest2, invert_second = map_s1_lfo_dest_to_hive_dests(dest_value, hive_data)

    if dest1 is None:
        set_hive(hive_data, mm_section, "Dest1", "none:assigned")
        set_hive(hive_data, mm_section, "Depth1", 0.0)
        set_hive(hive_data, mm_section, "Dest2", "none:assigned")
        set_hive(hive_data, mm_section, "Depth2", 0.0)
        return

    depth = scale_s1_lfo_amount_to_hive_depth(amount_value)

    set_hive(hive_data, mm_section, "Dest1", dest1)
    set_hive(hive_data, mm_section, "Depth1", depth)

    if dest2 is not None:
        set_hive(hive_data, mm_section, "Dest2", dest2)
        set_hive(hive_data, mm_section, "Depth2", -depth if invert_second else depth)
    else:
        set_hive(hive_data, mm_section, "Dest2", "none:assigned")
        set_hive(hive_data, mm_section, "Depth2", 0.0)
    

def map_s1_polyphony_to_hive_voices(v):
    # Synth1 polyphony: 1..32
    # Hive report:
    # 2->0, 3->1, 4->2, 5->3, 6->4, 8->5, 12->6, 16->7
    options = [
        (2, 0),
        (3, 1),
        (4, 2),
        (5, 3),
        (6, 4),
        (8, 5),
        (12, 6),
        (16, 7),
    ]
    best = min(options, key=lambda x: abs(v - x[0]))
    return best[1]


def map_s1_unison_voices_to_hive_unison(v):
    # Synth1 gives actual count 2..8.
    # Hive "Unison" exact meaning not fully confirmed, but use count-ish approximation.
    return clamp(v, 1, 8)


# -------------------------------------------------
# LFO sync / trig approximations
# -------------------------------------------------

def map_s1_keysync_switch_to_hive_trig(v):
    # Synth1: 0 Off, 1 On
    # Hive reports Trig exists, baseline often 1 = gate
    return 1 if v else 0


def map_s1_tempo_sync_switch_to_hive_sync(current_sync_value, switch_value):
    # This remains rough because Hive Sync enum table isn't fully mapped yet.
    # If OFF, keep current init value.
    # If ON, also keep current init value for now unless later refined.
    return current_sync_value


# -------------------------------------------------
# FX logic
# -------------------------------------------------

def reset_main_fx_to_neutral(hive_data):
    # Distort off-ish
    set_hive(hive_data, "Distort", "Amount", 0.0)
    set_hive(hive_data, "Distort", "Mix", 0.0)

    # Phaser off-ish
    set_hive(hive_data, "Phaser", "Wet", 0.0)
    set_hive(hive_data, "Phaser", "FB", 0.0)

    # Compressor neutral-ish
    set_hive(hive_data, "Comp", "Amount", 0.0)
    set_hive(hive_data, "Comp", "Output", 0.0)


def apply_synth1_main_fx(s1_params, hive_data):
    """
    Synth1 major FX block:
      77 on/off
      78 type
      79 ctrl1
      80 ctrl2
      81 level

    Only one of these should be active at a time in Synth1.
    """
    fx_on = s1_params.get(77, 0)
    fx_type = s1_params.get(78, 0)
    ctrl1 = s1_params.get(79, 64)
    ctrl2 = s1_params.get(80, 64)
    level = s1_params.get(81, 0)

    reset_main_fx_to_neutral(hive_data)

    if not fx_on:
        return

    wet_half = scale_fx_level_half_wet(level)

    # Synth1:
    # 0 = Analogue Distortion1
    # 1 = Analogue Distortion2
    # 2 = Digital Dist
    # 3 = Decimator
    # 4 = Ring Mod
    # 5 = Compressor
    # 6 = Phaser1
    # 7 = Phaser2
    # 8 = Phaser3
    # 9 = Phaser4

    if fx_type in (0, 1, 2, 3):
        # Distortion family
        set_hive(hive_data, "Distort", "Type", fx_type if fx_type <= 3 else 0)
        set_hive(hive_data, "Distort", "Amount", scale_linear(ctrl1, 0, 127, 0.0, 60.0))
        set_hive(hive_data, "Distort", "Tone", scale_0_127_to_100(ctrl2))
        set_hive(hive_data, "Distort", "Mix", wet_half)

    elif fx_type == 4:
        # Ring Mod: no direct good equivalent. Approximate lightly as digital/distortion-ish.
        set_hive(hive_data, "Distort", "Type", 2)
        set_hive(hive_data, "Distort", "Amount", scale_linear(ctrl1, 0, 127, 0.0, 35.0))
        set_hive(hive_data, "Distort", "Tone", scale_0_127_to_100(ctrl2))
        set_hive(hive_data, "Distort", "Mix", wet_half)

    elif fx_type == 5:
        # Compressor
        set_hive(hive_data, "Comp", "Amount", scale_0_127_to_100(ctrl1))
        # Use ctrl2 as output trim approx
        out = scale_0_127_center_64_to_bipolar_100(ctrl2) * 0.25
        set_hive(hive_data, "Comp", "Output", out)
        # mix is fixed-ish already in base preset; leave unless later confirmed

    elif fx_type in (6, 7, 8, 9):
        # Phaser family
        set_hive(hive_data, "Phaser", "Type", clamp(fx_type - 6, 0, 3))
        set_hive(hive_data, "Phaser", "Rate", scale_0_127_to_100(ctrl1))
        set_hive(hive_data, "Phaser", "FB", scale_0_127_to_100(ctrl2))
        set_hive(hive_data, "Phaser", "Wet", wet_half)


def apply_synth1_chorus(s1_params, hive_data):
    # 66 on/off
    # 47 type
    # 52 time (no clear direct Hive field)
    # 53 depth
    # 54 rate
    # 55 feedback (no direct chorus feedback, phaser fb only)
    # 56 level
    chorus_on = s1_params.get(66, 0)
    if not chorus_on:
        set_hive(hive_data, "Chorus", "Wet", 0.0)
        return

    chorus_type = s1_params.get(64, 0)
    depth = s1_params.get(53, 64)
    rate = s1_params.get(54, 64)
    level = s1_params.get(56, 64)

    # Synth1 type: 0=x2, 1=x1, 5=x4
    # Hive report: x1=0, x2=1, x4=2
    chorus_type_map = {
        1: 0,  # x1
        0: 1,  # x2
        5: 2,  # x4
    }

    set_hive(hive_data, "Chorus", "Type", chorus_type_map.get(chorus_type, 1))
    set_hive(hive_data, "Chorus", "Depth", scale_0_127_to_100(depth))
    set_hive(hive_data, "Chorus", "Rate", scale_0_127_to_100(rate))
    set_hive(hive_data, "Chorus", "Wet", scale_fx_level_half_wet(level))


def apply_synth1_delay(s1_params, hive_data):
    delay_on = s1_params.get(65, 0)
    delay_time = s1_params.get(35, None)
    delay_feedback = s1_params.get(36, 0)
    delay_mix = s1_params.get(37, 0)
    delay_type = s1_params.get(82, 0)
    delay_spread = s1_params.get(83, 64)
    delay_tone = s1_params.get(98, 64)

    if not delay_on:
        set_hive(hive_data, "Delay", "Mix", 0.0)
        return

    set_hive(hive_data, "Delay", "Mode", map_s1_delay_type_to_hive(delay_type))
    set_hive(hive_data, "Delay", "FeedBck", scale_0_127_to_100(delay_feedback))
    set_hive(hive_data, "Delay", "Mix", scale_0_127_to_100(delay_mix))
    set_hive(hive_data, "Delay", "Width", scale_0_127_to_100(delay_spread))

    # Tone split approximation:
    # lower tone -> lower LP, higher tone -> lower HP? keep simple for now
    set_hive(hive_data, "Delay", "LP", scale_0_127_to_100(delay_tone))
    set_hive(hive_data, "Delay", "HP", scale_linear(delay_tone, 0, 127, 0.0, 25.0))

    if delay_time is not None:
        l_delay, r_delay = map_s1_delay_time_to_hive_lr(delay_time)
        set_hive(hive_data, "Delay", "LDelay", l_delay)
        set_hive(hive_data, "Delay", "RDelay", r_delay)


def map_s1_delay_time_to_hive_lr(v):
    # Returns: (LDelay, RDelay)
    # Hive delay enums from your report:
    # 0=1/64, 1=1/32, 2=1/16T, 3=1/16, 4=1/16D,
    # 5=1/8T, 6=1/8, 7=1/8D, 8=1/4T, 9=1/4, 10=1/4D,
    # 11=1/2T, 12=1/2, 13=1/2D
    table = {
        0:  (12, 12),  # 1
        1:  (13, 13),  # 1 + 1/2
        2:  (12, 12),  # 1/2
        3:  (11, 11),  # 1/2T
        4:  (10, 10),  # 1/4D
        5:  (9, 9),    # 1/4
        6:  (8, 8),    # 1/4T
        7:  (7, 7),    # 1/8D
        8:  (6, 6),    # 1/8
        9:  (5, 5),    # 1/8T
        10: (4, 4),    # 1/16D
        11: (3, 3),    # 1/16
        12: (2, 2),    # 1/16T
        13: (1, 1),    # 1/32
        14: (0, 0),    # 1/64
    }
    return table.get(v, (6, 6))


def apply_synth1_ringmod_filter2(s1_params, hive_data):
    """
    Synth1 ID 7 = osc2 ring switch
    Approximate using Hive Filter2 in Sideband mode.
    """

    ring_on = s1_params.get(7, 0)

    if not ring_on:
        set_hive(hive_data, "Filter2", "Volume", 0.0)
        return

    # Route osc signals into Filter2 only
    set_hive(hive_data, "Filter2", "inO1", 1)
    set_hive(hive_data, "Filter2", "inO2", 1)
    set_hive(hive_data, "Filter2", "inS1", 0)
    set_hive(hive_data, "Filter2", "inS2", 0)
    set_hive(hive_data, "Filter2", "inF", 0)

    # Sideband mode
    set_hive(hive_data, "Filter2", "Type", 10)

    # Mirror main filter so the extra layer follows the patch
    if "Filter1" in hive_data:
        if "Gain" in hive_data["Filter1"]:
            set_hive(hive_data, "Filter2", "Gain", hive_data["Filter1"]["Gain"])
        if "Cutoff" in hive_data["Filter1"]:
            set_hive(hive_data, "Filter2", "Cutoff", hive_data["Filter1"]["Cutoff"])
        if "Res" in hive_data["Filter1"]:
            set_hive(hive_data, "Filter2", "Res", hive_data["Filter1"]["Res"])
        if "Key" in hive_data["Filter1"]:
            set_hive(hive_data, "Filter2", "Key", hive_data["Filter1"]["Key"])
        if "Env" in hive_data["Filter1"]:
            set_hive(hive_data, "Filter2", "Env", hive_data["Filter1"]["Env"])
        if "Volume" in hive_data["Filter1"]:
            set_hive(hive_data, "Filter2", "Volume", hive_data["Filter1"]["Volume"])
        else:
            set_hive(hive_data, "Filter2", "Volume", 50.0)

    # Sideband-specific support values
    set_hive(hive_data, "Filter2", "Mix", 100.0)
    set_hive(hive_data, "Filter2", "Ratio", 50.0)


# -------------------------------------------------
# Mod Matrix
# -------------------------------------------------

def scale_s1_midi_amount_to_hive_depth_id50(v):
    # Synth1 ID 50 center = 63
    return scale_0_127_center_63_to_bipolar_100(v)


def scale_s1_midi_amount_to_hive_depth_id51(v):
    # Synth1 ID 51 center = 64
    return scale_0_127_center_64_to_bipolar_100(v)


def map_s1_midi_source_to_hive(v):
    """
    Synth1 raw source values:
      45057 = Mod Wheel
      45058 = Breath Control
      45059 = Control 3
      45063 = Volume
      45067 = Expression
      53248 = Channel Aftertouch
      57344 = Pitch Bend

    Hive report:
      ModWheel   = 1
      PitchBend  = 2
      Control3   = 3
      Expression = 4
      Volume     = 16
      Aftertouch = 17
    """
    table = {
        45057: 1,    # Mod Wheel
        45058: 3,    # Breath Control -> approximate to CtrlA/Control3
        45059: 3,    # Control 3
        45063: 16,   # Volume
        45067: 4,    # Expression
        53248: 17,   # Channel Aftertouch
        57344: 2,    # Pitch Bend
    }
    return table.get(v, 0)


def map_s1_midi_dest_to_hive_dests(v, s1_params=None, hive_data=None):
    """
    Returns:
        (dest1, dest2, invert_second)

    Uses Synth1 destination ID and, where needed, Synth1 FX type (ID 78)
    to choose the best Hive MM destination(s).
    """
    fx_type = s1_params.get(78, 0) if s1_params else 0

    table = {
        -1: (None, None, False),

        76: ("Osc1:Detune", None, False),
        45: ("Filter2:Mix", None, False),
        95: ("Osc1:SubTune", None, False),
        2:  ("Osc2:Tune", None, False),

        # Osc env approximations you said were acceptable earlier
        12: ("ModEnv1:Atk", None, False),
        13: ("ModEnv1:Dec", None, False),
        11: ("Filter1:Env", None, False),

        15: ("ModEnv1:Atk", None, False),
        16: ("ModEnv1:Dec", None, False),
        17: ("ModEnv1:Sus", None, False),
        18: ("ModEnv1:Rel", None, False),

        19: ("Filter1:Cutoff", None, False),
        20: ("Filter1:Res", None, False),
        21: ("Filter1:Env", None, False),
        23: ("Filter1:Gain", None, False),
        22: ("Filter1:Key", None, False),

        25: ("AmpEnv1:Atk", None, False),
        26: ("AmpEnv1:Dec", None, False),
        27: ("AmpEnv1:Sus", None, False),
        28: ("AmpEnv1:Rel", None, False),

        29: ("Osc1:Volume", "Osc2:Volume", False),

        61: ("EQ:HighF", "EQ:BassF", False),
        62: ("EQ:HighG", "EQ:MidG", False),
        60: ("EQ:MidF", None, False),

        90: ("Osc1:Pan", "Osc2:Pan", False),

        35: ("Delay:TimeScl", None, False),
        83: ("Delay:Width", None, False),
        36: ("Delay:FeedBck", None, False),
        98: ("Delay:LP", None, False),
        37: ("Delay:Mix", None, False),

        53: ("Chorus:Depth", None, False),
        54: ("Chorus:Rate", None, False),
        56: ("Chorus:Wet", None, False),

        39: ("VCC:Porta", None, False),
        75: ("Osc2:Detune", None, False),
        84: ("Osc1:Width", "Osc2:Width", False),

        43: ("LFO1:Rate", None, False),
        44: ("MM1:Depth1", "MM1:Depth2", False),
        48: ("LFO2:Rate", None, False),
        49: ("MM2:Depth1", "MM2:Depth2", False),
    }

    # FX-dependent routing only
    if v == 79:
        # FX Control 1
        if fx_type in (0, 1, 2, 3, 4):
            return ("Distort:Amount", None, False)
        elif fx_type == 5:
            return ("Comp:Amount", None, False)
        elif fx_type in (6, 7, 8, 9):
            return ("Phaser:Rate", None, False)
        return (None, None, False)

    if v == 80:
        # FX Control 2
        if fx_type in (0, 1, 2, 3, 4):
            return ("Distort:Tone", None, False)
        elif fx_type == 5:
            return ("Comp:Output", None, False)
        elif fx_type in (6, 7, 8, 9):
            return ("Phaser:Phase", None, False)
        return (None, None, False)

    if v == 81:
        # FX Level
        if fx_type in (0, 1, 2, 3, 4):
            return ("Distort:Mix", None, False)
        elif fx_type == 5:
            return ("Comp:Amount", None, False)   # weakest approximation, but keeps modulation functional
        elif fx_type in (6, 7, 8, 9):
            return ("Phaser:Wet", None, False)
        return (None, None, False)

    return table.get(v, (None, None, False))


def apply_s1_midi_matrix(hive_data, mm_section, source_raw_value, dest_raw_value, amount_value, amount_scaler, s1_params):
    """
    Generic mapper for Synth1 MIDI/Wheel matrix -> Hive MM5/MM6
    """
    source_value = map_s1_midi_source_to_hive(source_raw_value)
    dest1, dest2, invert_second = map_s1_midi_dest_to_hive_dests(dest_raw_value, s1_params=s1_params, hive_data=hive_data)

    if source_value == 0 or dest1 is None:
        set_hive(hive_data, mm_section, "Active", 0)
        set_hive(hive_data, mm_section, "Source", 0)
        set_hive(hive_data, mm_section, "Dest1", "none:assigned")
        set_hive(hive_data, mm_section, "Depth1", 0.0)
        set_hive(hive_data, mm_section, "Dest2", "none:assigned")
        set_hive(hive_data, mm_section, "Depth2", 0.0)
        return

    depth = amount_scaler(amount_value)

    set_hive(hive_data, mm_section, "Active", 1)
    set_hive(hive_data, mm_section, "Source", source_value)
    set_hive(hive_data, mm_section, "Dest1", dest1)
    set_hive(hive_data, mm_section, "Depth1", depth)

    if dest2 is not None:
        set_hive(hive_data, mm_section, "Dest2", dest2)
        set_hive(hive_data, mm_section, "Depth2", -depth if invert_second else depth)
    else:
        set_hive(hive_data, mm_section, "Dest2", "none:assigned")
        set_hive(hive_data, mm_section, "Depth2", 0.0)


# -------------------------------------------------
# Conversion
# -------------------------------------------------

def apply_safe_global_defaults(hive_data):
    # Filter routing defaults for Synth1-style signal flow
    set_hive(hive_data, "Filter1", "inO1", 1)
    set_hive(hive_data, "Filter1", "inS1", 1)
    set_hive(hive_data, "Filter1", "inO2", 1)
    set_hive(hive_data, "Filter1", "inS2", 0)

    # Second sub should be inaudible for Synth1 conversion
    set_hive(hive_data, "Osc2", "SubVol", 0.0)


def convert_s1_to_hive(s1_params, hive_data):
    apply_safe_global_defaults(hive_data)
    init_lfo_matrix_sources(hive_data)

    # -------------------------
    # Oscillators
    # -------------------------
    if 0 in s1_params:
        set_hive(hive_data, "Osc1", "Wave", map_s1_wave_to_hive(s1_params[0]))

    if 1 in s1_params:
        set_hive(hive_data, "Osc2", "Wave", map_s1_osc2_wave_to_hive(s1_params[1]))

    if 2 in s1_params:
        octv, semi = s1_pitch_to_hive_octave_semi(s1_params[2])
        set_hive(hive_data, "Osc2", "Octave", octv)
        set_hive(hive_data, "Osc2", "Semi", semi)

    if 3 in s1_params:
        semi = round(scale_linear(s1_params[3], 0, 127, -12.0, 12.0))
        semi = clamp(semi, -12, 12)
        set_hive(hive_data, "Osc2", "Semi", semi)

    if 5 in s1_params:
        osc1_vol, osc2_vol = s1_mix_to_hive_volumes(s1_params[5])
        set_hive(hive_data, "Osc1", "Volume", osc1_vol)
        set_hive(hive_data, "Osc2", "Volume", osc2_vol)

    if 9 in s1_params:
        set_hive(hive_data, "VCC", "Trsp", clamp(int(s1_params[9]), -24, 24))

    if 72 in s1_params:
        set_hive(hive_data, "VCC", "FTun", scale_0_127_center_64_to_bipolar_100(s1_params[72]))

    if 76 in s1_params:
        set_hive(hive_data, "Osc1", "Detune", scale_0_127_to_100(s1_params[76]))

    if 90 in s1_params:
        pan = scale_0_127_to_pan(s1_params[90])
        set_hive(hive_data, "Osc1", "Pan", pan)
        set_hive(hive_data, "Osc2", "Pan", pan)

    if 95 in s1_params:
        set_hive(hive_data, "Osc1", "SubVol", scale_0_127_to_100(s1_params[95]))

    if 96 in s1_params:
        set_hive(hive_data, "Osc1", "SubWave", map_s1_subwave_to_hive(s1_params[96]))

    if 97 in s1_params:
        set_hive(hive_data, "Osc1", "SubTune", 0 if s1_params[97] == 0 else -12)

    # -------------------------
    # Filter
    # -------------------------
    if 14 in s1_params:
        set_hive(hive_data, "Filter1", "Type", map_s1_filter_type_to_hive(s1_params[14]))

    if 15 in s1_params:
        adjusted_mod_attack = adjust_env_time_value(s1_params[15])
        set_hive(hive_data, "ModEnv1", "Atk", scale_0_127_to_100(adjusted_mod_attack))

    if 16 in s1_params:
        set_hive(hive_data, "ModEnv1", "Dec", scale_0_127_to_100(s1_params[16]))

    if 17 in s1_params:
        set_hive(hive_data, "ModEnv1", "Sus", scale_0_127_to_100(s1_params[17]))

    if 18 in s1_params:
        adjusted_mod_release = adjust_env_time_value(s1_params[18])
        set_hive(hive_data, "ModEnv1", "Rel", scale_0_127_to_100(adjusted_mod_release))

    if 19 in s1_params:
        set_hive(hive_data, "Filter1", "Cutoff", scale_0_127_to_150_cutoff(s1_params[19]))

    if 20 in s1_params:
        set_hive(hive_data, "Filter1", "Res", scale_0_127_to_100(s1_params[20]))

    if 21 in s1_params:
        set_hive(hive_data, "Filter1", "Env", scale_0_127_center_63_to_bipolar_100(s1_params[21]))

    if 22 in s1_params:
        set_hive(hive_data, "Filter1", "Key", scale_0_127_to_100(s1_params[22]))

    if 23 in s1_params:
        set_hive(hive_data, "Filter1", "Gain", scale_0_127_to_100(s1_params[23]))

    if 24 in s1_params:
        # switch approximation
        set_hive(hive_data, "ModEnv1", "Vel", 100.0 if s1_params[24] else 0.0)

    # -------------------------
    # Ring Mod approximation
    # -------------------------
    apply_synth1_ringmod_filter2(s1_params, hive_data)

    # -------------------------
    # Amp
    # -------------------------
    if 25 in s1_params:
        adjusted_attack = adjust_env_time_value(s1_params[25])
        set_hive(hive_data, "AmpEnv1", "Atk", scale_0_127_to_100(adjusted_attack))

    if 26 in s1_params:
        set_hive(hive_data, "AmpEnv1", "Dec", scale_0_127_to_100(s1_params[26]))

    if 27 in s1_params:
        set_hive(hive_data, "AmpEnv1", "Sus", scale_0_127_to_100(s1_params[27]))

#     if 28 in s1_params:
#         adjusted_release = adjust_env_time_value(s1_params[28])
#         set_hive(hive_data, "AmpEnv1", "Rel", scale_0_127_to_100(adjusted_release))

    if 29 in s1_params:
        # amp gain approximation: use comp output gently
        out = scale_linear(s1_params[29], 0, 127, -6.0, 6.0)
        set_hive(hive_data, "Comp", "Output", out)

    if 30 in s1_params:
        set_hive(hive_data, "AmpEnv1", "Vel", scale_0_127_to_100(s1_params[30]))

    # -------------------------
    # Voice / performance
    # -------------------------
    if 38 in s1_params:
        set_hive(hive_data, "VCC", "Mode", map_s1_voice_mode_to_hive(s1_params[38]))

    if 39 in s1_params:
        set_hive(hive_data, "VCC", "Porta", scale_0_127_to_100(s1_params[39]))

    if 40 in s1_params:
        pb = clamp(int(s1_params[40]), 0, 24)
        set_hive(hive_data, "VCC", "PB", pb)
        set_hive(hive_data, "VCC", "PBD", pb)

    if 74 in s1_params:
        # If Porta Auto is OFF in S1, user note says set Porta to zero
        if s1_params[74] == 0:
            set_hive(hive_data, "VCC", "Porta", 0.0)

    if 92 in s1_params:
        trig = map_s1_unison_phase_to_hive_trigger(s1_params[92])
        set_hive(hive_data, "Osc1", "Trigger", trig)
        set_hive(hive_data, "Osc2", "Trigger", trig)

    # -------------------------
    # Unison
    # -------------------------
    # ID 73 = unison switch
    # ID 75 = unison detune
    # ID 84 = unison spread
    # ID 93 = unison number of voices

    if 73 in s1_params and s1_params[73] == 0:
        # Unison OFF in Synth1 -> force Hive unison to single voice
        set_hive(hive_data, "Osc1", "Unison", 1)
        set_hive(hive_data, "Osc2", "Unison", 1)
    elif 93 in s1_params:
        # Unison ON (or no explicit switch present) -> use Synth1 unison count
        u = map_s1_unison_voices_to_hive_unison(s1_params[93])
        set_hive(hive_data, "Osc1", "Unison", u)
        set_hive(hive_data, "Osc2", "Unison", u)

    if 75 in s1_params:
        # Using Osc2.Detune as your chosen approximation for unison detune
        set_hive(hive_data, "Osc2", "Detune", scale_0_127_to_100(s1_params[75]))

    if 84 in s1_params:
        # Using Osc1.Width + Osc2.Width as linked unison spread approximation
        spread = scale_0_127_to_100(s1_params[84])
        set_hive(hive_data, "Osc1", "Width", spread)
        set_hive(hive_data, "Osc2", "Width", spread)

    if 94 in s1_params:
        set_hive(hive_data, "VCC", "Voices", map_s1_polyphony_to_hive_voices(s1_params[94]))

    # -------------------------
    # Arp
    # -------------------------
    if 59 in s1_params:
        set_hive(hive_data, "ARP", "OnOff", 1 if s1_params[59] else 0)

    if 31 in s1_params:
        set_hive(hive_data, "ARP", "Dir", map_s1_arp_type_to_hive_dir(s1_params[31]))

    if 32 in s1_params:
        set_hive(hive_data, "ARP", "Oct", map_s1_arp_range_to_hive(s1_params[32]))

    if 33 in s1_params:
        clk_base, clk_mult = map_s1_arp_beat_to_hive(s1_params[33])
        set_hive(hive_data, "CLK", "Base", clk_base)
        set_hive(hive_data, "CLK", "Mult", clk_mult)

    if 34 in s1_params:
        set_hive(hive_data, "SEQ", "Gate", scale_0_127_to_100(s1_params[34]))

    # -------------------------
    # LFO
    # -------------------------
    if 42 in s1_params:
        set_hive(hive_data, "LFO1", "Wave", map_s1_lfo1_wave_to_hive(s1_params[42]))

    if 43 in s1_params:
        # Hive report shows LFO Rate approx -5..+5
        set_hive(hive_data, "LFO1", "Rate", scale_linear(s1_params[43], 0, 127, -5.0, 5.0))

    if 67 in s1_params:
        current_sync = float(hive_data["LFO1"].get("Sync", "2"))
        set_hive(hive_data, "LFO1", "Sync", map_s1_tempo_sync_switch_to_hive_sync(current_sync, s1_params[67]))

    if 68 in s1_params:
        set_hive(hive_data, "LFO1", "Trig", map_s1_keysync_switch_to_hive_trig(s1_params[68]))

    if 41 in s1_params or 44 in s1_params or 57 in s1_params:
        apply_s1_lfo_matrix(
            hive_data=hive_data,
            mm_section="MM1",
            source_value=29,                         # MM1.Source.LFO1
            active_value=s1_params.get(57, 0),
            dest_value=s1_params.get(41, -1),
            amount_value=s1_params.get(44, 0),
        )

    if 47 in s1_params:
        set_hive(hive_data, "LFO2", "Wave", map_s1_lfo2_wave_to_hive(s1_params[47]))

    if 48 in s1_params:
        set_hive(hive_data, "LFO2", "Rate", scale_linear(s1_params[48], 0, 127, -5.0, 5.0))

    if 69 in s1_params:
        current_sync = float(hive_data["LFO2"].get("Sync", "6"))
        set_hive(hive_data, "LFO2", "Sync", map_s1_tempo_sync_switch_to_hive_sync(current_sync, s1_params[69]))

    if 70 in s1_params:
        set_hive(hive_data, "LFO2", "Trig", map_s1_keysync_switch_to_hive_trig(s1_params[70]))

    if 46 in s1_params or 49 in s1_params or 58 in s1_params:
        apply_s1_lfo_matrix(
            hive_data=hive_data,
            mm_section="MM2",
            source_value=30,                         # MM2.Source.LFO2
            active_value=s1_params.get(58, 0),
            dest_value=s1_params.get(46, -1),
            amount_value=s1_params.get(49, 0),
        )

    # -------------------------
    # EQ
    # -------------------------
    if 62 in s1_params:
        eq_level = scale_0_127_center_64_to_bipolar_100(s1_params[62]) * 0.15
        set_hive(hive_data, "EQ", "BassG", eq_level)
        set_hive(hive_data, "EQ", "MidG", eq_level)
        set_hive(hive_data, "EQ", "HighG", eq_level)

    if 60 in s1_params:
        tone = s1_params[60]

        # Left = high-cut / darker
        # Right = low-cut / thinner
        bass_f = scale_linear(tone, 0, 127, 20.0, 80.0)
        high_f = scale_linear(tone, 0, 127, 40.0, 100.0)

        set_hive(hive_data, "EQ", "BassF", bass_f)
        set_hive(hive_data, "EQ", "HighF", high_f)

    if 61 in s1_params:
        mid_f = scale_0_127_to_100(s1_params[61])
        set_hive(hive_data, "EQ", "MidF", mid_f)

    # -------------------------
    # Chorus / Delay / Main FX
    # -------------------------
    apply_synth1_chorus(s1_params, hive_data)
    apply_synth1_delay(s1_params, hive_data)
    apply_synth1_main_fx(s1_params, hive_data)

    # -------------------------
    # MIDI / Wheel modulation matrix (Synth1 -> Hive MM5/MM6)
    # -------------------------

    if 86 in s1_params or 87 in s1_params or 50 in s1_params:
        apply_s1_midi_matrix(
            hive_data=hive_data,
            mm_section="MM5",
            source_raw_value=s1_params.get(86, 0),
            dest_raw_value=s1_params.get(87, -1),
            amount_value=s1_params.get(50, 63),
            amount_scaler=scale_s1_midi_amount_to_hive_depth_id50,
            s1_params=s1_params,
        )

    if 88 in s1_params or 89 in s1_params or 51 in s1_params:
        apply_s1_midi_matrix(
            hive_data=hive_data,
            mm_section="MM6",
            source_raw_value=s1_params.get(88, 0),
            dest_raw_value=s1_params.get(89, -1),
            amount_value=s1_params.get(51, 64),
            amount_scaler=scale_s1_midi_amount_to_hive_depth_id51,
            s1_params=s1_params,
        )

    return hive_data


# -------------------------------------------------
# Main
# -------------------------------------------------

def main():
    if not INIT_FILE.exists():
        raise FileNotFoundError(f"Base preset not found: {INIT_FILE}")

    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Synth1 input folder not found: {INPUT_DIR}")

    init_data, init_order, init_header_lines, init_blob_text = parse_h2p(INIT_FILE)

    sy1_files = sorted(INPUT_DIR.rglob("*.sy1"))
    if not sy1_files:
        print("No .sy1 files found.")
        return

    converted = 0
    failed = 0

    for sy1_file in sy1_files:
        try:
            s1 = parse_synth1_preset(sy1_file)

            hive_data = OrderedDict(
                (section, OrderedDict(pairs)) for section, pairs in init_data.items()
            )

            hive_data = convert_s1_to_hive(s1["params"], hive_data)

            rel_parent = sy1_file.parent.relative_to(INPUT_DIR)
            preset_number = sy1_file.stem
            patch_name = sanitize_patch_name(s1["name"])

            bank_name = get_bank_name_from_folder(sy1_file.parent)
            description = get_readme_description(sy1_file.parent)
            meta_lines = build_meta_header(bank_name, description)

            out_name = f"{preset_number} {patch_name}.h2p"
            out_path = OUTPUT_DIR / rel_parent / out_name

            write_h2p(out_path, hive_data, init_order, init_header_lines, init_blob_text, meta_lines)
            print(f"OK: {sy1_file} -> {out_path}")
            converted += 1

        except Exception as e:
            print(f"FAILED: {sy1_file} -> {e}")
            failed += 1

    print()
    print(f"Done. Converted: {converted}, Failed: {failed}")
    print(f"Output folder: {OUTPUT_DIR}")
    print("Closing in 3 seconds...")
    time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        print("Closing in 5 seconds...")
        time.sleep(5)
        raise