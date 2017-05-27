## RustFmt Installation

Make sure you have the `rustfmt` executable in your $PATH. Install it with Cargo:

```sh
cargo install rustfmt
```

If the plugin can't find the executable, open Preferences -> Package Settings ->
RustFmt -> Settings. Run `which rustfmt` and set the resulting path as the
`executable` setting. On my MacOS system, the path looms like this:

```sublime-settings
  "executable": "/Users/username/.cargo/bin/rustfmt"
```
