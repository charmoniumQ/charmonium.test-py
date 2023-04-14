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
