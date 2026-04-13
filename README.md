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
| `list_files` | When `LOCAL_MEDIA_BASE` is set: list top-level names under that directory (same idea as [taderich73/filesystem-access](https://lmstudio.ai/taderich73/filesystem-access) `list_files`) |
| `read_file` | Read a UTF-8 file under `LOCAL_MEDIA_BASE` via a relative `file_name` (plugin-style path rules) |
| `write_file` | Write UTF-8 content under `LOCAL_MEDIA_BASE`, creating parent dirs as needed |
| `create_directory` | Create a subdirectory under `LOCAL_MEDIA_BASE` |
| `extract_metadata` | Read an image or video under `LOCAL_MEDIA_BASE`; optional JSON array output under the same base; same path rules as `read_file` |
| `write_metadata` | Update EXIF in place on `.jpg` / `.jpeg` / `.webp` under `LOCAL_MEDIA_BASE` (same path rules as `write_file`) |

Each list element is an object: `{"path": "<dot or bracket path>", "value": ...}` where `value` is a leaf (string, number, boolean, or small JSON-serializable structure).

### Replicating the LM Studio “Base Directory” text field

In the LM Studio Hub plugin [taderich73/filesystem-access](https://lmstudio.ai/taderich73/filesystem-access), the orange **Base Directory** label, grey subtitle *The directory path where files will be stored.*, and path text box are **not** hand-built UI: they come from `@lmstudio/sdk` **config schematics**. The upstream field is keyed `folderName` and read in tools via `ctl.getPluginConfig(configSchematics).get("folderName")`.

**If you are building a TypeScript LM Studio plugin** and want the same field, define it explicitly (this is the pattern from upstream [`config.ts`](https://lmstudio.ai/taderich73/filesystem-access/files/src/config.ts)):

```ts
import { createConfigSchematics } from "@lmstudio/sdk";

export const configSchematics = createConfigSchematics()
  .field(
    "folderName",
    "string",
    {
      displayName: "Base Directory",
      subtitle: "The directory path where files will be stored.",
      placeholder: "/path/to/directory",
      isParagraph: false,
    },
    ``,
  )
  .build();
```

**If you are connecting this Python MCP server** (Streamable HTTP), LM Studio does not run that `config.ts`; there is no generated settings panel for arbitrary MCP processes. Replicate the *behavior* of the text field by setting the same absolute path in **`LOCAL_MEDIA_BASE`** wherever you configure the server process (shell, systemd, Kubernetes, or Docker `environment`). That value is exactly what you would type into the plugin’s Base Directory box.

**If you use Cursor**, put the path in `mcp.json` under `env` (see the example below).

See also [LM Studio developer docs](https://lmstudio.ai/docs/developer) for plugin APIs beyond the hub file mirror.

### LM Studio `filesystem-access` parity

This server mirrors the plugin’s path rules (`^[\w./-]+$`, no `..`, resolved under the configured root) and tool names for `list_files`, `read_file`, `write_file`, and `create_directory`, plus `extract_metadata` and `write_metadata` on the same root. The configured root is `LOCAL_MEDIA_BASE`, analogous to `folderName` in the plugin.

## Configuration (environment)

| Variable | Default | Description |
| --- | --- | --- |
| `DATA_DIR` | `/data` | Root directory for all relative paths (including JSON outputs from local media extraction) |
| `LOCAL_MEDIA_BASE` | unset | **Base directory** for filesystem and base-scoped metadata tools (equivalent to the LM Studio plugin *Base Directory* / `folderName`: *The directory path where files will be stored.*). Use an absolute path, e.g. `/home/you/Cards` or `/data` inside Docker |
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

**Base Directory equivalent:** this package runs **Streamable HTTP** (`python -m exifsniffer`). With a **`url`** entry, Cursor does not start the server, so set `LOCAL_MEDIA_BASE` in the environment of the process that listens on the port (for example [docker-compose.yml](docker-compose.yml) `environment`, or your shell before starting):

```bash
export LOCAL_MEDIA_BASE=/home/you/Cards
export DATA_DIR="$PWD/data"
python -m exifsniffer
```

That `LOCAL_MEDIA_BASE` value is the same path you would type into the LM Studio plugin **Base Directory** field.

Place the JSON entry in **project** `.cursor/mcp.json` or **global** `~/.cursor/mcp.json`. Restart Cursor after changes.

If you expose the server on another host/port, replace `localhost:3000` accordingly.

## Tests

```bash
pytest
```

## License

See [LICENSE](LICENSE).
