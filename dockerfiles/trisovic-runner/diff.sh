#!/usr/bin/bash

set -e

here="$(dirname ${0})"

tempdir="$(mktemp -d)"
git clone https://github.com/atrisovic/dataverse-r-study "${tempdir}" 2> /dev/null
for file in $(ls ${here}); do
	if [ "${file}" != "diff.sh" ] && [ "${file}" != "diff" ]; then
		diff="$(diff --unified=3 --ignore-all-space ${tempdir}/docker/${file} ${here}/${file} || true)"
		if [ -n "${diff}" ]; then
			echo "${file}"
			echo "${diff}"
		fi
	fi
done
rm --recursive --force "${tempdir}"
