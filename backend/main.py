# =============================================================================
# main.py — FaaS Runner Backend
# =============================================================================
#
# CHANGES MADE:
#
# 1. Added `from typing import Optional`
#    — Needed to mark the image upload field as optional in the upload endpoint.
#
# 2. Added `import re`
#    — Used by the dependency detection functions to scan script source code.
#
# 3. Added PYTHON_STDLIB and NODE_BUILTIN sets
#    — Lists of built-in module names that do NOT need to be installed.
#      Used to filter out false positives during dependency detection.
#
# 4. Added PYTHON_PACKAGE_MAP dictionary
#    — Maps import names to their real pip package names.
#      e.g. "PIL" -> "Pillow", "cv2" -> "opencv-python-headless"
#
# 5. Added detect_python_deps(source) function
#    — Scans Python source code for third-party imports using regex.
#      Returns a list of pip package names to install.
#
# 6. Added detect_node_deps(source) function
#    — Scans Node.js source code for require() and import statements.
#      Returns a list of npm package names to install.
#
# 7. Added build_command(runtime, deps) function
#    — Builds the shell command that runs inside the Docker container.
#      If dependencies were detected, it prepends a pip/npm install step.
#
# 8. Updated /functions/upload endpoint
#    — Now accepts an optional `image` file alongside the script.
#    — Saves the image to the function's upload folder.
#    — Runs dependency detection on the uploaded script source.
#    — Returns detected_deps in the response so the UI can show them.
#    — Fixed path traversal risk: uses os.path.basename() on filenames.
#
# 9. Updated /functions/{fn_id}/invoke endpoint
#    — Uses build_command() instead of hardcoded RUNTIME_COMMANDS.
#    — Mounts the input image into /input/ inside the container if provided.
#    — Enables network only when dependencies need to be installed.
#    — Increased mem_limit to 256m to accommodate package installs.
#    — Fixed mutable default argument: payload: dict = None instead of {}.
#    — Returns installed_deps in the response for transparency.
#
# 10. Removed RUNTIME_COMMANDS dict
#    — Replaced by the more flexible build_command() function.
#
# =============================================================================

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uuid, os, re, docker

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for deployed functions (lost on server restart)
functions = {}

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")

docker_client = docker.from_env()

RUNTIME_IMAGES = {
    "python": "python:3.13-slim",
    "node":   "node:20-slim",
    "bash":   "bash:5"
}

# Python standard library modules — these don't need pip install
PYTHON_STDLIB = {
    "os", "sys", "re", "math", "json", "time", "datetime", "random",
    "string", "io", "struct", "zlib", "base64", "hashlib", "uuid",
    "collections", "itertools", "functools", "pathlib", "shutil",
    "subprocess", "threading", "multiprocessing", "logging", "unittest",
    "typing", "abc", "copy", "enum", "dataclasses", "contextlib",
    "traceback", "warnings", "gc", "inspect", "ast", "dis", "token",
    "tokenize", "csv", "configparser", "argparse", "getopt", "glob",
    "fnmatch", "tempfile", "stat", "platform", "socket", "ssl",
    "http", "urllib", "email", "html", "xml", "sqlite3", "decimal",
    "fractions", "statistics", "array", "queue", "heapq", "bisect",
    "weakref", "operator", "textwrap", "pprint", "reprlib", "numbers",
    "cmath", "codecs", "unicodedata", "locale", "gettext",
    "builtins", "__future__"
}

# Node.js built-in modules — these don't need npm install
NODE_BUILTIN = {
    "fs", "path", "os", "http", "https", "url", "util", "events",
    "stream", "buffer", "crypto", "child_process", "cluster", "net",
    "dns", "readline", "repl", "vm", "zlib", "assert", "console",
    "process", "timers", "string_decoder", "querystring", "punycode",
    "domain", "module", "v8", "perf_hooks", "async_hooks", "worker_threads"
}

# Maps Python import names to their actual pip package names
PYTHON_PACKAGE_MAP = {
    "PIL":      "Pillow",
    "cv2":      "opencv-python-headless",
    "sklearn":  "scikit-learn",
    "skimage":  "scikit-image",
    "bs4":      "beautifulsoup4",
    "yaml":     "PyYAML",
    "dotenv":   "python-dotenv",
    "dateutil": "python-dateutil",
    "Crypto":   "pycryptodome",
    "jwt":      "PyJWT",
    "attr":     "attrs",
}


def detect_python_deps(source: str) -> list:
    """Scan Python source for third-party imports, return pip package names."""
    packages = set()
    patterns = [
        r"^\s*import\s+([\w]+)",
        r"^\s*from\s+([\w]+)\s+import",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, source, re.MULTILINE):
            mod = match.group(1)
            if mod not in PYTHON_STDLIB:
                pkg = PYTHON_PACKAGE_MAP.get(mod, mod)
                packages.add(pkg)
    return list(packages)


