// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.overlay

import android.content.Context
import android.graphics.PixelFormat
import android.os.Build
import android.view.Gravity
import android.view.View
import android.view.WindowManager

/**
 * "贴边距离"滑块的实时预览：在屏幕左右各画一条半透粉色条带，宽度 = 当前 inset。
 * 用户拖动滑块时直观看到悬浮球将会让出的边距宽度（参考 MIUI 悬浮窗边距 UX）。
 *
 * 通过 WindowManager + TYPE_APPLICATION_OVERLAY 直接覆盖在设置页之上，不依赖 CaptureService。
 * 需要 SYSTEM_ALERT_WINDOW 权限（项目悬浮球功能本来就要求过）；没授权时 addView 静默失败。
 *
 * 使用方式：SettingsScreen 在 `floatingDockInset` 变化时调 [update]，slider section dispose 时调 [hide]。
 */
internal class EdgeInsetPreviewOverlay(private val context: Context) {

    private val wm = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private var leftView: View? = null
    private var rightView: View? = null
    private var lastUserInsetPx: Int = -1

    /**
     * 显示左右两条粉色条带，宽度 = 球贴边时的**真实距离**（与 FloatingButtonManager.snapToEdge 一致）：
     * 左条 = userInsetPx + max(cornerR, safeLeft)；右条镜像。
     * 用户 inset ≤ 0 且不可见区也 0 时整体 hide。
     */
    fun update(userInsetPx: Int) {
        // 预览跟 FloatingButtonManager.snapToEdge 一致：inset 严格 = 球距物理屏边的距离。
        val px = userInsetPx.coerceAtLeast(0)
        if (px <= 0) { hide(); return }
        if (px == lastUserInsetPx && leftView != null) return
        lastUserInsetPx = px
        if (leftView == null) {
            leftView = makeBar().also {
                runCatching { wm.addView(it, paramsForSide(px, leftSide = true)) }
            }
            rightView = makeBar().also {
                runCatching { wm.addView(it, paramsForSide(px, leftSide = false)) }
            }
        } else {
            runCatching { wm.updateViewLayout(leftView, paramsForSide(px, leftSide = true)) }
            runCatching { wm.updateViewLayout(rightView, paramsForSide(px, leftSide = false)) }
        }
    }

    fun hide() {
        leftView?.let { runCatching { wm.removeView(it) } }
        rightView?.let { runCatching { wm.removeView(it) } }
        leftView = null
        rightView = null
        lastUserInsetPx = -1
    }

    /** 跟 FloatingButtonManager.maxRoundedCornerRadiusPx 同算法。 */
    private fun maxRoundedCornerRadiusPx(): Int {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            return (24 * context.resources.displayMetrics.density).toInt()
        }
        val display = wm.defaultDisplay ?: return 0
        val positions = intArrayOf(
            android.view.RoundedCorner.POSITION_TOP_LEFT,
            android.view.RoundedCorner.POSITION_TOP_RIGHT,
            android.view.RoundedCorner.POSITION_BOTTOM_LEFT,
            android.view.RoundedCorner.POSITION_BOTTOM_RIGHT
        )
        return positions.maxOf { display.getRoundedCorner(it)?.radius ?: 0 }
    }

    /** 跟 FloatingButtonManager.systemInsetsLtrb 取 left/right 部分。 */
    private fun systemInsetsLeftRight(): Pair<Int, Int> {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return 0 to 0
        val winInsets = runCatching { wm.currentWindowMetrics.windowInsets }.getOrNull()
            ?: return 0 to 0
        val types = android.view.WindowInsets.Type.systemBars() or
            android.view.WindowInsets.Type.displayCutout()
        val ins = winInsets.getInsetsIgnoringVisibility(types)
        return ins.left to ins.right
    }

    private fun makeBar(): View = View(context).apply {
        setBackgroundColor(BAR_COLOR)
    }

    private fun paramsForSide(widthPx: Int, leftSide: Boolean): WindowManager.LayoutParams {
        val overlayType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }
        return WindowManager.LayoutParams(
            widthPx,
            WindowManager.LayoutParams.MATCH_PARENT,
            overlayType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or (if (leftSide) Gravity.START else Gravity.END)
            x = 0; y = 0
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                layoutInDisplayCutoutMode =
                    WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            }
        }
    }

    companion object {
        private const val BAR_COLOR: Int = 0x55FF4081.toInt()
    }
}
