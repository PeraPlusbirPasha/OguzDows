package org.oguzdows.mobile;

import org.junit.Test;
import static org.junit.Assert.*;

public final class PlatformRulesTest {
    @Test public void ordinaryNumbersAreNormalized() {
        assertEquals("+905551112233", PlatformRules.number("+90 (555) 111-22.33"));
        assertEquals("5551234", PlatformRules.number("5551234"));
        assertEquals("112", PlatformRules.number("112")); // Routing, not validation, delegates emergencies to the system.
    }
    @Test public void serviceCodesAndInjectionAreRejected() {
        for (String number : new String[]{"*#06#", "555;123", "555?body=x", "555\n123", "++90555", "55", "123456789012345678901", "5551234%0A", "tel:5551234", "１２３４５"})
            assertEquals(number, "", PlatformRules.number(number));
        assertEquals("", PlatformRules.number(null));
    }
    @Test public void smsLengthAndControlsAreBounded() {
        assertTrue(PlatformRules.smsBody("Merhaba Rıfkı.\nİkinci satır\t✓"));
        assertTrue(PlatformRules.smsBody("a".repeat(2000)));
        assertFalse(PlatformRules.smsBody("a".repeat(2001)));
        assertFalse(PlatformRules.smsBody("  \n"));
        assertFalse(PlatformRules.smsBody("Merhaba\0"));
        assertFalse(PlatformRules.smsBody(null));
    }
    @Test public void packageNamesCannotBecomeIntentsOrPaths() {
        assertTrue(PlatformRules.packageName("org.fdroid.fdroid"));
        assertTrue(PlatformRules.packageName("org.oguzdows.fixture"));
        for (String value : new String[]{"org.foo/Bar", "intent://app", "../x", "org.foo?x=1", "org..app", "com.app;rm"}) assertFalse(PlatformRules.packageName(value));
    }
    @Test public void signedApkFileNamesStayWithinTheRepository() {
        assertTrue(PlatformRules.apkName("org.fdroid.fdroid_1023000.apk"));
        for (String value : new String[]{"../app.apk", "/app.apk", "app.apk?x", "app.apk#x", "%2e%2e.apk", ".hidden.apk", "app.apks", "app\\test.apk"}) assertFalse(PlatformRules.apkName(value));
    }
    @Test public void hashesKeepLeadingZerosAndNeverUseLocaleDigits() {
        assertEquals("000f80ff", PlatformRules.hex(new byte[]{0, 15, (byte)128, (byte)255}));
    }
}
