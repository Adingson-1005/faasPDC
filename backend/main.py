from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uuid, os, docker

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

RUNTIME_COMMANDS = {
    "python": "python /script",
    "node": "node /script",
    "bash": "bash /script"
}

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
    with open(file_path, "wb") as f:
        f.write(await file.read())

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
        "status": "ready"
    }

    return {"id": fn_id, "name": name, "status": "deployed"}

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
    image = RUNTIME_IMAGES.get(runtime)
    command = RUNTIME_COMMANDS.get(runtime)

    if not image:
        return {"error": "Unsupported runtime"}

    try:
        # Pull image if not already available
        try:
            docker_client.images.get(image)
        except docker.errors.ImageNotFound:
            docker_client.images.pull(image)

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

        # Run script inside a container
        container = docker_client.containers.run(
                image=image,
                command=command,
                volumes=volumes,
                remove=True,
                stdout=True,
                stderr=True,
                mem_limit="128m",
                nano_cpus=500_000_000,
                network_disabled=True
            )
        return {
            "stdout": container.decode("utf-8"),
            "stderr": "",
            "exit_code": 0
        }

    except docker.errors.ContainerError as e:
        return {
            "stdout": "",
            "stderr": e.stderr.decode("utf-8") if e.stderr else str(e),
            "exit_code": 1
        }
    except Exception as e:
        return {"error": str(e)}

@app.delete("/functions/{fn_id}")
def delete_function(fn_id: str):
    if fn_id in functions:
        del functions[fn_id]
        return {"status": "deleted"}
    return {"error": "Not found"}