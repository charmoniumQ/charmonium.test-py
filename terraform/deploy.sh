#! /usr/bin/env bash

set -e -o nounset -x

cd $(dirname $(dirname $0))

node_count=$(terraform -chdir=terraform output --raw worker_count)
hosts=(manager $(seq 0 $((node_count - 1)) | xargs --replace=R echo worker-R))

echo "## Test connectivity"

failures=0
for host in "${hosts[@]}"; do
	if ! ssh -F terraform/ssh_config -o ConnectTimeout=3 "${host}" sudo rm -rf work; then
		failures=1
	fi
done

if [ "${failures}" == 1 ]; then
	echo "## Deploy cloud infrastructure"

	terraform -chdir=terraform apply -auto-approve
	for host in "${hosts[@]}"; do
		# These may be new nodes, so they may have new SSH key signatures
		ssh-keygen -R "${host}"
		ssh -F terraform/ssh_config "${host}" sudo rm -rf work
	done
fi

echo "## Rsync local -> remote"

for host in "${hosts[@]}"; do
	(rsync \
		--exclude terraform \
		--exclude build \
		--exclude .direnv \
		--exclude .git \
		--exclude .cache \
		--exclude .cache2 \
		--exclude .mypy_cache \
		--archive \
		--compress \
		--rsh='ssh -F ./terraform/ssh_config' \
		./ \
		"${host}:work/" \
	|| echo "${host}: failed to rsync") &
done
wait

echo "## Launch Dask manager"

if [ ! -f dockerfiles/main_image ]; then
	./dockerfiles/build.sh
	if [ ! -f dockerfiles/main_image ]; then
		echo 'Ensure `./dockerfiles/build.sh` writes the name of an image to dockerfiles/main_image'
		exit 1
	fi
fi
main_image=$(cat dockerfiles/charmonium_test_py_image)
manager_private_ip="$(terraform -chdir=terraform output --raw manager_private_ip)"
scheduler_port=9000
dashboard_port=9200
notebook_port=9400
acr_name=wfregtest

ssh \
	-T \
	-F terraform/ssh_config \
	manager \
	"if docker ps --all | grep dask-scheduler > /dev/null; then
		docker stop dask-scheduler > /dev/null
		docker rm dask-scheduler > /dev/null
	fi
	/home/azureuser/.local/bin/az login --identity > /dev/null
	/home/azureuser/.local/bin/az acr login --name ${acr_name}
	docker run \
		--detach \
		--restart always \
		--name dask-scheduler \
		--volume /home/azureuser/work/:/work \
		--workdir /work \
		--env PYTHONPATH=/work \
		--net=host \
		--volume /var/run/docker.sock:/var/run/docker.sock \
		--volume /var/lib/docker:/var/lib/docker \
		--volume /home/azureuser/.docker:/.docker \
		--volume /my-tmp:/my-tmp \
		${main_image} \
		dask scheduler \
			--host manager \
			--port ${scheduler_port} \
			--dashboard \
			--dashboard-address=:${dashboard_port}" \
&

echo "## Launch Dask workers"

#workers_per_node=1
workers_per_node=4
first_worker_port=9000
last_worker_port=$((first_worker_port + workers_per_node))
first_dashboard_port=9200
last_dashboard_port=$((first_dashboard_port + workers_per_node))
first_nanny_port=9400
last_nanny_port=$((first_nanny_port + workers_per_node))

for host in $(seq 0 $((node_count - 1)) | xargs -I% echo 'worker-%'); do
	# We remove the host key because in previous deployments, there would be a different host/hostkey behind the name "${host}".
	# But we still need to disable StrictHostKeyChecking, because otherwise it will pause and wait for us to approve this unknown hostkey.
	# We can trust this if we trust manager's host key.
	ssh-keygen -R $host

	(ssh \
		-T \
		-F terraform/ssh_config \
		"${host}" \
		"if docker ps --all | grep dask-worker > /dev/null; then
			docker stop dask-worker > /dev/null
			docker rm dask-worker > /dev/null
		fi
		/home/azureuser/.local/bin/az login --identity > /dev/null
		/home/azureuser/.local/bin/az acr login --name ${acr_name}
		docker run \
			--detach \
			--restart always \
			--name dask-worker \
			--volume /home/azureuser/work/:/work \
			--workdir /work \
			--env PYTHONPATH=/work \
			--net=host \
			--volume /var/run/docker.sock:/var/run/docker.sock \
			--volume /var/lib/docker:/var/lib/docker \
			--volume /home/azureuser/.docker:/.docker \
			--volume /my-tmp:/my-tmp \
			${main_image} \
			dask worker \
				--name ${host} \
				--nworkers ${workers_per_node} \
				--nthreads 1 \
				--worker-port ${first_worker_port}:${last_worker_port} \
				--dashboard \
				--dashboard-address :${first_dashboard_port} \
				--nanny-port ${first_nanny_port}:${last_nanny_port} \
				tcp://manager:${scheduler_port} \
		" || echo "${host}: failed to setup"
	) &
	sleep 0.1
	# Should we set --host to their private ip?
	# That's too much work.
	# 0.0.0.0 (default) will also work, although it is more permissive.
done
wait

# echo "## Done"
# 
# echo "Run this command to connect to the dashboard on http://localhost:${dashboard_port}"
# echo '    ' ssh \
# 	-F terraform/ssh_config \
# 	-L "${dashboard_port}:localhost:${dashboard_port}" \
# 	manager

echo "## The main event"

echo "http://localhost:${dashboard_port} for Dask dashboard"

ssh \
	-F ./terraform/ssh_config \
	-L "${dashboard_port}:localhost:${dashboard_port}" \
	-t \
	manager \
		"tmux new-session -A -s run -d bash ; tmux send-keys 'docker run --rm --interactive --tty --volume /home/azureuser/work/:/work --workdir /work --env PYTHONPATH=/work  --net=host --volume /var/run/docker.sock:/var/run/docker.sock --volume /var/lib/docker:/var/lib/docker --volume /home/azureuser/.docker:/.docker --volume /my-tmp:/my-tmp ${main_image} python -c from\ charmonium.test_py.trisovic_replication\ import\ run\;\ run\(\)' C-m ; tmux attach-session"
