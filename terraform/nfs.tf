# resource "azurerm_storage_account" "default-premium" {
#   name                     = "wfregtestfiles"
#   resource_group_name      = azurerm_resource_group.default.name
#   location                 = azurerm_resource_group.default.location
#   account_tier             = "Premium"
#   account_replication_type = "LRS"
#   account_kind             = "FileStorage"
# }
# 
# resource "azurerm_storage_share" "default" {
#   name                 = "default"
#   storage_account_name = azurerm_storage_account.default-premium.name
#   quota                = 100
#   enabled_protocol     = "NFS"
# }
# 
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
