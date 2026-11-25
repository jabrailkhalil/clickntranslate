package dev.clickn.translate.ui

import org.junit.Assert.*
import org.junit.Test

class PhotoSelectionStateTest {
    @Test fun recreationAndRepeatedLaunchDoNotResurrectRemovedOrSubmittedPhotos() {
        val shared = listOf("content://owned/one", "content://owned/two")
        val first = PhotoSelectionState().acceptShare(7, shared)
        val edited = first.select(listOf(shared[1], "content://owned/added"))
        val restored = PhotoSelectionState.restore(edited.save())
        assertEquals(edited, restored.acceptShare(7, shared))
        val afterSubmit = restored.select(emptyList())
        assertEquals(afterSubmit, PhotoSelectionState.restore(afterSubmit.save()).acceptShare(7, shared))
        // A new user share, even with exactly the same URIs, is a new request.
        assertEquals(shared, afterSubmit.acceptShare(8, shared).uris)
        assertEquals(8L, afterSubmit.acceptShare(8, shared).handledShareId)
    }

    @Test fun editedSelectionIsBoundedAndAnEmptyLaunchCannotClearIt() {
        val many = (1..130).map { "content://owned/$it" }
        val state = PhotoSelectionState().acceptShare(1, listOf(" content://owned/a ", "content://owned/a"))
        assertEquals(listOf("content://owned/a"), state.uris)
        val selected = state.select(many + many)
        assertEquals(many.take(100), selected.uris)
        assertEquals(selected, selected.acceptShare(2, emptyList()))
        assertEquals(selected, PhotoSelectionState.restore(selected.save()))
        assertEquals(PhotoSelectionState(), PhotoSelectionState.restore(emptyList()))
    }
}
