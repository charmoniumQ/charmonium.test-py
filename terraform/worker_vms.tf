resource "azurerm_network_interface" "worker_nic" {
  count               = var.workers
  name                = "worker-nic-${count.index}"
  location            = azurerm_resource_group.default.location
  resource_group_name = azurerm_resource_group.default.name

  ip_configuration {
    name                          = "worker-${count.index}"
    subnet_id                     = azurerm_subnet.default.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_linux_virtual_machine" "worker" {
  count                 = var.workers
  name                  = "worker-${count.index}"
  location              = azurerm_resource_group.default.location
  resource_group_name   = azurerm_resource_group.default.name
  size                  = var.worker_vm_size
  admin_username        = var.username
  network_interface_ids = [azurerm_network_interface.worker_nic[count.index].id]
  disable_password_authentication = true
  admin_ssh_key {
    username   = var.username
    public_key = tls_private_key.manager.public_key_openssh
  }
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
    disk_size_gb         = var.worker_disk_size_gb
  }
  identity {
    type = "SystemAssigned"
  }
  connection {
    type              = "ssh"
    user              = var.username
    host              = self.private_ip_address
    private_key       = tls_private_key.developer.private_key_openssh
    bastion_user      = var.username
  	bastion_host      = azurerm_linux_virtual_machine.manager.public_ip_address
    bastion_host_key  = tls_private_key.developer.private_key_openssh
  }
  provisioner "remote-exec" {
    inline = var.vm_setup_script
  }
}
