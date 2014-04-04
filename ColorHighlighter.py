# -*- coding: utf-8 -*-
import sublime, sublime_plugin
import os
import stat
import re
import colorsys
import subprocess

try:
    import colors
except ImportError:
    colors = __import__("Color Highlighter", fromlist=["colors"]).colors

version = "5.0"

hex_letters = "0123456789ABCDEFabcdef"
settings_file = "ColorHighlighter.sublime-settings"


def print_error(err):
    print(err.replace("\\n", "\n"))


def write_file(fl, s):
    f = open(fl, "w")
    f.write(s)
    f.close()

def write_bin_file(fl, s):
    f = open(fl, "wb")
    f.write(s)
    f.close()

def read_file(fl):
    f = open(fl, "r")
    res = f.read()
    f.close()
    return res


def tohex(r, g, b):
    return "#%02X%02X%02XFF" % (r, g, b)

def tohexa(r, g, b, a):
    return "#%02X%02X%02X%02X" % (r, g, b, a)


regex_rgb_s = "[r][g][b][(][ ]*\d{1,3}[ ]*[,][ ]*\d{1,3}[ ]*[,][ ]*\d{1,3}[ ]*[)]"
regex_rgba_s = "[r][g][b][a][(][ ]*\d{1,3}[ ]*[,][ ]*\d{1,3}[ ]*[,][ ]*\d{1,3}[ ]*[,][ ]*(?:\d{1,3}|[0|1]?\.\d+)[ ]*[)]"
regex_array_s = "[\[][ ]*\d{1,3}[ ]*[,][ ]*\d{1,3}[ ]*[,][ ]*\d{1,3}(?:[ ]*|[,][ ]*(?:\d{1,3}|[0|1]?\.\d+)[ ]*)[\]]"
regex_all_s = "((?:%s)|(?:%s)|(?:%s)|(?:%s)|(?:%s)|(?:%s)|(?:%s))" % ("[#][0-9a-fA-F]{8}", "[#][0-9a-fA-F]{6}", "[#][0-9a-fA-F]{4}", "[#][0-9a-fA-F]{3}", regex_rgb_s, regex_rgba_s, regex_array_s)
regex_rgb = re.compile(regex_rgb_s)
regex_rgba = re.compile(regex_rgba_s)
regex_array = re.compile(regex_array_s)
regex_all = re.compile(regex_all_s)


def hex_col_conv(col):
    if col[0] != "#":
        return None

    l = len(col)
    for c in col[1:]:
        if c not in hex_letters:
            return None
    if l == 4:
        return "#" + col[1]*2 + col[2]*2 + col[3]*2 + "FF"
    if l == 5:
        return "#" + col[1]*2 + col[2]*2 + col[3]*2 + col[4]*2
    elif l == 7:
        return col + "FF"
    elif l == 9:
        return col
    return None

def conv_to_hex(view, col, cols):
    if col is None or len(col) == 0:
        return None

    res = hex_col_conv(col)
    if res is not None:
        return res

    res = colors.names_to_hex.get(col)
    if res is not None:
        return conv_to_hex(view, res, cols)

    cs = cols.get(view.id())
    if cs is None:
        return None

    return conv_to_hex(view, cs.get(col), cols)

def to_hex_fmt(col):
    if col is None or len(col) == 0:
        return None

    res = hex_col_conv(col)
    if res is not None:
        return res

    if col.startswith("rgb("):
        return parse_col_rgb(col)

    if col.startswith("rgba("):
        return parse_col_rgba(col)
    
    return colors.names_to_hex.get(col)


def get_format(col):
    if col is None or len(col) == 0:
        return None

    if col[0] == "#":
        l = len(col)
        if l in [4, 5, 7, 9]:
            for c in col[1:]:
                if c not in hex_letters:
                    return None
            return "#%d" % l
        return None

    if col.startswith("rgb("):
        return "rgb"
    if col.startswith("rgba("):
        return col.find(".") == -1 and "rgbad" or "rgbaf"
    if col.startswith("["):
        return "arr"

    if colors.names_to_hex.get(col):
        return "named"
    return None


