import requests as req
import json
from typing import Iterable

from ..codes import WorkflowCode, DataverseDataset
from ..types import Registry

class TrisovicDataverse(Registry):
    """Future users should see dataverse.py in this same directory."""
    def get_codes(self) -> Iterable[WorkflowCode]:
        # See https://github.com/atrisovic/dataverse-r-study/blob/master/get-dois/get-r-dois.ipynb

        unique_dois = set[str]()
        condition = True
        start = 0
        total = 0
        per_page = 1000
        while condition:
            # check for native Harvard files with isHarvested%3Afalse
            query = "https://dataverse.harvard.edu/api/search?q=(fileContentType%3Atype%2Fx-r-syntax%20AND%20isHarvested%3Afalse)&type=file"
            query = query + "&start=" + str(start)
            query = query + "&per_page=" + str(per_page)
            print("Looking at files from page " + str(start))

            res = req.get(query)
            res_dict = json.loads(res.text)

            total = res_dict['data']['total_count']
            for item in res_dict['data']['items']:
                unique_dois.add(item['dataset_persistent_id'])

            start = start + per_page
            condition = start < total

        for doi in unique_dois:
            yield WorkflowCode(DataverseDataset(doi), "R")
