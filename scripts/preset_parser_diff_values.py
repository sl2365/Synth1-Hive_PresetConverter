from pathlib import Path
from collections import OrderedDict


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

INIT_FILE = BASE_DIR / "Hive-INIT.h2p"
INPUT_DIR = BASE_DIR / "input" / "- Hive"
OUTPUT_FILE = BASE_DIR / "Hive-Report.ini"


def strip_blob(text: str) -> str:
    marker = "\n$$$$"
    idx = text.find(marker)
    if idx != -1:
        return text[:idx]
    idx = text.find("$$$$")
    if idx != -1:
        return text[:idx]
    return text


def parse_h2p(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = strip_blob(text)

    data = OrderedDict()
    current_section = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("//"):
            continue

        if line.startswith("/*") or line.startswith("*/"):
            continue

        if line.startswith("#cm="):
            current_section = line[4:].strip()
            if current_section not in data:
                data[current_section] = OrderedDict()
            continue

        if "=" in line and not line.startswith("#"):
            if current_section is None:
                current_section = "__global__"
                if current_section not in data:
                    data[current_section] = OrderedDict()

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if "//" in value:
                value = value.split("//", 1)[0].strip()

            data[current_section][key] = value

    return data


def flatten_h2p(parsed):
    flat = OrderedDict()
    for section, pairs in parsed.items():
        for key, value in pairs.items():
            flat[f"{section}.{key}"] = value
    return flat


def compare_to_init(init_flat, test_flat):
    diffs = []

    all_keys = set(init_flat.keys()) | set(test_flat.keys())

    for key in sorted(all_keys):
        init_val = init_flat.get(key)
        test_val = test_flat.get(key)
        if init_val != test_val:
            diffs.append((key, init_val, test_val))

    return diffs


def extract_target_from_folder(folder_name: str):
    """
    Expected folder format:
        Hive-Osc1.Wave
        Hive-Filter1.Type
        Hive-LFO1.Wave
    Returns:
        prefix, target_key
    """
    if "-" not in folder_name:
        return folder_name, None

    prefix, target_key = folder_name.split("-", 1)
    return prefix, target_key


def main():
    if not INIT_FILE.exists():
        raise FileNotFoundError(f"INIT file not found: {INIT_FILE}")

    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input folder not found: {INPUT_DIR}")

    init_parsed = parse_h2p(INIT_FILE)
    init_flat = flatten_h2p(init_parsed)

    output_lines = []
    review_lines = []

    h2p_files = sorted(INPUT_DIR.rglob("*.h2p"))

    for test_file in h2p_files:
        rel_path = test_file.relative_to(INPUT_DIR)
        folder_name = test_file.parent.name
        preset_name = test_file.stem.strip()

        prefix, target_key = extract_target_from_folder(folder_name)

        test_parsed = parse_h2p(test_file)
        test_flat = flatten_h2p(test_parsed)

        diffs = compare_to_init(init_flat, test_flat)

        if len(diffs) == 0:
            if target_key is None:
                review_lines.append(
                    f"; REVIEW: {rel_path} -> no differences found and folder name has no target key"
                )
                continue

            if target_key not in init_flat:
                review_lines.append(
                    f"; REVIEW: {rel_path} -> no differences found, but target key '{target_key}' not found in INIT"
                )
                continue

            init_value = init_flat[target_key]
            output_lines.append(f"{folder_name}.{preset_name} = {init_value}")
            continue

        if len(diffs) == 1:
            changed_key, init_val, test_val = diffs[0]

            if target_key is not None and changed_key != target_key:
                review_lines.append(
                    f"; REVIEW: {rel_path} -> expected target '{target_key}', but actual changed key was '{changed_key}'"
                )

            output_lines.append(f"{folder_name}.{preset_name} = {test_val}")
            continue

        review_lines.append(f"; REVIEW: {rel_path} -> multiple differences found:")
        for changed_key, init_val, test_val in diffs:
            review_lines.append(f";   {changed_key}: INIT={init_val} TEST={test_val}")

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as f:
        f.write("=====================================\n")
        f.write("; Hive Parameter Difference Report\n")
        f.write("=====================================\n\n")

        if output_lines:
            for line in output_lines:
                f.write(line + "\n")

        if review_lines:
            f.write("\n")
            for line in review_lines:
                f.write(line + "\n")

    print(f"Done. Report written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()