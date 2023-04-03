#! /usr/bin/env nix-shell
#! nix-shell -i bash -p terraform -p azure-cli

set -e -o nounset

cd $(dirname $(dirname $0))

tag=$(git rev-parse HEAD)
images=(r-runner charmonium-test-py)
registry=wfregtest

if ! az ad signed-in-user show | grep mail; then
	az login
	az acr login --name ${registry}
fi

terraform -chdir=terraform apply -auto-approve

for image in "${images[@]}"; do
	docker buildx build . --file dockerfiles/${image}/Dockerfile --tag ${registry}.azurecr.io/${image}:${tag}
	docker image push ${registry}.azurecr.io/${image}:${tag}
done

terraform -chdir=terraform output --raw developer_ssh_key > terraform/key
chmod 0600 terraform/key

cat <<EOF > terraform/ssh_config
Host manager
    HostName $(terraform -chdir=terraform output --raw manager_ip)
    IdentityFile ${PWD}/terraform/key
    User azureuser

EOF

worker_count=$(terraform -chdir=terraform output --raw worker_count)

for worker in $(seq 0 $((worker_count - 1))); do
    cat <<EOF >> terraform/ssh_config
Host worker-${worker}
    HostName worker-${worker}
    IdentityFile ${PWD}/terraform/key
    User azureuser
    ProxyJump manager

EOF
done

for host in manager $(seq 0 $((worker_count - 1)) | xargs -I% echo 'worker-%'); do
    #ssh-keygen -R $host
    (ssh -T -o StrictHostKeyChecking=no -F terraform/ssh_config $host "pwd" || echo "$host: failed to setup") &
    sleep 0.1
done
wait
#docker run --rm wfregtest.azurecr.io/charmonium-test-py:b756a7550581125bed1cd3771de53e0120fdb375 poetry run dask-worker
#docker run --rm wfregtest.azurecr.io/charmonium-test-py:b756a7550581125bed1cd3771de53e0120fdb375 poetry run ipython
