## Overview

RustFmt is a Sublime Text 3 plugin that auto-formats Rust code with [`rustfmt`](https://github.com/rust-lang-nursery/rustfmt) or another executable.

Unlike `BeautifyRust`, it's fast and works on buffers that have yet not been saved as files. Unlike `RustFormat`, it preserves the buffer scroll position. It also supports `rustfmt.toml`.

## Dependencies

Requires Sublime Text version 3124 or later.

Requires [`rustfmt`](https://github.com/rust-lang/rustfmt) to be on [PATH](https://en.wikipedia.org/wiki/PATH_(variable)). Installation:

```sh
rustup component add rustfmt
```

## Installation

### Package Control

1. Get [Package Control](https://packagecontrol.io)
2. Open command palette: `Shift+Super+P` or `Shift+Ctrl+P`
3. `Package Control: Install Package`
4. `RustFmt`

### Manual

Clone the repo:

```sh
git clone https://github.com/mitranim/sublime-rust-fmt.git
```

Then symlink it to your Sublime packages directory. Example for MacOS:

```sh
mv sublime-rust-fmt RustFmt
cd RustFmt
ln -sf "$(pwd)" "$HOME/Library/Application Support/Sublime Text 3/Packages/"
```

To find the packages directory, use Sublime Text menu → Preferences → Browse Packages.

## Usage

By default, RustFmt will autoformat files before saving. You can trigger it
manually with the `RustFmt: Format Buffer` command in the command palette.

If the plugin can't find the executable:

  * run `which rustfmt` to get the absolute executable path
  * set it as the `executable` setting, see [Settings](#settings) below

On MacOS, it might end up like this:

```sublime-settings
  "executable": ["/Users/username/.cargo/bin/rustfmt"]
```

Can pass additional arguments:

```sublime-settings
  "executable": ["rustup", "run", "nightly", "rustfmt"]
```

## Settings

See [`RustFmt.sublime-settings`](RustFmt.sublime-settings) for all available settings. To override them, open:

```
Preferences → Package Settings → RustFmt → Settings
```

RustFmt looks for settings in the following places:

  * `"RustFmt"` dict in general Sublime settings, possibly project-specific
  * `RustFmt.sublime-settings`, default or user-created

The general Sublime settings take priority. To override them on a per-project basis, create a `"RustFmt"` entry:

```sublime-settings
  "RustFmt": {
    "format_on_save": false
  },
```

## Commands

In Sublime's command palette:

* `RustFmt: Format Buffer`

## Hotkeys

To avoid potential conflicts, this plugin does not come with hotkeys. To hotkey
the format command, add something like this to your `.sublime-keymap`:

```sublime-keymap
{
  "keys": ["ctrl+super+k"],
  "command": "rust_fmt_format_buffer",
  "context": [{"key": "selector", "operator": "equal", "operand": "source.rust"}]
}
```

## License

https://en.wikipedia.org/wiki/WTFPL
