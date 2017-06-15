import sublime
import sublime_plugin
import subprocess as sub
import os
import sys

from .lib.myers_diff import myers_diffs, cleanup_efficiency, Ops


SETTINGS = 'RustFmt.sublime-settings'


def is_rust_view(view):
    return view.score_selector(0, 'source.rust') > 0


def is_windows():
    return os.name == 'nt'


def settings_get(key):
    return sublime.load_settings(SETTINGS).get(key)


def settings_set(key):
    sublime.load_settings(SETTINGS).set(key)
    sublime.save_settings(SETTINGS)


def process_startup_info():
    if not is_windows():
        return None
    startupinfo = sub.STARTUPINFO()
    startupinfo.dwFlags |= sub.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = sub.SW_HIDE
    return startupinfo


def run_format(input, encoding):
    proc = sub.Popen(
        args=[settings_get('executable'), '--write-mode=display'],
        stdin=sub.PIPE,
        stdout=sub.PIPE,
        stderr=sub.PIPE,
        startupinfo=process_startup_info(),
        universal_newlines=False
    )
    (stdout, stderr) = proc.communicate(input=bytes(input, encoding=encoding))
    return (stdout.decode(encoding), stderr.decode(encoding))


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

        (stdout, stderr) = run_format(input=content, encoding=self.view.encoding())

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
        if is_rust_view(view) and settings_get('format_on_save'):
            view.run_command('rust_fmt_format_buffer')
