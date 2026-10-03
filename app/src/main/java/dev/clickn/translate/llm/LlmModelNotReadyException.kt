// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.llm

/**
 * 端侧 LLM 模型尚未下载 / 校验失败。UI 层（SettingsScreen 或翻译结果浮卡）捕获后，
 * 引导用户去设置页"端侧 LLM 翻译"区块完成下载。
 *
 * 对标 [dev.clickn.translate.ocr.ModelNotReadyException]。
 */
class LlmModelNotReadyException(message: String) : Exception(message)
