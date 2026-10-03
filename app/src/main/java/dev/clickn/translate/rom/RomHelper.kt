// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.rom

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import timber.log.Timber

/**
 * 处理国产 ROM（小米 / OPPO / VIVO / 华为 / 三星）对悬浮窗、后台启动、自启动的特殊设置项。
 * 各家 OEM 的设置页 Activity 名是约定俗成的，可能随系统版本变化；如果跳转失败回落到通用电池设置。
 */
object RomHelper {

    enum class Brand { XIAOMI, OPPO, VIVO, HUAWEI, SAMSUNG, MEIZU, ONEPLUS, OTHER }

    val brand: Brand by lazy { detectBrand() }

    private fun detectBrand(): Brand {
        val m = Build.MANUFACTURER.lowercase()
        val b = Build.BRAND.lowercase()
        return when {
            "xiaomi" in m || "redmi" in b -> Brand.XIAOMI
            "oppo" in m || "realme" in b -> Brand.OPPO
            "vivo" in m || "iqoo" in b -> Brand.VIVO
            "huawei" in m || "honor" in b -> Brand.HUAWEI
            "samsung" in m -> Brand.SAMSUNG
            "meizu" in m -> Brand.MEIZU
            "oneplus" in m -> Brand.ONEPLUS
            else -> Brand.OTHER
        }
    }

    /** "自启动" / "后台弹窗" 等 ROM 特定设置页 Intent 列表（按优先级试）。失败回落到 App 详情页。
     *  注意：这里不混入电池白名单的 intent；电池白名单走 [batteryWhitelistIntents]，UI 上拆成两个独立按钮。
     */
    fun autoStartIntents(context: Context): List<Intent> {
        val pkg = context.packageName
        val cn: (String, String) -> Intent = { p, c ->
            Intent().apply { component = ComponentName(p, c) }
        }
        val list = when (brand) {
            Brand.XIAOMI -> listOf(
                cn("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"),
                cn("com.miui.securitycenter", "com.miui.permcenter.permissions.PermissionsEditorActivity")
                    .putExtra("extra_pkgname", pkg)
            )
            Brand.OPPO -> listOf(
                cn("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity"),
                cn("com.coloros.safecenter", "com.coloros.safecenter.startupapp.StartupAppListActivity"),
                cn("com.oppo.safe", "com.oppo.safe.permission.startup.StartupAppListActivity")
            )
            Brand.VIVO -> listOf(
                cn("com.iqoo.secure", "com.iqoo.secure.ui.phoneoptimize.AddWhiteListActivity"),
                cn("com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity")
            )
            Brand.HUAWEI -> listOf(
                cn("com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
                cn("com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity")
            )
            Brand.SAMSUNG -> listOf(
                cn("com.samsung.android.lool", "com.samsung.android.sm.ui.battery.BatteryActivity")
            )
            Brand.MEIZU -> listOf(
                cn("com.meizu.safe", "com.meizu.safe.permission.SmartBGActivity")
            )
            Brand.ONEPLUS -> listOf(
                cn("com.oneplus.security", "com.oneplus.security.chainlaunch.view.ChainLaunchAppListActivity")
            )
            Brand.OTHER -> emptyList()
        }
        // App 详情页作为终极兜底（自启动入口在国内 ROM 里通常藏在这里的"权限管理"下）。
        return list + Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$pkg"))
    }

    /** 电池白名单请求 / 设置入口。和 [autoStartIntents] 是不同概念，UI 上独立成一个按钮。 */
    fun batteryWhitelistIntents(context: Context): List<Intent> {
        val pkg = context.packageName
        val list = mutableListOf<Intent>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            // 优先弹"是否忽略电池优化"系统对话框，一键加入白名单
            list += Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$pkg"))
            // 弹窗失败回落到电池优化列表页
            list += Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
        }
        // 终极兜底：App 详情页
        list += Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$pkg"))
        return list
    }

    /** 依次尝试启动 intent 列表，第一个能起的算成功。 */
    fun launchFirstAvailable(context: Context, intents: List<Intent>): Boolean {
        for (intent in intents) {
            try {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
                return true
            } catch (t: Throwable) {
                Timber.d(t, "ROM intent skipped: ${intent.component ?: intent.action}")
            }
        }
        return false
    }

    /** 当前是否已被加入电池白名单。 */
    fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager ?: return false
        return pm.isIgnoringBatteryOptimizations(context.packageName)
    }
}
