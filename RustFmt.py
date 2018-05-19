import sublime
import sublime_plugin
import subprocess as sub
import os
import sys


SETTINGS = 'RustFmt.sublime-settings'
DICT_KEY = 'RustFmt'


def is_rust_view(view):
    return view.score_selector(0, 'source.rust') > 0


def is_windows():
    return os.name == 'nt'


def get_setting(view, key):
    global_dict = view.settings().get(DICT_KEY)
    if isinstance(global_dict, dict) and key in global_dict:
        return global_dict[key]
    return sublime.load_settings(SETTINGS).get(key)


# Copied from other plugins, haven't personally tested on Windows
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


def find_config_path(path):
    return first(map(config_for_dir, walk_to_root(path)), lambda x: x is not None)


def run_format(view, input, encoding):
    args = to_list(get_setting(view, 'executable'))

    if get_setting(view, 'legacy_write_mode_option'):
        args += ['--write-mode', 'display']
    else:
        args += ['--emit', 'stdout']

    if get_setting(view, 'use_config_path'):
        path = view.file_name() or first(view.window().folders(), bool)
        config = path and find_config_path(path)
        if config:
            args += ['--config-path', config]

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


class rust_fmt_format_buffer(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_rust_view(self.view)

    def run(self, edit):
        view = self.view
        content = view.substr(sublime.Region(0, view.size()))

        (stdout, stderr) = run_format(
            view=view,
            input=content,
            encoding=view_encoding(view)
        )

        if stderr:
            print('RustFmt error:', file=sys.stderr)
            print(stderr, file=sys.stderr)
            return

        view.settings().set('translate_tabs_to_spaces', True)

        position = view.viewport_position()

        view.replace(edit, sublime.Region(0, view.size()), stdout)

        # Works only on the main thread, hence the timer
        restore = lambda: view.set_viewport_position(position, animate=False)
        sublime.set_timeout(restore, 0)


class rust_fmt_listener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        if is_rust_view(view) and get_setting(view, 'format_on_save'):
            view.run_command('rust_fmt_format_buffer')
