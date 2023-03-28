import dataclasses
import requests
import json
import os
import hashlib
import subprocess
import time
import re
import sys
import pathlib

from ..types import Code

# See https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py
@dataclasses.dataclass(frozen=True)
class DataverseDataset(Code):
    persistent_id: str

    def checkout(self, path: pathlib.Path) -> None:
        # See https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py
        server = "http://dataverse.harvard.edu/api/"
        version = ":latest"
        query = server + "datasets/:persistentId/versions/" + version + "?persistentId=" + self.persistent_id

        j = requests.get(query).json()

        for obj in j['data']['files']:
            fileid = obj['dataFile']['id']
            filename = obj['label']    # for ingested tabular files, restore the original file name extension:
            if 'originalFileFormat' in obj['dataFile'].keys():
                dlurl = server + '/access/datafile/' + str(fileid) + '?format=original'
                originaltype = obj['dataFile']['originalFileFormat']
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
                dlurl = server + '/access/datafile/' + str(fileid)
            # Allow 3 retries
            for _ in range(3):
                result = requests.get(dlurl).content
                downloaded_hash = hashlib.md5(result).hexdigest()
                expected_hash = obj["dataFile"]["md5"]
                if downloaded_hash == expected_hash:
                    (path / filename).parent.mkdir(exist_ok=True, parents=True)
                    (path / filename).write_bytes(result)
                    break
            else:
                raise RuntimeError(f"Hash mismatch: {downloaded_hash=} {expected_hash=}")
