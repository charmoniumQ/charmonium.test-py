resource "tls_private_key" "developer" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

# This represents actions taken by the manager
resource "tls_private_key" "manager" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "local_file" "developer_private_key" {
  filename = "developer_private_key"
  file_permission = "0600"
  content = tls_private_key.developer.private_key_openssh
}

resource "azurerm_network_security_group" "sshable_nsg" {
  name                = "sshable-nsg"
  location            = azurerm_resource_group.default.location
  resource_group_name = azurerm_resource_group.default.name
  security_rule {
    name                       = "SSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "local_file" "ssh_config" {
  filename = "ssh_config"
  file_permission = "0644"
  content  = <<-EOT
    Host manager
        HostName ${azurerm_linux_virtual_machine.manager.public_ip_address}
        IdentityFile ./terraform/developer_private_key
        User azureuser

    %{ for worker in azurerm_linux_virtual_machine.worker }
    Host ${worker.name}
        HostName ${worker.name}
        IdentityFile ./terraform/developer_private_key
        User azureuser
        ProxyJump manager
        CheckHostIP no
        StrictHostKeyChecking accept-new

    %{ endfor }
  EOT
}
