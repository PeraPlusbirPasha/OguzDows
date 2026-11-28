package org.oguzdows.mobile

import org.junit.Assert.*
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.nio.file.Files

class ConnectedRulesTest {
    @Test fun sixStableDesktopFamiliesHaveDifferentBoundedGeometry() {
        assertEquals(setOf("oguzdows", "kde", "gnome", "xfce", "windows11", "mac"), ShellStyles.layouts.map { it.id }.toSet())
        assertEquals(6, ShellStyles.layouts.size)
        assertTrue(ShellStyles.layouts.all { it.columns in 2..5 })
        assertTrue(ShellStyles.layouts.any { it.rail })
        assertTrue(ShellStyles.layouts.any { it.tiles })
        assertEquals("oguzdows", ShellStyles.layout("javascript:bad").id)
    }
    @Test fun wallpaperAccentsAreCoordinatedAndCorruptionIsBounded() {
        assertEquals(ShellStyles.accent(0, true), ShellStyles.accent(-1, true))
        assertEquals(ShellStyles.accent(3, false), ShellStyles.accent(400, false))
        assertEquals(4, (0..3).map { ShellStyles.accent(it, true) }.distinct().size)
        assertEquals(4, (0..3).map { ShellStyles.accent(it, false) }.distinct().size)
        assertTrue((0..3).all { ShellStyles.webAccent(it) in listOf("sea", "copper", "plum") })
    }
    @Test fun invitationsAcceptOnlyNumericPrivateLinkLocalAndTestLoopback() {
        for (ip in listOf("10.0.2.2", "192.168.1.2", "172.16.0.1", "172.31.255.254", "169.254.1.2", "127.0.0.1")) assertTrue(ip, BridgeRules.localAddress(ip))
        for (ip in listOf("example.com", "localhost", "8.8.8.8", "::1", "0.0.0.0", "224.0.0.1", "172.32.0.1", "192.168.001.2", "192.168.1.999", "192.0.0.1")) assertFalse(ip, BridgeRules.localAddress(ip))
    }
    @Test fun fileNamesCannotBeTraversalControlsOrUnbounded() {
        assertEquals("İmece notları.txt", BridgeRules.name("İmece notları.txt"))
        for (bad in listOf("../a", "a/b", "a\\b", ".", "..", "x\n.txt", "\u202Efile.apk", "\u0000", "a".repeat(161))) {
            try { BridgeRules.name(bad); fail(bad) } catch (_: IllegalArgumentException) { }
        }
    }
    @Test fun boundedCopyHashesRealBytesAndRefusesOversizeBeforeWritingOverflow() {
        val bytes = "real fixture\n".toByteArray()
        val out = ByteArrayOutputStream()
        val result = BridgeRules.copy(ByteArrayInputStream(bytes), out, 100)
        assertEquals(bytes.size.toLong(), result.first)
        assertArrayEquals(bytes, out.toByteArray())
        assertEquals(BridgeRules.sha(bytes), result.second)
        try { BridgeRules.copy(ByteArrayInputStream(bytes), ByteArrayOutputStream(), 2); fail() } catch (_: IllegalArgumentException) { }
    }
    @Test fun shaVerificationNeverTreatsAFileNameOrARequestAsTransferSuccess() {
        val file = Files.createTempFile("oguzkopru-unit-", ".txt").toFile()
        try {
            val bytes = "inert only".toByteArray(); file.writeBytes(bytes)
            BridgeRules.verify(file, bytes.size.toLong(), BridgeRules.sha(bytes))
            try { BridgeRules.verify(file, bytes.size.toLong(), "0".repeat(64)); fail() } catch (_: IllegalArgumentException) { }
            try { BridgeRules.verify(file, bytes.size.toLong() + 1, BridgeRules.sha(bytes)); fail() } catch (_: IllegalArgumentException) { }
        } finally { file.delete() }
    }
    @Test fun credentialsAreCryptographicallyRandomFixedLengthAndQueuesAreBounded() {
        assertTrue(BridgeRules.hash(BridgeRules.token()))
        assertTrue(BridgeRules.id(BridgeRules.token(16)))
        assertNotEquals(BridgeRules.token(), BridgeRules.token())
        assertFalse(BridgeRules.hash("A".repeat(64)))
        assertEquals(8, BridgeRules.MAX_ITEMS)
        assertEquals(128L * 1024 * 1024, BridgeRules.MAX_FILE)
        assertEquals(15 * 60 * 1000L, BridgeRules.TTL)
    }
}
