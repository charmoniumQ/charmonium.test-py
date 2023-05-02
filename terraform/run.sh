#! /usr/bin/env bash

set -e -o nounset

cd $(dirname $(dirname $0))

dashboard_port=9200
main_image=$(cat dockerfiles/charmonium_test_py_image)
worker_count=$(terraform -chdir=terraform output --raw worker_count)

echo "## Rsync local -> remote"

hosts=(manager $(seq 0 $((worker_count - 1)) | xargs --replace=R echo worker-R))
for host in "${hosts[@]}"; do
	ssh -F terraform/ssh_config "${host}"  sudo rm -rf work
	(rsync \
		--verbose \
		--exclude terraform \
		--exclude .git \
		--exclude .cache \
		--exclude .cache2 \
		--exclude .mypy_cache \
		--archive \
		--compress \
		--rsh='ssh -F ./terraform/ssh_config' \
		./ \
		"${host}:work/" \
		| pr --omit-header --indent=2 \
	|| echo "${host}: failed to rsync") &
done
wait

echo "## The main event"

echo "http://localhost:${dashboard_port} for Dask dashboard"

cmd="python -m charmonium.test_py.main"
if [ "${#}" -eq 1 ] && [ -n "${1}" ]; then
	cmd="${1}"
	echo "Running: ${cmd}"
fi

docker_cmd=$(echo docker run \
    --rm \
    --interactive \
    --tty \
    --volume /home/azureuser/work/:/work \
    --workdir /work \
    --env PYTHONPATH=/work \
    --net=host \
    --volume /var/run/docker.sock:/var/run/docker.sock \
    --volume /var/lib/docker:/var/lib/docker \
    --volume /home/azureuser/.docker:/.docker \
    --volume /my-tmp:/my-tmp \
    ${main_image} \
        ${cmd}
)

echo $docker_cmd

ssh \
	-F ./terraform/ssh_config \
	-L "${dashboard_port}:localhost:${dashboard_port}" \
	-t \
	manager \
		"tmux new-session -A -s run -d bash ; tmux send-keys '${docker_cmd}' C-m ; tmux attach-session"
