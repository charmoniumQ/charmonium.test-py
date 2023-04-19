resource "azurerm_public_ip" "manager_ip" {
  name                = "manager"
  resource_group_name = azurerm_resource_group.default.name
  location            = azurerm_resource_group.default.location
  allocation_method   = "Dynamic"
}

resource "azurerm_network_interface" "manager_nic" {
  name                = "manager-nic"
  location            = azurerm_resource_group.default.location
  resource_group_name = azurerm_resource_group.default.name

  ip_configuration {
    name                          = "manager"
    subnet_id                     = azurerm_subnet.default.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.manager_ip.id
  }
}

resource "azurerm_network_interface_security_group_association" "manager" {
  network_interface_id      = azurerm_network_interface.manager_nic.id
  network_security_group_id = azurerm_network_security_group.sshable_nsg.id
}

resource "azurerm_linux_virtual_machine" "manager" {
  name                  = "manager"
  location              = azurerm_resource_group.default.location
  resource_group_name   = azurerm_resource_group.default.name
  size                  = var.manager_vm_size
  admin_username        = var.username
  network_interface_ids = [azurerm_network_interface.manager_nic.id]
  disable_password_authentication = true
  admin_ssh_key {
    username   = var.username
    public_key = tls_private_key.developer.public_key_openssh
  }
  source_image_reference {
    publisher = var.vm_image.publisher
    offer     = var.vm_image.offer
    sku       = var.vm_image.sku
    version   = var.vm_image.version
  }
  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = var.manager_disk_size_gb
  }
  identity {
    type = "SystemAssigned"
  }
  connection {
    type        = "ssh"
    user        = var.username
    host        = azurerm_linux_virtual_machine.manager.public_ip_address
    private_key = tls_private_key.developer.private_key_openssh
  }
  provisioner "file" {
    content = tls_private_key.manager.private_key_openssh
    destination = "/home/${var.username}/.ssh/id_rsa"
  }
  provisioner "remote-exec" {
    inline = concat(
      [
        "chmod 0600 ~/.ssh/id_rsa",
      ],
      var.vm_setup_script,
    )
  }
}

output "manager_private_ip" {
  value = azurerm_linux_virtual_machine.manager.private_ip_address
}