def parse_col_rgb(col):
    vals = list(map(lambda s: int(s.strip()), col[4:-1].split(",")))
    return tohex(vals[0], vals[1], vals[2])

def parse_col_rgba(col):
    vals = list(map(lambda s: s.strip(), col[5:-1].split(",")))
    return tohexa(int(vals[0]), int(vals[1]), int(vals[2]), vals[3].find(".") != -1 and int(float(vals[3]) * 255) or int(vals[3]))

def parse_col_array(col):
    vals = col[1:-1].split(",")
    if len(vals) == 3:
        return tohex(int(vals[0]), int(vals[1]), int(vals[2]))
    elif len(vals) == 4:
        return tohexa(int(vals[0]), int(vals[1]), int(vals[2]), vals[3].find(".") != -1 and int(float(vals[3]) * 255) or int(vals[3]))

def isInColor(view, sel, colors, array_format):
    b = sel.begin()
    if b != sel.end():
        return None, None, None

    word = view.word(b)
    # sass/less variable
    if view.substr(word.begin() - 1) in ["@", "$"]:
        word1 = sublime.Region(word.begin() - 1, word.end())
        res = conv_to_hex(view, view.substr(word1), colors)
        if res is not None:
            return word1, res, True
        return None, None, None
    # less variable interpolation
    elif view.substr(word.begin() - 1) == "{" and view.substr(word.begin() - 2) == "@" and view.substr(word.end()) == "}":
        word1 = sublime.Region(word.begin() - 2, word.end() + 1)
        res = conv_to_hex(view, "@" + view.substr(word), colors)
        if res is not None:
            return word1, res, True
        return None, None, None
    # hex colors
    elif view.substr(word.begin() - 1) == "#" and view.substr(word.begin() - 2) not in ["&"]:
        word1 = sublime.Region(word.begin() - 1, word.end())
        res = conv_to_hex(view, view.substr(word1), colors)
        if res is not None:
            return word1, res, False
        return None, None, None

    # just color
    if view.substr(word.begin() - 1) in [" ", ":"]:
        res = conv_to_hex(view, view.substr(word), colors)
        if res is not None:
            return word, res, False

    # rgb(...)
    line = view.line(b)
    line_txt = view.substr(line)
    for m in regex_rgb.findall(line_txt):
        start = line_txt.find(m) + line.begin()
        end = start + len(m)
        if b > start and b < end:
            return sublime.Region(start, end), parse_col_rgb(m), False

    # rgba(...)
    for m in regex_rgba.findall(line_txt):
        start = line_txt.find(m) + line.begin()
        end = start + len(m)
        if b > start and b < end:
            return sublime.Region(start, end), parse_col_rgba(m), False

    if array_format:
        for m in regex_array.findall(line_txt):
            start = line_txt.find(m) + line.begin()
            end = start + len(m)
            if b > start and b < end:
                return sublime.Region(start, end), parse_col_array(m), False

    return None, None, None


def get_cont_col(col):
    (h, s, v) = colorsys.rgb_to_hsv(int(col[1:3],16)/255.0, int(col[3:5],16)/255.0, int(col[5:7],16)/255.0)
    v1 = v * (s - 1) + 1
    s1 = 0
    if abs(v1) > 1e-10:
        s1 = v * s / v1
    (r, g, b) = colorsys.hsv_to_rgb(h >= 0.5 and h - 0.5 or h + 0.5, s1, v1)
    return tohex(int(r * 255), int(g * 255), int(b * 255)) # true complementary


def region_name(s):
    return "mcol_" + s[1:]


def set_scheme(view, cs):
    cs = cs.replace("\\", "/")
    sets = view.settings()
    if sets.get("color_scheme") != cs:
        print("set_scheme", sets.get("color_scheme"), cs)
        sets.set("color_scheme", cs)


