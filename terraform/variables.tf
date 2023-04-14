variable "rg_name" {
  type    = string
  default = "terraform"
}

variable "manager_disk_size_gb" {
  type    = string
  default = "40"
  # Usually can't be smaller than 30
}

# See https://azureprice.net/
variable "manager_vm_size" {
  type    = string
  default = "Standard_D2as_v5"
}

variable "workers" {
  type    = number
  default = 1
}

variable "worker_disk_size_gb" {
  type    = string
  default = "300"
  # Usually can't be smaller than 30
}

variable "worker_vm_size" {
  type    = string
  default = "Standard_D4as_v5"
}

variable "username" {
  type = string
  default = "azureuser"
}

output "worker_count" {
  value = var.workers
}

variable "location" {
  type = string
  default = "eastus"
}

variable "acr_name" {
  type = string
  default = "wfregtest"
}

variable "storage_account_name" {
  type = string
  default = "wfregtest"
}

variable "vm_image" {
  type = object({
    publisher = string
    offer     = string
    sku       = string
    version   = string
  })
  default = {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-minimal-jammy"
    sku       = "minimal-22_04-lts-gen2"
    version   = "22.04.202211160"
  }
}
