// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.service

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 全进程内 CaptureService 运行状态。UI（MainScreen）观察这个 StateFlow 显示运行中/未运行，
 * 并据此 enable/disable 启动/停止按钮，避免用户重复点。
 */
object CaptureServiceState {
    private val _running = MutableStateFlow(false)
    val running: StateFlow<Boolean> = _running.asStateFlow()

    internal fun setRunning(v: Boolean) {
        _running.value = v
    }
}
