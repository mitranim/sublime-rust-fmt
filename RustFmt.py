import sublime
import sublime_plugin
import subprocess as sub
import os
import sys

from .lib.myers_diff import myers_diffs, cleanup_efficiency, Ops


SETTINGS = 'RustFmt.sublime-settings'
DICT_KEY = 'RustFmt'


def is_rust_view(view):
    return view.score_selector(0, 'source.rust') > 0


def is_windows():
    return os.name == 'nt'


def settings_get(view, key):
    global_dict = view.settings().get(DICT_KEY)
    if isinstance(global_dict, dict) and key in global_dict:
        return global_dict[key]
    return sublime.load_settings(SETTINGS).get(key)


def process_startup_info():
    if not is_windows():
        return None
    startupinfo = sub.STARTUPINFO()
    startupinfo.dwFlags |= sub.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = sub.SW_HIDE
    return startupinfo


def walk_to_root(path):
    if path is None:
        return

    if os.path.isdir(path):
        yield path

    while not os.path.samefile(path, os.path.dirname(path)):
        path = os.path.dirname(path)
        yield path


def config_for_dir(dir):
    path = os.path.join(dir, 'rustfmt.toml')
    if os.path.exists(path) and os.path.isfile(path):
        return path

    hidden_path = os.path.join(dir, '.rustfmt.toml')
    if os.path.exists(hidden_path) and os.path.isfile(hidden_path):
        return hidden_path

    return None


def first(iterable, condition = lambda x: True):
    return next((x for x in iterable if condition(x)), None)


def run_format(view, input, encoding):
    args = to_list(settings_get(view, 'executable')) + ['--write-mode=display']

    iterable = map(config_for_dir, walk_to_root(view.file_name()))
    config = first(iterable, lambda x: x is not None)
    if config is not None:
        args += ['--config-path={}'.format(config)]

    proc = sub.Popen(
        args=args,
        stdin=sub.PIPE,
        stdout=sub.PIPE,
        stderr=sub.PIPE,
        startupinfo=process_startup_info(),
        universal_newlines=False
    )
    (stdout, stderr) = proc.communicate(input=bytes(input, encoding=encoding))
    return (stdout.decode(encoding), stderr.decode(encoding))


def to_list(value):
    if isinstance(value, list): return value
    return [value]


def view_encoding(view):
    encoding = view.encoding()
    return 'UTF-8' if encoding == 'Undefined' else encoding


class RustFmtViewMergeException(Exception):
    pass


def merge_into_view(view, edit, new_src):
    def subview(start, end):
        return view.substr(sublime.Region(start, end))
    diffs = myers_diffs(subview(0, view.size()), new_src)
    cleanup_efficiency(diffs)
    merged_len = 0
    for (op_type, patch) in diffs:
        patch_len = len(patch)
        if op_type == Ops.EQUAL:
            if subview(merged_len, merged_len+patch_len) != patch:
                raise RustFmtViewMergeException('mismatch')
            merged_len += patch_len
        elif op_type == Ops.INSERT:
            view.insert(edit, merged_len, patch)
            merged_len += patch_len
        elif op_type == Ops.DELETE:
            if subview(merged_len, merged_len+patch_len) != patch:
                raise RustFmtViewMergeException('mismatch')
            view.erase(edit, sublime.Region(merged_len, merged_len+patch_len))


class rust_fmt_format_buffer(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_rust_view(self.view)

    def run(self, edit):
        content = self.view.substr(sublime.Region(0, self.view.size()))

        (stdout, stderr) = run_format(
            view=self.view,
            input=content,
            encoding=view_encoding(self.view)
        )

        if stderr:
            print('RustFmt error:', file=sys.stderr)
            print(stderr, file=sys.stderr)
            return

        self.view.settings().set('translate_tabs_to_spaces', True)

        # (1) Broken approach

        # Would be so nice and simple to just replace the view buffer.
        # Unfortunately it causes the scroll position to jump around.
        # Saving and restoring scroll position doesn't seem to work.

        # position = self.view.viewport_position()
        # self.view.replace(edit, sublime.Region(0, self.view.size()), stdout)
        # self.view.set_viewport_position(xy=position, animate=False)

        # (2) Working approach

        # This ridiculously convoluted method preserves the scroll position

        merge_into_view(self.view, edit, stdout)


class rust_fmt_listener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        if is_rust_view(view) and settings_get(view, 'format_on_save'):
            view.run_command('rust_fmt_format_buffer')
