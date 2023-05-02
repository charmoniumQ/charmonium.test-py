import asyncio
import dataclasses
import hashlib
import re
import pathlib
import warnings
from typing import Awaitable

import aiofiles
import aiohttp
import charmonium.time_block
import requests

from ..config import harvard_dataverse_token, ssl_context
from ..types import Code

# TODO: download a Zip archive of the whole dataset instead of downloading each file individually.

@dataclasses.dataclass(frozen=True)
class DataverseDataset(Code):
    persistent_id: str
    server = "http://dataverse.harvard.edu/api/"

    @charmonium.time_block.decor()
    def checkout(self, path: pathlib.Path) -> None:
        asyncio.run(self.acheckout(path))

    def size_est(self) -> int:
        url = f"{self.server}/datasets/:persistentId/versions/:latest?persistentId={self.persistent_id}"
        response = requests.get(
            url,
            # headers={"X-Dataverse-key": harvard_dataverse_token()},
        )
        response_obj = response.json()
        if "data" not in response_obj:
            raise RuntimeError(f"Unexpected JSON schema: {url} -> {response_obj}")
        return sum(
            file["dataFile"]["filesize"]
            for file in response_obj['data']['files']
        )

    async def acheckout(self, path: pathlib.Path) -> None:
        # See https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f"{self.server}/datasets/:persistentId/versions/:latest?persistentId={self.persistent_id}",
                    # headers={"X-Dataverse-key": harvard_dataverse_token()},
                    ssl=ssl_context(),
            ) as response:
                response_obj = await response.json()

            fetches = list[Awaitable[None]]()
            for file in response_obj.get('data', {}).get('files', []):
                if file["restricted"]:
                    continue
                fileid = file['dataFile']['id']
                filename = file['label']    # for ingested tabular files, restore the original file name extension:
                if 'originalFileFormat' in file['dataFile'].keys():
                    dlurl = f'{self.server}/access/datafile/{fileid}?format=original'
                    originaltype = file['dataFile']['originalFileFormat']
                    if originaltype == 'application/x-rlang-transport':
                        filename = re.sub('\.[^\.]*$', '.RData', filename)
                    elif originaltype.startswith('application/x-stata'):
                        filename = re.sub('\.[^\.]*$', '.dta', filename)
                    elif originaltype == 'application/x-spss-sav':
                        filename = re.sub('\.[^\.]*$', '.sav', filename)
                    elif originaltype == 'application/x-spss-por':
                        filename = re.sub('\.[^\.]*$', '.por', filename)
                    elif originaltype == 'text/csv':
                        filename = re.sub('\.[^\.]*$', '.csv', filename)
                else:
                    dlurl = f'{self.server}/access/datafile/{fileid}'
                fetches.append(self.fetch(session, dlurl, path / filename, file["dataFile"]["md5"], file["dataFile"]["filesize"]))
            await asyncio.gather(*fetches)

    async def fetch(self, session: aiohttp.ClientSession, dlurl: str, dest: pathlib.Path, expected_hash: str, size: int) -> None:
        chunk_size = 1024 * 1024 * 64 # 64 MiB
        speed_kbps = 100
        safety_factor = 10
        min_timeout = 30
        time_estimate = int(size * 8 / (speed_kbps * 1000))
        timeout = max(time_estimate * safety_factor, min_timeout)
        if time_estimate > 30:
            pass
            # warnings.warn(f"Might take a while: {dlurl} {size=} {time_estimate=} {timeout=}")
        try:
            async with session.get(
                    dlurl,
                    # headers={"X-Dataverse-key": harvard_dataverse_token()},
                    timeout=timeout,
                    ssl=ssl_context(),
            ) as response:
                hasher = hashlib.md5()
                dest.parent.mkdir(exist_ok=True, parents=True)
                async with aiofiles.open(str(dest), mode="wb") as dest_file:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        await dest_file.write(chunk)
                        hasher.update(chunk)
        except Exception as exc:
            raise RuntimeError(f"Couldn't get: {dlurl}\nof {self.persistent_id}") from exc
        downloaded_hash = hasher.hexdigest()
        if downloaded_hash != expected_hash:
            raise HashMismatchError(f"Hash mismatch getting: {dlurl}\nof {self.persistent_id}\n{downloaded_hash=}\n{expected_hash=}")


class HashMismatchError(Exception):
    pass
