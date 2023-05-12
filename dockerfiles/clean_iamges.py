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
    actual_images.add(obj["Repository"] + ":" + obj["Tag"])

subprocess.run(["docker", "rmi", *(actual_images - used_images)], check=True)
