#!/usr/bin/env sh
if git diff-index --quiet HEAD --; then
	suffix=clean
else
	suffix=$(date +%s)
fi
echo commit-$(git rev-parse HEAD | cut --bytes=1-8)-$suffix
