#!/usr/bin/env sh

terraform -chdir=terraform apply -var='workers=0' -auto-approve

az vm deallocate --resource-group terraform --name manager