class HtmlGen:
    colors = []
    color_scheme = None
    fake_scheme = None
    need_upd = False
    string = ""
    gen_string = """
<dict>
<key>name</key>
<string>mon_color</string>
<key>scope</key>
<string>%s</string>
<key>settings</key>
<dict>
<key>background</key>
<string>%s</string>
<key>caret</key>
<string>%s</string>
<key>foreground</key>
<string>%s</string>
</dict>
</dict>\n
"""

    def __init__(self, cs):
        self.color_scheme = cs
        self.fake_scheme = os.path.join("Color Highlighter", os.path.split(cs)[-1])

    def add_color(self, col):
        if col in self.colors:
            return
        self.colors.append(col)
        cont = get_cont_col(col)
        self.string += self.gen_string % (region_name(col), col, cont, cont)
        self.need_upd = True

    def update_view(self, view):
        path = os.path.join(sublime.packages_path(), self.fake_scheme)
        if not os.path.exists(path):
            set_scheme(view, self.color_scheme)
        else:
            set_scheme(view, os.path.join("Packages", self.fake_scheme))

    def update(self, view):
        if not self.need_upd:
            return False

        if get_version() >= 3000:
            cont = sublime.load_resource(self.color_scheme)
        else:
            cont = read_file(os.path.join(sublime.packages_path(), self.color_scheme[9:])).decode("utf-8")
        n = cont.find("<array>") + len("<array>")
        cont = cont[:n] + self.string + cont[n:]
        write_bin_file(os.path.join(sublime.packages_path(), self.fake_scheme), cont.encode("utf-8"))

        self.need_upd = False
        return True

    def restore(self):
        self.colors = []
        self.string = ""
        path = os.path.join(sublime.packages_path(), self.fake_scheme)
        if os.path.exists(path):
            os.remove(path)


def extract_sass_name_val(line):
    pos = line.find(":")
    if pos == -1:
        return None, None

    var = line[:pos].rstrip()
    col = line[pos+1:].lstrip()
    return var, col

def _extract_sass_fname(name):
    if not name.endswith(".sass"):
        name += ".sass"
    name = os.path.join(os.path.dirname(nm), name)
    if not os.path.exists(name):
        return None
    return name

def _extract_scss_fname(name):
    if not name.endswith(".scss"):
        name += ".scss"
    name = os.path.join(os.path.dirname(nm), name)
    if not os.path.exists(name):
        return None
    return name

def extract_sass_fname(view, line):
    nm = view.file_name()
    if nm is None:
        return None

    line = line[8:-1].strip()[1:-1]
    name = _extract_sass_fname(line)
    if name is None:
        name = _extract_scss_fname(line)
    return name

def find_sass_vars(view, text, cols):
    for line in map(lambda s: s.strip(), text.split("\n")):
        if len(line) < 2 or line[0] != "$":
            continue

        if line.startswith("@import"):
            name = extract_sass_fname(view, line)
            if name != None:
                find_sass_vars(view, read_file(name), cols)
            continue

        var, col = extract_sass_name_val(line)
        if var != None:
            cols[var] = col

def extract_less_name_val(line):
    pos = line.find(":")
    if pos == -1:
        return None, None

    var = line[:pos].rstrip()
    col = line[pos+1:-1].strip()
    return var, col

def extract_less_fname(view, line):
    nm = view.file_name()
    if nm is None:
        return None
    name = line[8:-1].strip()[1:-1]
    if not name.endswith(".less"):
        name += ".less"
    name = os.path.join(os.path.dirname(nm), name)
    if not os.path.exists(name):
        return None
    return name

def find_less_vars(view, text, cols):
    for line in map(lambda s: s.strip(), text.split("\n")):
        if len(line) < 2 or line[0] != "@":
            continue

        if line.startswith("@import"):
            name = extract_less_fname(view, line)
            if name != None:
                find_less_vars(view, read_file(name), cols)
            continue

        var, col = extract_less_name_val(line)
        if var != None:
            cols[var] = col


def get_doc_text(view):
    return view.substr(sublime.Region(0, view.size())) # TODO: better way to select all document


