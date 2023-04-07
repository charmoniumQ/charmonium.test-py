resource azurerm_role_assignment manager-storage {
  scope                = azurerm_storage_account.default.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_virtual_machine.manager.identity[0].principal_id
}

resource azurerm_role_assignment manager-acr {
  principal_id                     = azurerm_linux_virtual_machine.manager.identity[0].principal_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.default.id
}

resource azurerm_role_assignment worker-data {
  count                = var.workers
  scope                = azurerm_storage_account.default.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_virtual_machine.worker[count.index].identity[0].principal_id
}

resource azurerm_role_assignment worker-acr {
  count                            = var.workers
  principal_id                     = azurerm_linux_virtual_machine.worker[count.index].identity[0].principal_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.default.id
}
