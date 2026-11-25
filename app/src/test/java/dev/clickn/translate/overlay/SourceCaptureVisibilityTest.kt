package dev.clickn.translate.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class SourceCaptureVisibilityTest {
    @Test
    fun hidesExistingVisibleRootsAndRestoresTheirDesiredStates() {
        val owner = owner()
        val visible = Root(VISIBLE)
        val invisible = Root(INVISIBLE)
        val gone = Root(GONE)
        listOf(visible, invisible, gone).forEach { owner.track(it) }

        val lease = owner.hideForSourceObservation()
        assertTrue(lease.changedVisibility)
        assertEquals(INVISIBLE, visible.visibility)
        assertEquals(INVISIBLE, invisible.visibility)
        assertEquals(GONE, gone.visibility)

        lease.close()
        assertEquals(VISIBLE, visible.visibility)
        assertEquals(INVISIBLE, invisible.visibility)
        assertEquals(GONE, gone.visibility)
    }

    @Test
    fun nestedLeasesCanCloseOutOfOrderAndEachClosesOnlyOnce() {
        val owner = owner()
        val root = Root(VISIBLE)
        owner.track(root)
        val outer = owner.hideForSourceObservation()
        val inner = owner.hideForSourceObservation()
        assertTrue(outer.changedVisibility)
        assertFalse(inner.changedVisibility)

        outer.close()
        outer.close()
        assertEquals(INVISIBLE, root.visibility)
        inner.close()
        inner.close()
        assertEquals(VISIBLE, root.visibility)
        assertEquals(listOf(INVISIBLE, VISIBLE), root.writes)
    }

    @Test
    fun newlyCreatedRootsStayHiddenBeforeTheyAreAttachedAndStreamingUpdatesCannotShowThem() {
        val owner = owner()
        val lease = owner.hideForSourceObservation()
        val streaming = Root(VISIBLE)
        owner.track(streaming, VISIBLE)
        owner.setDesired(streaming, VISIBLE)
        owner.setDesired(streaming, VISIBLE)

        assertFalse(lease.changedVisibility) // Snapshot; this root has never been painted.
        assertEquals(INVISIBLE, streaming.visibility)
        assertEquals(listOf(INVISIBLE), streaming.writes)
        lease.close()
        assertEquals(VISIBLE, streaming.visibility)
    }

    @Test
    fun captureAndEditorVisibilityChangesDuringObservationRemainInForceAfterRestore() {
        val owner = owner()
        val captureHidden = Root(VISIBLE)
        val editorHidden = Root(VISIBLE)
        owner.track(captureHidden)
        owner.track(editorHidden)
        val lease = owner.hideForSourceObservation()
        owner.setDesired(captureHidden, INVISIBLE)
        owner.setDesired(editorHidden, GONE)

        lease.close()
        assertEquals(INVISIBLE, captureHidden.visibility)
        assertEquals(GONE, editorHidden.visibility)
        owner.setDesired(captureHidden, VISIBLE)
        assertEquals(VISIBLE, captureHidden.visibility)
    }

    @Test
    fun sourceSuppressionSurvivesIndependentCaptureHideAndUnhide() {
        val owner = owner()
        val root = Root(INVISIBLE)
        owner.track(root)
        val lease = owner.hideForSourceObservation()
        assertFalse(lease.changedVisibility)
        owner.setDesired(root, VISIBLE)
        owner.setDesired(root, INVISIBLE)
        owner.setDesired(root, VISIBLE)
        assertEquals(INVISIBLE, root.visibility)

        lease.close()
        assertEquals(VISIBLE, root.visibility)
    }

    @Test
    fun removedWindowIsUntrackedBeforeAsyncRemovalAndCannotBeResurrectedByRestore() {
        val owner = owner()
        val removed = Root(VISIBLE)
        owner.track(removed)
        val lease = owner.hideForSourceObservation()
        owner.untrack(removed)
        removed.removed = true
        owner.setDesired(removed, VISIBLE) // A stale queued update must not re-register it.
        val replacement = Root(VISIBLE)
        owner.track(replacement)

        lease.close()
        assertEquals(INVISIBLE, removed.visibility)
        assertEquals(listOf(INVISIBLE), removed.writes)
        assertEquals(VISIBLE, replacement.visibility)
    }

    @Test
    fun noVisibleRootsMeansNoFreshFrameRequirement() {
        val owner = owner()
        val empty = owner.hideForSourceObservation()
        assertFalse(empty.changedVisibility)
        empty.close()
        owner.track(Root(INVISIBLE))
        owner.track(Root(GONE))
        val hidden = owner.hideForSourceObservation()
        assertFalse(hidden.changedVisibility)
        hidden.close()
    }

    @Test
    fun compositeReportsAnyChangeAndRestoresAllChildrenDespiteOneCleanupFailure() {
        val events = mutableListOf<Int>()
        val failure = IllegalStateException("owned cleanup failed")
        val first = object : SourceObservationLease {
            override val changedVisibility = false
            override fun close() { events += 1 }
        }
        val second = object : SourceObservationLease {
            override val changedVisibility = true
            override fun close() { events += 2; throw failure }
        }
        val lease = combineSourceObservationLeases(first, second)
        assertTrue(lease.changedVisibility)
        assertSame(failure, assertThrows(IllegalStateException::class.java) { lease.close() })
        lease.close()
        assertEquals(listOf(2, 1), events)
    }

    private class Root(var visibility: Int) {
        var removed = false
        val writes = mutableListOf<Int>()
    }

    private fun owner() = SourceCaptureVisibility<Root>(
        readVisibility = { it.visibility },
        writeVisibility = { root, visibility ->
            check(!root.removed) { "A removed root was restored" }
            root.visibility = visibility
            root.writes += visibility
        },
        visible = VISIBLE,
        suppressed = INVISIBLE,
    )

    private companion object {
        const val VISIBLE = 0
        const val INVISIBLE = 4
        const val GONE = 8
    }
}