def parse_stylesheet(view, colors):
    nm = view.file_name()
    if nm is None:
        return

    name, ext = os.path.splitext(nm)
    text = get_doc_text(view)
    if ext in [".sass", ".scss"]:
        find_sass_vars(view, text, colors)
    elif ext in [".less"]:
        find_less_vars(view, text, colors)


class Logic:
    views_ids = []
    views = {}
    settings = {}
    

    color_schemes = {}
    def get_html_gen(self, cs):
        if cs not in self.color_schemes.keys():
            self.color_schemes[cs] = HtmlGen(cs)
        return self.color_schemes[cs]


    def on_g_settings_change(self):
        # sets = sublime.load_settings("Preferences.sublime-settings")
        pass

    def on_ch_settings_change(self):
        sets = sublime.load_settings(settings_file)

        enabled = sets.get("enabled")
        if enabled != self.settings["enabled"]:
            self.settings["enabled"] = enabled
            self.on_selection_modified(sublime.active_window().active_view())

        style = sets.get("style")
        if style != self.settings["style"]:
            self.settings["style"] = style
            self.on_selection_modified(sublime.active_window().active_view())

        highlight_all = sets.get("highlight_all")
        if highlight_all != self.settings["highlight_all"]:
            self.settings["highlight_all"] = highlight_all
            self.on_activated(sublime.active_window().active_view())

        ha_style = sets.get("ha_style")
        if ha_style != self.settings["ha_style"]:
            self.settings["ha_style"] = ha_style
            self.on_activated(sublime.active_window().active_view())

    def on_settings_change_view(self, view):
        sets = view.settings()
        cs = sets.get("color_scheme")
        print("on_settings_change_view(%d)" % (view.id()), self.settings["color_scheme"], cs)
        if cs.endswith(".tmTheme") and not cs.startswith(os.path.join("Packages", "Color Highlighter")) and cs != self.settings["color_scheme"]:
            self.views[view.id()]["settings"]["color_scheme"] = cs
            print("New Color Scheme: " + cs)
            htmlGen = self.get_html_gen(cs)
            self.views[view.id()]["html_gen"] = htmlGen
            htmlGen.update_view(view)
            
