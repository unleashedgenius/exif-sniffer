# ExifSniffer MCP Server

Container-ready [Model Context Protocol](https://modelcontextprotocol.io) server (Python, official `mcp` SDK) exposing **Streamable HTTP** on `/mcp`. Tools download remote media and extract image EXIF / video container metadata as **JSON arrays** of `{path, value}` rows.

The Python package and CLI are **`exifsniffer`** (`python -m exifsniffer`, console script `exifsniffer`).

## Git

After you create a repository on your Git host, add it as `origin` and push (branch name may vary):

```bash
git remote add origin <your-repository-url>
git push -u origin main
```

## Tools

| Tool | Purpose |
| --- | --- |
| `fetch_remote_media` | HTTP(S) download into `DATA_DIR` with SSRF guards and size limits; returns a JSON list of metadata rows |
| `extract_metadata_to_json` | Pillow EXIF for images; PNG **`tEXt`** / **`zTXt`** text chunks; `ffprobe` JSON for videos; writes a JSON **array** file and returns the same list |
| `validate_local_media_root` | Checks that `local_media_root` is an absolute path to an existing directory (returns `usable` and `resolved_root` or `error`) |
| `list_local_media_images` | Lists images under a caller-supplied absolute `local_media_root` (optional subdirectory, optional recursion, `max_files` cap) |
| `extract_local_media_metadata_to_json` | Same extraction as `extract_metadata_to_json` but reads the source from `local_media_root` + relative path; JSON output still goes under `DATA_DIR` |
| `update_local_media_exif` | Reads and rewrites EXIF on `.jpg` / `.jpeg` / `.webp` under `local_media_root` using `set_tags` and `remove_tags` (piexif; in-place) |

Each list element is an object: `{"path": "<dot or bracket path>", "value": ...}` where `value` is a leaf (string, number, boolean, or small JSON-serializable structure).

## Configuration (environment)

| Variable | Default | Description |
| --- | --- | --- |
| `DATA_DIR` | `/data` | Root directory for all relative paths (including JSON outputs from local media extraction) |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `3000` | Listen port |
| `MAX_DOWNLOAD_BYTES` | `100000000` | Maximum download size |
| `FETCH_CONNECT_TIMEOUT_S` | `10` | Connect timeout (seconds) |
| `FETCH_READ_TIMEOUT_S` | `120` | Read timeout (seconds) |
| `FETCH_MAX_REDIRECTS` | `8` | Max HTTP redirects |
| `FETCH_ALLOW_PRIVATE_HOSTS` | unset | Set to `true` to allow RFC1918/link-local targets (unsafe) |
| `FETCH_ALLOWED_HOST_SUFFIXES` | unset | Comma-separated; if set, host must match one suffix |
| `FETCH_BLOCKED_HOST_SUFFIXES` | unset | Comma-separated host suffix blocklist |

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# ffprobe required for video:
export DATA_DIR="$PWD/data"
mkdir -p "$DATA_DIR"
export PORT=3000
python -m exifsniffer
```

## Docker

```bash
docker compose up --build
```

The image `exifsniffer:local` runs the app as a non-root user; data persists in the `exifsniffer_data` volume.

## Cursor `mcp.json` entry

After the server listens on port `3000` (host), add:

```json
{
  "mcpServers": {
    "exif-sniffer": {
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

Place this in **project** `.cursor/mcp.json` or **global** `~/.cursor/mcp.json`. Restart Cursor after changes.

If you expose the server on another host/port, replace `localhost:3000` accordingly.

## Tests

```bash
pytest
```

## License

See [LICENSE](LICENSE).
