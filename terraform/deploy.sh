#! /usr/bin/env nix-shell
#! nix-shell -i bash -p terraform -p azure-cli

set -e -o nounset

cd $(dirname $(dirname $0))

echo "## Deploy cloud infrastructure"

terraform -chdir=terraform apply -auto-approve

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
scheduler_port=8129
dashboard_port=8787
notebook_port=8421

ssh \
	-T \
	-F terraform/ssh_config \
	manager \
	<<EOF
if docker ps --all | grep dask-scheduler; then
	docker stop dask-scheduler
	docker rm dask-scheduler
fi
docker run \
	--detach \
	--restart on-failure \
	--name dask-scheduler \
	--publish "${scheduler_port}:${scheduler_port}" \
	--publish "${dashboard_port}:${dashboard_port}" \
	"${main_image}" \
		dask-scheduler \
		--port "${scheduler_port}" \
		--dashboard \
		--dashboard-address=":${dashboard_port}"
EOF

echo "## Launch Dask workers"

worker_count=$(terraform -chdir=terraform output --raw worker_count)
first_worker_port=8123
last_worker_port=$(python -c "print(${first_worker_port} + 100)")

for host in $(seq 0 $((worker_count - 1)) | xargs -I% echo 'worker-%'); do
	# We remove the host key because in previous deployments, there would be a different host/hostkey behind the name "${host}".
	# But we still need to disable StrictHostKeyChecking, because otherwise it will pause and wait for us to approve this unknown hostkey.
	# We can trust this if we trust manager's host key.
	ssh-keygen -R $host

	(ssh \
		-T \
		-F terraform/ssh_config \
		-o StrictHostKeyChecking=no \
		"${host}" \
		docker run \
			--detach \
			--restart on-failure \
			--name dask-worker \
			--publish "${first_worker_port}-${last_worker_port}:${first_worker_port}-${last_worker_port}" \
			--publish "${dashboard_port}:${dashboard_port}" \
			"${main_image}" \
				dask-worker \
				--name "${host}" \
				--worker-port "${first_worker_port}:${last_worker_port}" \
				--dashboard \
				--dashboard-address ":${dashboard_port}" \
				--nworkers auto \
				"tcp://${manager_private_ip}:${scheduler_port}" \
		|| echo "${host}: failed to setup") &
	sleep 0.1
	# Should we set --host to their private ip?
	# That's too much work.
	# 0.0.0.0 (default) will also work, although it is more permissive.
done
wait

echo "## Done"

echo "Run this command to connect to the dashboard:"
echo ssh \
	-F terraform/ssh_config \
	-L "${dashboard_port}:localhost:${dashboard_port}" \
	-L "${notebook_port}:localhost:${notebook_port}" \
	manager
echo docker run --rm "${main_image}" python -m charmonium.test_py.trisovic_main
echo docker run --publish "${notebook_port}:${notebook_port}" --rm "${main_image}" jupyter-lab
echo open http://localhost:${dashboard_port}
