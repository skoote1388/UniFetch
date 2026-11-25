# UniFetch

**One fetch. Every system.**

UniFetch is a lightweight, dependency-free, Neofetch-style system information tool
for Linux, macOS, and BSD.

## Requirements

- Python 3.8 or newer
- Optional utilities improve detection: `lspci`, `nvidia-smi`, and `xprop`

Missing utilities or unavailable information are skipped automatically.

## Run from source

```bash
python3 unifetch.py
```

## Install for your user

```bash
chmod +x install.sh
./install.sh
```

The installer places the command at `~/.local/bin/unifetch`. If that directory is
not in your `PATH`, add it to your shell configuration.

For Bash:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

For Fish:

```fish
fish_add_path ~/.local/bin
```

## Options

```bash
unifetch
unifetch --json
unifetch --no-color
unifetch --logo
unifetch --version
```

## Current detection

- Linux distribution via `/etc/os-release`
- macOS and common BSD variants
- CPU, GPU, memory, uptime, root filesystem usage
- Shell, terminal, desktop environment, and window system
- Package counts for common package managers

Detection is best-effort. Different operating systems expose different system details,
so some fields may be unavailable on minimal installations.

## Roadmap

- [ ] More distribution-specific logos
- [ ] User-editable themes and layouts
- [ ] Better BSD and macOS hardware detection
- [ ] Multiple disk and battery reporting
- [ ] Configuration file support
- [ ] Automated tests across operating systems

## License

MIT. See [LICENSE](LICENSE).
