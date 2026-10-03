// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.llm

internal object LocalLlmAccelerationPolicy {
    const val VULKAN_OFFLOAD_ENV = "CLICKTRANSLATE_VULKAN_OFFLOAD"

    fun requestsVulkan(
        kind: LlmModelKind,
        experimentalVulkanEnabled: Boolean = false,
    ): Boolean = experimentalVulkanEnabled && kind == LlmModelKind.SAKURA_1_5B_Q4

    fun nativeFlag(
        kind: LlmModelKind,
        experimentalVulkanEnabled: Boolean = false,
    ): String = if (requestsVulkan(kind, experimentalVulkanEnabled)) "1" else "0"
}
