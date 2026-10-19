def replace_all(line, matches, replacement, word_pass=None, cap_first=True):
    line = line.strip()
    if matches is None:
        return line
    c_list = list(line)
    for match in matches:
        if word_pass is not None:
            if any([_ in "".join(c_list[match.start():match.end()]) for _ in word_pass]):
                continue
        c_list[match.start()] = replacement
        if cap_first:
            if match.start() == 0:
                c_list[0] = c_list[0][:1].upper() + c_list[0][1:]
            else:
                i = match.start() - 1
                while i >= 0 and c_list[i] in " ":
                    i -= 1
                if c_list[i] in ".!?":
                    c_list[match.start()] = c_list[match.start()][:1].upper() + c_list[match.start()][1:]
        for i in range(match.start() + 1, match.end()):
            c_list[i] = ""
    return "".join(c_list)

def uncensor(line):
    uncensor_dict = {
        "fuck": (r"(\*\*\*\*(?=( it|ing|er|'s sake| sake|'em | 'em| em| him| her| them)))|((?<=(mother))\*\*\*\*)|((?<=(as ))\*\*\*\*)|((?<= )[Ff][^a-tw-yzA-TW-YZ]?[^abd-yzABD-YZ]?[^a-jl-yzA-JL-YZ]?(?=([ !?'\"]|ed |ing |er |in |in' |ers|ed-up |\.[^a-zA-Z])))", ("f", "F")),
        "shit": (r"((?<=(as ))\*\*\*\*)|((?<=(little ))\*\*\*\*)|((?<= )[Ss][^a-gi-yzA-GI-YZ]?[^a-hj-yzA-HJ-YZ]?[^a-su-yzA-SU-YZ]?(?=([ !?'\"]|\.[^a-zA-Z])))", ("sit", "si", "st", "s", "S")),
        "bitch": (r"(\*\*\*\*\*(?=(es| ass|-ass|ass| gon)))|((?<= )[Bb][^a-hj-yzA-HJ-YZ]?[^a-su-yzA-SU-YZ]?[^abd-yzABD-YZ]?[^a-gi-yzA-GI-YZ]?(?=([ !?'\"]|es |\.[^a-zA-Z])))", ("bit", "b", "B")),
    }
    for k, v in uncensor_dict.items():
        line = replace_all(line, re.finditer(v[0], line), k, v[1])
    return line

def default_formatter(line):
    if any([line.strip().startswith(_) for _ in ["作词", "编曲", "制作", "作曲", "混音", "人声", "母带", "监制", "词", "曲", "录", "附加制作", "鼓", "贝斯", "吉他", "音频"]]):
        line = ""
    line = uncensor(line)
    if line == "":
        return "♬"
    return line

STYLES = dict()

import os
import importlib.util
import regex as re
import sys

from .utils.tools import hex_to_rgba
from .utils.dataclasses import TrackInfo
from .globalvariables import DEFAULT_THEME, THEME_FOLDER
from PyQt5.QtGui import QFontDatabase
import glob
# theme_files = glob.glob('**/*.py', root_dir=THEME_FOLDER, recursive=True)
def search_py(rootdir):
    file_list = []
    for root, directories, files in os.walk(rootdir):
        root = root.replace(rootdir, "")[1:]
        for file in files:
            if(file.endswith(".py")):
                file_list.append(os.path.join(root, file))
    return file_list

def load_themes():
    global STYLES
    STYLES = {
        "default": {
            "background-color": "#00000000",
            
            "font-color": "#bbbbbb",
            "font-family": "Spotify Mix, Arial, Microsoft YaHei UI",
            "font-size": "30px",
            "font-weight": "normal",
            "font-italic": False,
            
            
            "line-color": "#7c7a77",
            "line-width": 0.3,

            "use-shadow": True,
            "shadow-color": "#ffff97",
            "shadow-offset": [0, 0],
            "shadow-radius": 4,
            
            "flip-text": False,
            
            "format": default_formatter,
            
            "entering": "fadein",
            "sustaining": "flickering",
            "leaving": "fadeout"
        }
    }
    
    theme_files = search_py(THEME_FOLDER)
    theme_files = filter(lambda x: x.endswith(".py"), theme_files)

    for theme_file in theme_files:
        theme_name = theme_file[:-3]
        if theme_name not in STYLES:
            spec = importlib.util.spec_from_file_location("styles", os.path.join(THEME_FOLDER, theme_file))
            styles_module = importlib.util.module_from_spec(spec)
            sys.modules["styles"] = styles_module
            spec.loader.exec_module(styles_module)
            new_styles = styles_module.STYLES
            for k in list(new_styles.keys()):
                new_styles[theme_file.replace(".py", "").replace("\\", "/") + " - " + k] = new_styles.pop(k)
            STYLES.update(new_styles)

    print("Loaded Styles:", STYLES.keys())