def detect_node_deps(source: str) -> list:
    """Scan Node.js source for require()/import calls, return npm package names."""
    packages = set()
    patterns = [
        r'require\(["\']([^"\'./][^"\']*)["\']',
        r'from\s+["\']([^"\'./][^"\']*)["\']',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, source):
            pkg = match.group(1).split("/")[0]
            if pkg not in NODE_BUILTIN:
                packages.add(pkg)
    return list(packages)


def build_command(runtime: str, deps: list) -> str:
    """
    Build the shell command for the container.
    Prepends a package install step if dependencies were detected.
    """
    if runtime == "python":
        install = ("pip install --quiet " + " ".join(deps) + " && ") if deps else ""
        return f'sh -c "{install}python /script"'
    elif runtime == "node":
        install = ("npm install --silent " + " ".join(deps) + " && ") if deps else ""
        return f'sh -c "{install}node /script"'
    elif runtime == "bash":
        return "bash /script"
    return None


@app.get("/")
def root():
    return {"status": "FaaS Runner is running"}


@app.post("/functions/upload")
async def upload_function(
    name: str = Form(...),
    runtime: str = Form(...),
    file: UploadFile = File(...),
    image: Optional[UploadFile] = File(None)  # optional input image
):
    fn_id = str(uuid.uuid4())[:8]
    fn_dir = os.path.join(UPLOADS_DIR, fn_id)
    os.makedirs(fn_dir, exist_ok=True)

    # Use basename to prevent path traversal attacks
    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(fn_dir, safe_filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Auto-detect dependencies from the script source
    deps = []
    try:
        source = content.decode("utf-8")
        if runtime == "python":
            deps = detect_python_deps(source)
        elif runtime == "node":
            deps = detect_node_deps(source)
    except Exception:
        pass

    # Save optional input image if provided
    image_path = None
    if image and image.filename:
        safe_image_name = os.path.basename(image.filename)
        image_path = os.path.join(fn_dir, safe_image_name)
        with open(image_path, "wb") as f:
            f.write(await image.read())

    functions[fn_id] = {
        "id":         fn_id,
        "name":       name,
        "runtime":    runtime,
        "filename":   safe_filename,
        "file_path":  file_path,
        "image_path": image_path,
        "deps":       deps,
        "status":     "ready"
    }

    return {
        "id":            fn_id,
        "name":          name,
        "status":        "deployed",
        "detected_deps": deps
    }


@app.get("/functions")
def list_functions():
    return list(functions.values())


@app.post("/functions/{fn_id}/invoke")
def invoke_function(fn_id: str, payload: dict = None):  # fixed mutable default arg
    fn = functions.get(fn_id)
    if not fn:
        return {"error": "Function not found"}

    runtime     = fn["runtime"]
    file_path   = os.path.abspath(fn["file_path"])
    deps        = fn.get("deps", [])
    docker_image = RUNTIME_IMAGES.get(runtime)

    if not docker_image:
        return {"error": "Unsupported runtime"}

    command = build_command(runtime, deps)

    try:
        # Pull the Docker image if not already downloaded
        try:
            docker_client.images.get(docker_image)
        except docker.errors.ImageNotFound:
            docker_client.images.pull(docker_image)

        # Always mount the script at /script (read-only)
        volumes = {
            file_path: {"bind": "/script", "mode": "ro"}
        }

        # Also mount the input image at /input/<filename> if one was uploaded
        if fn.get("image_path") and os.path.exists(fn["image_path"]):
            image_filename = os.path.basename(fn["image_path"])
            volumes[os.path.abspath(fn["image_path"])] = {
                "bind": f"/input/{image_filename}",
                "mode": "ro"
            }

        # Enable network only if packages need to be installed
        # (disabled for scripts with no dependencies for security)
        network_disabled = len(deps) == 0

        result = docker_client.containers.run(
            image=docker_image,
            command=command,
            volumes=volumes,
            remove=True,
            stdout=True,
            stderr=True,
            mem_limit="256m",
            nano_cpus=500_000_000,
            network_disabled=network_disabled
        )

        return {
            "stdout":         result.decode("utf-8"),
            "stderr":         "",
            "exit_code":      0,
            "installed_deps": deps
        }

    except docker.errors.ContainerError as e:
        return {
            "stdout":         "",
            "stderr":         e.stderr.decode("utf-8") if e.stderr else str(e),
            "exit_code":      1,
            "installed_deps": deps
        }
    except Exception as e:
        return {"error": str(e)}


@app.delete("/functions/{fn_id}")
def delete_function(fn_id: str):
    if fn_id in functions:
        del functions[fn_id]
        return {"status": "deleted"}
    return {"error": "Not found"}
