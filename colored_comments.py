import sublime
import sublime_plugin
from .color_manager import ColorManager
import regex
from collections import OrderedDict
from os import path

NAME = "Colored Comments"
VERSION = "2.1.0"
SETTINGS = dict()
TAG_MAP = dict()
TAG_REGEX = OrderedDict()


class ColorCommentsEventListener(sublime_plugin.EventListener):
    def on_load(self, view):
        view.run_command("colored_comments")

    def on_modified(self, view):
        view.run_command("colored_comments")


class ColoredCommentsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if self.view.match_selector(0, "text.plain"):
            return
        global TAG_MAP, SETTINGS, TAG_REGEX
        get_settings()

        comment_selector = "comment - punctuation.definition.comment"
        regions = self.view.find_by_selector(comment_selector)

        if SETTINGS.get("prompt_new_color_scheme", True):
            color_scheme_manager = ColorManager(
                "User/Colored Comments", TAG_MAP, SETTINGS, False
            )
            color_scheme_manager.create_user_custom_theme()
        self.ApplyDecorations(TAG_REGEX, regions, TAG_MAP, SETTINGS)

    def ApplyDecorations(self, delimiter, regions, tags, settings):
        to_decorate = dict()

        for tag in tags:
            to_decorate[tag] = []

        previous_match = ""
        for region in regions:
            for reg in self.view.split_by_newlines(region):
                reg_text = self.view.substr(reg).strip()
                for tag_identifier in delimiter:
                    matches = delimiter[tag_identifier].search(reg_text)
                    if not matches:
                        if len(reg_text) != 0:
                            if (
                                settings.get("continued_matching")
                                and previous_match != ""
                                and reg_text[0] == "-"
                            ):
                                to_decorate[previous_match] += [reg]
                            else:
                                previous_match = ""
                        continue
                    previous_match = tag_identifier
                    to_decorate[tag_identifier] += [reg]
                    break

            for value in to_decorate:
                sel_tag = tags[value]
                flags = self.get_tag_flags(sel_tag)
                scope_to_use = ""
                if "scope" in sel_tag.keys():
                    scope_to_use = sel_tag["scope"]
                else:
                    scope_to_use = (
                        "colored.comments.color."
                        + sel_tag["color"]["name"].replace(" ", ".").lower()
                    )

                self.view.add_regions(
                    value, to_decorate[value], scope_to_use, "", flags
                )

    def get_tag_flags(self, tag):
        options = {
            "outline": sublime.DRAW_NO_FILL,
            "underline": sublime.DRAW_SOLID_UNDERLINE,
            "stippled_underline": sublime.DRAW_STIPPLED_UNDERLINE,
            "squiggly_underline": sublime.DRAW_SQUIGGLY_UNDERLINE,
        }
        flags = sublime.PERSISTENT
        for key, value in options.items():
            if key in tag.keys() and tag[key] is True:
                flags |= value
        return flags


class ColoredCommentsThemeGeneratorCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global TAG_MAP, SETTINGS, TAG_REGEX
        get_settings()
        TAG_REGEX = generate_identifier_expression(TAG_MAP)
        color_scheme_manager = ColorManager(
            "User/Colored Comments", TAG_MAP, SETTINGS, True
        )
        color_scheme_manager.create_user_custom_theme()


class ColoredCommentsThemeRevertCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global SETTINGS
        get_settings()
        preferences = sublime.load_settings("Preferences.sublime-settings")
        old_color_scheme = SETTINGS.get("old_color_scheme", "")
        if old_color_scheme == "" or not path.exists(old_color_scheme):
            preferences.erase("color_scheme")
        else:
            preferences.set("color_scheme", old_color_scheme)
        sublime.save_settings("Preferences.sublime-settings")
        SETTINGS.erase("old_color_scheme")
        sublime.save_settings("colored_comments.sublime-settings")


def escape_regex(pattern):
    pattern = regex.escape(pattern)
    for character in "'<>`":
        pattern = pattern.replace("\\" + character, character)
    return pattern


def generate_identifier_expression(tags):
    unordered_tags = dict()
    ordered_tags = OrderedDict()
    identifiers = OrderedDict()
    for key, value in tags.items():
        priority = 2147483647
        if value.get("priority", False):
            priority = value.get("priority")
            try:
                priority = int(priority)
            except ValueError:
                priority = 2147483647
        if not unordered_tags.get(priority, False):
            unordered_tags[priority] = list()
        unordered_tags[priority] += [{"name": key, "settings": value}]
    for key in sorted(unordered_tags):
        ordered_tags[key] = unordered_tags[key]

    for key, value in ordered_tags.items():
        for tag in value:
            tag_identifier = "^("
            tag_identifier += (
                tag["settings"]["identifier"]
                if tag["settings"].get("is_regex", False)
                else escape_regex(tag["settings"]["identifier"])
            )
            tag_identifier += ")[ \t]+(?:.*)"
            identifiers[tag["name"]] = regex.compile(tag_identifier)
    return identifiers


def get_settings():
    global TAG_MAP, SETTINGS
    SETTINGS = sublime.load_settings("colored_comments.sublime-settings")
    TAG_MAP = SETTINGS.get("tags", [])


def plugin_loaded():
    get_settings()
    global TAG_MAP, TAG_REGEX
    TAG_REGEX = generate_identifier_expression(TAG_MAP)


def plugin_unloaded():
    preferences = sublime.load_settings("Preferences.sublime-settings")
    cc_preferences = sublime.load_settings("colored_comments.sublime-settings")
    old_color_scheme = cc_preferences.get("old_color_scheme", "")
    if old_color_scheme != "":
        preferences.set("color_scheme", old_color_scheme)
    else:
        preferences.erase("color_scheme")
    sublime.save_settings("Preferences.sublime-settings")