load_themes()

from io import BytesIO
from PIL import Image

def extract_m3_palette(thumb_bytes: bytes):
    if not thumb_bytes:
        return None
    try:
        img = Image.open(BytesIO(thumb_bytes)).convert("RGB")
        small = img.resize((48, 48), Image.Resampling.LANCZOS)
        colors = small.getcolors(maxcolors=2304)
        if not colors:
            return None
        colors.sort(key=lambda x: x[0], reverse=True)
        dominant_rgb = colors[0][1]

        def luminance(rgb):
            return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]

        def to_hex(rgb):
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        # Material 3 accent: find the most vibrant/saturated color among dominant candidates
        best_accent = dominant_rgb
        max_saturation = -1
        for count, rgb in colors[:15]:
            r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
            mx, mn = max(r, g, b), min(r, g, b)
            sat = (mx - mn) / mx if mx > 0 else 0
            if sat > max_saturation and 40 < luminance(rgb) < 220:
                max_saturation = sat
                best_accent = rgb

        accent_hex = to_hex(best_accent)
        accent_lum = luminance(best_accent)

        # High-contrast readable text
        text_color = "#ffffff" if accent_lum < 160 else "#121212"

        # Frosted glass background: translucent dark with slight tint of dominant color (Telegram translucent style)
        tint_r = int(dominant_rgb[0] * 0.15 + 18 * 0.85)
        tint_g = int(dominant_rgb[1] * 0.15 + 18 * 0.85)
        tint_b = int(dominant_rgb[2] * 0.15 + 20 * 0.85)
        frosted_bg = f"#{tint_r:02x}{tint_g:02x}{tint_b:02x}cc"  # 80% opacity

        return {
            "font-color": text_color,
            "shadow-color": accent_hex,
            "progress-color": accent_hex,
            "progress-line-color": accent_hex + "44",
            "background-color": frosted_bg,
            "line-color": "#ffffff18",
            "line-width": 0.5,
        }
    except Exception as e:
        print(f"Error extracting M3 palette: {e}")
        return None

def get_style(track: TrackInfo):
    stl = STYLES["default"].copy()
    stl_name = "default"
    matched = False
    
    for name, style in STYLES.items():
        if name == "default" or "rule" not in style:
            continue
        if "rule" in style and style["rule"](track):
            stl_name = name
            matched = True
            print(f"Matching theme {name}")
            stl.update(style)
            if "format" in style:
                stl["format"] = lambda line: (style["format"](STYLES["default"]["format"](line)))
            if "font-family" in style:
                if any([_ in style["font-family"].lower() for _ in [".ttf", ".otf"]]) and os.path.exists(style["font-family"]):
                        stl["font-family"] = style["font-family"]
                else:
                    stl["font-family"] = ", ".join(list(filter(lambda x: x != " ", [_.strip() for _ in style["font-family"].split(",") + STYLES["default"]["font-family"].split(",")])))
            break

    # If no specific artist rule matched, dynamically apply Frosted Material 3 Palette from album cover
    if not matched and track and getattr(track, "thumbnail_bytes", None):
        dynamic_pal = extract_m3_palette(track.thumbnail_bytes)
        if dynamic_pal:
            stl_name = "Frosted Material 3"
            stl.update(dynamic_pal)
            matched = True

    if not matched and (DEFAULT_THEME is not None and DEFAULT_THEME in STYLES):
        stl_name = DEFAULT_THEME.replace("\\", "/")
        style = STYLES[stl_name]
        # print(f"Using Default theme {stl_name}")
        stl.update(STYLES[stl_name])
        if "format" in style:
            stl["format"] = lambda line: (style["format"](STYLES["default"]["format"](line)))         
    for key, value in stl.items():
        if 'color' in key:
            if isinstance(value, str) and re.match(r'^#[0-9a-fA-F]{3}([0-9a-fA-F]{3,5})?$', value):
                stl[key] = hex_to_rgba(value)
    stl.update({"name": stl_name})
    
    return stl