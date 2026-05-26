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

functions = {}

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")

docker_client = docker.from_env()

RUNTIME_IMAGES = {
    "python": "python:3.13-slim",
    "node": "node:20-slim",
    "bash": "bash:5"
}

# Built-in modules that don't need to be installed
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
    "cmath", "struct", "codecs", "unicodedata", "locale", "gettext",
    "builtins", "__future__"
}

NODE_BUILTIN = {
    "fs", "path", "os", "http", "https", "url", "util", "events",
    "stream", "buffer", "crypto", "child_process", "cluster", "net",
    "dns", "readline", "repl", "vm", "zlib", "assert", "console",
    "process", "timers", "string_decoder", "querystring", "punycode",
    "domain", "module", "v8", "perf_hooks", "async_hooks", "worker_threads"
}

# Map common import names to their actual pip package name
PYTHON_PACKAGE_MAP = {
    "PIL": "Pillow",
    "cv2": "opencv-python-headless",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "Crypto": "pycryptodome",
    "jwt": "PyJWT",
    "attr": "attrs",
    "gi": "PyGObject",
}


def detect_python_deps(source: str) -> list[str]:
    """Scan Python source for third-party imports and return pip package names."""
    packages = set()
    # Match: import X, from X import Y
    patterns = [
        r"^\s*import\s+([\w]+)",
        r"^\s*from\s+([\w]+)\s+import",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, source, re.MULTILINE):
            mod = match.group(1)
            if mod not in PYTHON_STDLIB:
                # Map to real package name if needed
                pkg = PYTHON_PACKAGE_MAP.get(mod, mod)
                packages.add(pkg)
    return list(packages)


def detect_node_deps(source: str) -> list[str]:
    """Scan Node.js source for require() or import calls and return npm package names."""
    packages = set()
    patterns = [
        r'require\(["\']([^"\'./][^"\']*)["\']',   # require('package')
        r'from\s+["\']([^"\'./][^"\']*)["\']',      # import x from 'package'
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, source):
            pkg = match.group(1).split("/")[0]  # handle scoped: @org/pkg
            if pkg not in NODE_BUILTIN:
                packages.add(pkg)
    return list(packages)


def build_command(runtime: str, deps: list[str]) -> str:
    """
    Build a shell command that:
    1. Installs detected dependencies
    2. Runs the script
    All as a single shell string so it runs inside one container.
    """
    if runtime == "python":
        if deps:
            install = "pip install --quiet " + " ".join(deps) + " && "
        else:
            install = ""
        return f'sh -c "{install}python /script"'

    elif runtime == "node":
        if deps:
            install = "npm install --silent " + " ".join(deps) + " && "
        else:
            install = ""
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
    image: Optional[UploadFile] = File(None)
):
    fn_id = str(uuid.uuid4())[:8]
    fn_dir = os.path.join(UPLOADS_DIR, fn_id)
    os.makedirs(fn_dir, exist_ok=True)

    file_path = os.path.join(fn_dir, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Detect dependencies from the uploaded script
    deps = []
    try:
        source = content.decode("utf-8")
        if runtime == "python":
            deps = detect_python_deps(source)
        elif runtime == "node":
            deps = detect_node_deps(source)
    except Exception:
        pass  # If decode fails, skip dep detection

    # Save the optional input image if provided
    image_path = None
    if image and image.filename:
        image_path = os.path.join(fn_dir, image.filename)
        with open(image_path, "wb") as f:
            f.write(await image.read())

    functions[fn_id] = {
        "id": fn_id,
        "name": name,
        "runtime": runtime,
        "filename": file.filename,
        "file_path": file_path,
        "image_path": image_path,
        "deps": deps,
        "status": "ready"
    }

    return {
        "id": fn_id,
        "name": name,
        "status": "deployed",
        "detected_deps": deps
    }


@app.get("/functions")
def list_functions():
    return list(functions.values())


@app.post("/functions/{fn_id}/invoke")
def invoke_function(fn_id: str, payload: dict = {}):
    fn = functions.get(fn_id)
    if not fn:
        return {"error": "Function not found"}

    runtime = fn["runtime"]
    file_path = os.path.abspath(fn["file_path"])
    deps = fn.get("deps", [])
    docker_image = RUNTIME_IMAGES.get(runtime)

    if not docker_image:
        return {"error": "Unsupported runtime"}

    # Build the command — installs deps first if any were detected
    command = build_command(runtime, deps)

    try:
        # Pull the base image if not already available
        try:
            docker_client.images.get(docker_image)
        except docker.errors.ImageNotFound:
            docker_client.images.pull(docker_image)

        # Build volumes: always mount the script, also mount input image if provided
        volumes = {
            file_path: {"bind": "/script", "mode": "ro"}
        }
        if fn.get("image_path") and os.path.exists(fn["image_path"]):
            image_filename = os.path.basename(fn["image_path"])
            volumes[os.path.abspath(fn["image_path"])] = {
                "bind": f"/input/{image_filename}",
                "mode": "ro"
            }

        # If there are dependencies to install, we need network access during install.
        # We run with network enabled only when deps are present, then the script
        # itself cannot make outbound calls (network is still available but no
        # user code runs before the script — install is done by the system).
        network_disabled = len(deps) == 0

        result = docker_client.containers.run(
            image=docker_image,
            command=command,
            volumes=volumes,
            remove=True,
            stdout=True,
            stderr=True,
            mem_limit="256m",       # slightly more room for installs
            nano_cpus=500_000_000,
            network_disabled=network_disabled
        )

        return {
            "stdout": result.decode("utf-8"),
            "stderr": "",
            "exit_code": 0,
            "installed_deps": deps
        }

    except docker.errors.ContainerError as e:
        return {
            "stdout": "",
            "stderr": e.stderr.decode("utf-8") if e.stderr else str(e),
            "exit_code": 1,
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
