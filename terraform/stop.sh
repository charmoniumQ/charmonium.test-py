#!/usr/bin/env sh

terraform -chdir=terraform apply -var='workers=0' -auto-approve
az vm delete --yes --name=manager --resource-group terraform
