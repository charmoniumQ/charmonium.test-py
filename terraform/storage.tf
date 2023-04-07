# resource "azurerm_storage_account" "default-premium" {
#   name                     = "wfregtestfiles"
#   resource_group_name      = azurerm_resource_group.default.name
#   location                 = azurerm_resource_group.default.location
#   account_tier             = "Premium"
#   account_replication_type = "LRS"
#   account_kind             = "FileStorage"
# }

# resource "azurerm_storage_share" "default" {
#   name                 = "default"
#   storage_account_name = azurerm_storage_account.default-premium.name
#   quota                = 100
#   enabled_protocol     = "NFS"
# }

# resource "azurerm_private_endpoint" "nfs" {
#   name                = "nfs"
#   resource_group_name = azurerm_resource_group.default.name
#   location            = azurerm_resource_group.default.location
#   subnet_id           = azurerm_subnet.default.id
#   private_service_connection = {
# 	name                           = "nfs"
# 	is_manual_connection           = false
# 	private_connection_resource_id = 
#   }
# }

resource "azurerm_storage_account" "default" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.default.name
  location                 = azurerm_resource_group.default.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "index3" {
  name                  = "index3"
  storage_account_name  = azurerm_storage_account.default.name
  container_access_type = "blob" # blobs are publicly accessible
}

resource "azurerm_storage_container" "data3" {
  name                  = "data3"
  storage_account_name  = azurerm_storage_account.default.name
  container_access_type = "blob" # blobs are publicly accessible
}

resource "azurerm_storage_container" "index4" {
  name                  = "index4"
  storage_account_name  = azurerm_storage_account.default.name
  container_access_type = "blob" # blobs are publicly accessible
}

resource "azurerm_storage_container" "data4" {
  name                  = "data4"
  storage_account_name  = azurerm_storage_account.default.name
  container_access_type = "blob" # blobs are publicly accessible
}

resource "azurerm_storage_container" "deployment" {
  name                  = "deployment"
  storage_account_name  = azurerm_storage_account.default.name
  container_access_type = "blob" # blobs are publicly accessible
}