#FFF
    inited = False
    def init(self):
        if self.inited:
            return

        sets = sublime.load_settings(settings_file)

        self.settings["enabled"] = sets.get("enabled")
        self.settings["highlight_all"] = sets.get("highlight_all")
        self.settings["style"] = sets.get("style")
        self.settings["ha_style"] = sets.get("ha_style")

        sets.clear_on_change("ColorHighlighter")
        sets.add_on_change("ColorHighlighter", lambda: self.on_ch_settings_change())

        sets = sublime.load_settings("Preferences.sublime-settings")

        self.settings["color_scheme"] = sets.get("color_scheme")

        sets.clear_on_change("ColorHighlighter")
        sets.add_on_change("ColorHighlighter", lambda: self.on_g_settings_change())

        self.inited = True

    def init_view(self, view):
        if view.id() in self.views.keys():
            return
        sets = view.settings()
        cs = sets.get("color_scheme")
        htmlGen = self.get_html_gen(cs)
        htmlGen.update_view(view)
        self.views[view.id()] = {"view": view, "colors": {}, "regions": [], "hl_all_regions": [], "settings" : {"color_scheme": cs}, "html_gen": htmlGen}
        sets.clear_on_change("ColorHighlighter")
        sets.add_on_change("ColorHighlighter", lambda v=view: self.on_settings_change_view(v))


    def on_new(self, view):
        self.init()
        self.init_view(view)

    def on_clone(self, view):
        self.on_new(view)

    def on_load(self, view):
        self.on_new(view)

    def on_close(self, view):
        del(self.views[view.id()])

    def on_activated(self, view):
        self.init()
        self.init_view(view)

        view_obj = self.views[view.id()]

        view_obj["colors"] = {}
        parse_stylesheet(view, view_obj["colors"])

        self.clean_hl_all_regions(view)
        if not self.settings["highlight_all"]:
            return
        
        htmlGen = view_obj["html_gen"]
        regs = view_obj["hl_all_regions"]

        res = self.find_all(regex_all, get_doc_text(view), view, htmlGen, view_obj["colors"])
        if htmlGen.update(view):
            htmlGen.update_view(view)

        i = 0
        flags = self.get_regions_ha_flags()
        for s, e, col in res:
            i += 1
            st = "mon_CH_ALL_" + str(i)
            regs.append(st)
            view.add_regions(st, [sublime.Region(s, e)], region_name(col), "", flags)

    def on_selection_modified(self, view):
        self.init()
        self.init_view(view)

        self.clean_regions(view)
        if not self.settings["enabled"]:
            return

        view_obj = self.views[view.id()]
        htmlGen = view_obj["html_gen"]
        regs = view_obj["regions"]

        words = self.get_words(view, htmlGen, view_obj["colors"])
        if htmlGen.update(view):
            htmlGen.update_view(view)

        i = 0
        flags = self.get_regions_flags()
        for w, col, _ in words:
            i += 1
            s = "mon_CH_" + str(i)
            regs.append(s)
            view.add_regions(s, [w], region_name(col), "", flags)
        

    def find_all(self, regex, text, view, htmlGen, colors):
        res = []
        m = regex.search(text)
        array_format = self.get_arr_fmt(view)
        while m:
            wd, col, var = isInColor(view, sublime.Region(m.start()+1, m.start()+1), colors, array_format=array_format)
            if col is not None:
                res.append((wd.begin(), wd.end(), col))
                htmlGen.add_color(col)
            m = regex.search(text, m.end())
        return res

    def _get_regions_flags(self, style):
        if style == "default" or style == "filled":
            return 0
        if get_version() < 3000:
            if style == "outlined":
                return sublime.DRAW_OUTLINED
        else:
            if style == "outlined":
                return sublime.DRAW_NO_FILL
            if style == "underlined" or style == "underlined_solid":
                return sublime.DRAW_NO_FILL|sublime.DRAW_NO_OUTLINE|sublime.DRAW_SOLID_UNDERLINE
            elif style == "underlined_strippled":
                return sublime.DRAW_NO_FILL|sublime.DRAW_NO_OUTLINE|sublime.DRAW_STIPPLED_UNDERLINE
            elif style == "underlined_squiggly":
                return sublime.DRAW_NO_FILL|sublime.DRAW_NO_OUTLINE|sublime.DRAW_SQUIGGLY_UNDERLINE
        return 0

    def get_regions_flags(self):
        return self._get_regions_flags(self.settings["style"])

    def get_regions_ha_flags(self):
        return self._get_regions_flags(self.settings["ha_style"])

    def clean_regions(self, view):
        view_obj = self.views[view.id()]
        for s in view_obj["regions"]:
            view.erase_regions(s)
        view_obj["regions"] = []

    def clean_hl_all_regions(self, view):
        view_obj = self.views[view.id()]
        for s in view_obj["hl_all_regions"]:
            view.erase_regions(s)
        view_obj["hl_all_regions"] = []

    def get_arr_fmt(self, view):
        array_format = False
        nm = view.file_name()
        if nm is not None:
            name, ext = os.path.splitext(nm)
            if ext in [".sublime-theme"]:
                array_format = True
        return array_format

    def get_words(self, view, htmlGen, colors):
        words = []
        array_format = self.get_arr_fmt(view)
        for s in view.sel():
            wd, col, var = isInColor(view, s, colors, array_format=array_format)
            if col is None:
                continue
            htmlGen.add_color(col)
            words.append((wd, col, var))
        return words

    def get_words_pub(self, view):
        view_obj = self.views[view.id()]
        return self.get_words(view, view_obj["html_gen"], view_obj["colors"])

global_logic = Logic()


