import asyncio
import dataclasses
import hashlib
import re
import pathlib
from typing import Awaitable

import charmonium.time_block
import aiohttp

from ..types import Code

@dataclasses.dataclass(frozen=True)
class DataverseDataset(Code):
    persistent_id: str

    @charmonium.time_block.decor()
    def checkout(self, path: pathlib.Path) -> None:
        asyncio.run(self.acheckout(path))

    async def acheckout(self, path: pathlib.Path) -> None:
        # See https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py
        server = "http://dataverse.harvard.edu/api/"
        url = f"{server}/datasets/:persistentId/versions/:latest?persistentId={self.persistent_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response_obj = await response.json()

            fetches = list[Awaitable[None]]()
            for file in response_obj['data']['files']:
                fileid = file['dataFile']['id']
                filename = file['label']    # for ingested tabular files, restore the original file name extension:
                if 'originalFileFormat' in file['dataFile'].keys():
                    dlurl = f'{server}/access/datafile/{fileid}?format=original'
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
                    dlurl = f'{server}/access/datafile/{fileid}'
                fetches.append(self.fetch(session, dlurl, path / filename, file["dataFile"]["md5"]))
            await asyncio.gather(*fetches)

    @staticmethod
    async def fetch(session: aiohttp.ClientSession, dlurl: str, dest: pathlib.Path, expected_hash: str) -> None:
        # Allow 3 retries
        for try_ in range(3):
            async with session.get(dlurl) as response:
                result = await response.read()
                downloaded_hash = hashlib.md5(result).hexdigest()
                if downloaded_hash == expected_hash:
                    dest.parent.mkdir(exist_ok=True, parents=True)
                    dest.write_bytes(result)
                    break
        else:
            raise RuntimeError(f"Hash mismatch: {downloaded_hash=} {expected_hash=}")
