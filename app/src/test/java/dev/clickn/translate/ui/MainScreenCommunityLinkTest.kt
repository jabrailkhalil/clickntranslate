// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import dev.clickn.translate.AppBrand
import java.net.URI
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MainScreenCommunityLinkTest {
    @Test
    fun communityLink_opensTheOfficialTelegramChannelWithoutTrackingParameters() {
        val uri = URI(AppBrand.COMMUNITY_URL)
        assertEquals("https", uri.scheme)
        assertEquals("t.me", uri.host)
        assertEquals("/jabrail_digital", uri.path)
        assertNull(uri.query)
        assertNull(uri.userInfo)
    }
}
