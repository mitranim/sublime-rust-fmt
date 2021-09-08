import sublime
import sublime_plugin
import subprocess as sub
import os
import sys
from . import difflib

SETTINGS = 'RustFmt.sublime-settings'
DICT_KEY = 'RustFmt'
IS_WINDOWS = os.name == 'nt'


def is_rust_view(view):
    return view.score_selector(0, 'source.rust') > 0


def get_setting(view, key):
    global_overrides = view.settings().get(DICT_KEY)
    if isinstance(global_overrides, dict) and key in global_overrides:
        return global_overrides[key]
    return sublime.load_settings(SETTINGS).get(key)


def get_env(view):
    val = get_setting(view, 'env')
    if val is None:
        return None
    env = os.environ.copy()
    env.update(val)
    return env


# Copied from other plugins, haven't personally tested on Windows
def process_startup_info():
    if not IS_WINDOWS:
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


def find_config_path(path):
    for dir in walk_to_root(path):
        config = config_for_dir(dir)
        if config:
            return config


def guess_cwd(view):
    mode = get_setting(view, 'cwd_mode')

    if mode.startswith(':'):
        return mode[1:]

    if mode == 'none':
        return None

    if mode == 'project_root':
        if len(view.window().folders()):
            return view.window().folders()[0]
        return None

    if mode == 'auto':
        if view.file_name():
            return os.path.dirname(view.file_name())
        elif len(view.window().folders()):
            return view.window().folders()[0]


def merge_into_view(view, edit, new_src):
    def subview(start, end):
        return view.substr(sublime.Region(start, end))
    diffs = difflib.myers_diffs(subview(0, view.size()), new_src)
    difflib.cleanup_efficiency(diffs)
    merged_len = 0
    for (op_type, patch) in diffs:
        patch_len = len(patch)
        if op_type == difflib.Ops.EQUAL:
            if subview(merged_len, merged_len+patch_len) != patch:
                raise Exception("[sublime-rust-fmt] mismatch between diff's source and current content")
            merged_len += patch_len
        elif op_type == difflib.Ops.INSERT:
            view.insert(edit, merged_len, patch)
            merged_len += patch_len
        elif op_type == difflib.Ops.DELETE:
            if subview(merged_len, merged_len+patch_len) != patch:
                raise Exception("[sublime-rust-fmt] mismatch between diff's source and current content")
            view.erase(edit, sublime.Region(merged_len, merged_len+patch_len))


def run_format(view, input, encoding):
    exec = get_setting(view, 'executable')
    args = exec if isinstance(exec, list) else [exec]

    if get_setting(view, 'legacy_write_mode_option'):
        args += ['--write-mode', 'display']

    if get_setting(view, 'use_config_path'):
        path = view.file_name() or (
            len(view.window().folders()) and view.window().folders()[0] or None
        )

        config = path and find_config_path(path)
        if config:
            args += ['--config-path', config]

    proc = sub.Popen(
        args=args,
        stdin=sub.PIPE,
        stdout=sub.PIPE,
        stderr=sub.PIPE,
        startupinfo=process_startup_info(),
        universal_newlines=False,
        cwd=guess_cwd(view),
        env=get_env(view),
    )

    (stdout, stderr) = proc.communicate(input=bytes(input, encoding=encoding))
    (stdout, stderr) = stdout.decode(encoding), stderr.decode(encoding)

    if proc.returncode != 0:
        err = sub.CalledProcessError(proc.returncode, args)

        if get_setting(view, 'error_messages'):
            msg = str(err)
            if len(stderr) > 0:
                msg += ':\n' + stderr
            # rustfmt stupidly prints error messages to stdout
            elif len(stdout) > 0:
                msg += ':\n' + stdout
            msg += '\nNote: to disable error popups, set the RustFmt setting "error_messages" to false.'
            sublime.error_message(msg)

        raise err

    if len(stderr) > 0:
        print('[sublime-rust-fmt]:', stderr, file=sys.stderr)

    return stdout


def view_encoding(view):
    encoding = view.encoding()
    return 'UTF-8' if encoding == 'Undefined' else encoding


class rust_fmt_format_buffer(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_rust_view(self.view)

    def run(self, edit):
        view = self.view
        content = view.substr(sublime.Region(0, view.size()))

        stdout = run_format(
            view=view,
            input=content,
            encoding=view_encoding(view),
        )

        merge_type = get_setting(view, 'merge_type')

        if merge_type == 'diff':
            merge_into_view(view, edit, stdout)

        elif merge_type == 'replace':
            position = view.viewport_position()
            view.replace(edit, sublime.Region(0, view.size()), stdout)
            # Works only on main thread, hence lambda and timer.
            restore = lambda: view.set_viewport_position(position, animate=False)
            sublime.set_timeout(restore, 0)

        else:
            raise Exception('[sublime-rust-fmt] unknown merge_type setting: {}'.format(merge_type))


class rust_fmt_listener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        if is_rust_view(view) and get_setting(view, 'format_on_save'):
            view.run_command('rust_fmt_format_buffer')