class ChSetSetting(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        sublime.load_settings(settings_file).set(args["setting"], args["value"])
        sublime.save_settings(settings_file)

    def is_visible(self, **args):
        setting = args["setting"]
        if setting == "style":
            if get_version() >= 3000:
                return True
            return args["value"] in ["default", "filled", "outlined"]
        elif setting == "ha_style":
            if get_version() >= 3000:
                return True
            return args["value"] in ["default", "filled", "outlined"]
        elif setting == "enabled":
            return args["value"] != global_logic.settings["enabled"]
        elif setting == "highlight_all":
            return args["value"] != global_logic.settings["highlight_all"]
        return False


class ColorSelection(sublime_plugin.EventListener):
    def on_new(self, view):
        # print("on_new(%d)" % (view.id()))
        global_logic.on_new(view)

    def on_clone(self, view):
        # print("on_clone(%d)" % (view.id()))
        global_logic.on_clone(view)

    def on_close(self, view):
        # print("on_close(%d)" % (view.id()))
        global_logic.on_close(view)

    def on_selection_modified(self, view):
        # print("on_selection_modified(%d)" % (view.id()))
        global_logic.on_selection_modified(view)

    def on_activated(self, view):
        # print("on_activated(%d)" % (view.id()))
        global_logic.on_activated(view)

    # def on_deactivated(self, view):
    #     print("on_deactivated(%d)" % (view.id()))

    # def on_load(self, view):
    #     print("on_load(%d)" % (view.id()))

    # def on_pre_close(self, view):
    #     print("on_pre_close(%d)" % (view.id()))


# command to restore color scheme
class RestoreColorSchemeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for hg in global_logic.color_schemes:
            hg.restore()


def get_version():
    return int(sublime.version())


def get_platform():
    plat = sublime.platform()
    if plat == "windows":
        plat = "win"
    return plat


def get_ext():
    plat = get_platform()
    res = plat + "_" + sublime.arch()
    if plat == "win":
        res += ".exe"
    return res


def plugin_loaded():
    path = os.path.join(sublime.packages_path(), "Color Highlighter")
    if get_version() >= 3000:
        if not os.path.exists(path):
            os.mkdir(path)

    bin = "ColorPicker_" + get_ext()
    fpath = os.path.join(path, bin)
    if get_version() >= 3000:
        if not os.path.exists(fpath):
            data = sublime.load_binary_resource(os.path.join("Packages", "Color Highlighter", bin))
            if len(data) != 0:
                write_bin_file(fpath, data)
                os.chmod(fpath, stat.S_IXUSR|stat.S_IXGRP)
    else:
        if os.path.exists(fpath):
            os.chmod(fpath, stat.S_IXUSR|stat.S_IXGRP)

if get_version() < 3000:
    plugin_loaded()


def conv_to_format(base, col):
    fmt = get_format(base)
    if fmt is None:
        return None

    if fmt[0] == "#" or fmt == "named":
        return col

    if fmt == "rgb":
        return "rgb(%d,%d,%d)" % (int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16))
    if fmt == "rgbad":
        return "rgba(%d,%d,%d,%d)" % (int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16), int(col[7:9], 16))
    if fmt == "rgbaf":
        return "rgba(%d,%d,%d,%f)" % (int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16), int(col[7:9], 16)/255.0)


class ColorPickerCommand(sublime_plugin.TextCommand):
    words = []
    col = None
    ext = get_ext()

    def run(self, edit):
        path = os.path.join(sublime.packages_path(), "Color Highlighter", "ColorPicker_" + self.ext)
        words = global_logic.get_words_pub(self.view)
        popen = subprocess.Popen([path, self.col[1:-2]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        err = str(popen.stderr.read())[2:-1]
        if err is not None and len(err) != 0:
            print_error("Color Picker error:\n" + err)
            return

        output = str(popen.stdout.read())[2:-1]
        if output is None or len(output) == 0 or output == self.col or output == "#000000FF":
            return

        for w, c, v in self.words:
            if w is None or v:
                continue
            new_col = conv_to_format(self.view.substr(w), output)
            if new_col is None:
                continue
            self.view.replace(edit, w, new_col)

    def is_enabled(self):
        self.words = global_logic.get_words_pub(self.view)
        wd = None
        self.col = None
        for w, c, v in self.words:
            if w is not None and not v:
                wd, self.col = w, c
                break

        return wd is not None and self.col is not None
