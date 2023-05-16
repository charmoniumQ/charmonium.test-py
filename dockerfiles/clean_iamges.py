import subprocess
import pathlib
import json


used_images = {
    *pathlib.Path("dockerfiles/r-runners").read_text().strip().split("\n"),
    pathlib.Path("dockerfiles/main_image").read_text().strip(),
    pathlib.Path("dockerfiles/trisovic_runner_image").read_text().strip(),
}

lines = subprocess.run(["docker", "images", "--all", "--format", "json"], check=True, capture_output=True, text=True).stdout.strip().split("\n")
actual_images = set()
for line in lines:
    obj = json.loads(line)
    if obj["Repository"] in {"r-runners", "main_image", "trisovic_runner_image"}:
        actual_images.add(obj["Repository"] + ":" + obj["Tag"])

images_to_remove = actual_images - used_images
if images_to_remove:
    subprocess.run(["docker", "rmi", *images_to_remove], check=True)
