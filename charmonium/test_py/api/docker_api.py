import functools
import docker  # type: ignore

@functools.cache
def docker_client() -> docker.client.DockerClient:
    return docker.from_env()
