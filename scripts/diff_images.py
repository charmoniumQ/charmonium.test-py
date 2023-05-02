import pathlib
import itertools
import subprocess

images = ["atrisovic/aws-image", "atrisovic/aws-image-r36-m", "atrisovic/aws-image-r32", "atrisovic/aws-image-r40"]

def pull(image):
    path = pathlib.Path() / (image.replace("/", "_") + ".tar")
    if not path.exists():
        subprocess.run(["docker", "pull", image], capture_output=True, check=True)
        subprocess.run(["docker", "save", "--output", str(path), image], capture_output=True, check=True)
    return path


def diff(image0, image1):
    image0_path = pull(image0)
    image1_path = pull(image1)
    pwd = pathlib.Path().resolve()
    return subprocess.run(
        ["docker", "run", "--rm", "-t", "-w", str(pwd), "-v", f"{pwd}:{pwd}:ro", "registry.salsa.debian.org/reproducible-builds/diffoscope", image0_path, image1_path],
        capture_output=True,
        check=True,
    ).stdout

for i in range(len(images)):
    for j in range(i):
        print(diff(images[i], images[j]))
    print("\n")
