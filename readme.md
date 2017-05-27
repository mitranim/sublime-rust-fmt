## Overview

RustFmt is a Sublime Text 3 plugin that auto-formats Rust code with
[`rustfmt`](https://github.com/rust-lang-nursery/rustfmt) or another executable.

Unlike `BeautifyRust`, it's fast and works on buffers that have yet not been
saved as files. Unlike `RustFormat`, it preserves the buffer scroll position.

## Dependencies

Requires Sublime Text version 3124 or later.

Requires [`rustfmt`](https://github.com/rust-lang-nursery/rustfmt) to be on
[PATH](https://en.wikipedia.org/wiki/PATH_(variable)). Install it with Cargo:

```sh
cargo install rustfmt
```

## Installation

### Package Control

1. Get [Package Control](https://packagecontrol.io)
2. Open command palette: `Shift+Super+P` or `Shift+Ctrl+P`
3. `Package Control: Install Package`
4. `RustFmt`

### Manual

1. Open Sublime Text menu -> Preferences -> Browse Packages. This should open
   the packages folder in your OS file manager.

2. Clone repo:

```sh
git clone https://github.com/Mitranim/sublime-rust-format.git RustFmt
```

## Usage

By default, RustFmt will autoformat files before save. You can trigger it
manually with the `Ctrl+Super+k` hotkey or the `RustFmt: Format Buffer` command
in the command palette.

If the plugin can't find the executable, open Preferences -> Package Settings ->
RustFmt -> Settings. Run `which rustfmt` and set the resulting path as the
`executable` setting. On my MacOS system, the path looks like this:

```sublime-settings
  "executable": "/Users/username/.cargo/bin/rustfmt"
```

## Commands

Open the command palette with `Shift+Super+P` or `Shift+Ctrl+P`.

* `RustFmt: Format Buffer` (`Ctrl+Super+k`)

## Settings

Open Sublime Text menu -> Preferences -> Package Settings -> RustFmt -> Settings.

```sublime-settings
{
  // Format files automatically when saving
  "format_on_save": true,
  // Path to formatter executable; set to absolute path if plugin can't find it
  "executable": "rustfmt"
}
```
