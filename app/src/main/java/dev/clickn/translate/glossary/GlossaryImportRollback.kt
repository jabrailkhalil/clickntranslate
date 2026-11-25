package dev.clickn.translate.glossary

/** Local compensation token. Durable snapshots never enter a transferable settings package. */
class GlossaryImportRollback internal constructor(
    private val persist: ((List<Change>) -> Unit)? = null,
) {
    @kotlinx.serialization.Serializable
    internal data class Change(val before: GlossaryTermEntity?, val after: GlossaryTermEntity) {
        override fun toString(): String = "GlossaryImportChange(<redacted>)"
    }

    private val changes = mutableListOf<Change>()
    private var started = false

    @Synchronized internal fun begin() {
        check(!started) { "A glossary import checkpoint cannot be reused." }
        started = true
    }

    @Synchronized internal fun record(before: GlossaryTermEntity?, after: GlossaryTermEntity) {
        check(after.id > 0 && (before == null || before.id == after.id))
        changes += Change(before, after)
    }

    @Synchronized internal fun discard() { changes.clear() }

    @Synchronized internal fun reverseChanges(): List<Change> = changes.asReversed().toList()

    /** Called once, inside the Room transaction and before its commit. */
    @Synchronized internal fun persistBeforeCommit() { persist?.invoke(changes.toList()) }

    override fun toString(): String = "GlossaryImportRollback(<redacted>)"

    internal companion object {
        fun restoreToken(snapshot: List<Change>): GlossaryImportRollback = GlossaryImportRollback().also {
            it.started = true
            it.changes.addAll(snapshot)
        }
    }
}
