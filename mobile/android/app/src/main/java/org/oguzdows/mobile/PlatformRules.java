package org.oguzdows.mobile;

import java.util.Locale;

/** Pure validation shared by the platform entry points; never accepts USSD/service codes. */
public final class PlatformRules {
    private PlatformRules() {}

    public static String number(String input) {
        if (input == null || !input.matches("[+0-9 ().-]{3,40}")) return "";
        String value = input.replaceAll("[ ().-]", "");
        return value.matches("\\+?[0-9]{3,20}") ? value : "";
    }

    public static boolean smsBody(String input) {
        return input != null && !input.trim().isEmpty() && input.length() <= 2000
            && !input.matches("(?s).*[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F\\x7F].*");
    }

    public static boolean packageName(String input) {
        return input != null && input.length() <= 200
            && input.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+");
    }

    public static boolean apkName(String input) {
        return input != null && input.length() <= 240 && !input.startsWith(".")
            && input.matches("[A-Za-z0-9_][A-Za-z0-9_.-]*\\.apk");
    }

    public static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) out.append(String.format(Locale.ROOT, "%02x", b & 255));
        return out.toString();
    }
}
