import functools
import os
import warnings

import github


gat_env_var = "GITHUB_ACCESS_TOKEN"


@functools.cache
def github_client() -> github.Github:
    f"""Return a singleton Github client that we will use for the entire process.

    This will try to import github.

    This will try to read the environment variable {gat_env_var} for the GitHub Access Token.

    Generate with https://github.com/settings/tokens

    """
    if gat_env_var not in os.environ:
        warnings.warn(f"`{gat_env_var}` not set. Falling back to unauthenticated GitHub API.")
        return github.Github()
    return github.Github(os.environ[gat_env_var])
