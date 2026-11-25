package dev.clickn.translate.gallery

import android.content.ComponentName
import android.net.Uri
import android.provider.DocumentsContract
import androidx.test.platform.app.InstrumentationRegistry

/** Client only: runs inside the instrumented target, whose classpath contains Kotlin/AndroidX. */
internal object GalleryExportDocumentsFixture {
    fun parentUri(): Uri {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val provider = instrumentation.context.packageManager.getProviderInfo(
            ComponentName(instrumentation.context, GalleryExportDocumentsTestProvider::class.java), 0,
        )
        callControl(GalleryExportDocumentsTestProvider.GRANT_METHOD)
        return DocumentsContract.buildDocumentUriUsingTree(
            DocumentsContract.buildTreeDocumentUri(checkNotNull(provider.authority), GalleryExportDocumentsTestProvider.ROOT_ID),
            GalleryExportDocumentsTestProvider.ROOT_ID,
        )
    }

    fun revoke(parent: Uri) {
        check(DocumentsContract.getTreeDocumentId(parent) == GalleryExportDocumentsTestProvider.ROOT_ID)
        callControl(GalleryExportDocumentsTestProvider.REVOKE_METHOD)
    }

    private fun callControl(method: String) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val controller = instrumentation.context.packageManager.getProviderInfo(
            ComponentName(instrumentation.context, GalleryExportGrantTestProvider::class.java), 0,
        )
        val target = instrumentation.targetContext
        val acknowledgement = target.contentResolver.call(
            Uri.parse("content://${checkNotNull(controller.authority)}"), method, target.packageName, null,
        )
        check(acknowledgement?.getBoolean(GalleryExportDocumentsTestProvider.ACK_COMPLETED) == true) {
            "The owned fixture did not acknowledge the permission operation."
        }
    }
}
