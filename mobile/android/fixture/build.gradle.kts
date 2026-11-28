plugins { id("com.android.application") }
android {
    namespace = "org.oguzdows.fixture"
    compileSdk = 35
    defaultConfig {
        applicationId = "org.oguzdows.fixture"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "1.0-test-only"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
